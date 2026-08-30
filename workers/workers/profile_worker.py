"""profile_document stage: build the document retrieval profile.

Consumes `profile_document.v1` outbox events (scheduled by the census
after extract). The profile is deterministic aggregation over the
document's parents, entities, facts, and ingestion profile — no LLM.
Coverage fields commit with the profile so an incomplete routing
representation is never silently accepted (receipt discipline).
"""
from __future__ import annotations

import json
import logging
import time

import psycopg
from psycopg import Connection

from polymath_shared.db import tx
from polymath_shared.logging import configure_logging
from polymath_shared.receipts import (
    StageFailed,
    claim_events,
    stage_contract_hash,
    stage_transaction,
)
from workers.document_profile_builder import SUMMARY_CONTRACT, build_profile

STAGE = "profile_document"
EVENT_TYPE = "profile_document.v1"
CONTRACT_VERSION = "1.2.0"   # SUMMARY-COMPILER-V1 cards

log = logging.getLogger("profile-document")


def _documents_for_run(conn: Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT d.doc_id, d.source_name, d.profile
          FROM documents d
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s
         ORDER BY d.doc_id
        """,
        (run_id,),
    ).fetchall()
    return [{"doc_id": r[0], "source_name": r[1], "profile": r[2] or {}} for r in rows]


def _parents_for_doc(conn: Connection, doc_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT chunk_id, summary, text FROM chunks
         WHERE doc_id = %s AND tier = 'parent'
         ORDER BY chunk_index
        """,
        (doc_id,),
    ).fetchall()
    return [{"chunk_id": r[0], "summary": r[1], "text": r[2]} for r in rows]


def _children_for_doc(conn: Connection, doc_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT chunk_id, parent_id, text, region_role FROM chunks
         WHERE doc_id = %s AND tier = 'child'
         ORDER BY chunk_index
        """,
        (doc_id,),
    ).fetchall()
    return [{"chunk_id": r[0], "parent_id": r[1], "text": r[2], "region_role": r[3]}
            for r in rows]


def _facts_for_doc(conn: Connection, doc_id: str, chunk_order: dict[str, int]) -> list[dict]:
    """Facts linked to this document's chunks by evidence offsets — the
    triple signal of SUMMARY-COMPILER-V1. `trusted` = ACCEPT decisions
    (serialized as relations); anything else only ranks."""
    rows = conn.execute(
        """
        SELECT e.chunk_id, e.span_offsets, f.predicate, f.decision, f.fact_id,
               s.normalized_surface, o.normalized_surface
          FROM evidence e
          JOIN facts f ON f.fact_id = e.fact_id
          JOIN entities s ON s.entity_id = f.subject_id
          JOIN entities o ON o.entity_id = f.object_id
         WHERE e.doc_id = %s
        """,
        (doc_id,),
    ).fetchall()
    out: list[dict] = []
    for chunk_id, so, predicate, decision, fact_id, subj, obj in rows:
        so = so if isinstance(so, dict) else (json.loads(so) if so else {})
        start = so.get("evidence_start", so.get("start"))
        end = so.get("evidence_end", so.get("end"))
        out.append({
            "chunk_id": chunk_id, "predicate": predicate,
            "subject": so.get("subject_surface") or subj,
            "object": so.get("object_surface") or obj,
            "start": int(start) if start is not None else None,
            "end": int(end) if end is not None else None,
            "trusted": decision == "ACCEPT", "fact_id": fact_id,
            "order": chunk_order.get(chunk_id, 10**9),
        })
    out.sort(key=lambda f: (f["order"], f["start"] if f["start"] is not None else -1, f["fact_id"]))
    return out


def _digests_for_doc(conn: Connection, doc_id: str) -> dict[str, list[dict]]:
    """The extractor's per-neighborhood digests for this document (latest
    extract artifact of a run that ingested it), keyed by parent id."""
    row = conn.execute(
        """
        SELECT a.payload->'llm_extraction'->'digests'
          FROM artifacts a
          JOIN runs r ON r.run_id = a.run_id
          JOIN documents d ON d.corpus_id = r.corpus_id
                          AND d.source_name = r.metadata->>'source_name'
         WHERE d.doc_id = %s AND a.stage = 'extract'
           AND jsonb_exists(a.payload, 'llm_extraction')
         ORDER BY a.created_at DESC
         LIMIT 1
        """,
        (doc_id,),
    ).fetchone()
    out: dict[str, list[dict]] = {}
    for d in (row[0] if row and row[0] else []) or []:
        nid = str(d.get("neighborhood_id") or "")
        out.setdefault(nid.rsplit(":", 1)[0], []).append(d)
    return out


def _upsert_slot(conn: Connection, *, kind: str, corpus_id: str, doc_id: str,
                 parent_id: str | None, source_id: str,
                 variants: list[tuple[object, bool]]) -> list[str]:
    """One routing slot = (doc, kind, parent). Every variant row is
    persisted; exactly one is active (unique partial index). Replay with
    identical inputs lands on identical ids and flags."""
    from polymath_shared.retrieval_summaries import CONTRACT, summary_id
    ids = [summary_id(kind, source_id, c.embed_text) for c, _ in variants]
    conn.execute(
        """UPDATE retrieval_summaries SET active = FALSE
            WHERE doc_id = %s AND kind = %s AND COALESCE(parent_id, '') = %s AND active""",
        (doc_id, kind, parent_id or ""),
    )
    for (compiled, active), sid in zip(variants, ids):
        conn.execute(
            """
            INSERT INTO retrieval_summaries (summary_id, kind, contract, corpus_id,
                                             doc_id, parent_id, summary_text, provenance,
                                             variant, active, plain_summary, relations,
                                             keywords, coverage)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (summary_id) DO UPDATE
               SET active = EXCLUDED.active, contract = EXCLUDED.contract,
                   variant = EXCLUDED.variant, plain_summary = EXCLUDED.plain_summary,
                   relations = EXCLUDED.relations, keywords = EXCLUDED.keywords,
                   coverage = EXCLUDED.coverage, provenance = EXCLUDED.provenance
            """,
            (sid, kind, CONTRACT, corpus_id, doc_id, parent_id, compiled.embed_text,
             json.dumps(compiled.sentences), compiled.variant, active, compiled.summary,
             json.dumps(compiled.relation_items), json.dumps(compiled.keywords),
             json.dumps(compiled.coverage)),
        )
    return ids


def _persist_retrieval_summaries(
    conn: Connection,
    *,
    corpus_id: str,
    doc_id: str,
    parents: list[dict],
    children: list[dict],
) -> dict:
    """SUMMARY-COMPILER-V1 routing cards (contract retrieval-summary-v3).

    Deterministic compiler always writes the section and document cards;
    the extractor's digest, when clean, is the ACTIVE section variant.
    Noise regions never feed a card; a parent whose children are all
    noise has no card (and the verifier does not expect one)."""
    from polymath_shared.region_role import is_summarizable as _is_summarizable
    from polymath_shared.retrieval_summaries import (
        DOC_SUMMARY_KIND,
        SECTION_SUMMARY_KIND,
        build_background,
        compile_document,
        compile_section,
        digest_variant,
    )

    excluded = sum(1 for c in children if not _is_summarizable(c.get("region_role")))
    children = [c for c in children if _is_summarizable(c.get("region_role"))]
    live_parent_ids = {c["parent_id"] for c in children}
    parents = [p for p in parents if p["chunk_id"] in live_parent_ids]
    stats = {"sections": 0, "llm_digest_active": 0, "uncovered": 0, "document": 0,
             "children_excluded": excluded}
    if not parents:
        return stats
    chunk_order = {c["chunk_id"]: i for i, c in enumerate(children)}
    facts = _facts_for_doc(conn, doc_id, chunk_order)
    digests = _digests_for_doc(conn, doc_id)
    background = build_background([c["text"] for c in children])
    by_parent: dict[str, list[dict]] = {}
    for child in children:
        by_parent.setdefault(child["parent_id"] or "", []).append(child)

    compiled_parents: list[dict] = []
    for parent in parents:
        pid = parent["chunk_id"]
        kids = by_parent.get(pid, [])
        kid_ids = {k["chunk_id"] for k in kids}
        det = compile_section(kids, parent_id=pid, background=background,
                              facts=[f for f in facts if f["chunk_id"] in kid_ids])
        llm = digest_variant(digests.get(pid, []), det)
        variants: list[tuple[object, bool]] = [(det, llm is None)]
        if llm is not None:
            variants.append((llm, True))
            stats["llm_digest_active"] += 1
        _upsert_slot(conn, kind=SECTION_SUMMARY_KIND, corpus_id=corpus_id, doc_id=doc_id,
                     parent_id=pid, source_id=pid, variants=variants)
        stats["sections"] += 1
        stats["uncovered"] += len(det.coverage.get("uncovered") or [])
        compiled_parents.append({"chunk_id": pid, "summary": det.summary,
                                 "text": parent.get("text") or ""})

    doc = compile_document(compiled_parents, doc_id=doc_id, facts=facts)
    _upsert_slot(conn, kind=DOC_SUMMARY_KIND, corpus_id=corpus_id, doc_id=doc_id,
                 parent_id=None, source_id=doc_id, variants=[(doc, True)])
    stats["document"] = 1
    return stats


def _entities_for_doc(conn: Connection, doc_id: str) -> list[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT e.normalized_surface, e.core_type
          FROM evidence ev
          JOIN facts f ON f.fact_id = ev.fact_id
          JOIN entities e ON e.entity_id = f.subject_id OR e.entity_id = f.object_id
         WHERE ev.doc_id = %s
        """,
        (doc_id,),
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _predicates_for_doc(conn: Connection, doc_id: str) -> list[tuple[str, int]]:
    rows = conn.execute(
        """
        SELECT f.predicate, COUNT(*)
          FROM facts f
          JOIN evidence ev ON ev.fact_id = f.fact_id
         WHERE ev.doc_id = %s
         GROUP BY f.predicate
        """,
        (doc_id,),
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def process_event(conn: Connection, event: dict) -> None:
    run_id = event["run_id"]

    contract = stage_contract_hash(STAGE, {
        "contract_version": CONTRACT_VERSION,
        "summary_contract": SUMMARY_CONTRACT,
    })

    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract) as writer:
        profiles: list[dict] = []
        summary_stats: list[dict] = []
        for doc in _documents_for_run(conn, run_id):
            parents = _parents_for_doc(conn, doc["doc_id"])
            children = _children_for_doc(conn, doc["doc_id"])
            entities = _entities_for_doc(conn, doc["doc_id"])
            predicates = _predicates_for_doc(conn, doc["doc_id"])
            profile = build_profile(
                doc_id=doc["doc_id"],
                source_name=doc["source_name"],
                ingestion_profile=doc.get("profile", {}),
                parent_chunks=parents,
                entities=entities,
                predicate_counts=predicates,
            )
            conn.execute(
                """
                UPDATE documents
                   SET retrieval_profile = %s,
                       profile_contract = %s,
                       source_parent_count = %s,
                       summarized_parent_count = %s,
                       profile_coverage = %s
                 WHERE doc_id = %s
                """,
                (json.dumps(profile.model_dump()), SUMMARY_CONTRACT,
                 profile.source_parent_count, profile.summarized_parent_count,
                 profile.coverage, doc["doc_id"]),
            )
            corpus_row = conn.execute(
                "SELECT corpus_id FROM documents WHERE doc_id = %s", (doc["doc_id"],)
            ).fetchone()
            card_stats = _persist_retrieval_summaries(
                conn,
                corpus_id=corpus_row[0] if corpus_row else "",
                doc_id=doc["doc_id"],
                parents=parents,
                children=children,
            )
            summary_stats.append({"doc_id": doc["doc_id"], **card_stats})
            profiles.append(profile.model_dump())

        writer.artifact({"documents_profiled": len(profiles),
                         "routing_cards": summary_stats})
        writer.run_status("reconciling")


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 1) -> None:
    """LONG-STAGE-LEASE-CORRECTNESS-V1: claim depth 1.

    A worker executes tickets serially, so claiming ahead bought nothing
    but made "held" differ from "being processed" -- and a stage running
    past claim_ttl_s let the reaper expire the queued ones. Parallelism
    comes from running several workers of a type.
    """
    from polymath_shared.worker_runtime import run_worker

    run_worker('profile_document', [EVENT_TYPE], process_event,
               poll_interval_s=poll_interval_s, batch_size=batch_size)

if __name__ == "__main__":
    run_forever()

"""V5 L1 — raw evidence capture (evidence plumbing, NOT a semantic authority).

This module records what the provider said; it decides nothing. It is
deliberately NOT in `_SEMANTIC_AUTHORITY_MODULES`: adding it must not move
the semantic bundle hash, and a qualification gate asserts exactly that.

    Filtering decides what becomes knowledge.
    Filtering never decides whether observed evidence survives.
"""
from __future__ import annotations

from typing import Any

from polymath_shared.identity import content_hash

RAW_EVIDENCE_CONTRACT = "raw-evidence-ledger-v1"


def provider_contract(*, provider: str, model_id: str, revision: str,
                      task: str, threshold: float, labels: list[str]) -> dict:
    return {
        "contract": RAW_EVIDENCE_CONTRACT,
        "provider": provider,
        "model_id": model_id,
        "revision": revision,
        "task": task,
        "threshold": threshold,
        "labels_sha256": content_hash({"labels": sorted(labels)}),
    }


def proposal_row(doc_id: str, chunk_id: str, item: dict, contract: dict) -> tuple:
    """One raw span exactly as the provider returned it. The id is
    content-addressed over everything that identifies the OBSERVATION —
    including the provider contract — so the same observation replayed lands
    on the same primary key, and a changed provider/labels/threshold yields
    new rows instead of silently overwriting history."""
    pid = "rawent_" + content_hash({
        "doc": doc_id, "chunk": chunk_id,
        "start": item["start"], "end": item["end"],
        "surface": item["text"], "label": item["label"],
        "score": round(float(item["score"]), 6),
        "provider": contract["labels_sha256"] + contract["revision"] + contract["task"],
    })
    import json
    return (pid, doc_id, chunk_id, int(item["start"]), int(item["end"]),
            item["text"], item["label"], float(item["score"]),
            json.dumps(contract, sort_keys=True))


def evidence_row(doc_id: str, chunk_id: str, item: dict, contract: dict) -> tuple:
    row = proposal_row(doc_id, chunk_id, item, contract)
    return ("rawev_" + row[0][len("rawent_"):],) + row[1:]


_INSERT = {
    "raw_entity_proposals":
        "INSERT INTO raw_entity_proposals (proposal_id, doc_id, chunk_id,"
        " char_start, char_end, surface, provider_label, provider_score,"
        " provider_contract) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        " ON CONFLICT (proposal_id) DO NOTHING",
    "raw_predicate_evidence":
        "INSERT INTO raw_predicate_evidence (evidence_id, doc_id, chunk_id,"
        " char_start, char_end, surface, provider_label, provider_score,"
        " provider_contract) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        " ON CONFLICT (evidence_id) DO NOTHING",
}


def bulk_write(conn: Any, table: str, rows: list[tuple]) -> int:
    """Idempotent bulk insert inside the caller's stage transaction, so raw
    evidence commits with the stage receipt and rolls back with the stage."""
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(_INSERT[table], rows)
    return len(rows)


def ledger_hash(conn: Any, doc_ids: list[str]) -> dict:
    """Deterministic content hash of a document set's L1 ledger, for
    replay/qualification comparison. Excludes created_at by construction."""
    out = {}
    for table, idcol in (("raw_entity_proposals", "proposal_id"),
                         ("raw_predicate_evidence", "evidence_id")):
        rows = conn.execute(
            f"SELECT {idcol} FROM {table} WHERE doc_id = ANY(%s) ORDER BY {idcol}",
            (doc_ids,)).fetchall()
        out[table] = {"count": len(rows),
                      "sha256": content_hash({"ids": [r[0] for r in rows]})}
    return out


def hypothesis_row(doc_id: str, h: dict) -> tuple:
    """One rescue decision as an L2 record. Ids are content-addressed over
    the decision's identifying content, so replays are idempotent."""
    import json
    hid = "hyp_" + content_hash({
        "doc": doc_id, "chunk": h["chunk_id"], "mechanism": h["mechanism"],
        "src": [h.get("source_char_start"), h.get("source_char_end")],
        "dst": [h["proposed_char_start"], h["proposed_char_end"]],
        "surface": h["proposed_surface"], "status": h["status"],
    })
    return (hid, doc_id, h["chunk_id"], h["mechanism"],
            h.get("source_char_start"), h.get("source_char_end"),
            h.get("source_surface"),
            h["proposed_char_start"], h["proposed_char_end"],
            h["proposed_surface"], h["status"], h["disposition"],
            json.dumps(h.get("evidence") or {}, sort_keys=True))


_INSERT["span_hypotheses"] = (
    "INSERT INTO span_hypotheses (hypothesis_id, doc_id, chunk_id, mechanism,"
    " source_char_start, source_char_end, source_surface, proposed_char_start,"
    " proposed_char_end, proposed_surface, status, disposition, evidence)"
    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    " ON CONFLICT (hypothesis_id) DO NOTHING")


BUNDLE_CONTRACT = "document-evidence-bundle-v1"

_BUNDLE_MEMBERS = (
    ("chunks", "SELECT chunk_id FROM chunks WHERE doc_id=%s ORDER BY chunk_id"),
    ("sentence_slices",
     "SELECT chunk_id, slice_index, chunk_start, chunk_end FROM sentence_slices"
     " WHERE doc_id=%s ORDER BY chunk_id, slice_index"),
    ("layout",
     "SELECT kind, char_start, char_end FROM document_layout WHERE doc_id=%s"
     " ORDER BY char_start, char_end"),
    ("raw_entity_proposals",
     "SELECT proposal_id FROM raw_entity_proposals WHERE doc_id=%s ORDER BY proposal_id"),
    ("raw_predicate_evidence",
     "SELECT evidence_id FROM raw_predicate_evidence WHERE doc_id=%s ORDER BY evidence_id"),
    ("span_hypotheses",
     "SELECT hypothesis_id FROM span_hypotheses WHERE doc_id=%s ORDER BY hypothesis_id"),
)


class IncompleteEvidence(RuntimeError):
    """Fail closed: a bundle over missing required evidence is not a bundle.
    Reconstructing the gap with a heuristic is exactly what V5 forbids."""


def bundle_manifest(conn: Any, doc_id: str, *, require_slices: bool = True) -> dict:
    """`require_slices=False` is the LLM-DIRECT (llm_live) contract: the
    syntax/slice interpreter never runs there, so the bundle's evidence is
    the raw ledger (proposals + predicate evidence) over the chunks; a
    missing slice manifest is expected, not a gap. MEASURED 2026-08-30:
    the first live llm_live ingest failed every extract attempt here."""
    members, counts = {}, {}
    for name, sql in _BUNDLE_MEMBERS:
        rows = conn.execute(sql, (doc_id,)).fetchall()
        counts[name] = len(rows)
        members[name] = content_hash({"rows": [list(map(str, r)) for r in rows]})
    if counts["chunks"] == 0:
        raise IncompleteEvidence(f"{doc_id}: no chunks — nothing to bundle")
    if require_slices and counts["sentence_slices"] == 0:
        raise IncompleteEvidence(
            f"{doc_id}: no sentence-slice manifest — the interpreter view is "
            "required evidence (sentence-slice-manifest-v1) and may not be "
            "reconstructed")
    body = {"contract": BUNDLE_CONTRACT, "doc_id": doc_id, "members": members}
    return {"doc_id": doc_id, "evidence_contract": BUNDLE_CONTRACT,
            "bundle_sha256": content_hash(body),
            "member_hashes": members, "counts": counts}


def write_bundle(conn: Any, doc_id: str, *, require_slices: bool = True) -> dict:
    import json
    m = bundle_manifest(conn, doc_id, require_slices=require_slices)
    conn.execute(
        """
        INSERT INTO document_evidence_bundles
            (doc_id, evidence_contract, bundle_sha256, member_hashes, counts)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (doc_id) DO UPDATE
            SET bundle_sha256=EXCLUDED.bundle_sha256,
                member_hashes=EXCLUDED.member_hashes,
                counts=EXCLUDED.counts, updated_at=now()
        """,
        (m["doc_id"], m["evidence_contract"], m["bundle_sha256"],
         json.dumps(m["member_hashes"], sort_keys=True),
         json.dumps(m["counts"], sort_keys=True)))
    return m


def relation_candidate_row(doc_id: str, chunk_id: str, candidate, decision) -> tuple:
    """One compiled relation candidate with its disposition (L4, I7)."""
    fact = getattr(decision, "fact", None)
    subj, obj = candidate.subject, candidate.object
    cid = "relc_" + content_hash({
        "doc": doc_id, "chunk": chunk_id,
        "evidence": [candidate.evidence.start, candidate.evidence.end,
                     candidate.evidence.evidence_class],
        "subject": [subj.span.start, subj.span.end, subj.span.core_type.value],
        "object": [obj.span.start, obj.span.end, obj.span.core_type.value],
        "decision": decision.decision,
    })
    return (cid, doc_id, chunk_id,
            candidate.evidence.evidence_class,
            # PROVENANCE. This read `trigger_surface`, which EvidenceSpan
            # does not define, so getattr returned None for every candidate
            # ever recorded: 34,655 of 34,655 rows across every corpus,
            # including all 8,834 ACCEPT/QUALIFY. Licensing was working the
            # whole time -- `_trigger_matches` tests `trigger_lemma` against
            # the licensed verb/noun/multiword arms -- but the ledger never
            # recorded WHICH trigger licensed a fact, so no fact could be
            # audited back to its lexical cause. A silent getattr default
            # turned a contract field into a permanent NULL.
            (getattr(candidate.evidence, "trigger_lemma", None)
             or getattr(candidate.evidence, "text", None)),
            subj.span.text, subj.resolved_entity_id,
            obj.span.text, obj.resolved_entity_id,
            getattr(decision, "rule_id", None),
            decision.decision, str(decision.reason or "")[:400],
            fact.fact_id if fact else None,
            # PREDICATE-COMPILER-V2 slice 1: syntax provenance. Legacy
            # candidates carry None here, which is the measurable signal.
            getattr(candidate, "trigger_token_id", None),
            getattr(candidate, "subject_token_id", None),
            getattr(candidate, "object_token_id", None),
            getattr(candidate, "dependency_path", None),
            _binding_source_text(candidate),
            (getattr(candidate, "sentence_id", None)
             or (f"{chunk_id}#s{candidate.sentence_index}"
                 if candidate.sentence_index else None)))


def _binding_source_text(candidate):
    source = getattr(candidate, "binding_source", None)
    if source is None:
        lse = getattr(candidate, "lexical_semantic_evidence", None)
        sources = getattr(lse, "binding_sources", None) if lse else None
        if sources:
            source = sources[0]
    return source.value if hasattr(source, "value") else source


_INSERT["relation_candidates"] = (
    "INSERT INTO relation_candidates (candidate_id, doc_id, chunk_id,"
    " evidence_class, trigger_surface, subject_surface, subject_entity_id,"
    " object_surface, object_entity_id, predicate, decision, reason, fact_id,"
    " trigger_token_id, subject_token_id, object_token_id, dependency_path,"
    " binding_source, sentence_id)"
    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    " ON CONFLICT (candidate_id) DO NOTHING")

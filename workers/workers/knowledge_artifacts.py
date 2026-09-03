"""KNOWLEDGE-ARTIFACT-PERSISTENCE-V1 — the compile_objects stage's persister.

Moved out of `extract_worker` on 2026-09-03 (LLM-DIRECT-CANON, ADR-0017):
the extract worker is LLM-direct only; Procedure/Concept artifacts are a
separate deterministic lane (their own stage ticket, `compile_objects.v1`)
and never touch the entity graph here. Behaviour is byte-for-byte the
previous `_persist_knowledge_artifacts`.
"""
from __future__ import annotations

import json

from psycopg import Connection



_BUNDLE_STAMP: str | None = None


def _bundle_hash() -> str:
    global _BUNDLE_STAMP
    if _BUNDLE_STAMP is None:
        from polymath_shared.execution_bundle import (
            bundle_id, compute_execution_bundle)
        _BUNDLE_STAMP = bundle_id(compute_execution_bundle())
    return _BUNDLE_STAMP


def _record_lane_attempt(conn: Connection, *, doc_id: str, corpus_id: str,
                         lane: str, opportunities: int, accepted: int,
                         capped: bool) -> None:
    """SEMANTIC-LANE-LIVENESS-V1 durable disposition.

    NO_OPPORTUNITY is a CORRECT outcome and must stay distinguishable
    from a lane that saw evidence and produced nothing (GATED) -- the
    latter is the dead-feature signal."""
    if opportunities <= 0:
        disposition = "NO_OPPORTUNITY"
    elif accepted > 0:
        disposition = "ACCEPTED"
    else:
        disposition = "GATED"
    conn.execute(
        """
        INSERT INTO knowledge_lane_attempts
            (doc_id, corpus_id, lane, opportunities, accepted, capped,
             disposition, bundle_hash)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (doc_id, lane) DO UPDATE SET
            opportunities = EXCLUDED.opportunities,
            accepted = EXCLUDED.accepted,
            capped = EXCLUDED.capped,
            disposition = EXCLUDED.disposition,
            bundle_hash = EXCLUDED.bundle_hash,
            created_at = now()
        """,
        (doc_id, corpus_id, lane, opportunities, accepted, capped,
         disposition, _bundle_hash()))


def _persist_knowledge_artifacts(conn: Connection, *, corpus_id: str,
                                 doc_id: str, doc_text: str,
                                 chunk_ids: list[str],
                                 durable_surfaces: list[str]) -> dict:
    """KNOWLEDGE-ARTIFACT-PERSISTENCE-V1: compile Procedure/Concept
    artifacts as first-class objects. They are NOT facts and never touch
    the entity graph here; retrieval projection is the projector's job.
    Content-addressed ids make replay idempotent.

    EXTRACTION-ELIGIBILITY-V1: the compilers are the LOCAL-EVIDENCE
    detectors — cheap, deterministic, self-gating (no procedural or
    conceptual evidence → no artifact). Document-level classification
    is recorded as routing metadata but never vetoes a compiler:
    eligible content always gets evaluated."""
    from polymath_shared.knowledge_router.classifier import classify_document
    from polymath_shared.knowledge_objects.concept import (
        compile_concept_inventory)
    from polymath_shared.knowledge_objects.procedure import compile_procedures

    routing = classify_document(doc_text)["routing"]
    counts = {"procedures": 0, "concepts": 0,
              "routing_disabled": sorted(routing.get("disabled") or [])}

    # SEMANTIC-LANE-LIVENESS-V1: record the OPPORTUNITY, not just the
    # output. An artifact count alone cannot tell "12 of 12 opportunities
    # captured" from "12 of 400", which is precisely how a lane can look
    # alive while being deeply lossy. Counters are diagnostic and share
    # the compilers' own helpers, so they cannot drift from what the
    # compilers actually evaluate.
    from polymath_shared.knowledge_objects import concept as _concept_mod
    from polymath_shared.knowledge_objects import procedure as _procedure_mod
    from workers.summarizer import split_sentences as _split

    _doc_sentences = _split(doc_text)
    # V2 counter for a V2 compiler. Measuring opportunities with the v1
    # whitelist while compiling with the v2 detector would report more
    # artifacts ACCEPTED than opportunities SEEN — a lane that looks
    # like it manufactures evidence.
    _proc_opportunities = _procedure_mod.count_opportunities_v2(
        doc_text, frozenset(e.lower() for e in (durable_surfaces or ())))
    _concept_opportunities = _concept_mod.count_opportunities(_doc_sentences)

    # procedure lane: always evaluated; the compiler self-gates on
    # local procedural evidence.
    #
    # PROCEDURE_ARTIFACT_V2 (P3): one artifact per LOCAL TASK, not one
    # per document. A runbook page holding three separate tasks used to
    # collapse into a single artifact whose goal was the first task's
    # second step. Artifact ids stay content-addressed, so N rows per
    # document remain idempotent on replay.
    for proc in compile_procedures(
            document_id=doc_id, corpus_id=corpus_id, text=doc_text,
            admitted_entities=durable_surfaces,
            source_chunk_ids=chunk_ids):
        conn.execute(
            """
            INSERT INTO procedure_artifacts
                (procedure_id, document_id, corpus_id, title, goal,
                 steps_json, tools_json, confidence, source_chunk_ids,
                 provenance, generated_by_bundle_hash)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (procedure_id) DO UPDATE SET
                source_chunk_ids = EXCLUDED.source_chunk_ids,
                provenance = EXCLUDED.provenance,
                generated_by_bundle_hash = EXCLUDED.generated_by_bundle_hash
            """,
            (proc["artifact_id"], doc_id, corpus_id,
             proc.get("title", ""), proc.get("goal", ""),
             json.dumps(proc.get("steps", [])),
             json.dumps(proc.get("tools", [])),
             float(proc.get("confidence", 0.0)), list(chunk_ids),
             json.dumps(proc.get("provenance", {})),
             _bundle_hash()))
        counts["procedures"] += 1

    # concept lane: always evaluated; the compiler self-gates on
    # local definitional evidence
    from workers.summarizer import split_sentences
    # CONCEPT_CONTRACT_V2 (P4): the durable inventory. max_concepts=10
    # used to stop the scan at ten, so a 400-page book stored ten
    # concepts and never read the rest — 12 of 13 live documents held
    # exactly ten by construction. Storage is now governed by name
    # admission; the top-N survives as `summary_rank` for routing cards.
    concepts = compile_concept_inventory(
        document_id=doc_id, corpus_id=corpus_id,
        sentences=split_sentences(doc_text),
        admitted_entities=durable_surfaces,
        source_chunk_ids=chunk_ids)
    for c in concepts:
        conn.execute(
            """
            INSERT INTO concept_artifacts
                (concept_id, document_id, corpus_id, name, description,
                 domain, related_entities, source_sentence, confidence,
                 supporting_chunks, provenance, generated_by_bundle_hash)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (concept_id) DO UPDATE SET
                supporting_chunks = EXCLUDED.supporting_chunks,
                provenance = EXCLUDED.provenance,
                generated_by_bundle_hash = EXCLUDED.generated_by_bundle_hash
            """,
            (c["artifact_id"], doc_id, corpus_id, c["name"],
             c.get("description", ""), c.get("domain", "general"),
             json.dumps(c.get("related_entities", [])),
             c.get("source_sentence", ""),
             float(c.get("confidence", 0.0)), list(chunk_ids),
             json.dumps(c.get("provenance", {})),
             _bundle_hash()))
        counts["concepts"] += 1

    _record_lane_attempt(conn, doc_id=doc_id, corpus_id=corpus_id,
                         lane="procedure",
                         opportunities=_proc_opportunities,
                         accepted=counts["procedures"], capped=False)
    _record_lane_attempt(conn, doc_id=doc_id, corpus_id=corpus_id,
                         lane="concept",
                         opportunities=_concept_opportunities,
                         accepted=counts["concepts"],
                         # CONCEPT_CONTRACT_V2 has no storage ceiling, so
                         # the lane can no longer be truncated by a cap.
                         # A shortfall now means admission refused the
                         # candidate, which is a quality decision with a
                         # recorded reason — not silent truncation.
                         capped=False)
    counts["procedure_opportunities"] = _proc_opportunities
    counts["concept_opportunities"] = _concept_opportunities
    return counts

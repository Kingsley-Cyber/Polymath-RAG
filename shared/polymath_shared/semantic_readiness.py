"""SEMANTIC-READINESS-V1: an explicit semantic-completion verdict,
separate from `query_ready`.

`query_ready` is the CONTROL contract: the blocking ingestion/
projection path converged (its semantics are mature and frozen — this
module never redefines them). What it does NOT promise is that every
semantic lane executed successfully: the artifact lane records its
exceptions in the extract-stage artifact payload and continues with
zero counts, summary stages are non-blocking, and artifact projections
were not part of promotion verification (SMART verification REQ-015).

This view answers the different question from DURABLE state only:

    did FACT / PROCEDURE / CONCEPT extraction, the summary hierarchy,
    the corpus map, and the artifact projections all COMPLETE — where
    ZERO legitimate yield is completion and FAILED execution is not?

Verdicts:
    SEMANTIC_COMPLETE     every required lane executed; yields may be 0
    SEMANTIC_INCOMPLETE   lanes still pending (summaries/map/receipts)
    SEMANTIC_FAILED       a lane recorded a failure (artifacts_error)

Postgres receipts prove state; logs do not.
"""
from __future__ import annotations

SEMANTIC_READINESS_VERSION = "semantic-readiness-v1"

COMPLETE = "SEMANTIC_COMPLETE"
INCOMPLETE = "SEMANTIC_INCOMPLETE"
FAILED = "SEMANTIC_FAILED"


def semantic_completion(conn, corpus_id: str) -> dict:
    """One deterministic read of the durable semantic-lane state."""
    runs = conn.execute(
        """SELECT status, COUNT(*) FROM runs
            WHERE corpus_id = %s GROUP BY status""",
        (corpus_id,)).fetchall()
    run_counts = {status: n for status, n in runs}
    total_runs = sum(run_counts.values())
    query_ready_runs = run_counts.get("query_ready", 0)

    # Artifact-lane FAILURES: the extract stage records swallowed
    # artifact exceptions durably as payload key 'artifacts_error'.
    failures = conn.execute(
        """SELECT a.run_id, a.payload->>'artifacts_error'
             FROM artifacts a
             JOIN runs r ON r.run_id = a.run_id
            WHERE r.corpus_id = %s
              AND a.stage = 'extract'
              AND jsonb_exists(a.payload, 'artifacts_error')""",
        (corpus_id,)).fetchall()
    artifact_lane_failures = [
        {"run_id": rid, "error": err} for rid, err in failures]

    # EXTRACTION-COVERAGE-V1: the same verdict the census uses as its
    # promotion barrier, shown per run. HARD reasons (dropped /
    # unaccounted neighborhoods) are FAILED execution, not zero yield.
    from polymath_shared.extraction_coverage import coverage_verdict
    from polymath_shared.settings import get_settings
    floor = float(get_settings().control.extraction_coverage_floor)
    ext_rows = conn.execute(
        """SELECT r.run_id, r.status, r.metadata->>'source_name',
                  a.payload->'llm_extraction'->'stats',
                  r.metadata->'degraded_reasons'
             FROM runs r
             LEFT JOIN LATERAL (
                 SELECT payload FROM artifacts x
                  WHERE x.run_id = r.run_id AND x.stage = 'extract'
                    AND jsonb_exists(x.payload, 'llm_extraction')
                  ORDER BY x.created_at DESC LIMIT 1) a ON TRUE
            WHERE r.corpus_id = %s
            ORDER BY r.created_at, r.run_id""",
        (corpus_id,)).fetchall()
    extraction = []
    for rid, status, source_name, stats, degraded_reasons in ext_rows:
        v = coverage_verdict(stats, floor=floor)
        v.update({"run_id": rid, "status": status, "source_name": source_name,
                  "degraded_reasons": degraded_reasons})
        extraction.append(v)
    extraction_failures = [
        {"run_id": e["run_id"], "source_name": e["source_name"], "reasons": e["reasons"]}
        for e in extraction if not e["ok"]]
    warnings = [f"{e['source_name'] or e['run_id'][:20]}: {w}"
                for e in extraction for w in e["warnings"]]

    docs = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE corpus_id = %s",
        (corpus_id,)).fetchone()[0]
    doc_summaries = conn.execute(
        "SELECT COUNT(DISTINCT document_id) FROM document_summaries WHERE corpus_id = %s",
        (corpus_id,)).fetchone()[0]
    parent_summaries = conn.execute(
        "SELECT COUNT(*) FROM parent_summaries WHERE corpus_id = %s "
        "AND superseded_at IS NULL",
        (corpus_id,)).fetchone()[0]
    corpus_map_rows = conn.execute(
        "SELECT COUNT(*) FROM corpus_summaries WHERE corpus_id = %s",
        (corpus_id,)).fetchone()[0]

    procedures = conn.execute(
        "SELECT COUNT(*) FROM procedure_artifacts WHERE corpus_id = %s",
        (corpus_id,)).fetchone()[0]
    concepts = conn.execute(
        "SELECT COUNT(*) FROM concept_artifacts WHERE corpus_id = %s",
        (corpus_id,)).fetchone()[0]
    facts = conn.execute(
        """SELECT COUNT(DISTINCT f.fact_id) FROM facts f
             JOIN evidence ev ON ev.fact_id = f.fact_id
             JOIN documents d ON d.doc_id = ev.doc_id
            WHERE d.corpus_id = %s AND f.decision = 'ACCEPT'""",
        (corpus_id,)).fetchone()[0]

    # Artifact PROJECTION completeness: every persisted procedure/
    # concept artifact carries an active qdrant routing receipt.
    unprojected_procedures = conn.execute(
        """SELECT COUNT(*) FROM procedure_artifacts p
            WHERE p.corpus_id = %s AND NOT EXISTS (
                SELECT 1 FROM projection_receipts pr
                 WHERE pr.projection = 'qdrant'
                   AND pr.entity_kind = 'routing_procedure'
                   AND pr.entity_id = p.procedure_id
                   AND pr.active)""",
        (corpus_id,)).fetchone()[0]
    unprojected_concepts = conn.execute(
        """SELECT COUNT(*) FROM concept_artifacts c
            WHERE c.corpus_id = %s AND NOT EXISTS (
                SELECT 1 FROM projection_receipts pr
                 WHERE pr.projection = 'qdrant'
                   AND pr.entity_kind = 'routing_concept'
                   AND pr.entity_id = c.concept_id
                   AND pr.active)""",
        (corpus_id,)).fetchone()[0]

    pending: list[str] = []
    if total_runs == 0 or docs == 0:
        pending.append("no_ingested_documents")
    if total_runs and query_ready_runs == 0:
        pending.append("no_query_ready_run")
    if docs and doc_summaries < docs:
        pending.append(f"document_summaries_{doc_summaries}_of_{docs}")
    if docs and parent_summaries == 0:
        pending.append("no_parent_summaries")
    if docs and corpus_map_rows == 0:
        pending.append("no_corpus_map")
    if unprojected_procedures:
        pending.append(f"unprojected_procedures_{unprojected_procedures}")
    if unprojected_concepts:
        pending.append(f"unprojected_concepts_{unprojected_concepts}")

    if artifact_lane_failures or extraction_failures:
        verdict = FAILED
    elif pending:
        verdict = INCOMPLETE
    else:
        verdict = COMPLETE

    return {
        "contract": SEMANTIC_READINESS_VERSION,
        "corpus_id": corpus_id,
        "verdict": verdict,
        "pending": pending,
        "artifact_lane_failures": artifact_lane_failures,
        "extraction": extraction,
        "extraction_failures": extraction_failures,
        "warnings": warnings,
        "runs": run_counts,
        "counts": {
            "documents": docs,
            "document_summaries": doc_summaries,
            "parent_summaries": parent_summaries,
            "corpus_map_rows": corpus_map_rows,
            "facts_accepted": facts,
            "procedures": procedures,
            "concepts": concepts,
        },
        # Zero yield is legitimate completion; only FAILURE or PENDING
        # execution blocks the verdict. This line is the contract.
        "zero_yield_is_completion": True,
    }

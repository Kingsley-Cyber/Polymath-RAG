"""COMPILE-OBJECTS-STAGE-V1 (§11, owner 2026-08-30): the deterministic
concept/procedure compilers as a first-class, provider-agnostic stage.

The GLiNER→LLM migration left the compilers threaded through the extract
branches — a bolt-on call inside llm_live, an inline call in the legacy
path. As a stage they gain their own contract hash, stage attempts,
receipts, artifact, and opportunity accounting — and they run IDENTICALLY
under either provider era: the inputs are the admitted mentions (surfaces)
and the document's child-chunk text, both provider-neutral by the time
this stage claims.

Consumes `compile_objects.v1` (ticket DAG, non-blocking: a failure
degrades knowledge objects, never blocks QUERY_READY). Idempotent:
artifact ids are content-addressed; replay writes zero rows.
"""
from __future__ import annotations

import logging

from psycopg import Connection

from polymath_shared.logging import configure_logging
from polymath_shared.receipts import (
    StageFailed,
    stage_contract_hash,
    stage_transaction,
)

STAGE = "compile_objects"
EVENT_TYPE = "compile_objects.v1"
CONTRACT_VERSION = "1.0.0"

log = logging.getLogger("compile-objects")


def _run_documents(conn: Connection, run_id: str) -> list[str]:
    """The run's documents. Runs are per-document (document_processing_runs
    is the durable link); the corpus-wide fallback covers legacy runs
    minted before that table was populated."""
    rows = conn.execute(
        "SELECT DISTINCT document_id FROM document_processing_runs WHERE run_id = %s",
        (run_id,),
    ).fetchall()
    if rows:
        return [r[0] for r in rows]
    rows = conn.execute(
        """
        SELECT d.doc_id FROM documents d
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s
           AND d.source_name = (SELECT metadata->>'source_name' FROM runs
                                 WHERE run_id = %s)
        """,
        (run_id, run_id),
    ).fetchall()
    return [r[0] for r in rows]


def process_event(conn: Connection, event: dict) -> None:
    from workers.knowledge_artifacts import _persist_knowledge_artifacts

    run_id = event["run_id"]
    row = conn.execute(
        "SELECT corpus_id FROM runs WHERE run_id = %s", (run_id,)
    ).fetchone()
    if row is None:
        raise StageFailed(run_id, STAGE)
    corpus_id = row[0]

    contract = stage_contract_hash(STAGE, {
        "contract_version": CONTRACT_VERSION,
        # v2 (2026-09-03, GENERATION-SWAP-V1): the persister UPSERTs, refreshing
        # supporting_chunks/source_chunk_ids on replay instead of DO NOTHING —
        # a new contract hash, so every corpus re-grounds its artifacts once.
        "persistence": "knowledge-artifact-persistence-v2",
    })

    with stage_transaction(conn, run_id=run_id, stage=STAGE,
                           contract_hash=contract) as writer:
        doc_ids = _run_documents(conn, run_id)
        per_doc = {}
        for doc_id in doc_ids:
            chunk_rows = conn.execute(
                """
                SELECT chunk_id, text FROM chunks
                 WHERE doc_id = %s AND tier = 'child'
                 ORDER BY chunk_index
                """,
                (doc_id,),
            ).fetchall()
            if not chunk_rows:
                per_doc[doc_id] = {"skipped": "no child chunks"}
                continue
            surfaces = [r[0] for r in conn.execute(
                """
                SELECT DISTINCT surface FROM mentions
                 WHERE doc_id = %s AND surface IS NOT NULL
                 ORDER BY surface
                """,
                (doc_id,),
            ).fetchall()]
            counts = _persist_knowledge_artifacts(
                conn, corpus_id=corpus_id, doc_id=doc_id,
                doc_text="\n".join(r[1] for r in chunk_rows),
                chunk_ids=[r[0] for r in chunk_rows],
                durable_surfaces=surfaces)
            per_doc[doc_id] = counts
        writer.artifact({
            "contract": "compile-objects-v1",
            "corpus_id": corpus_id,
            "documents": len(doc_ids),
            "per_document": per_doc,
            "concepts": sum(int(c.get("concepts") or 0)
                            for c in per_doc.values()),
            "procedures": sum(int(c.get("procedures") or 0)
                              for c in per_doc.values()),
        })
        writer.run_status("reconciling")


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 1) -> None:
    from polymath_shared.worker_runtime import run_worker

    run_worker("compile_objects", [EVENT_TYPE], process_event,
               poll_interval_s=poll_interval_s, batch_size=batch_size)


if __name__ == "__main__":
    configure_logging("worker-compile-objects")
    run_forever()

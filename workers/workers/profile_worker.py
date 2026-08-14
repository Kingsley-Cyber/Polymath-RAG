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
CONTRACT_VERSION = "1.0.0"

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
        for doc in _documents_for_run(conn, run_id):
            parents = _parents_for_doc(conn, doc["doc_id"])
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
            profiles.append(profile.model_dump())

        writer.artifact({"documents_profiled": len(profiles)})
        writer.run_status("reconciling")


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 4) -> None:
    configure_logging("worker-profile-document")
    while True:
        try:
            with tx() as conn:
                events = claim_events(conn, [EVENT_TYPE], batch_size)
                if events:
                    for event in events:
                        try:
                            process_event(conn, event)
                            log.info("document profile committed", extra={
                                "run_id": event["run_id"], "stage": STAGE,
                            })
                        except StageFailed as exc:
                            log.error(str(exc), extra={
                                "run_id": event["run_id"], "stage": STAGE,
                                "error_code": "stage_failed",
                            })
        except psycopg.errors.OperationalError as exc:
            log.warning("postgres unavailable; backing off", extra={"error_code": "pg_unavailable"})
        except Exception as exc:
            log.exception("profile stage failed", extra={"error_code": type(exc).__name__})
        time.sleep(poll_interval_s)


if __name__ == "__main__":
    run_forever()

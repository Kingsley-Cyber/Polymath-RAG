"""Qdrant projector: chunks -> vector points. A durable projection stage.

Consumes `extracted.v1` outbox events. Projects EVERY chunk of the run's
documents (children and parents) into the collection
`polymath_<corpus_hash>_<embedding_contract>`.

Idempotency contract (PLAN Phase F):

  - point ids are the source chunk ids — Qdrant never invents identity;
  - payload carries corpus_id, doc_id, parent_id, content_hash,
    embedding_contract — everything needed to rebuild;
  - the Postgres projection receipt commits AFTER the Qdrant write, in
    the stage transaction: receipts are the commit point, Qdrant writes
    are re-drivable (a crash between the two leaves an orphan point
    that VERIFY_PROJECTIONS detects, acceptance test 7).

The vector database never decides whether a chunk exists.
"""
from __future__ import annotations

import json
import logging
import os
import time

import psycopg
from psycopg import Connection
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from polymath_shared.db import tx
from polymath_shared.logging import configure_logging
from polymath_shared.projection_contracts import (
    EMBEDDING_CONTRACT,
    EMBEDDING_CONTRACTS,
    KIND_CHUNK,
    PROJECTION_QDRANT,
    embed,
    projection_id,
    qdrant_collection_name,
    qdrant_point_uuid,
    receipt_hash,
)
from polymath_shared.receipts import (
    StageFailed,
    claim_events,
    stage_contract_hash,
    stage_transaction,
)
from polymath_shared.settings import get_settings

STAGE = "project_qdrant"
EVENT_TYPE = "project_qdrant.v1"

CONTRACT_VERSION = "1.0.0"

log = logging.getLogger("project-qdrant")


def _collection_exists(client: QdrantClient, name: str) -> bool:
    try:
        client.get_collection(name)
        return True
    except Exception:
        return False


def _ensure_collection(client: QdrantClient, name: str) -> None:
    if _collection_exists(client, name):
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=EMBEDDING_CONTRACTS[EMBEDDING_CONTRACT]["dim"],
            distance=Distance.COSINE,
        ),
    )


def _chunks_for_run(conn: Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.chunk_id, c.doc_id, c.parent_id, c.chunk_index, c.tier,
               c.text, c.summary, d.corpus_id
          FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s
         ORDER BY c.chunk_index
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "chunk_id": row[0],
            "doc_id": row[1],
            "parent_id": row[2],
            "chunk_index": row[3],
            "tier": row[4],
            "text": row[5],
            "summary": row[6],
            "corpus_id": row[7],
        }
        for row in rows
    ]


def _write_points(client: QdrantClient, collection: str, chunks: list[dict]) -> None:
    points = [
        PointStruct(
            id=qdrant_point_uuid(chunk["chunk_id"]),
            vector=embed(chunk["text"], EMBEDDING_CONTRACT),
            payload={
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "parent_id": chunk["parent_id"] or "",
                "corpus_id": chunk["corpus_id"],
                "tier": chunk["tier"],
                "chunk_index": chunk["chunk_index"],
                "content_hash": projection_id(
                    PROJECTION_QDRANT, KIND_CHUNK, chunk["chunk_id"], CONTRACT_VERSION
                ),
                "embedding_contract": EMBEDDING_CONTRACT,
                "text": chunk["text"],
                "summary": chunk["summary"],
            },
        )
        for chunk in chunks
    ]
    client.upsert(collection_name=collection, points=points, wait=True)


def _receipts(conn: Connection, chunks: list[dict]) -> None:
    for chunk in chunks:
        conn.execute(
            """
            INSERT INTO projection_receipts (projection, entity_kind, entity_id, receipt_hash)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (projection, entity_kind, entity_id) DO NOTHING
            """,
            (PROJECTION_QDRANT, KIND_CHUNK, chunk["chunk_id"],
             receipt_hash(PROJECTION_QDRANT, KIND_CHUNK, chunk["chunk_id"], CONTRACT_VERSION)),
        )


def process_event(conn: Connection, event: dict) -> None:
    payload = event["payload"]
    run_id = event["run_id"]
    corpus_id = payload.get("corpus_id")
    chunks = _chunks_for_run(conn, run_id)

    contract = stage_contract_hash(STAGE, {
        "projection": PROJECTION_QDRANT,
        "embedding_contract": EMBEDDING_CONTRACT,
        "contract_version": CONTRACT_VERSION,
    })

    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract) as writer:
        writer.artifact({"chunk_count": len(chunks), "embedding_contract": EMBEDDING_CONTRACT})

        if chunks:
            client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
            try:
                corpus_id = corpus_id or chunks[0]["corpus_id"]
                collection = qdrant_collection_name(corpus_id, EMBEDDING_CONTRACT)
                _ensure_collection(client, collection)
                _write_points(client, collection, chunks)
            finally:
                client.close()
            _receipts(conn, chunks)

        crash_after = int(os.environ.get("POLYMATH_TEST_CRASH_AFTER_POINTS", "0"))
        if crash_after and len(chunks) >= crash_after:
            # Fault injection for acceptance test 3 (kill the projector
            # mid-flight). Never set in production.
            raise RuntimeError("fault injection: simulated crash after points write")

        # No outbox event: the control census schedules the verify stage
        # from this receipt.
        writer.run_status("reconciling")


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 4) -> None:
    configure_logging("worker-project-qdrant")
    while True:
        try:
            with tx() as conn:
                events = claim_events(conn, [EVENT_TYPE], batch_size)
                if events:
                    for event in events:
                        try:
                            process_event(conn, event)
                            log.info("qdrant projection processed", extra={
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
            log.exception("qdrant projection failed", extra={"error_code": type(exc).__name__})
        time.sleep(poll_interval_s)


if __name__ == "__main__":
    run_forever()

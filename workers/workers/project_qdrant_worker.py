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
    record_projection_attempt,
    stage_contract_hash,
    stage_transaction,
)
from polymath_shared.settings import get_settings

STAGE = "project_qdrant"
EVENT_TYPE = "project_qdrant.v1"

CONTRACT_VERSION = "1.1.0"

log = logging.getLogger("project-qdrant")


def _active_contract():
    """Resolve the active embedding contract through the shared resolver
    (friendly id or derived contract id)."""
    from polymath_shared.embedding_contracts import active_contract

    return active_contract()


def _embed_texts(contract, texts: list[str]) -> list[list[float]]:
    """Embed under the active contract: local fn or the embedder sidecar."""
    if contract.embed_fn is not None:
        return [contract.embed(text, "child_chunk") for text in texts]
    from polymath_shared.clients import EmbedderClient

    client = EmbedderClient()
    try:
        client.verify_pin()
        return client.embed(texts, "child_chunk")["vectors"]
    finally:
        client.close()


def _collection_exists(client: QdrantClient, name: str) -> bool:
    try:
        client.get_collection(name)
        return True
    except Exception:
        return False


def _ensure_collection(client: QdrantClient, name: str, dim: int) -> None:
    if _collection_exists(client, name):
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
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


def _write_points(client: QdrantClient, collection: str, chunks: list[dict], contract) -> None:
    vectors = _embed_texts(contract, [chunk["text"] for chunk in chunks])
    points = [
        PointStruct(
            id=qdrant_point_uuid(chunk["chunk_id"]),
            vector=vectors[i],
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
                "embedding_contract": contract.contract_id,
                "text": chunk["text"],
                "summary": chunk["summary"],
            },
        )
        for i, chunk in enumerate(chunks)
    ]
    client.upsert(collection_name=collection, points=points, wait=True)


# ---------------------------------------------------------------------------
# R1A substrate: routing representations (SUMMARIES ROUTE / CHILDREN PROVE)
# ---------------------------------------------------------------------------
ROUTING_KIND_DOCUMENT_SUMMARY = "routing_document_summary"
ROUTING_KIND_SECTION_SUMMARY = "routing_section_summary"
ROUTING_KIND_CHILD = "routing_child"

ROUTING_CONTRACT_VERSION = "1.0.0"


def _routing_rows(conn: Connection, run_id: str) -> list[dict]:
    """Authoritative routing representations for the run's corpus:
    canonical DOCUMENT_RETRIEVAL_SUMMARY + SECTION_RETRIEVAL_SUMMARY
    rows (contract retrieval-summary-v2) + child evidence chunks."""
    from polymath_shared.retrieval_summaries import (
        DOC_SUMMARY_KIND,
        SECTION_SUMMARY_KIND,
    )

    rows = conn.execute(
        """
        SELECT rs.summary_id, rs.kind, rs.summary_text, rs.corpus_id, rs.doc_id,
               rs.parent_id, d.source_name
          FROM retrieval_summaries rs
          JOIN documents d ON d.doc_id = rs.doc_id
          JOIN runs r ON r.corpus_id = rs.corpus_id
         WHERE r.run_id = %s
         ORDER BY rs.doc_id, rs.parent_id NULLS FIRST
        """,
        (run_id,),
    ).fetchall()
    out = []
    for row in rows:
        kind = ROUTING_KIND_DOCUMENT_SUMMARY if row[1] == DOC_SUMMARY_KIND else ROUTING_KIND_SECTION_SUMMARY
        out.append({
            "summary_id": row[0],
            "representation_kind": kind,
            "text": row[2],
            "corpus_id": row[3],
            "doc_id": row[4],
            "parent_id": row[5],
            "source_name": row[6],
        })
    children = conn.execute(
        """
        SELECT c.chunk_id, c.doc_id, c.parent_id, c.text, d.corpus_id
          FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s AND c.tier = 'child'
         ORDER BY c.chunk_index
        """,
        (run_id,),
    ).fetchall()
    for row in children:
        out.append({
            "summary_id": None,
            "representation_kind": ROUTING_KIND_CHILD,
            "text": row[3],
            "corpus_id": row[4],
            "doc_id": row[1],
            "parent_id": row[2],
            "source_name": "",
            "chunk_id": row[0],
        })
    return out


def _write_routing_points(client: QdrantClient, collection: str, rows: list[dict], contract) -> None:
    # the embedder contract bounds batches at 32 texts per request
    batch_limit = getattr(contract, "batch_limit", 32) or 32
    vectors: list[list[float]] = []
    for i in range(0, len(rows), batch_limit):
        vectors.extend(_embed_texts(contract, [r["text"] for r in rows[i:i + batch_limit]]))
    points = []
    for i, r in enumerate(rows):
        point_id = qdrant_point_uuid(r["summary_id"] or r["chunk_id"])
        points.append(PointStruct(
            id=point_id,
            vector=vectors[i],
            payload={
                "summary_id": r["summary_id"],
                "chunk_id": r.get("chunk_id"),
                "representation_kind": r["representation_kind"],
                "corpus_id": r["corpus_id"],
                "doc_id": r["doc_id"],
                "parent_id": r["parent_id"] or "",
                "source_name": r["source_name"],
                "embedding_contract": contract.contract_id,
                "text": r["text"],
            },
        ))
    client.upsert(collection_name=collection, points=points, wait=True)


def process_event(conn: Connection, event: dict) -> None:
    payload = event["payload"]
    run_id = event["run_id"]
    corpus_id = payload.get("corpus_id")
    chunks = _chunks_for_run(conn, run_id)
    contract = _active_contract()

    stage_contract = stage_contract_hash(STAGE, {
        "projection": PROJECTION_QDRANT,
        "embedding_contract": contract.contract_id,
        "contract_version": CONTRACT_VERSION,
        "routing_contract": "neural-embed-v1",
        "routing_contract_version": ROUTING_CONTRACT_VERSION,
    })

    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=stage_contract) as writer:
        writer.artifact({
            "chunk_count": len(chunks),
            "embedding_contract": contract.contract_id,
        })

        if chunks:
            client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
            try:
                corpus_id = corpus_id or chunks[0]["corpus_id"]
                collection = qdrant_collection_name(corpus_id, contract.contract_id)
                _ensure_collection(client, collection, contract.dimension)
                _write_points(client, collection, chunks, contract)
            finally:
                client.close()
            for chunk in chunks:
                record_projection_attempt(
                    conn,
                    projection=PROJECTION_QDRANT,
                    entity_kind=KIND_CHUNK,
                    entity_id=chunk["chunk_id"],
                    receipt_hash=receipt_hash(PROJECTION_QDRANT, KIND_CHUNK, chunk["chunk_id"], CONTRACT_VERSION),
                    contract=contract.contract_id,
                )

        # R1A routing representations under the QUALIFIED neural
        # contract, in a separate collection (hash vectors never appear
        # semantically equivalent to neural vectors). Idempotent upserts
        # (point ids are summary/chunk content ids).
        from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT

        routing_contract = NEURAL_EMBED_CONTRACT
        routing_rows = _routing_rows(conn, run_id)
        if routing_rows:
            client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=120)
            try:
                routing_collection = qdrant_collection_name(
                    corpus_id or routing_rows[0]["corpus_id"], routing_contract.contract_id
                )
                _ensure_collection(client, routing_collection, routing_contract.dimension)
                _write_routing_points(client, routing_collection, routing_rows, routing_contract)
            finally:
                client.close()
            for r in routing_rows:
                record_projection_attempt(
                    conn,
                    projection=PROJECTION_QDRANT,
                    entity_kind=r["representation_kind"],
                    entity_id=r["summary_id"] or r["chunk_id"],
                    receipt_hash=receipt_hash(
                        PROJECTION_QDRANT, r["representation_kind"],
                        r["summary_id"] or r["chunk_id"], ROUTING_CONTRACT_VERSION,
                    ),
                    contract=routing_contract.contract_id,
                )

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

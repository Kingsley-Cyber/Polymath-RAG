"""VERIFY_PROJECTIONS: the acceptance gate between projection writes and
query_ready. Reconciliation semantics:

  - desired = the run's chunks (Qdrant) and entities/facts/evidence (Neo4j);
  - receipts = observed Postgres state; live stores = observed store state;
  - store lost an artifact -> receipt is cleared (the census re-drives
    the projector stage);
  - store has an extra artifact (crash orphan) -> deleted from the store;
  - receipt without a source row (orphan) -> deleted.

Verify NEVER touches Postgres semantic truth (chunks, facts, evidence
rows are read-only here). Receipts and projection store contents are
derived, disposable state by design (PLAN Phase F).
"""
from __future__ import annotations

import logging
import time

import psycopg
from psycopg import Connection
from polymath_shared.stores import qdrant_client as _qdrant_client

from polymath_shared.db import tx
from polymath_shared.logging import configure_logging
from polymath_shared.embedding_contracts import active_contract
from polymath_shared.projection_contracts import qdrant_collection_name
from polymath_shared.receipts import (
    StageFailed,
    claim_events,
    stage_contract_hash,
    stage_transaction,
    supersede_projection_claims,
)
from polymath_shared.settings import get_settings
from polymath_shared.stores import neo4j_driver as _neo4j_driver

STAGE = "verify_projections"
EVENT_TYPE = "verify.v1"
CONTRACT_VERSION = "1.0.0"

log = logging.getLogger("verify-projections")


def _run_identity(conn: Connection, run_id: str) -> str | None:
    row = conn.execute("SELECT corpus_id FROM runs WHERE run_id = %s", (run_id,)).fetchone()
    return row[0] if row else None


def _desired_chunk_ids(conn: Connection, run_id: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT c.chunk_id FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s ORDER BY c.chunk_id
        """,
        (run_id,),
    ).fetchall()
    return [r[0] for r in rows]


def _receipt_chunk_ids(conn: Connection, corpus: str, projection: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT pr.entity_id FROM projection_receipts pr
          JOIN chunks c ON c.chunk_id = pr.entity_id
          JOIN documents d ON d.doc_id = c.doc_id
         WHERE pr.projection = %s AND pr.entity_kind = 'chunk' AND pr.active AND d.corpus_id = %s
        """,
        (projection, corpus),
    ).fetchall()
    return [r[0] for r in rows]


def _clear_receipts(conn: Connection, projection: str, entity_ids: list[str]) -> None:
    """Supersede active claims (history survives in projection_attempts)."""
    supersede_projection_claims(conn, projection=projection, entity_ids=entity_ids)


def _delete_orphan_receipts(conn: Connection, projection: str) -> list[str]:
    """Supersede claims whose source entity no longer exists."""
    rows = conn.execute(
        """
        SELECT pr.entity_id FROM projection_receipts pr
         WHERE pr.projection = %s AND pr.entity_kind = 'chunk' AND pr.active
           AND NOT EXISTS (SELECT 1 FROM chunks c WHERE c.chunk_id = pr.entity_id)
        """,
        (projection,),
    ).fetchall()
    ids = [r[0] for r in rows]
    supersede_projection_claims(conn, projection=projection, entity_ids=ids)
    return ids


def reconcile_qdrant(conn: Connection, run_id: str, corpus: str) -> dict:
    settings = get_settings()
    collection = qdrant_collection_name(corpus, active_contract().contract_id)
    desired = set(_desired_chunk_ids(conn, run_id))
    receipts = set(_receipt_chunk_ids(conn, corpus, "qdrant"))

    client = _qdrant_client()
    try:
        store_ids: set[str] = set()
        try:
            points, _ = client.scroll(collection_name=collection, limit=100_000, with_vectors=False)
            store_ids = {str(p.payload.get("chunk_id")) for p in points if p.payload}
        except Exception:
            store_ids = set()
    finally:
        client.close()

    # Store lost artifacts -> clear receipts so the census re-drives.
    missing_in_store = receipts - store_ids
    if missing_in_store:
        _clear_receipts(conn, "qdrant", sorted(missing_in_store))

    # Orphan store artifacts (no receipt, no source) -> delete from store.
    orphans_in_store = store_ids - receipts
    if orphans_in_store:
        client = _qdrant_client()
        try:
            points, _ = client.scroll(collection_name=collection, limit=100_000, with_vectors=False)
            orphan_point_ids = [
                p.id for p in points
                if p.payload and str(p.payload.get("chunk_id")) in orphans_in_store
            ]
            if orphan_point_ids:
                client.delete(collection_name=collection, points_selector=orphan_point_ids)
        finally:
            client.close()

    orphan_receipts = _delete_orphan_receipts(conn, "qdrant")
    # Recompute AFTER clearing: every desired chunk still lacking a
    # receipt (or whose receipt was just cleared) is a gap.
    missing_receipts = desired - (receipts - missing_in_store)

    return {
        "missing_in_store": sorted(missing_in_store),
        "orphans_in_store": sorted(orphans_in_store),
        "orphan_receipts": orphan_receipts,
        "missing_receipts": sorted(missing_receipts),
    }


def reconcile_neo4j(conn: Connection, run_id: str, corpus: str) -> dict:
    desired = set(_desired_chunk_ids(conn, run_id))
    receipts = set(_receipt_chunk_ids(conn, corpus, "neo4j"))

    driver = _neo4j_driver()
    try:
        with driver.session() as session:
            result = session.run("MATCH (c:Chunk) RETURN c.chunk_id AS id")
            store_ids = {r["id"] for r in result}
            # Delete orphan chunk nodes (no receipt).
            orphans = store_ids - receipts
            for chunk_id in orphans:
                session.run(
                    "MATCH (c:Chunk {chunk_id: $id}) DETACH DELETE c", id=chunk_id
                )
            # Facts: edges whose fact has no receipt are orphans (delete);
            # receipts whose fact lost its edge are gaps (clear receipt so
            # the census re-drives project_neo4j).
            result = session.run("MATCH ()-[r:REL]->() RETURN r.fact_id AS id")
            edge_ids = {r["id"] for r in result if r["id"]}
            fact_receipts = set(_receipt_kind_ids(conn, corpus, "neo4j", "fact"))
            for fact_id in edge_ids - fact_receipts:
                session.run(
                    "MATCH ()-[r:REL {fact_id: $id}]->() DELETE r", id=fact_id
                )
            missing_edges = fact_receipts - edge_ids
            if missing_edges:
                conn.execute(
                    """
                    UPDATE projection_receipts SET active = FALSE
                     WHERE projection = 'neo4j' AND entity_kind = 'fact'
                       AND entity_id = ANY(%s)
                    """,
                    (sorted(missing_edges),),
                )
    finally:
        driver.close()

    missing_in_store = receipts - store_ids
    if missing_in_store:
        _clear_receipts(conn, "neo4j", sorted(missing_in_store))

    orphan_receipts = _delete_orphan_receipts(conn, "neo4j")
    missing_receipts = desired - (receipts - missing_in_store)

    return {
        "missing_in_store": sorted(missing_in_store),
        "orphans_in_store": sorted(store_ids - receipts),
        "orphan_receipts": orphan_receipts,
        "missing_receipts": sorted(missing_receipts),
        "missing_facts": sorted(missing_edges) if missing_edges else [],
    }


def _receipt_kind_ids(conn: Connection, corpus: str, projection: str, kind: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT pr.entity_id FROM projection_receipts pr
         WHERE pr.projection = %s AND pr.entity_kind = %s AND pr.active
        """,
        (projection, kind),
    ).fetchall()
    return [r[0] for r in rows]


def process_event(conn: Connection, event: dict) -> None:
    run_id = event["run_id"]
    corpus = _run_identity(conn, run_id)
    if corpus is None:
        raise RuntimeError(f"run {run_id} not found")

    qdrant_report = reconcile_qdrant(conn, run_id, corpus)
    neo4j_report = reconcile_neo4j(conn, run_id, corpus)

    contract = stage_contract_hash(STAGE, {"contract_version": CONTRACT_VERSION})
    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract) as writer:
        writer.artifact({"qdrant": qdrant_report, "neo4j": neo4j_report})

        loss = (
            qdrant_report["missing_in_store"] + qdrant_report["orphans_in_store"]
            + neo4j_report["missing_in_store"] + neo4j_report["orphans_in_store"]
        )
        problem = (
            qdrant_report["missing_receipts"]
            + neo4j_report["missing_receipts"]
            + neo4j_report["missing_facts"]
        )
        if loss or problem:
            # Degraded (not failed): the census re-drives projectors and
            # verify re-runs until the stores and receipts converge.
            writer.run_status("degraded")
            log.warning("verification found projection gaps; run degraded", extra={
                "run_id": run_id, "stage": STAGE, "error_code": "projection_gaps",
            })
        else:
            writer.run_status("query_ready")


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 4) -> None:
    configure_logging("worker-verify")
    while True:
        try:
            with tx() as conn:
                events = claim_events(conn, [EVENT_TYPE], batch_size)
                if events:
                    for event in events:
                        try:
                            process_event(conn, event)
                            log.info("projections verified", extra={
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
            log.exception("verification failed", extra={"error_code": type(exc).__name__})
        time.sleep(poll_interval_s)


if __name__ == "__main__":
    run_forever()

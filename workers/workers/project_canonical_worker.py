"""project_canonical stage: project the C1 canonical registry into Neo4j
(C2, ADR 0009 consequence).

Consumes `project_canonical.v1` outbox events (scheduled by the census
after `canonicalize`). Neo4j RECEIVES Postgres identities only
(canonical_id, local entity ids, evidence ids) — it never invents one
and never decides identity.

Graph writes (existing conventions extended, no parallel ontology):

    (:CanonicalEntity {canonical_id, ...})
        -[:HAS_MEMBER {decision, confidence, basis,
                       canonicalizer_version, local_entity_id}]->
    (:Entity {entity_id})          # from project_neo4j
    (:Evidence {evidence_id})      # from project_neo4j
        -[:FROM_CHUNK]->           # added here: source-provenance link
    (:Chunk {chunk_id})            # from project_neo4j

Replay is a no-op (MERGE on unique keys); incremental corpus changes
converge (receipts supersede); Neo4j loss is reconstructed from
Postgres by the census re-arm. Local entity/fact/evidence rows are
never mutated; no new semantic facts are created.
"""
from __future__ import annotations

import json
import logging
import time

import psycopg
from psycopg import Connection

from polymath_shared.db import tx
from polymath_shared.logging import configure_logging
from polymath_shared.projection_contracts import (
    KIND_CANONICAL_ENTITY,
    KIND_CANONICAL_MEMBERSHIP,
    KIND_EVIDENCE_CHUNK,
    PROJECTION_NEO4J,
    receipt_hash,
)
from polymath_shared.receipts import (
    StageFailed,
    claim_events,
    record_projection_attempt,
    stage_contract_hash,
    stage_transaction,
)
from polymath_shared.stores import neo4j_driver

STAGE = "project_canonical"
EVENT_TYPE = "project_canonical.v1"
CONTRACT_VERSION = "1.0.0"

log = logging.getLogger("project-canonical")

CANONICAL_CONSTRAINTS = [
    "CREATE CONSTRAINT canonical_id_unique IF NOT EXISTS "
    "FOR (c:CanonicalEntity) REQUIRE c.canonical_id IS UNIQUE",
]

CANONICAL_QUERIES = {
    "node": """
    MERGE (c:CanonicalEntity {canonical_id: $canonical_id})
      ON CREATE SET c.canonical_type = $canonical_type,
                    c.normalized_name = $normalized_name,
                    c.corpus_id = $corpus_id,
                    c.canonicalizer_version = $canonicalizer_version
    """,
    "membership": """
    MERGE (c:CanonicalEntity {canonical_id: $canonical_id})
    MERGE (e:Entity {entity_id: $local_entity_id})
    MERGE (c)-[m:HAS_MEMBER {local_entity_id: $local_entity_id}]->(e)
      ON CREATE SET m.decision = $decision,
                    m.confidence = $confidence,
                    m.basis = $basis,
                    m.canonicalizer_version = $canonicalizer_version
    """,
    "evidence_chunk": """
    MERGE (ev:Evidence {evidence_id: $evidence_id})
    MERGE (ch:Chunk {chunk_id: $chunk_id})
    MERGE (ev)-[:FROM_CHUNK]->(ch)
    """,
}


def canonical_projection_plan(
    canonical_entities: list[dict],
    memberships: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Pure, deterministic projection plan (unit-testable): the exact
    node/edge parameter sets the graph writes use. Ordering is sorted;
    identical input yields an identical plan."""
    return {
        "nodes": sorted(
            canonical_entities,
            key=lambda r: (r.get("canonical_id") or "",),
        ),
        "memberships": sorted(
            memberships,
            key=lambda r: (r.get("canonical_id") or "", r.get("local_entity_id") or ""),
        ),
        "evidence_chunks": sorted(
            (
                {
                    "evidence_id": r.get("evidence_id"),
                    "chunk_id": r.get("chunk_id"),
                }
                for r in evidence_rows
                if r.get("evidence_id") and r.get("chunk_id")
            ),
            key=lambda r: (r["evidence_id"], r["chunk_id"]),
        ),
    }


def _corpus_canonical_rows(conn: Connection, corpus_id: str) -> tuple[list[dict], list[dict]]:
    nodes = conn.execute(
        """
        SELECT canonical_id, canonical_type, normalized_name, canonicalizer_version
          FROM canonical_entities
         WHERE corpus_id = %s
         ORDER BY canonical_id
        """,
        (corpus_id,),
    ).fetchall()
    memberships = conn.execute(
        """
        SELECT canonical_id, local_entity_id, decision, confidence, basis,
               canonicalizer_version
          FROM canonical_memberships
         WHERE corpus_id = %s
         ORDER BY local_entity_id
        """,
        (corpus_id,),
    ).fetchall()
    return (
        [{"canonical_id": r[0], "canonical_type": r[1], "normalized_name": r[2],
          "canonicalizer_version": r[3], "corpus_id": corpus_id} for r in nodes],
        [{"canonical_id": r[0], "local_entity_id": r[1], "decision": r[2],
          "confidence": r[3], "basis": r[4] or [], "canonicalizer_version": r[5]}
         for r in memberships],
    )


def _corpus_evidence_rows(conn: Connection, corpus_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT ev.evidence_id, ev.chunk_id
          FROM evidence ev
          JOIN documents d ON d.doc_id = ev.doc_id
         WHERE d.corpus_id = %s
         ORDER BY ev.evidence_id
        """,
        (corpus_id,),
    ).fetchall()
    return [{"evidence_id": r[0], "chunk_id": r[1]} for r in rows]


def _write_canonical_graph(driver, plan: dict) -> None:
    with driver.session() as session:
        for node in plan["nodes"]:
            session.run(CANONICAL_QUERIES["node"], **node)
        for membership in plan["memberships"]:
            session.run(
                CANONICAL_QUERIES["membership"],
                **{
                    "canonical_id": membership["canonical_id"],
                    "local_entity_id": membership["local_entity_id"],
                    "decision": membership["decision"],
                    "confidence": membership["confidence"],
                    "basis": membership["basis"],
                    "canonicalizer_version": membership["canonicalizer_version"],
                },
            )
        for link in plan["evidence_chunks"]:
            session.run(CANONICAL_QUERIES["evidence_chunk"], **link)


def _receipts(conn: Connection, plan: dict) -> None:
    for node in plan["nodes"]:
        record_projection_attempt(
            conn,
            projection=PROJECTION_NEO4J,
            entity_kind=KIND_CANONICAL_ENTITY,
            entity_id=node["canonical_id"],
            receipt_hash=receipt_hash(
                PROJECTION_NEO4J, KIND_CANONICAL_ENTITY,
                node["canonical_id"], CONTRACT_VERSION,
            ),
            contract=CONTRACT_VERSION,
        )
    for membership in plan["memberships"]:
        record_projection_attempt(
            conn,
            projection=PROJECTION_NEO4J,
            entity_kind=KIND_CANONICAL_MEMBERSHIP,
            entity_id=membership["local_entity_id"],
            receipt_hash=receipt_hash(
                PROJECTION_NEO4J, KIND_CANONICAL_MEMBERSHIP,
                membership["local_entity_id"], CONTRACT_VERSION,
            ),
            contract=CONTRACT_VERSION,
        )
    for link in plan["evidence_chunks"]:
        record_projection_attempt(
            conn,
            projection=PROJECTION_NEO4J,
            entity_kind=KIND_EVIDENCE_CHUNK,
            entity_id=link["evidence_id"],
            receipt_hash=receipt_hash(
                PROJECTION_NEO4J, KIND_EVIDENCE_CHUNK,
                link["evidence_id"], CONTRACT_VERSION,
            ),
            contract=CONTRACT_VERSION,
        )


def process_event(conn: Connection, event: dict) -> None:
    run_id = event["run_id"]
    row = conn.execute(
        "SELECT corpus_id FROM runs WHERE run_id = %s", (run_id,)
    ).fetchone()
    if row is None:
        raise StageFailed(run_id, STAGE)
    corpus_id = row[0]

    nodes, memberships = _corpus_canonical_rows(conn, corpus_id)
    evidence_rows = _corpus_evidence_rows(conn, corpus_id)
    plan = canonical_projection_plan(nodes, memberships, evidence_rows)

    contract = stage_contract_hash(STAGE, {
        "projection": PROJECTION_NEO4J,
        "contract_version": CONTRACT_VERSION,
    })

    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract) as writer:
        writer.artifact({
            "canonical_entities": len(plan["nodes"]),
            "memberships": len(plan["memberships"]),
            "evidence_chunks": len(plan["evidence_chunks"]),
        })

        driver = neo4j_driver()
        try:
            with driver.session() as session:
                for statement in CANONICAL_CONSTRAINTS:
                    session.run(statement)
            _write_canonical_graph(driver, plan)
        finally:
            driver.close()
        _receipts(conn, plan)
        writer.run_status("reconciling")


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 4) -> None:
    configure_logging("worker-project-canonical")
    while True:
        try:
            with tx() as conn:
                events = claim_events(conn, [EVENT_TYPE], batch_size)
                if events:
                    for event in events:
                        try:
                            process_event(conn, event)
                            log.info("canonical projection processed", extra={
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
            log.exception("canonical projection failed", extra={"error_code": type(exc).__name__})
        time.sleep(poll_interval_s)


if __name__ == "__main__":
    run_forever()

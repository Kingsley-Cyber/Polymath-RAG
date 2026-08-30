"""Neo4j projector: entities + facts + evidence -> constrained MERGE. A
durable projection stage.

Consumes `extracted.v1` outbox events. Neo4j RECEIVES the Postgres
identities (entity_id, fact_id, evidence_id); it never invents one.
Uniqueness constraints (stores/neo4j/constraints/0001_uniqueness.cypher)
make MERGE atomic and idempotent under parallelism (docx §17).

Receipts are the commit point: graph writes happen first, then the
Postgres projection receipt commits in the stage transaction. A crash
between the two leaves an orphan in Neo4j that VERIFY_PROJECTIONS
detects (acceptance test 7) — never silent acceptance.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import psycopg
from neo4j import GraphDatabase
from psycopg import Connection

from polymath_shared.db import tx
from polymath_shared.logging import configure_logging
from polymath_shared.neo4j_eligibility import entity_eligible_sql, fact_eligible_sql
from polymath_shared.projection_contracts import (
    KIND_ENTITY,
    KIND_EVIDENCE,
    KIND_FACT,
    NEO4J_CONSTRAINT_FILE,
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
from polymath_shared.settings import get_settings
from polymath_shared.stores import neo4j_driver

STAGE = "project_neo4j"
EVENT_TYPE = "project_neo4j.v1"
CONTRACT_VERSION = "1.0.0"

log = logging.getLogger("project-neo4j")

CONSTRAINTS = [
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
    "CREATE CONSTRAINT fact_id_unique IF NOT EXISTS FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
    "CREATE CONSTRAINT doc_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE",
]

PROJECTION_QUERIES = [
    # Document -> Chunk (children and parents)
    """
    MERGE (d:Document {doc_id: $doc_id})
    MERGE (c:Chunk {chunk_id: $chunk_id})
      ON CREATE SET c.tier = $tier, c.chunk_index = $chunk_index
    MERGE (d)-[:HAS_CHUNK]->(c)
    """,
    # Entity nodes
    """
    MERGE (e:Entity {entity_id: $entity_id})
      ON CREATE SET e.core_type = $core_type, e.surface = $surface
    """,
    # Fact traversal edges (Subject)-[:REL {fact_id}]->(Object): one edge
    # per fact (docx §18 — the traversal edge carries the fact id).
    """
    MERGE (s:Entity {entity_id: $subject_id})
    MERGE (o:Entity {entity_id: $object_id})
    MERGE (s)-[r:REL {fact_id: $fact_id}]->(o)
      ON CREATE SET r.predicate = $predicate
    """,
    # Fact -> Evidence provenance links
    """
    MERGE (f:Fact {fact_id: $fact_id})
    MERGE (e:Evidence {evidence_id: $evidence_id})
    MERGE (f)-[:SUPPORTED_BY]->(e)
    """,
]


def _driver():
    return neo4j_driver()


def _apply_constraints(driver) -> None:
    with driver.session() as session:
        for statement in CONSTRAINTS:
            session.run(statement)


def _graph_rows(conn: Connection, run_id: str) -> dict[str, list[dict]]:
    docs = conn.execute(
        """
        SELECT c.chunk_id, c.doc_id, c.tier, c.chunk_index
          FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s
         ORDER BY c.chunk_index
        """,
        (run_id,),
    ).fetchall()
    entities = conn.execute(
        """
        SELECT DISTINCT e.entity_id, e.core_type, e.normalized_surface
          FROM facts f
          JOIN evidence ev ON ev.fact_id = f.fact_id
          JOIN documents d ON d.doc_id = ev.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
          JOIN entities e ON e.entity_id = f.subject_id OR e.entity_id = f.object_id
         WHERE r.run_id = %s
           AND """ + entity_eligible_sql("e") + """
        """,
        (run_id,),
    ).fetchall()
    facts = conn.execute(
        """
        SELECT f.fact_id, f.predicate, f.subject_id, f.object_id, f.decision
          FROM facts f
          JOIN evidence e ON e.fact_id = f.fact_id
          JOIN documents d ON d.doc_id = e.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s
           AND """ + fact_eligible_sql("f") + """
        """,
        (run_id,),
    ).fetchall()
    evidence = conn.execute(
        """
        SELECT e.evidence_id, e.fact_id
          FROM evidence e
          JOIN documents d ON d.doc_id = e.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s
        """,
        (run_id,),
    ).fetchall()

    entity_rows = [{"entity_id": r[0], "core_type": r[1], "surface": r[2]}
                   for r in entities]
    fact_rows = [{"fact_id": r[0], "predicate": r[1], "subject_id": r[2],
                  "object_id": r[3]} for r in facts]

    # GRAPH-ENDPOINT-GUARD-V2 (2026-08-28). Defence in depth against the
    # measured bypass: the fact projection's
    #   MERGE (s:Entity {entity_id: $subject_id})
    # CREATES an endpoint node, so a fact that slipped the eligibility
    # filter silently manufactured an Entity the canonical entity policy
    # had refused. That is how pronoun nodes reached the live graph
    # (`they --uses--> ssh`) while 0 pronoun ENTITIES carried a receipt.
    #
    # A fact may project ONLY if both endpoints are in the eligible
    # entity set this same query produced. One authority, not two
    # competing policies.
    eligible = {e["entity_id"] for e in entity_rows}
    projectable, refused = [], []
    for f in fact_rows:
        if f["subject_id"] in eligible and f["object_id"] in eligible:
            projectable.append(f)
        else:
            refused.append(f["fact_id"])
    if refused:
        log.warning(
            "graph endpoint guard refused %d fact(s) whose endpoints are "
            "not eligible entities", len(refused),
            extra={"error_code": "graph_endpoint_ineligible",
                   "run_id": run_id})

    return {
        "docs": [{"doc_id": r[1], "chunk_id": r[0], "tier": r[2], "chunk_index": r[3]} for r in docs],
        "entities": entity_rows,
        "facts": projectable,
        "refused_facts": refused,
        "evidence": [{"evidence_id": r[0], "fact_id": r[1]} for r in evidence],
    }


def _already_current(conn: Connection,
                     wanted: list[tuple[str, str, str]]) -> set[tuple[str, str]]:
    """(entity_kind, entity_id) pairs whose ACTIVE receipt already matches
    the hash this projection would write (same contract as the qdrant
    lane's helper).

    The graph desired-state is corpus-wide by design, so every run's
    ticket re-derives the whole corpus. Correct for retrieval, quadratic
    for ingestion: on cysa-study-v1 (12 runs, one corpus) each reopened
    ticket rewrote every node and receipt — 286k receipt writes over
    14.6k distinct entities in one measured 15-minute window
    (STALL-2026-08-27). Receipt-current rows are skipped; a contract
    change, a receipt cleared by VERIFY, or new content all produce a
    different hash and are re-projected. Batched: the corpus-wide wanted
    set times three params per row would exceed the 65,535-parameter
    protocol limit in one VALUES join.
    """
    current: set[tuple[str, str]] = set()
    batch = 10_000
    for i in range(0, len(wanted), batch):
        part = wanted[i:i + batch]
        rows = conn.execute(
            """
            SELECT pr.entity_kind, pr.entity_id
              FROM projection_receipts pr
              JOIN (VALUES %s) AS w(kind, eid, rhash)
                ON pr.entity_kind = w.kind AND pr.entity_id = w.eid
               AND pr.receipt_hash = w.rhash
             WHERE pr.projection = %%s AND pr.active
            """ % ",".join(["(%s,%s,%s)"] * len(part)),
            [v for triple in part for v in triple] + [PROJECTION_NEO4J],
        ).fetchall()
        current.update((k, e) for k, e in rows)
    return current


def _skip_current_rows(conn: Connection,
                       rows: dict[str, list[dict]]) -> tuple[dict[str, list[dict]], int]:
    """Drop rows whose active receipt is already current; return the
    filtered row set and how many were skipped."""
    from polymath_shared.projection_contracts import KIND_CHUNK

    keyed = (
        ("docs", KIND_CHUNK, "chunk_id"),
        ("entities", KIND_ENTITY, "entity_id"),
        ("facts", KIND_FACT, "fact_id"),
        ("evidence", KIND_EVIDENCE, "evidence_id"),
    )
    wanted: list[tuple[str, str, str]] = []
    for rows_key, kind, id_key in keyed:
        for row in rows[rows_key]:
            source_id = row[id_key]
            wanted.append((kind, source_id,
                           receipt_hash(PROJECTION_NEO4J, kind, source_id,
                                        CONTRACT_VERSION)))
    current = _already_current(conn, wanted)
    if not current:
        return rows, 0
    filtered: dict[str, list[dict]] = {}
    skipped = 0
    for rows_key, kind, id_key in keyed:
        kept = [row for row in rows[rows_key]
                if (kind, row[id_key]) not in current]
        skipped += len(rows[rows_key]) - len(kept)
        filtered[rows_key] = kept
    return filtered, skipped


def _write_graph(driver, rows: dict[str, list[dict]]) -> None:
    with driver.session() as session:
        for row in rows["docs"]:
            session.run(PROJECTION_QUERIES[0], **row)
        for row in rows["entities"]:
            session.run(PROJECTION_QUERIES[1], **row)
        for row in rows["facts"]:
            session.run(PROJECTION_QUERIES[2], **row)
        for row in rows["evidence"]:
            session.run(PROJECTION_QUERIES[3], **row)


def _receipts(conn: Connection, rows: dict[str, list[dict]]) -> None:
    for kind, source_key in (
        (KIND_ENTITY, "entity_id"),
        (KIND_FACT, "fact_id"),
        (KIND_EVIDENCE, "evidence_id"),
    ):
        rows_key = {"entity_id": "entities", "fact_id": "facts", "evidence_id": "evidence"}[source_key]
        for row in rows[rows_key]:
            source_id = row[source_key]
            record_projection_attempt(
                conn,
                projection=PROJECTION_NEO4J,
                entity_kind=kind,
                entity_id=source_id,
                receipt_hash=receipt_hash(PROJECTION_NEO4J, kind, source_id, CONTRACT_VERSION),
                contract=CONTRACT_VERSION,
            )
    from polymath_shared.projection_contracts import KIND_CHUNK

    for row in rows["docs"]:
        record_projection_attempt(
            conn,
            projection=PROJECTION_NEO4J,
            entity_kind=KIND_CHUNK,
            entity_id=row["chunk_id"],
            receipt_hash=receipt_hash(PROJECTION_NEO4J, KIND_CHUNK, row["chunk_id"], CONTRACT_VERSION),
            contract=CONTRACT_VERSION,
        )


def process_event(conn: Connection, event: dict) -> None:
    run_id = event["run_id"]
    rows = _graph_rows(conn, run_id)
    rows, skipped_current = _skip_current_rows(conn, rows)

    contract = stage_contract_hash(STAGE, {
        "projection": PROJECTION_NEO4J,
        "contract_version": CONTRACT_VERSION,
    })

    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract) as writer:
        writer.artifact({
            "docs": len(rows["docs"]),
            "entities": len(rows["entities"]),
            "facts": len(rows["facts"]),
            "evidence": len(rows["evidence"]),
            "endpoint_refused_facts": len(rows.get("refused_facts") or []),
            "skipped_current": skipped_current,
        })

        if any(rows[k] for k in ("docs", "entities", "facts", "evidence")):
            driver = _driver()
            try:
                _apply_constraints(driver)
                _write_graph(driver, rows)
            finally:
                driver.close()
            _receipts(conn, rows)

        crash_after = int(os.environ.get("POLYMATH_TEST_CRASH_AFTER_GRAPH", "0"))
        if crash_after and len(rows["facts"]) >= crash_after:
            raise RuntimeError("fault injection: simulated crash after graph write")

        # No outbox event: the control census schedules the verify stage
        # from this receipt.
        writer.run_status("reconciling")


def run_forever(poll_interval_s: float = 2.0, batch_size: int = 1) -> None:
    """LONG-STAGE-LEASE-CORRECTNESS-V1: claim depth 1.

    A worker executes tickets serially, so claiming ahead bought nothing
    but made "held" differ from "being processed" -- and a stage running
    past claim_ttl_s let the reaper expire the queued ones. Parallelism
    comes from running several workers of a type.
    """
    from polymath_shared.worker_runtime import run_worker

    run_worker('project_neo4j', [EVENT_TYPE], process_event,
               poll_interval_s=poll_interval_s, batch_size=batch_size)

if __name__ == "__main__":
    run_forever()

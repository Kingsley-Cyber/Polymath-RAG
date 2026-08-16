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


ROUTING_KINDS = (
    "routing_document_summary",
    "routing_section_summary",
    "routing_child",
)


def _desired_routing_ids(conn: Connection, corpus: str) -> dict[str, set[str]]:
    """R1B reconciliation: authoritative routing representation ids per
    kind. Summaries come from retrieval_summaries (contract
    retrieval-summary-v2); children from the chunk rows."""
    doc_rows = conn.execute(
        """
        SELECT rs.summary_id FROM retrieval_summaries rs
         WHERE rs.corpus_id = %s AND rs.kind = 'document_retrieval_summary'
        """,
        (corpus,),
    ).fetchall()
    section_rows = conn.execute(
        """
        SELECT rs.summary_id FROM retrieval_summaries rs
         WHERE rs.corpus_id = %s AND rs.kind = 'section_retrieval_summary'
        """,
        (corpus,),
    ).fetchall()
    child_rows = conn.execute(
        """
        SELECT c.chunk_id FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
         WHERE d.corpus_id = %s AND c.tier = 'child'
        """,
        (corpus,),
    ).fetchall()
    return {
        "routing_document_summary": {r[0] for r in doc_rows},
        "routing_section_summary": {r[0] for r in section_rows},
        "routing_child": {r[0] for r in child_rows},
    }


def _routing_receipts(conn: Connection, corpus: str) -> dict[str, set[str]]:
    """Active qdrant routing receipts scoped to the corpus's
    authoritative entities (summary rows / child chunks)."""
    doc_rows = conn.execute(
        """
        SELECT pr.entity_id FROM projection_receipts pr
          JOIN retrieval_summaries rs ON rs.summary_id = pr.entity_id
         WHERE pr.projection = 'qdrant' AND pr.entity_kind = 'routing_document_summary'
           AND pr.active AND rs.corpus_id = %s
        """,
        (corpus,),
    ).fetchall()
    section_rows = conn.execute(
        """
        SELECT pr.entity_id FROM projection_receipts pr
          JOIN retrieval_summaries rs ON rs.summary_id = pr.entity_id
         WHERE pr.projection = 'qdrant' AND pr.entity_kind = 'routing_section_summary'
           AND pr.active AND rs.corpus_id = %s
        """,
        (corpus,),
    ).fetchall()
    child_rows = conn.execute(
        """
        SELECT pr.entity_id FROM projection_receipts pr
          JOIN chunks c ON c.chunk_id = pr.entity_id
          JOIN documents d ON d.doc_id = c.doc_id
         WHERE pr.projection = 'qdrant' AND pr.entity_kind = 'routing_child'
           AND pr.active AND d.corpus_id = %s
        """,
        (corpus,),
    ).fetchall()
    return {
        "routing_document_summary": {r[0] for r in doc_rows},
        "routing_section_summary": {r[0] for r in section_rows},
        "routing_child": {r[0] for r in child_rows},
    }


def reconcile_routing_qdrant(conn: Connection, corpus: str) -> dict:
    """R1B: neural routing projections cannot silently disappear.

    A query-ready corpus whose neural routing points are lost must be
    detected: receipts cleared for lost store artifacts (census
    re-drives the projector) and orphan store points (no receipt)
    removed. Same receipt-is-the-commit-point discipline as chunks."""
    from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT

    desired = _desired_routing_ids(conn, corpus)
    receipts = _routing_receipts(conn, corpus)

    client = _qdrant_client()
    try:
        collection = qdrant_collection_name(corpus, NEURAL_EMBED_CONTRACT.contract_id)
        store: dict[str, dict[str, set[str]]] = {k: set() for k in ROUTING_KINDS}
        try:
            points, _ = client.scroll(collection_name=collection, limit=100_000,
                                      with_payload=True, with_vectors=False)
            for p in points:
                if not p.payload:
                    continue
                kind = p.payload.get("representation_kind")
                if kind in store:
                    store[kind].add(str(p.payload.get("summary_id") or p.payload.get("chunk_id")))
        except Exception:
            store = {k: set() for k in ROUTING_KINDS}
    finally:
        client.close()

    report = {"missing_in_store": [], "orphans_in_store": [], "missing_receipts": []}
    for kind in ROUTING_KINDS:
        lost = receipts[kind] - store[kind]
        if lost:
            _clear_receipts(conn, "qdrant", sorted(lost))
            report["missing_in_store"].extend(sorted(lost))
        orphans = store[kind] - receipts[kind]
        report["orphans_in_store"].extend(sorted(orphans))
        missing = desired[kind] - (receipts[kind] - lost)
        report["missing_receipts"].extend(sorted(missing))
    return report


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

    # I3R-R5B orphan semantics: a store point is an orphan ONLY when no
    # authoritative source artifact desires it anymore. Points whose
    # chunk row still exists but whose receipt is temporarily absent
    # are IN-FLIGHT, not orphans — keep them; the missing-receipts gap
    # below re-drives the projector instead.
    orphans_in_store = store_ids - receipts
    true_orphans = orphans_in_store - desired
    in_flight = orphans_in_store & desired
    if true_orphans:
        client = _qdrant_client()
        try:
            points, _ = client.scroll(collection_name=collection, limit=100_000, with_vectors=False)
            orphan_point_ids = [
                p.id for p in points
                if p.payload and str(p.payload.get("chunk_id")) in true_orphans
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
        "orphans_in_store": sorted(true_orphans),
        "in_flight_points_kept": sorted(in_flight),
        "orphan_receipts": orphan_receipts,
        "missing_receipts": sorted(missing_receipts),
    }


def reconcile_neo4j(conn: Connection, run_id: str, corpus: str) -> dict:
    desired = set(_desired_chunk_ids(conn, run_id))
    receipts = set(_receipt_chunk_ids(conn, corpus, "neo4j"))
    # Neo4j is a SHARED graph: a chunk is an orphan only when it has no
    # active receipt ANYWHERE (bulk-acceptance-discovered defect — the
    # corpus-scoped receipt set made one corpus's verify delete other
    # corpora's legitimately receipted chunks).
    global_receipts = set(_receipt_kind_ids(conn, corpus, "neo4j", "chunk"))

    driver = _neo4j_driver()
    try:
        with driver.session() as session:
            result = session.run("MATCH (c:Chunk) RETURN c.chunk_id AS id")
            store_ids = {r["id"] for r in result}
            # I3R-R5B: a chunk node is an orphan ONLY when no authoritative
            # chunk row still exists anywhere; nodes with a live source row
            # but a missing receipt are in-flight and are kept.
            live_chunks = {r[0] for r in conn.execute(
                "SELECT chunk_id FROM chunks").fetchall()}
            orphans = store_ids - global_receipts - live_chunks
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
            # Eligibility boundary (D1): facts whose endpoints are
            # MENTION_ONLY are parked by design — their edges must not
            # survive and their receipts (if any) are erroneous. The
            # predicate is corpus-independent (admission classes live
            # on entity rows), so this never clears another corpus's
            # eligible receipts.
            ineligible_facts = _ineligible_fact_ids(conn)
            for fact_id in (edge_ids & ineligible_facts):
                session.run(
                    "MATCH ()-[r:REL {fact_id: $id}]->() DELETE r", id=fact_id
                )
            erroneous = fact_receipts & ineligible_facts
            if erroneous:
                conn.execute(
                    """
                    UPDATE projection_receipts SET active = FALSE
                     WHERE projection = 'neo4j' AND entity_kind = 'fact'
                       AND entity_id = ANY(%s)
                    """,
                    (sorted(erroneous),),
                )
                fact_receipts -= erroneous
            # I3R-R5A: an edge without a receipt is deleted ONLY when no
            # authoritative eligible fact still desires it. Edges whose
            # fact is ineligible were already deleted above (D1 boundary);
            # every remaining edge without a receipt is an IN-FLIGHT
            # projection (edge written, receipt pending) — keep it and
            # report it so the run re-enters the census and the projector
            # converges the bookkeeping.
            in_flight_edges = sorted(edge_ids - fact_receipts)
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
        "orphans_in_store": sorted(orphans),
        "orphan_receipts": orphan_receipts,
        "missing_receipts": sorted(missing_receipts),
        "missing_facts": sorted(missing_edges) if missing_edges else [],
        "in_flight_fact_edges_kept": in_flight_edges,
    }


def _ineligible_fact_ids(conn: Connection) -> set[str]:
    from polymath_shared.neo4j_eligibility import ineligible_fact_ids_sql

    rows = conn.execute(ineligible_fact_ids_sql()).fetchall()
    return {r[0] for r in rows}


def _receipt_kind_ids(conn: Connection, corpus: str, projection: str, kind: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT pr.entity_id FROM projection_receipts pr
         WHERE pr.projection = %s AND pr.entity_kind = %s AND pr.active
        """,
        (projection, kind),
    ).fetchall()
    return [r[0] for r in rows]


def _desired_canonical_ids(conn: Connection, corpus: str) -> list[str]:
    rows = conn.execute(
        "SELECT canonical_id FROM canonical_entities WHERE corpus_id = %s ORDER BY canonical_id",
        (corpus,),
    ).fetchall()
    return [r[0] for r in rows]


def _desired_membership_ids(conn: Connection, corpus: str) -> list[str]:
    rows = conn.execute(
        "SELECT local_entity_id FROM canonical_memberships WHERE corpus_id = %s ORDER BY local_entity_id",
        (corpus,),
    ).fetchall()
    return [r[0] for r in rows]


def _desired_evidence_ids(conn: Connection, corpus: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT ev.evidence_id FROM evidence ev
          JOIN documents d ON d.doc_id = ev.doc_id
         WHERE d.corpus_id = %s ORDER BY ev.evidence_id
        """,
        (corpus,),
    ).fetchall()
    return [r[0] for r in rows]


def _supersede_receipts(conn: Connection, entity_ids: list[str]) -> None:
    """Supersede active claims (history survives in projection_attempts)."""
    supersede_projection_claims(conn, projection="neo4j", entity_ids=sorted(set(entity_ids)))


def reconcile_canonical(conn: Connection, run_id: str, corpus: str) -> dict:
    """Reconcile the C2 canonical projection (nodes, memberships,
    evidence->chunk links) against Postgres and receipts.

    Store lost an artifact -> receipt cleared (census re-drives
    project_canonical). Store has an extra artifact (crash orphan) ->
    deleted. Receipt without a source row -> superseded."""
    from polymath_shared.projection_contracts import (
        KIND_CANONICAL_ENTITY,
        KIND_CANONICAL_MEMBERSHIP,
        KIND_EVIDENCE_CHUNK,
    )

    desired_nodes = set(_desired_canonical_ids(conn, corpus))
    desired_memberships = set(_desired_membership_ids(conn, corpus))
    desired_evidence = set(_desired_evidence_ids(conn, corpus))
    node_receipts = set(_receipt_kind_ids(conn, corpus, "neo4j", KIND_CANONICAL_ENTITY))
    membership_receipts = set(_receipt_kind_ids(conn, corpus, "neo4j", KIND_CANONICAL_MEMBERSHIP))
    evidence_receipts = set(_receipt_kind_ids(conn, corpus, "neo4j", KIND_EVIDENCE_CHUNK))

    # Receipts whose source rows no longer exist (orphan receipts) are
    # superseded FIRST so the store-orphan scan below sees the updated
    # active receipt set (an edge whose membership was deleted must be
    # recognized as a store orphan in this same run).
    orphan_node_receipts = node_receipts - {
        r[0] for r in conn.execute(
            "SELECT canonical_id FROM canonical_entities").fetchall()}
    orphan_membership_receipts = membership_receipts - {
        r[0] for r in conn.execute(
            "SELECT local_entity_id FROM canonical_memberships").fetchall()}
    orphan_evidence_receipts = evidence_receipts - {
        r[0] for r in conn.execute("SELECT evidence_id FROM evidence").fetchall()}
    superseded = set()
    if orphan_node_receipts:
        _supersede_receipts(conn, sorted(orphan_node_receipts))
        superseded |= orphan_node_receipts
    if orphan_membership_receipts:
        _supersede_receipts(conn, sorted(orphan_membership_receipts))
        superseded |= orphan_membership_receipts
    if orphan_evidence_receipts:
        _supersede_receipts(conn, sorted(orphan_evidence_receipts))
        superseded |= orphan_evidence_receipts

    active_nodes = node_receipts - superseded
    active_memberships = membership_receipts - superseded
    active_evidence = evidence_receipts - superseded

    driver = _neo4j_driver()
    try:
        with driver.session() as session:
            store_nodes = {r["id"] for r in session.run(
                "MATCH (c:CanonicalEntity) RETURN c.canonical_id AS id")}
            store_memberships = {r["id"] for r in session.run(
                "MATCH (:CanonicalEntity)-[m:HAS_MEMBER]->() RETURN m.local_entity_id AS id")}
            store_evidence_links = {r["id"] for r in session.run(
                "MATCH (ev:Evidence)-[:FROM_CHUNK]->() RETURN ev.evidence_id AS id")}

            orphan_nodes = store_nodes - active_nodes
            for canonical_id in orphan_nodes:
                session.run(
                    "MATCH (c:CanonicalEntity {canonical_id: $id}) DETACH DELETE c",
                    id=canonical_id,
                )
            orphan_memberships = store_memberships - active_memberships
            for local_entity_id in orphan_memberships:
                session.run(
                    "MATCH (:CanonicalEntity)-[m:HAS_MEMBER {local_entity_id: $id}]->() DELETE m",
                    id=local_entity_id,
                )
            orphan_links = store_evidence_links - active_evidence
            for evidence_id in orphan_links:
                session.run(
                    "MATCH (ev:Evidence {evidence_id: $id})-[r:FROM_CHUNK]->() DELETE r",
                    id=evidence_id,
                )
            missing_nodes = (active_nodes & desired_nodes) - store_nodes
            missing_memberships = (active_memberships & desired_memberships) - store_memberships
            missing_links = (active_evidence & desired_evidence) - store_evidence_links
    finally:
        driver.close()

    # Receipts exist but the store lost the artifact -> clear (re-drive).
    if missing_nodes:
        _supersede_receipts(conn, sorted(missing_nodes))
    if missing_memberships:
        _supersede_receipts(conn, sorted(missing_memberships))
    if missing_links:
        _supersede_receipts(conn, sorted(missing_links))

    cleared = superseded | missing_nodes | missing_memberships | missing_links

    missing_receipts = (
        (desired_nodes - (node_receipts - cleared))
        | (desired_memberships - (membership_receipts - cleared))
        | (desired_evidence - (evidence_receipts - cleared))
    )

    return {
        "missing_in_store": sorted(
            missing_nodes | missing_memberships | missing_links),
        "orphans_in_store": sorted(
            orphan_nodes | orphan_memberships | orphan_links),
        "orphan_receipts": sorted(superseded),
        "missing_receipts": sorted(missing_receipts),
    }


def process_event(conn: Connection, event: dict) -> None:
    run_id = event["run_id"]
    corpus = _run_identity(conn, run_id)
    if corpus is None:
        raise RuntimeError(f"run {run_id} not found")

    qdrant_report = reconcile_qdrant(conn, run_id, corpus)
    routing_report = reconcile_routing_qdrant(conn, corpus)
    neo4j_report = reconcile_neo4j(conn, run_id, corpus)
    canonical_report = reconcile_canonical(conn, run_id, corpus)

    contract = stage_contract_hash(STAGE, {"contract_version": CONTRACT_VERSION})
    with stage_transaction(conn, run_id=run_id, stage=STAGE, contract_hash=contract) as writer:
        writer.artifact({
            "qdrant": qdrant_report,
            "routing_qdrant": routing_report,
            "neo4j": neo4j_report,
            "canonical": canonical_report,
        })

        loss = (
            qdrant_report["missing_in_store"] + qdrant_report["orphans_in_store"]
            + routing_report["missing_in_store"]
            + neo4j_report["missing_in_store"] + neo4j_report["orphans_in_store"]
            + canonical_report["missing_in_store"] + canonical_report["orphans_in_store"]
        )
        problem = (
            qdrant_report["missing_receipts"]
            + routing_report["missing_receipts"]
            + neo4j_report["missing_receipts"]
            + neo4j_report["missing_facts"]
            + canonical_report["missing_receipts"]
            + canonical_report["orphan_receipts"]
            # I3R-R5: in-flight edges are kept, but they mean bookkeeping
            # has not converged yet — keep the run non-terminal so the
            # census re-drives the projector.
            + neo4j_report["in_flight_fact_edges_kept"]
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

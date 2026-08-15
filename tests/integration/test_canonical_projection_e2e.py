"""C2 acceptance: the canonical graph projection is complete,
traversable, replay-safe, incrementally convergent, and completely
rebuildable from Postgres — with orphan detection and census re-arm.

The live proof: CanonicalEntity -> member(Doc A) -> Fact A -> Evidence
A -> source A, and the same for Doc B; then destroy the canonical
projection in Neo4j and rebuild it exactly from Postgres.

Requires live stores: POLYMATH_INTEGRATION=1 (make db-up + db-migrate).
Seeded corpora use unique ids and clean up after themselves.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("POLYMATH_INTEGRATION") != "1",
        reason="set POLYMATH_INTEGRATION=1 with live stores (make db-up)",
    ),
]

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.identity import run_id  # noqa: E402
from polymath_shared.projection_contracts import (  # noqa: E402
    KIND_CANONICAL_ENTITY,
    KIND_CANONICAL_MEMBERSHIP,
    KIND_EVIDENCE_CHUNK,
)
from polymath_shared.stores import neo4j_driver  # noqa: E402
from workers.canonicalize_worker import process_event as _canonicalize  # noqa: E402
from workers.project_canonical_worker import process_event as _project  # noqa: E402
from workers.project_neo4j_worker import process_event as _project_neo4j  # noqa: E402
from workers.verify_worker import process_event as _verify  # noqa: E402

CORPUS = "c2_e2e"


def _cleanup() -> None:
    with tx() as conn:
        conn.execute(
            """
            DELETE FROM projection_receipts
             WHERE (entity_kind = 'canonical_entity' AND entity_id IN
                    (SELECT canonical_id FROM canonical_entities WHERE corpus_id = %s))
                OR (entity_kind = 'canonical_membership' AND entity_id IN
                    (SELECT local_entity_id FROM canonical_memberships WHERE corpus_id = %s))
                OR (entity_kind = 'evidence_chunk' AND entity_id LIKE 'ev_c2_%%')
            """,
            (CORPUS, CORPUS),
        )
        conn.execute("DELETE FROM canonicalization_decisions WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM canonical_memberships WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM canonical_entities WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM evidence WHERE fact_id LIKE 'fact_c2_%'")
        conn.execute("DELETE FROM facts WHERE fact_id LIKE 'fact_c2_%'")
        conn.execute("DELETE FROM entities WHERE entity_id LIKE 'ent_c2_%'")
        conn.execute("DELETE FROM chunks WHERE doc_id LIKE 'doc_c2_%'")
        conn.execute("DELETE FROM documents WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM runs WHERE corpus_id = %s", (CORPUS,))
    driver = neo4j_driver()
    try:
        with driver.session() as session:
            session.run(
                "MATCH (c:CanonicalEntity {corpus_id: $corpus}) DETACH DELETE c",
                corpus=CORPUS,
            ).consume()
            session.run(
                "MATCH (e:Entity) WHERE e.entity_id STARTS WITH 'ent_c2_' DETACH DELETE e"
            ).consume()
            session.run(
                "MATCH (ev:Evidence) WHERE ev.evidence_id STARTS WITH 'ev_c2_' DETACH DELETE ev"
            ).consume()
    finally:
        driver.close()


def _seed_doc(doc_id: str, source_name: str, chunk_id: str, text: str) -> None:
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO documents (doc_id, corpus_id, source_name, media_type,
                                   byte_length, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (doc_id) DO NOTHING
            """,
            (doc_id, CORPUS, source_name, "text/plain", len(text), f"hash-{doc_id}"),
        )
        conn.execute(
            """
            INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                text, summary, char_start, char_end)
            VALUES (%s, %s, NULL, 0, 'child', %s, '', 0, %s)
            ON CONFLICT (chunk_id) DO NOTHING
            """,
            (chunk_id, doc_id, text, len(text)),
        )


def _seed_entity(entity_id: str, core_type: str, surface: str) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s, %s, %s) "
            "ON CONFLICT (entity_id) DO NOTHING",
            (entity_id, core_type, surface),
        )


def _seed_fact(fact_id: str, predicate: str, subject_id: str, object_id: str,
               doc_id: str, chunk_id: str) -> None:
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO facts (fact_id, predicate, subject_id, object_id,
                               qualifiers, decision, rule_id, rule_version, provenance)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fact_id) DO NOTHING
            """,
            (fact_id, predicate, subject_id, object_id, "{}", "ACCEPT",
             "rule-1", "1.0.1", "{}"),
        )
        conn.execute(
            """
            INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id,
                                  span_offsets, rule_id, gliner_scores,
                                  extractor_version, rule_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (evidence_id) DO NOTHING
            """,
            (f"ev_c2_{fact_id}", fact_id, doc_id, chunk_id, "{}", "rule-1", "{}",
             "1.0", "1.0.1"),
        )


def _make_run() -> str:
    canonical = {
        "corpus_id": CORPUS,
        "source_name": f"{CORPUS}.txt",
        "media_type": "text/plain",
        "content_b64": "x",
        "config": {},
    }
    rid = run_id(CORPUS, canonical)
    with tx() as conn:
        conn.execute(
            "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, %s) "
            "ON CONFLICT (corpus_id) DO NOTHING",
            (CORPUS, "c2 e2e corpus", "c2-config"),
        )
        conn.execute(
            "INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s, %s, 'reconciling', %s) "
            "ON CONFLICT (run_id) DO NOTHING",
            (rid, CORPUS, json.dumps({"intake_payload": canonical})),
        )
    return rid


def _graph_state() -> dict:
    driver = neo4j_driver()
    try:
        with driver.session() as session:
            nodes = {r["id"]: r["props"] for r in session.run(
                "MATCH (c:CanonicalEntity {corpus_id: $corpus}) "
                "RETURN c.canonical_id AS id, properties(c) AS props",
                corpus=CORPUS)}
            memberships = {
                (r["canonical"], r["local"]): r["props"]
                for r in session.run(
                    "MATCH (c:CanonicalEntity {corpus_id: $corpus})-[m:HAS_MEMBER]->(e:Entity) "
                    "RETURN c.canonical_id AS canonical, e.entity_id AS local, properties(m) AS props",
                    corpus=CORPUS)}
            evidence_links = {
                r["evidence"]: r["chunk"] for r in session.run(
                    "MATCH (ev:Evidence)-[:FROM_CHUNK]->(ch:Chunk) "
                    "WHERE ev.evidence_id STARTS WITH 'ev_c2_' "
                    "RETURN ev.evidence_id AS evidence, ch.chunk_id AS chunk")}
    finally:
        driver.close()
    return {"nodes": nodes, "memberships": memberships, "evidence_links": evidence_links}


def _receipt_ids(kind: str) -> set[str]:
    with tx() as conn:
        rows = conn.execute(
            "SELECT entity_id FROM projection_receipts "
            "WHERE projection = 'neo4j' AND entity_kind = %s AND active",
            (kind,),
        ).fetchall()
    return {r[0] for r in rows}


def test_canonical_projection_e2e_full_lineage_and_rebuild() -> None:
    _cleanup()
    rid = _make_run()
    # Doc A: AcmeCorp founded by Alice. Doc B: same AcmeCorp (alias
    # member "ACME"), founded by Bob (CONFLICTING facts coexist).
    _seed_doc("doc_c2_a", "a.txt", "chunk_c2_a", "AcmeCorp was founded by AliceSmith.")
    _seed_doc("doc_c2_b", "b.txt", "chunk_c2_b", "ACME was founded by BobJones.")
    for eid, ctype, surface in [
        ("ent_c2_acme_a", "Organization", "AcmeCorp"),
        ("ent_c2_acme_b", "Organization", "ACME"),
        ("ent_c2_alice", "Person", "AliceSmith"),
        ("ent_c2_bob", "Person", "BobJones"),
    ]:
        _seed_entity(eid, ctype, surface)
    _seed_fact("fact_c2_a", "founded", "ent_c2_alice", "ent_c2_acme_a",
               "doc_c2_a", "chunk_c2_a")
    _seed_fact("fact_c2_b", "founded", "ent_c2_bob", "ent_c2_acme_b",
               "doc_c2_b", "chunk_c2_b")

    # Canonicalize with an explicit alias declaration. The base Neo4j
    # projection (Document/Chunk/Entity/Fact/Evidence + REL +
    # SUPPORTED_BY) runs first, as it does in production.
    with tx() as conn:
        conn.execute(
            "UPDATE corpora SET profile = %s WHERE corpus_id = %s",
            (json.dumps({"canonical_aliases": {"AcmeCorp": ["ACME"]}}), CORPUS),
        )
        _project_neo4j(conn, {"run_id": rid})
        _canonicalize(conn, {"run_id": rid})
        _project(conn, {"run_id": rid})

    # --- Graph completeness + lineage --------------------------------------
    with tx() as conn:
        canon_id = conn.execute(
            "SELECT canonical_id FROM canonical_memberships WHERE local_entity_id = %s",
            ("ent_c2_acme_a",),
        ).fetchone()[0]
    state = _graph_state()
    assert state["nodes"][canon_id]["normalized_name"] == "acmecorp"
    assert state["nodes"][canon_id]["canonicalizer_version"] == "1.0.0"

    memberships = state["memberships"]
    assert memberships[(canon_id, "ent_c2_acme_a")]["decision"] == "SAME_AS"
    alias = memberships[(canon_id, "ent_c2_acme_b")]
    assert alias["decision"] == "ALIAS_OF"
    assert alias["basis"] == ["explicit_source_alias"]
    assert alias["canonicalizer_version"] == "1.0.0"

    # Traversal: canonical -> member (doc A) -> fact -> evidence -> source;
    # same for doc B. Conflicting facts coexist as distinct REL edges.
    driver = neo4j_driver()
    try:
        with driver.session() as session:
            for entity, doc in (("ent_c2_acme_a", "doc_c2_a"), ("ent_c2_acme_b", "doc_c2_b")):
                rows = session.run(
                    """
                    MATCH (c:CanonicalEntity {canonical_id: $canon})
                          -[:HAS_MEMBER]->(e:Entity {entity_id: $entity})
                    MATCH (e)<-[r:REL]-(:Entity)
                    MATCH (f:Fact {fact_id: r.fact_id})
                          -[:SUPPORTED_BY]->(ev:Evidence)-[:FROM_CHUNK]->(ch:Chunk)
                    MATCH (d:Document {doc_id: $doc})-[:HAS_CHUNK]->(ch)
                    RETURN e.entity_id AS entity, f.fact_id AS fact,
                           ev.evidence_id AS evidence, ch.chunk_id AS chunk,
                           d.doc_id AS doc
                    """,
                    canon=canon_id, entity=entity, doc=doc,
                ).data()
                assert rows, f"lineage broken for {entity}"
                row = rows[0]
                assert row["doc"] == doc
                assert row["chunk"].startswith("chunk_c2_")
            rel_edges = session.run(
                "MATCH (:Entity)-[r:REL]->(:Entity) WHERE r.fact_id STARTS WITH 'fact_c2_' "
                "RETURN r.fact_id AS id").data()
            assert {r["id"] for r in rel_edges} == {"fact_c2_a", "fact_c2_b"}
    finally:
        driver.close()

    # --- Replay is a no-op -------------------------------------------------
    with tx() as conn:
        _project(conn, {"run_id": rid})
    assert _graph_state() == state

    # --- Incremental addition: only the expected delta ---------------------
    _seed_doc("doc_c2_c", "c.txt", "chunk_c2_c", "AcmeCorp ships tools.")
    _seed_entity("ent_c2_acme_c", "Organization", "AcmeCorp")
    _seed_fact("fact_c2_c", "ships", "ent_c2_acme_c", "ent_c2_bob",
               "doc_c2_c", "chunk_c2_c")
    with tx() as conn:
        _canonicalize(conn, {"run_id": rid})
        _project(conn, {"run_id": rid})
    state3 = _graph_state()
    assert set(state3["nodes"]) == set(state["nodes"])  # same canonical ids
    assert ("ent_c2_acme_c" in {
        m[1] for m in state3["memberships"]})
    assert state3["memberships"][(canon_id, "ent_c2_acme_c")]["decision"] == "SAME_AS"
    assert state3["evidence_links"]["ev_c2_fact_c2_c"] == "chunk_c2_c"

    # --- Removal removes/supersedes only affected state --------------------
    with tx() as conn:
        conn.execute("DELETE FROM evidence WHERE fact_id = 'fact_c2_c'")
        conn.execute("DELETE FROM facts WHERE fact_id = 'fact_c2_c'")
        conn.execute("DELETE FROM entities WHERE entity_id = 'ent_c2_acme_c'")
        conn.execute("DELETE FROM chunks WHERE doc_id = 'doc_c2_c'")
        conn.execute("DELETE FROM documents WHERE doc_id = 'doc_c2_c'")
        _canonicalize(conn, {"run_id": rid})
        _verify(conn, {"run_id": rid})
        _project(conn, {"run_id": rid})
    state4 = _graph_state()
    assert "ent_c2_acme_c" not in {m[1] for m in state4["memberships"]}
    assert "ev_c2_fact_c2_c" not in state4["evidence_links"]
    assert set(state4["nodes"]) == set(state["nodes"])
    assert set(state4["memberships"]) == set(state["memberships"])

    # --- Destructive reconstruction: destroy and rebuild EXACTLY -----------
    driver = neo4j_driver()
    try:
        with driver.session() as session:
            session.run(
                "MATCH (c:CanonicalEntity) WHERE c.canonical_id STARTS WITH 'cent_c2_' DETACH DELETE c")
            session.run(
                "MATCH (ev:Evidence)-[r:FROM_CHUNK]->(:Chunk) "
                "WHERE ev.evidence_id STARTS WITH 'ev_c2_' DELETE r")
    finally:
        driver.close()
    with tx() as conn:
        _verify(conn, {"run_id": rid})      # clears lost receipts (loud)
        _project(conn, {"run_id": rid})     # re-drives from Postgres
    rebuilt = _graph_state()
    assert rebuilt["nodes"] == state["nodes"]
    assert rebuilt["memberships"] == state["memberships"]
    assert rebuilt["evidence_links"] == state["evidence_links"]

    # --- Orphan detection: stray graph state is deleted by verify ----------
    driver = neo4j_driver()
    try:
        with driver.session() as session:
            session.run(
                "MERGE (c:CanonicalEntity {canonical_id: 'cent_c2_ghost', corpus_id: $corpus}) "
                "MERGE (e:Entity {entity_id: 'ent_c2_ghost'}) "
                "MERGE (c)-[m:HAS_MEMBER {local_entity_id: 'ent_c2_ghost'}]->(e)",
                corpus=CORPUS,
            ).consume()
    finally:
        driver.close()
    with tx() as conn:
        _verify(conn, {"run_id": rid})
    state5 = _graph_state()
    assert "cent_c2_ghost" not in state5["nodes"]
    assert "ent_c2_ghost" not in {m[1] for m in state5["memberships"]}

    # --- Census detects missing canonical projection state -----------------
    from control.control.census import compute_census
    from polymath_shared.identity import content_hash

    with tx() as conn:
        # Mark the full chain ok (the test drives workers directly, so
        # stage attempts are synthetic here) and supersede one
        # membership receipt -> census must re-arm project_canonical.
        for stage in ("intake", "extract", "profile_document", "project_qdrant",
                      "project_neo4j", "verify_projections", "canonicalize",
                      "project_canonical"):
            conn.execute(
                """
                INSERT INTO stage_attempts (run_id, stage, contract_hash, started_at, completed_at, outcome)
                VALUES (%s, %s, %s, now(), now(), 'ok')
                ON CONFLICT (run_id, stage, contract_hash) DO NOTHING
                """,
                (rid, stage, content_hash({"stage": stage, "test": "c2"})),
            )
        conn.execute(
            "UPDATE projection_receipts SET active = FALSE "
            "WHERE projection = 'neo4j' AND entity_kind = %s AND entity_id = %s",
            (KIND_CANONICAL_MEMBERSHIP, "ent_c2_acme_a"),
        )
    with tx() as conn:
        census = compute_census(conn, max_attempts=3)
        rearmed = {
            (g.stage, g.event_type) for g in census.gaps
            if g.run_id == rid and g.stage == "project_canonical"
        }
    assert rearmed == {("project_canonical", "project_canonical.v1")}

    # Receipts exist for nodes + memberships + evidence links. The
    # membership receipt for ent_c2_acme_a was deliberately superseded
    # in the census step above; the others stay active.
    assert canon_id in _receipt_ids(KIND_CANONICAL_ENTITY)
    assert "ent_c2_acme_b" in _receipt_ids(KIND_CANONICAL_MEMBERSHIP)
    assert "ev_c2_fact_c2_a" in _receipt_ids(KIND_EVIDENCE_CHUNK)
    _cleanup()


def test_verify_does_not_delete_other_corpora_chunks() -> None:
    """Bulk-acceptance-discovered defect: reconcile_neo4j deleted chunks
    receipted by OTHER corpora. A corpus's verify must only delete
    chunks with no receipt anywhere."""
    with tx() as conn:
        conn.execute(
            "INSERT INTO projection_receipts (projection, entity_kind, entity_id, receipt_hash, active) "
            "VALUES ('neo4j', 'chunk', 'chunk_foreign_survivor', 'hash', TRUE) "
            "ON CONFLICT (projection, entity_kind, entity_id) DO UPDATE SET active = TRUE"
        )
    driver = neo4j_driver()
    try:
        with driver.session() as s:
            s.run("MERGE (c:Chunk {chunk_id: 'chunk_foreign_survivor'})").consume()
    finally:
        driver.close()
    _cleanup()
    rid = _make_run()
    try:
        _seed_doc("doc_c2_x", "x.txt", "chunk_c2_x", "AcmeCorp ships tools.")
        _seed_entity("ent_c2_x", "Organization", "AcmeCorp")
        _seed_entity("ent_c2_x2", "Product", "tools")
        _seed_fact("fact_c2_x", "ships", "ent_c2_x", "ent_c2_x2", "doc_c2_x", "chunk_c2_x")
        with tx() as conn:
            _canonicalize(conn, {"run_id": rid})
            _project(conn, {"run_id": rid})
            _verify(conn, {"run_id": rid})
        driver = neo4j_driver()
        try:
            with driver.session() as s:
                survivor = s.run(
                    "MATCH (c:Chunk {chunk_id: 'chunk_foreign_survivor'}) RETURN c").single()
        finally:
            driver.close()
        assert survivor is not None, "foreign receipted chunk was deleted"
        with tx() as conn:
            conn.execute(
                "DELETE FROM projection_receipts WHERE entity_id = 'chunk_foreign_survivor'")
        driver = neo4j_driver()
        try:
            with driver.session() as s:
                s.run("MATCH (c:Chunk {chunk_id: 'chunk_foreign_survivor'}) DETACH DELETE c").consume()
        finally:
            driver.close()
    finally:
        _cleanup()

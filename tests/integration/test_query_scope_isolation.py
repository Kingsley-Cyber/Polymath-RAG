"""QUERY-SCOPE-V1 adversarial isolation: scope A must never surface
corpus B objects, even when B holds the apparently stronger match; and
missing scope is a typed 422 on EVERY public query route.

This is the regression for the 2026-08-26 SMART verification P0: the
missing-scope LEGACY path loaded 41,831 rows across 77 corpora and
disabled graph fact filtering.

Corpus B is seeded with a verbatim-match chunk AND a Neo4j-projected
fact whose entity surfaces match the query terms — so the ONLY thing
standing between B and the answer is corpus authorization. The B-scope
sanity leg proves the seeded knowledge IS retrievable, so an empty
A-scope result demonstrates isolation, not broken seeding.

Requires live stores: POLYMATH_INTEGRATION=1 (make db-up).
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

from fastapi.testclient import TestClient  # noqa: E402

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.stores import neo4j_driver  # noqa: E402
from orchestrator.orchestrator.main import app  # noqa: E402

CORPUS_A = "scope_iso_a"
CORPUS_B = "scope_iso_b"
QUERY = "who invented the zephyr engine"

ENT_VOSS = "ent_scopeiso_voss"
ENT_ZEPHYR = "ent_scopeiso_zephyr"
FACT_B = "fact_scopeiso_invented"

PROVENANCE = {
    "roleset": "create.01",
    "trigger_lemma": "invent",
    "trigger_surface": "invented",
    "orientation": "active",
    "weak": False,
}


def _cleanup() -> None:
    with tx() as conn:
        conn.execute("DELETE FROM evidence WHERE fact_id LIKE 'fact_scopeiso_%'")
        conn.execute("DELETE FROM facts WHERE fact_id LIKE 'fact_scopeiso_%'")
        conn.execute("DELETE FROM entities WHERE entity_id LIKE 'ent_scopeiso_%'")
        conn.execute("DELETE FROM chunks WHERE doc_id LIKE 'doc_scopeiso_%'")
        for corpus in (CORPUS_A, CORPUS_B):
            conn.execute("DELETE FROM documents WHERE corpus_id = %s", (corpus,))
            conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (corpus,))
    driver = neo4j_driver()
    try:
        with driver.session() as session:
            session.run(
                "MATCH (e:Entity) WHERE e.entity_id STARTS WITH 'ent_scopeiso_' DETACH DELETE e"
            )
    finally:
        driver.close()


def _seed() -> None:
    with tx() as conn:
        for corpus, name in ((CORPUS_A, "scope iso corpus A"),
                             (CORPUS_B, "scope iso corpus B")):
            conn.execute(
                "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, %s)",
                (corpus, name, "scope-iso-config"),
            )
        docs = [
            ("doc_scopeiso_a", CORPUS_A, "a.txt"),
            ("doc_scopeiso_b", CORPUS_B, "b.txt"),
        ]
        for doc_id, corpus, name in docs:
            conn.execute(
                """
                INSERT INTO documents (doc_id, corpus_id, source_name, media_type,
                                       byte_length, content_hash, retrieval_profile)
                VALUES (%s, %s, %s, 'text/plain', 60, %s, %s)
                """,
                (doc_id, corpus, name, f"hash-{doc_id}",
                 json.dumps({"semantic_summary": f"summary for {doc_id}"})),
            )
        chunks = [
            # A: weak, tangential match (no 'invented')
            ("chunk_scopeiso_a", "doc_scopeiso_a",
             "The zephyr engine was designed for quiet operation."),
            # B: the verbatim stronger match for the query
            ("chunk_scopeiso_b", "doc_scopeiso_b",
             "MarianaVoss invented the zephyr engine in 1998."),
        ]
        for cid, doc, text in chunks:
            conn.execute(
                """
                INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                    text, summary, char_start, char_end)
                VALUES (%s, %s, NULL, 0, 'child', %s, '', 0, %s)
                """,
                (cid, doc, text, len(text)),
            )
        for eid, ctype, surface in [
            (ENT_VOSS, "PERSON", "MarianaVoss"),
            (ENT_ZEPHYR, "ARTIFACT", "zephyr engine"),
        ]:
            conn.execute(
                "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s, %s, %s)",
                (eid, ctype, surface),
            )
        # The B fact: predicate on the HIGH_MEDIUM allowlist, entity
        # surfaces matching the query terms — graph-eligible in every
        # way EXCEPT corpus authorization under scope A.
        conn.execute(
            """
            INSERT INTO facts (fact_id, predicate, subject_id, object_id,
                               qualifiers, decision, rule_id, rule_version, provenance)
            VALUES (%s, 'created', %s, %s, '{}', 'ACCEPT', 'created-rule', '1.0.1', %s)
            """,
            (FACT_B, ENT_VOSS, ENT_ZEPHYR, json.dumps(PROVENANCE)),
        )
        conn.execute(
            """
            INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id,
                                  span_offsets, rule_id, gliner_scores,
                                  extractor_version, rule_version)
            VALUES (%s, %s, 'doc_scopeiso_b', 'chunk_scopeiso_b',
                    '{}', 'created-rule', '{}', '1.0', '1.0.1')
            """,
            (f"ev_{FACT_B}", FACT_B),
        )

    driver = neo4j_driver()
    try:
        with driver.session() as session:
            session.run(
                """
                MERGE (s:Entity {entity_id: $sid}) SET s.surface = 'marianavoss'
                MERGE (o:Entity {entity_id: $oid}) SET o.surface = 'zephyr engine'
                MERGE (s)-[r:REL {fact_id: $fid}]->(o)
                  SET r.predicate = 'created'
                """,
                sid=ENT_VOSS, oid=ENT_ZEPHYR, fid=FACT_B,
            )
    finally:
        driver.close()


def _assert_no_corpus_b(payload) -> None:
    blob = json.dumps(payload)
    assert "scopeiso_b" not in blob, f"corpus B object leaked: {blob[:400]}"
    assert CORPUS_B not in blob, f"corpus B id leaked: {blob[:400]}"
    assert FACT_B not in blob, f"corpus B fact leaked: {blob[:400]}"


def test_scope_a_never_surfaces_corpus_b() -> None:
    _cleanup()
    _seed()
    try:
        with TestClient(app) as client:
            # Sanity leg: under scope B the seeded knowledge IS
            # retrievable (the graph fact included). Without this, an
            # empty A result could mean broken seeding, not isolation.
            r_b = client.post("/retrieve", json={"query": QUERY, "corpus_id": CORPUS_B})
            assert r_b.status_code == 200, r_b.text
            body_b = r_b.json()
            assert any(f["fact_id"] == FACT_B for f in body_b["graph_facts"]), \
                "sanity leg failed: seeded graph fact not retrievable under its own scope"
            assert "chunk_scopeiso_b" in json.dumps(body_b)

            # Adversarial leg: scope A. Zero B documents, chunks,
            # facts, graph seeds, graph edges, evidence.
            for route, body in [
                ("/retrieve", {"query": QUERY, "corpus_id": CORPUS_A}),
                ("/evidence", {"query": QUERY, "corpus_id": CORPUS_A}),
                ("/chat", {"message": QUERY, "corpus_id": CORPUS_A}),
                ("/ask", {"question": QUERY, "corpus_id": CORPUS_A}),
            ]:
                resp = client.post(route, json=body)
                assert resp.status_code == 200, f"{route}: {resp.text[:300]}"
                _assert_no_corpus_b(resp.json())
    finally:
        _cleanup()


def test_missing_scope_fails_closed_on_every_route() -> None:
    _cleanup()
    _seed()
    try:
        with TestClient(app) as client:
            for route, body in [
                ("/retrieve", {"query": QUERY}),
                ("/evidence", {"query": QUERY}),
                ("/chat", {"message": QUERY}),
                ("/ask", {"question": QUERY}),
            ]:
                resp = client.post(route, json=body)
                assert resp.status_code == 422, f"{route}: {resp.status_code} {resp.text[:200]}"
                detail = resp.json()["detail"]
                assert detail["error_code"] == "QUERY_SCOPE_REQUIRED", f"{route}: {detail}"
    finally:
        _cleanup()


def test_single_corpus_modes_reject_wider_scope() -> None:
    """FAST/HYBRID/GRAPH are single-corpus engines: a wider resolved
    scope fails closed instead of silently narrowing or fanning out."""
    _cleanup()
    _seed()
    try:
        with TestClient(app) as client:
            for mode in ("FAST", "HYBRID", "GRAPH"):
                resp = client.post("/retrieve", json={
                    "query": QUERY,
                    "corpus_ids": [CORPUS_A, CORPUS_B],
                    "mode": mode,
                })
                assert resp.status_code == 422, f"{mode}: {resp.status_code} {resp.text[:200]}"
                assert resp.json()["detail"]["error_code"] == "mode_requires_single_corpus"
    finally:
        _cleanup()


def test_unknown_scope_targets_are_typed_404() -> None:
    with TestClient(app) as client:
        resp = client.post("/retrieve", json={
            "query": QUERY, "corpus_id": "no_such_corpus_xyz"})
        assert resp.status_code == 404
        assert resp.json()["detail"]["error_code"] == "QUERY_SCOPE_UNKNOWN"

        resp = client.post("/retrieve", json={
            "query": QUERY, "workspace": "no_such_workspace_xyz"})
        assert resp.status_code == 404
        assert resp.json()["detail"]["error_code"] == "QUERY_SCOPE_UNKNOWN"

"""CORPUS-MAP-PLANNING-V1 (SMART REQ-008): the stored corpus map must
ACTIVELY influence scoped retrieval navigation.

The proof is a behavioral delta on the same live route: a query whose
literal wording ("RAG") differs from the corpus vocabulary ("retrieval
augmented generation") finds nothing before the map/vocabulary rows
exist, and finds the supported concept after they exist — while every
returned object remains an authoritative stored row inside the
resolved scope, and a second out-of-scope corpus with an identical
vocabulary bridge contributes nothing.

Requires live stores: POLYMATH_INTEGRATION=1.
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
from orchestrator.orchestrator.main import app  # noqa: E402

CORPUS = "cmap_plan_v1"
CORPUS_B = "cmap_plan_v1_other"
QUERY = "explain the ideas behind RAG"  # literal wording ≠ corpus vocabulary


def _cleanup() -> None:
    with tx() as conn:
        for sql, args in [
            ("DELETE FROM concept_aliases WHERE concept_id LIKE %s", ("cfm_cmapplan%",)),
            ("DELETE FROM concept_support WHERE concept_id LIKE %s", ("cfm_cmapplan%",)),
            ("DELETE FROM concept_families WHERE corpus_id IN (%s, %s)", (CORPUS, CORPUS_B)),
            ("DELETE FROM concept_artifacts WHERE corpus_id IN (%s, %s)", (CORPUS, CORPUS_B)),
            ("DELETE FROM corpus_summaries WHERE corpus_id IN (%s, %s)", (CORPUS, CORPUS_B)),
            ("DELETE FROM documents WHERE corpus_id IN (%s, %s)", (CORPUS, CORPUS_B)),
            ("DELETE FROM corpora WHERE corpus_id IN (%s, %s)", (CORPUS, CORPUS_B)),
        ]:
            conn.execute(sql, args)


def _seed_knowledge() -> None:
    """The stored, supported knowledge — present in BOTH phases."""
    with tx() as conn:
        for corpus in (CORPUS, CORPUS_B):
            conn.execute(
                "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, %s)",
                (corpus, f"map planning fixture {corpus}", "cmap-config"))
            conn.execute(
                """INSERT INTO documents (doc_id, corpus_id, source_name, media_type,
                                          byte_length, content_hash)
                   VALUES (%s, %s, 'm.txt', 'text/plain', 10, %s)""",
                (f"doc_cmapplan_{corpus}", corpus, f"cmap-h-{corpus}"))
            conn.execute(
                """INSERT INTO concept_artifacts (concept_id, document_id, corpus_id,
                       name, description, domain, related_entities, source_sentence,
                       confidence, supporting_chunks, generated_by_bundle_hash)
                   VALUES (%s, %s, %s,
                           'retrieval augmented generation',
                           'a technique that grounds model outputs in retrieved documents',
                           'artificial_intelligence', '[]', 'seed sentence', 0.9,
                           %s, 'test-bundle')""",
                (f"cart_cmapplan_{corpus}", f"doc_cmapplan_{corpus}", corpus,
                 [f"chunk_cmapplan_{corpus}"]))


def _seed_map() -> None:
    """The corpus map + vocabulary bridge — phase 2 only."""
    with tx() as conn:
        for corpus in (CORPUS, CORPUS_B):
            conn.execute(
                """INSERT INTO corpus_summaries (summary_id, corpus_id, artifact_hash,
                       contract_version, created_by_worker, dominant_concepts,
                       document_clusters)
                   VALUES (%s, %s, 'h', 'v1', 'test',
                           %s::text[], %s)""",
                (f"csum_cmapplan_{corpus}", corpus,
                 ["retrieval augmented generation"],
                 json.dumps([{"label": "retrieval augmented generation cluster",
                              "document_summary_ids": [f"dsum_{corpus}"]}])))
            conn.execute(
                """INSERT INTO concept_families (concept_id, corpus_id, canonical_name,
                       artifact_hash, contract_version, created_by_worker)
                   VALUES (%s, %s, 'retrieval augmented generation', 'h', 'v1', 'test')""",
                (f"cfm_cmapplan_{corpus}", corpus))
            conn.execute(
                "INSERT INTO concept_aliases (concept_id, alias) VALUES (%s, 'RAG')",
                (f"cfm_cmapplan_{corpus}",))


def test_corpus_map_changes_candidate_neighborhood_within_scope() -> None:
    _cleanup()
    _seed_knowledge()
    try:
        with TestClient(app) as client:
            # Phase 1 — map absent: literal wording finds nothing.
            before = client.post("/ask", json={
                "question": QUERY, "corpus_id": CORPUS})
            assert before.status_code == 200, before.text
            b = before.json()
            assert b["map"]["consulted"] is False or not b["map"]["expansion_terms"]
            assert b["objects"]["concepts"] == [], (
                "fixture invalid: concept reachable without the map")

            # Phase 2 — map + vocabulary bridge present.
            _seed_map()
            after = client.post("/ask", json={
                "question": QUERY, "corpus_id": CORPUS})
            assert after.status_code == 200, after.text
            a = after.json()

            # the map was consulted and bridged RAG → the canonical name
            assert a["map"]["consulted"] is True
            assert any("retrieval augmented generation" == t.lower()
                       for t in a["map"]["expansion_terms"]), a["map"]
            assert any(n["source"] == "vocabulary_family"
                       for n in a["map"]["neighborhoods"])

            # the candidate neighborhood CHANGED: the supported stored
            # concept is now found —
            names = [c["name"] for c in a["objects"]["concepts"]]
            assert "retrieval augmented generation" in names

            # — and final evidence stays authoritative + scoped: the
            # object is the persisted row from THIS corpus only.
            for c in a["objects"]["concepts"]:
                assert c["corpus_id"] == CORPUS
            blob = json.dumps(a)
            assert CORPUS_B not in blob, "map expansion leaked scope"

            # planning trace carries provenance for the map contribution
            assert a["contracts"]["corpus_map_planning"] == \
                "corpus-map-planning-v1"
    finally:
        _cleanup()


def test_map_planner_is_scope_bounded() -> None:
    """The planner consults ONLY the resolved corpus set: corpus B's
    identical map rows produce no neighborhoods under scope A."""
    _cleanup()
    _seed_knowledge()
    _seed_map()
    try:
        from polymath_shared.corpus_map_planning import plan_with_corpus_map
        from polymath_shared.query_scope import resolve_query_scope

        with tx() as conn:
            scope = resolve_query_scope(conn, corpus_id=CORPUS)
            plan = plan_with_corpus_map(conn, scope, QUERY)
        assert plan["scope_corpus_ids"] == [CORPUS]
        touched = {n["corpus_id"] for n in plan["neighborhoods"]}
        assert touched <= {CORPUS}, touched
    finally:
        _cleanup()


def test_map_builder_now_receives_procedures() -> None:
    """REQ-007 companion: the production corpus-map builder call site
    passes persisted procedure artifacts into the accepted procedures
    input (source-level pin; the builder contract is unchanged)."""
    import inspect

    from polymath_shared import corpus_mapping

    src = inspect.getsource(corpus_mapping.run_corpus_mapping_ticket)
    assert "procedure_artifacts" in src
    assert "procedures=procedures" in src

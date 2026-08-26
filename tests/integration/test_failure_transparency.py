"""FAILURE-TRANSPARENCY-V1 + SEMANTIC-READINESS-V1 (SMART REQ-014/015).

1. A Neo4j backend failure is a typed 502 graph_backend_unavailable —
   never the same empty list as a valid zero-relationship result.
2. `semantic_completion` distinguishes ZERO LEGITIMATE YIELD
   (SEMANTIC_COMPLETE) from FAILED artifact execution
   (SEMANTIC_FAILED) from lanes still pending (SEMANTIC_INCOMPLETE) —
   so `query_ready` can never again overstate semantic completion.

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

from polymath_shared.db import tx  # noqa: E402

CORPUS = "ftrans_v1"


def _cleanup() -> None:
    with tx() as conn:
        for sql, args in [
            ("DELETE FROM evidence WHERE fact_id LIKE %s", ("fact_ftrans_%",)),
            ("DELETE FROM facts WHERE fact_id LIKE %s", ("fact_ftrans_%",)),
            ("DELETE FROM entities WHERE entity_id LIKE %s", ("ent_ftrans_%",)),
            ("DELETE FROM artifacts WHERE run_id LIKE %s", ("run_ftrans_%",)),
            ("DELETE FROM parent_summaries WHERE corpus_id = %s", (CORPUS,)),
            ("DELETE FROM document_summaries WHERE corpus_id = %s", (CORPUS,)),
            ("DELETE FROM corpus_summaries WHERE corpus_id = %s", (CORPUS,)),
            ("DELETE FROM chunks WHERE doc_id LIKE %s", ("doc_ftrans_%",)),
            ("DELETE FROM documents WHERE corpus_id = %s", (CORPUS,)),
            ("DELETE FROM runs WHERE corpus_id = %s", (CORPUS,)),
            ("DELETE FROM corpora WHERE corpus_id = %s", (CORPUS,)),
        ]:
            conn.execute(sql, args)


def _seed_base() -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, %s)",
            (CORPUS, "failure transparency fixture", "ftrans-config"))
        conn.execute(
            "INSERT INTO runs (run_id, corpus_id, status) VALUES ('run_ftrans_1', %s, 'query_ready')",
            (CORPUS,))
        conn.execute(
            """INSERT INTO documents (doc_id, corpus_id, source_name, media_type,
                                      byte_length, content_hash)
               VALUES ('doc_ftrans_1', %s, 'f.txt', 'text/plain', 10, 'ftrans-h1')""",
            (CORPUS,))
        conn.execute(
            """INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                   text, summary, char_start, char_end)
               VALUES ('chunk_ftrans_1', 'doc_ftrans_1', NULL, 0, 'child',
                       'ZephyrLabs created the quiet engine.', '', 0, 36)""")


def _complete_summaries() -> None:
    with tx() as conn:
        conn.execute(
            """INSERT INTO parent_summaries (summary_id, parent_id, corpus_id,
                   artifact_hash, contract_version, created_by_worker, summary)
               VALUES ('psum_ftrans_1', 'chunk_ftrans_1', %s, 'h', 'v1', 'test',
                       'a parent summary')""", (CORPUS,))
        conn.execute(
            """INSERT INTO document_summaries (summary_id, document_id, corpus_id,
                   artifact_hash, contract_version, created_by_worker, summary)
               VALUES ('dsum_ftrans_1', 'doc_ftrans_1', %s, 'h', 'v1', 'test',
                       'a document summary')""", (CORPUS,))
        conn.execute(
            """INSERT INTO corpus_summaries (summary_id, corpus_id, artifact_hash,
                   contract_version, created_by_worker)
               VALUES ('csum_ftrans_1', %s, 'h', 'v1', 'test')""", (CORPUS,))


def test_semantic_completion_zero_yield_is_complete():
    """Runs converged, summaries + map exist, zero facts/procedures/
    concepts: legitimate zero yield → SEMANTIC_COMPLETE."""
    _cleanup()
    _seed_base()
    _complete_summaries()
    try:
        from polymath_shared.semantic_readiness import semantic_completion

        with tx() as conn:
            verdict = semantic_completion(conn, CORPUS)
        assert verdict["verdict"] == "SEMANTIC_COMPLETE", verdict
        assert verdict["counts"]["procedures"] == 0
        assert verdict["counts"]["concepts"] == 0
        assert verdict["zero_yield_is_completion"] is True
    finally:
        _cleanup()


def test_semantic_completion_artifact_failure_is_failed():
    """The extract stage records swallowed artifact exceptions durably
    (payload key artifacts_error); the verdict must surface them as
    SEMANTIC_FAILED — never as zero yield."""
    _cleanup()
    _seed_base()
    _complete_summaries()
    try:
        with tx() as conn:
            conn.execute(
                """INSERT INTO artifacts (artifact_id, run_id, stage,
                       contract_hash, payload)
                   VALUES ('art_ftrans_fail', 'run_ftrans_1', 'extract', 'ch',
                           %s)""",
                (json.dumps({"artifacts_error":
                             "ValueError: injected artifact failure"}),))
        from polymath_shared.semantic_readiness import semantic_completion

        with tx() as conn:
            verdict = semantic_completion(conn, CORPUS)
        assert verdict["verdict"] == "SEMANTIC_FAILED", verdict
        assert verdict["artifact_lane_failures"] == [{
            "run_id": "run_ftrans_1",
            "error": "ValueError: injected artifact failure"}]
    finally:
        _cleanup()


def test_semantic_completion_missing_layers_is_incomplete():
    _cleanup()
    _seed_base()  # no summaries, no corpus map
    try:
        from polymath_shared.semantic_readiness import semantic_completion

        with tx() as conn:
            verdict = semantic_completion(conn, CORPUS)
        assert verdict["verdict"] == "SEMANTIC_INCOMPLETE", verdict
        assert "no_corpus_map" in verdict["pending"]
    finally:
        _cleanup()


def test_cross_corpus_content_collision_refuses_loudly():
    """doc_id is content-addressed globally; a document has exactly one
    corpus. Identical content ingested into a DIFFERENT corpus must be
    a typed loud refusal — never ON CONFLICT DO NOTHING minting a
    query_ready run over an empty corpus (measured 2026-08-26)."""
    import base64
    import sys as _sys
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parents[2]
    for extra in (root / "workers", root / "shared"):
        if str(extra) not in _sys.path:
            _sys.path.insert(0, str(extra))

    from polymath_shared.identity import document_id, normalize_document_bytes
    from polymath_shared.receipts import StageFailed
    from workers.intake_worker import process_event

    content = b"ZephyrLabs created the quiet engine for collision tests."
    normalized = normalize_document_bytes(
        content, strip_bom=True, normalize_crlf=True)
    doc_id = document_id(normalized)

    _cleanup()
    with tx() as conn:
        conn.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
        conn.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))
        conn.execute(
            "DELETE FROM corpora WHERE corpus_id IN ('ftrans_owner','ftrans_thief')")
        conn.execute("DELETE FROM runs WHERE corpus_id IN ('ftrans_owner','ftrans_thief')")
        conn.execute(
            "INSERT INTO corpora (corpus_id, name, config_hash) VALUES "
            "('ftrans_owner', 'o', 'c'), ('ftrans_thief', 't', 'c')")
        conn.execute(
            "INSERT INTO runs (run_id, corpus_id, status) VALUES "
            "('run_ftrans_own', 'ftrans_owner', 'intake'), "
            "('run_ftrans_thief', 'ftrans_thief', 'intake')")

    def _event(run_id, corpus):
        return {"run_id": run_id, "payload": {
            "corpus_id": corpus, "source_name": "c.md",
            "media_type": "text/markdown",
            "content_b64": base64.b64encode(content).decode()}}

    try:
        with tx() as conn:
            process_event(conn, _event("run_ftrans_own", "ftrans_owner"))
        with tx() as conn:
            owner = conn.execute(
                "SELECT corpus_id FROM documents WHERE doc_id = %s",
                (doc_id,)).fetchone()
        assert owner == ("ftrans_owner",)

        with pytest.raises(StageFailed):
            with tx() as conn:
                process_event(conn, _event("run_ftrans_thief", "ftrans_thief"))
        with tx() as conn:
            # ownership unchanged; the refusal is durable in the attempt
            owner = conn.execute(
                "SELECT corpus_id FROM documents WHERE doc_id = %s",
                (doc_id,)).fetchone()
            err = conn.execute(
                "SELECT error FROM stage_attempts WHERE run_id='run_ftrans_thief' "
                "AND stage='intake'").fetchone()
        assert owner == ("ftrans_owner",)
        assert err and "CROSS_CORPUS_CONTENT_COLLISION" in (err[0] or "")
    finally:
        with tx() as conn:
            conn.execute("DELETE FROM artifacts WHERE run_id LIKE %s", ("run_ftrans_%",))
            conn.execute("DELETE FROM receipts WHERE run_id LIKE %s", ("run_ftrans_%",))
            conn.execute("DELETE FROM stage_attempts WHERE run_id LIKE %s", ("run_ftrans_%",))
            conn.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
            conn.execute("DELETE FROM document_layout WHERE doc_id = %s", (doc_id,))
            conn.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))
            conn.execute("DELETE FROM outbox_events WHERE run_id LIKE %s", ("run_ftrans_%",))
            conn.execute("DELETE FROM runs WHERE corpus_id IN ('ftrans_owner','ftrans_thief')")
            conn.execute("DELETE FROM corpora WHERE corpus_id IN ('ftrans_owner','ftrans_thief')")


def test_graph_backend_failure_is_typed_not_empty(monkeypatch):
    """Injected Neo4j failure while seeds exist: the expansion raises
    the typed GraphBackendUnavailable and the route translator turns
    it into 502 graph_backend_unavailable. A valid zero result stays []
    (proven by the isolation suite's A-scope leg)."""
    _cleanup()
    _seed_base()
    try:
        with tx() as conn:
            conn.execute(
                """INSERT INTO entities (entity_id, core_type, normalized_surface)
                   VALUES ('ent_ftrans_z', 'ORGANIZATION', 'ZephyrLabs')""")
            conn.execute(
                """INSERT INTO facts (fact_id, predicate, subject_id, object_id,
                       qualifiers, decision, rule_id, rule_version, provenance)
                   VALUES ('fact_ftrans_1', 'created', 'ent_ftrans_z',
                           'ent_ftrans_z', '{}', 'ACCEPT', 'r', '1', '{}')""")
            conn.execute(
                """INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id,
                       span_offsets, rule_id, gliner_scores, extractor_version,
                       rule_version)
                   VALUES ('ev_ftrans_1', 'fact_ftrans_1', 'doc_ftrans_1',
                           'chunk_ftrans_1', '{}', 'r', '{}', '1', '1')""")

        import polymath_shared.stores as stores
        from orchestrator.orchestrator.api import retrieve as retrieve_mod

        class _ExplodingDriver:
            def session(self):
                raise RuntimeError("injected neo4j outage")

            def close(self):
                pass

        monkeypatch.setattr(stores, "neo4j_driver",
                            lambda: _ExplodingDriver())

        with pytest.raises(stores.GraphBackendUnavailable):
            retrieve_mod._neo4j_expand(
                ["zephyrlabs"], corpus_ids=[CORPUS],
                preferred_chunk_ids=["chunk_ftrans_1"])

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as e:
            retrieve_mod.graph_expand_or_502(
                ["zephyrlabs"], [CORPUS], ["chunk_ftrans_1"])
        assert e.value.status_code == 502
        assert e.value.detail["error_code"] == "graph_backend_unavailable"
    finally:
        _cleanup()

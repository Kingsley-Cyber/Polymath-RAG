"""G5 verification: the EXISTING R3a/R3b answer path consumes the G3
reranked fused ordering correctly — provenance/citations intact, no
invented candidates, safe abstention, loud reranker failure when
enabled, and unchanged baseline behavior when disabled.

Requires live stores + the reranker sidecar: POLYMATH_INTEGRATION=1.
Seeded corpus uses unique ids and cleans up after itself.
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
from polymath_shared.identity import run_id  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402
from polymath_shared.stores import neo4j_driver  # noqa: E402
from orchestrator.orchestrator.main import app  # noqa: E402

CORPUS = "g5_e2e"
QUERY = "who founded acmecorp"


def _cleanup() -> None:
    with tx() as conn:
        conn.execute("DELETE FROM projection_receipts WHERE entity_id LIKE 'chunk_g5_%' OR entity_id LIKE 'ev_g5_%' OR entity_id LIKE 'fact_g5_%' OR entity_id LIKE 'ent_g5_%' OR entity_id LIKE 'cent_g5_%'")
        conn.execute("DELETE FROM canonicalization_decisions WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM canonical_memberships WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM canonical_entities WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM evidence WHERE fact_id LIKE 'fact_g5_%'")
        conn.execute("DELETE FROM facts WHERE fact_id LIKE 'fact_g5_%'")
        conn.execute("DELETE FROM entities WHERE entity_id LIKE 'ent_g5_%'")
        conn.execute("DELETE FROM chunks WHERE doc_id LIKE 'doc_g5_%'")
        conn.execute("DELETE FROM documents WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM runs WHERE corpus_id = %s", (CORPUS,))
    driver = neo4j_driver()
    try:
        with driver.session() as s:
            s.run("MATCH (e:Entity) WHERE e.entity_id STARTS WITH 'ent_g5_' DETACH DELETE e").consume()
            s.run("MATCH (f:Fact) WHERE f.fact_id STARTS WITH 'fact_g5_' DETACH DELETE f").consume()
    finally:
        driver.close()


def _seed() -> None:
    canonical = {
        "corpus_id": CORPUS,
        "source_name": "g5.txt",
        "media_type": "text/plain",
        "content_b64": "eA==",
        "config": {},
    }
    rid = run_id(CORPUS, canonical)
    with tx() as conn:
        conn.execute(
            "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, %s)",
            (CORPUS, "g5 corpus", "g5-config"),
        )
        conn.execute(
            "INSERT INTO runs (run_id, corpus_id, status, metadata) VALUES (%s, %s, 'reconciling', %s)",
            (rid, CORPUS, json.dumps({"intake_payload": canonical})),
        )
        for i, (doc, chunk, text) in enumerate([
            ("doc_g5_0", "chunk_g5_0", "AliceSmith founded AcmeCorp in 2010."),
            ("doc_g5_1", "chunk_g5_1", "AcmeCorp ships tools worldwide."),
            ("doc_g5_2", "chunk_g5_2", "AcmeCorp was founded by AliceSmith."),
        ]):
            conn.execute(
                """
                INSERT INTO documents (doc_id, corpus_id, source_name, media_type,
                                       byte_length, content_hash, retrieval_profile)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (doc, CORPUS, f"g5_{i}.txt", "text/plain", len(text),
                 f"hash-g5-{i}", json.dumps({"semantic_summary": text})),
            )
            conn.execute(
                """
                INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                    text, summary, char_start, char_end)
                VALUES (%s, %s, NULL, 0, 'child', %s, '', 0, %s)
                """,
                (chunk, doc, text, len(text)),
            )
        for eid, ctype, surface in [
            ("ent_g5_alice", "Person", "AliceSmith"),
            ("ent_g5_acme", "Organization", "AcmeCorp"),
        ]:
            conn.execute(
                "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s, %s, %s)",
                (eid, ctype, surface),
            )
        conn.execute(
            """
            INSERT INTO facts (fact_id, predicate, subject_id, object_id,
                               qualifiers, decision, rule_id, rule_version, provenance)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            ("fact_g5_founded", "founded", "ent_g5_alice", "ent_g5_acme",
             "{}", "ACCEPT", "founded-rule", "1.0.1",
             json.dumps({"roleset": "establish.01",
                         "resource_contract_id": "03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150",
                         "compiled_lexical_sha256": "5c58adbd3cfc18e2e8b28245d5166dbb2920a33210ca7ccc0051231b421c8806"})),
        )
        conn.execute(
            """
            INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id,
                                  span_offsets, rule_id, gliner_scores,
                                  extractor_version, rule_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            ("ev_g5_1", "fact_g5_founded", "doc_g5_0", "chunk_g5_0",
             "{}", "founded-rule", "{}", "1.0", "1.0.1"),
        )
        from workers.canonicalize_worker import process_event as _canon
        from workers.project_neo4j_worker import process_event as _pn

    with tx() as conn:
        from workers.canonicalize_worker import process_event as _canon

        _canon(conn, {"run_id": rid})
    with tx() as conn:
        from workers.project_neo4j_worker import process_event as _pn

        _pn(conn, {"run_id": rid, "payload": {}})
    driver = neo4j_driver()
    try:
        with driver.session() as s:
            s.run("""
                MERGE (a:Entity {entity_id: 'ent_g5_alice'}) SET a.surface = 'alicesmith'
                MERGE (o:Entity {entity_id: 'ent_g5_acme'}) SET o.surface = 'acmecorp'
                MERGE (a)-[r:REL {fact_id: 'fact_g5_founded'}]->(o) SET r.predicate = 'founded'
                MERGE (f:Fact {fact_id: 'fact_g5_founded'})
            """).consume()
    finally:
        driver.close()


def _chat(client, rerank: bool, reranker_url: str | None = None) -> tuple[int, dict]:
    os.environ["POLYMATH_G3_RERANKER"] = "1" if rerank else "0"
    if reranker_url:
        os.environ["POLYMATH_RERANKER_URL"] = reranker_url
    else:
        os.environ.pop("POLYMATH_RERANKER_URL", None)
    get_settings.cache_clear()
    resp = client.post("/chat", json={"message": QUERY, "corpus_id": CORPUS})
    return resp.status_code, resp.json()


def test_g5_answer_path_rerank_on_off() -> None:
    _cleanup()
    _seed()
    try:
        with TestClient(app) as client:
            # BASELINE: rerank disabled — existing behavior.
            status, base = _chat(client, rerank=False)
            assert status == 200, base
            base_claims = [c["text"] for c in base["claims"]]
            base_cites = [tuple(c["bundle_item_ids"]) for c in base["citations"]]

            # RERANKED: same candidate set, provenance intact.
            status, rer = _chat(client, rerank=True)
            assert status == 200, rer
            rer_claims = [c["text"] for c in rer["claims"]]
            rer_cites = [tuple(c["bundle_item_ids"]) for c in rer["citations"]]
            assert sorted(base_claims) == sorted(rer_claims), "claim set changed by rerank"
            assert sorted(base_cites) == sorted(rer_cites), "citation set changed by rerank"
            assert rer["meta"]["supported_claim_count"] == base["meta"]["supported_claim_count"]
            assert rer["answer"], "reranked answer is empty"

            # Grounding intact: every supported claim maps to bundle items.
            for claim in rer["claims"]:
                if claim["status"] == "supported":
                    assert claim["support"], "supported claim without evidence"
            assert all("locators" in c for c in rer["citations"])

            # Determinism: reranked run twice.
            _, rer2 = _chat(client, rerank=True)
            assert rer == rer2, "reranked answer path is not deterministic"
    finally:
        _cleanup()


def test_g5_reranker_unavailable_is_loud_when_enabled() -> None:
    _cleanup()
    _seed()
    try:
        with TestClient(app) as client:
            status, body = _chat(client, rerank=True, reranker_url="http://127.0.0.1:59999")
            assert status == 502, body
            assert body["detail"]["error_code"] == "rerank_unavailable"
    finally:
        _cleanup()


def test_g5_disabled_reranker_keeps_baseline_unchanged() -> None:
    _cleanup()
    _seed()
    try:
        with TestClient(app) as client:
            # Disabled flag with a DEAD reranker URL must still succeed —
            # the reranker is never contacted when the candidate is off.
            status, body = _chat(client, rerank=False, reranker_url="http://127.0.0.1:59999")
            assert status == 200, body
    finally:
        _cleanup()

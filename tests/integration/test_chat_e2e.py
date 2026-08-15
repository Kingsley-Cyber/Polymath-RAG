"""R3b acceptance: query -> /evidence (R3a bundle) -> synthesis ->
/chat -> cited grounded answer, over live stores.

The E2E proves the /chat response is grounded in the R3a bundle: every
supported claim maps to a bundle item, every citation resolves to a
bundle item and retains the source locator.

Requires live stores: POLYMATH_INTEGRATION=1 (make db-up). Seeded
corpora use unique ids and clean up after themselves.
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

from polymath_shared.answer_synthesis import bundle_item_id  # noqa: E402
from polymath_shared.db import tx  # noqa: E402
from polymath_shared.stores import neo4j_driver  # noqa: E402
from orchestrator.orchestrator.main import app  # noqa: E402

CORPUS = "r3b_e2e"
ENT_ALICE = "ent_r3b_alice"
ENT_ACME = "ent_r3b_acme"
ENT_BOB = "ent_r3b_bob"
FACT_FOUNDED_A = "fact_r3b_founded_a"
FACT_FOUNDED_B = "fact_r3b_founded_b"

PROVENANCE = {
    "roleset": "establish.01",
    "trigger_lemma": "found",
    "trigger_surface": "founded",
    "verbnet_classes": ["establish-55.5"],
    "framenet_frames": ["Establishment"],
    "semlink_resolved": True,
    "resource_contract_id": "03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150",
    "compiled_lexical_sha256": "5c58adbd3cfc18e2e8b28245d5166dbb2920a33210ca7ccc0051231b421c8806",
    "orientation": "active",
    "weak": False,
}


def _cleanup() -> None:
    with tx() as conn:
        conn.execute("DELETE FROM evidence WHERE fact_id LIKE 'fact_r3b_%'")
        conn.execute("DELETE FROM facts WHERE fact_id LIKE 'fact_r3b_%'")
        conn.execute("DELETE FROM entities WHERE entity_id LIKE 'ent_r3b_%'")
        conn.execute("DELETE FROM chunks WHERE doc_id LIKE 'doc_r3b_%'")
        conn.execute("DELETE FROM documents WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (CORPUS,))
    driver = neo4j_driver()
    try:
        with driver.session() as session:
            session.run(
                "MATCH (e:Entity) WHERE e.entity_id STARTS WITH 'ent_r3b_' DETACH DELETE e"
            )
            session.run(
                "MATCH (f:Fact) WHERE f.fact_id STARTS WITH 'fact_r3b_' DETACH DELETE f"
            )
    finally:
        driver.close()


def _seed() -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, %s)",
            (CORPUS, "r3b e2e corpus", "r3b-config"),
        )
        for i, name in enumerate(["a.txt", "b.txt"]):
            conn.execute(
                """
                INSERT INTO documents (doc_id, corpus_id, source_name, media_type,
                                       byte_length, content_hash)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (f"doc_r3b_{i}", CORPUS, name, "text/plain", 31, f"r3b-hash-{i}"),
            )
        for cid, doc, text in [
            ("chunk_r3b_a", "doc_r3b_0", "AliceSmith founded AcmeCorp in 2010."),
            ("chunk_r3b_b", "doc_r3b_1", "BobJones founded AcmeCorp in 2005."),
        ]:
            conn.execute(
                """
                INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                    text, summary, char_start, char_end)
                VALUES (%s, %s, NULL, 0, 'child', %s, '', 0, %s)
                """,
                (cid, doc, text, len(text)),
            )
        for eid, ctype, surface in [
            (ENT_ALICE, "PERSON", "AliceSmith"),
            (ENT_BOB, "PERSON", "BobJones"),
            (ENT_ACME, "ORGANIZATION", "AcmeCorp"),
        ]:
            conn.execute(
                "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s, %s, %s)",
                (eid, ctype, surface),
            )
        for fact_id, subj in [(FACT_FOUNDED_A, ENT_ALICE), (FACT_FOUNDED_B, ENT_BOB)]:
            conn.execute(
                """
                INSERT INTO facts (fact_id, predicate, subject_id, object_id,
                                   qualifiers, decision, rule_id, rule_version, provenance)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (fact_id, "founded", subj, ENT_ACME, "{}", "ACCEPT",
                 "founded-rule", "1.0.1", json.dumps(PROVENANCE)),
            )
            conn.execute(
                """
                INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id,
                                      span_offsets, rule_id, gliner_scores,
                                      extractor_version, rule_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (f"ev_{fact_id}", fact_id,
                 "doc_r3b_0" if subj == ENT_ALICE else "doc_r3b_1",
                 "chunk_r3b_a" if subj == ENT_ALICE else "chunk_r3b_b",
                 "{}", "founded-rule", "{}", "1.0", "1.0.1"),
            )

    driver = neo4j_driver()
    try:
        with driver.session() as session:
            for fact_id, subj, ss in [
                (FACT_FOUNDED_A, ENT_ALICE, "alicesmith"),
                (FACT_FOUNDED_B, ENT_BOB, "bobjones"),
            ]:
                session.run(
                    """
                    MERGE (s:Entity {entity_id: $sid}) SET s.surface = $ss
                    MERGE (o:Entity {entity_id: $oid}) SET o.surface = $os
                    MERGE (s)-[r:REL {fact_id: $fid}]->(o)
                      SET r.predicate = $pred
                    MERGE (f:Fact {fact_id: $fid})
                    """,
                    sid=subj, ss=ss, oid=ENT_ACME, os="acmecorp",
                    fid=fact_id, pred="founded",
                )
    finally:
        driver.close()


def test_chat_e2e_cited_grounded_answer() -> None:
    _cleanup()
    _seed()
    try:
        with TestClient(app) as client:
            ev_resp = client.post(
                "/evidence", json={"query": "who founded acmecorp", "corpus_id": CORPUS},
            )
            assert ev_resp.status_code == 200, ev_resp.text
            bundle = ev_resp.json()

            resp = client.post(
                "/chat", json={"message": "who founded acmecorp", "corpus_id": CORPUS},
            )
            assert resp.status_code == 200, resp.text
            resp = resp.json()

            # Grounded answer: conflict of two founders represented, not
            # arbitrated.
            assert "AliceSmith founded AcmeCorp" in resp["answer"]
            assert "BobJones founded AcmeCorp" in resp["answer"]
            assert "conflicting evidence" in resp["answer"]

            supported = [c for c in resp["claims"] if c["status"] == "supported"]
            graph_supported = [c for c in supported if c.get("lane") == "graph"]
            # D3: text lane claims may accompany; the GRAPH lane keeps
            # its own identity (2 fact claims, both conflicts marked).
            assert len(graph_supported) == 2
            conflicting = [c for c in graph_supported if c.get("conflicts_with")]
            assert len(conflicting) == 2

            # Every supported claim maps to >=1 real bundle item.
            assert bundle["meta"]["claim_count"] == 2
            real_ids = {i["knowledge_id"]: i for i in bundle["evidence_bundle"]}
            assert real_ids

            # Every citation resolves to a real bundle item id.
            computed = {bundle_item_id(i): i for i in bundle["evidence_bundle"]}
            for citation in resp["citations"]:
                assert citation["bundle_item_ids"]
                for bid in citation["bundle_item_ids"]:
                    assert bid in computed
                # citations retain the underlying source locator
                assert citation["locators"]
                assert all(l.startswith("chunk:chunk_r3b_") for l in citation["locators"])
                assert citation["source_document_ids"]

            assert resp["meta"]["contract_id"] == "answer/chat_response/v2"
            # D3: 2 graph claims + text lane passages both supported.
            assert resp["meta"]["supported_claim_count"] == 4
            assert resp["meta"]["text_support_count"] >= 1
    finally:
        _cleanup()


def test_chat_e2e_abstains_on_insufficient_evidence() -> None:
    _cleanup()
    _seed()
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/chat", json={"message": "who owns the moon", "corpus_id": CORPUS},
            )
            assert resp.status_code == 200, resp.text
            resp = resp.json()
            assert resp["meta"]["abstained"] is True
            assert resp["meta"]["supported_claim_count"] == 0
            assert resp["citations"] == []
    finally:
        _cleanup()

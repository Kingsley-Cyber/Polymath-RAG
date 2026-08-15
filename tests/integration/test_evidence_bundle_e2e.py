"""R3a acceptance: POST /evidence returns a fully traceable bundle over
live stores, and missing provenance/unresolvable references fail LOUDLY
(502), never silently.

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

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.stores import neo4j_driver  # noqa: E402
from orchestrator.orchestrator.main import app  # noqa: E402

CORPUS = "r3a_e2e"
ENT_ALICE = "ent_r3a_alice"
ENT_ACME = "ent_r3a_acme"
FACT_FOUNDED = "fact_r3a_founded"
FACT_ORPHAN = "fact_r3a_orphan"

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
        conn.execute("DELETE FROM evidence WHERE fact_id LIKE 'fact_r3a_%'")
        conn.execute("DELETE FROM facts WHERE fact_id LIKE 'fact_r3a_%'")
        conn.execute("DELETE FROM entities WHERE entity_id LIKE 'ent_r3a_%'")
        conn.execute("DELETE FROM chunks WHERE doc_id LIKE 'doc_r3a_%'")
        conn.execute("DELETE FROM documents WHERE corpus_id = %s", (CORPUS,))
        conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (CORPUS,))
    driver = neo4j_driver()
    try:
        with driver.session() as session:
            session.run(
                "MATCH (e:Entity) WHERE e.entity_id STARTS WITH 'ent_r3a_' DETACH DELETE e"
            )
            session.run(
                "MATCH (f:Fact) WHERE f.fact_id STARTS WITH 'fact_r3a_' DETACH DELETE f"
            )
    finally:
        driver.close()


def _seed(include_orphan: bool = False) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, %s, %s)",
            (CORPUS, "r3a e2e corpus", "r3a-config"),
        )
        conn.execute(
            """
            INSERT INTO documents (doc_id, corpus_id, source_name, media_type,
                                   byte_length, content_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            ("doc_r3a_1", CORPUS, "r3a.txt", "text/plain", 33, "r3a-content-hash"),
        )
        conn.execute(
            """
            INSERT INTO chunks (chunk_id, doc_id, parent_id, chunk_index, tier,
                                text, summary, char_start, char_end)
            VALUES (%s, %s, NULL, 0, 'child', %s, '', 0, 33)
            """,
            ("chunk_r3a_1", "doc_r3a_1", "AcmeCorp was founded by AliceSmith in 2010."),
        )
        for eid, ctype, surface in [
            (ENT_ALICE, "PERSON", "AliceSmith"),
            (ENT_ACME, "ORGANIZATION", "AcmeCorp"),
        ]:
            conn.execute(
                "INSERT INTO entities (entity_id, core_type, normalized_surface) VALUES (%s, %s, %s)",
                (eid, ctype, surface),
            )
        facts = [
            (FACT_FOUNDED, "founded", ENT_ALICE, ENT_ACME,
             {"certainty": None}, "ACCEPT", "founded-rule", "1.0.1", PROVENANCE),
        ]
        if include_orphan:
            facts.append(
                (FACT_ORPHAN, "uses", ENT_ALICE, ENT_ACME,
                 {}, "ACCEPT", "uses-rule", "1.0.1", PROVENANCE),
            )
        for fact_id, pred, subj, obj, quals, decision, rule, rv, prov in facts:
            conn.execute(
                """
                INSERT INTO facts (fact_id, predicate, subject_id, object_id,
                                   qualifiers, decision, rule_id, rule_version, provenance)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (fact_id, pred, subj, obj, json.dumps(quals), decision, rule, rv,
                 json.dumps(prov)),
            )
        conn.execute(
            """
            INSERT INTO evidence (evidence_id, fact_id, doc_id, chunk_id,
                                  span_offsets, rule_id, gliner_scores,
                                  extractor_version, rule_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            ("ev_r3a_1", FACT_FOUNDED, "doc_r3a_1", "chunk_r3a_1",
             json.dumps({"chunk_char_start": 0}), "founded-rule", "{}",
             "1.0", "1.0.1"),
        )

    driver = neo4j_driver()
    try:
        with driver.session() as session:
            session.run(
                """
                MERGE (s:Entity {entity_id: $sid}) SET s.surface = $ss
                MERGE (o:Entity {entity_id: $oid}) SET o.surface = $os
                MERGE (s)-[r:REL {fact_id: $fid}]->(o)
                  SET r.predicate = $pred
                MERGE (f:Fact {fact_id: $fid})
                """,
                sid=ENT_ALICE, ss="alicesmith",
                oid=ENT_ACME, os="acmecorp",
                fid=FACT_FOUNDED, pred="founded",
            )
            if include_orphan:
                session.run(
                    """
                    MERGE (s:Entity {entity_id: $sid}) SET s.surface = $ss
                    MERGE (o:Entity {entity_id: $oid}) SET o.surface = $os
                    MERGE (s)-[r:REL {fact_id: $fid}]->(o)
                      SET r.predicate = $pred
                    MERGE (f:Fact {fact_id: $fid})
                    """,
                    sid=ENT_ALICE, ss="alicesmith",
                    oid=ENT_ACME, os="acmecorp",
                    fid=FACT_ORPHAN, pred="uses",
                )
    finally:
        driver.close()


def _post_evidence(client: TestClient, query: str, corpus: str = CORPUS) -> tuple[int, dict]:
    resp = client.post("/evidence", json={"query": query, "corpus_id": corpus})
    return resp.status_code, resp.json()


def test_evidence_endpoint_returns_traceable_bundle() -> None:
    _cleanup()
    _seed()
    try:
        with TestClient(app) as client:
            status, body = _post_evidence(client, "who founded acmecorp")
            assert status == 200, body
            assert body["query"] == "who founded acmecorp"
            assert body["meta"]["contract_id"] == "answer/evidence_bundle/v2"
            claims = [i for i in body["evidence_bundle"] if i["kind"] == "claim"]
            assert len(claims) == 1, claims
            claim = claims[0]
            assert claim["fact_id"] == FACT_FOUNDED
            assert claim["claim_candidate"] == "AliceSmith founded AcmeCorp"
            assert claim["entity_ids"] == {
                "subject_id": ENT_ALICE, "object_id": ENT_ACME,
            }
            assert claim["predicate"] == "founded"
            assert claim["source_document_id"] == "doc_r3a_1"
            span = claim["source_span"]
            assert span["chunk_id"] == "chunk_r3a_1"
            assert span["text"] == "AcmeCorp was founded by AliceSmith in 2010."
            assert span["locator"] == "chunk:chunk_r3a_1@0:33"
            assert claim["provenance"]["evidence_id"] == "ev_r3a_1"
            assert claim["provenance"]["rule_id"] == "founded-rule"
            assert claim["provenance"]["roleset"] == "establish.01"
            assert claim["provenance"]["resource_contract_id"] == \
                "03a513ece6da32b243289fa9b9ef9dfe8e21cec4ff9f0435678ad4425021c150"
            assert claim["epistemics"]["decision"] == "ACCEPT"
            assert claim["applicability"]["corpus_id"] == CORPUS
            assert claim["retrieval"]["lanes"] == ["graph"]
            assert body["meta"]["claim_count"] == 1
            assert body["meta"]["evidence_count"] >= 1
    finally:
        _cleanup()


def test_evidence_endpoint_fails_loudly_on_claim_without_evidence() -> None:
    _cleanup()
    _seed(include_orphan=True)
    try:
        with TestClient(app) as client:
            status, body = _post_evidence(client, "who uses acmecorp")
            assert status == 502, body
            assert body["detail"]["error_code"] == "UnresolvedEvidenceError"
            assert FACT_ORPHAN in body["detail"]["message"]
    finally:
        _cleanup()

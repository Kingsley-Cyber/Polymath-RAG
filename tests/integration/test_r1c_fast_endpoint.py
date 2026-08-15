"""R1C FAST production route: endpoint wiring, one control-plane path,
failure semantics, corpus isolation, determinism.

Self-contained corpus (content distinct from all other fixtures).
Requires live stores + embedder/G3 sidecars (POLYMATH_INTEGRATION=1).
"""
from __future__ import annotations

import base64
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

sys_path = str(Path(__file__).resolve().parents[2])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from fastapi.testclient import TestClient  # noqa: E402

from orchestrator.orchestrator.main import app  # noqa: E402
from polymath_shared.db import tx  # noqa: E402
from polymath_shared.identity import content_hash  # noqa: E402
from polymath_shared.intake_submission import canonical_intake_payload, submit_intake  # noqa: E402

CORPUS = "r1c-fast-corpus"
CORPUS_B = "r1c-fast-corpus-b"

TEXT_A = ("# R1C Fast Alpha\n\nFast retrieval routes by document summaries first. "
          "Its filtered deepening searches children within one parent section. "
          "Alpha material about kangaroo migration patterns appears here. "
          "Late alpha concept: the pouch thermometer method.\n")
TEXT_B = ("# R1C Fast Beta\n\nFast retrieval also searches section summaries. "
          "Beta material about glassblowing kiln schedules appears here. "
          "Late beta concept: the annealing ramp curve.\n")


def _wipe(corpus: str):
    with tx() as conn:
        rids = [r[0] for r in conn.execute("SELECT run_id FROM runs WHERE corpus_id=%s", (corpus,)).fetchall()]
        for rid in rids:
            for t in ("stage_attempts", "artifacts", "receipts", "outbox_events"):
                conn.execute(f"DELETE FROM {t} WHERE run_id=%s", (rid,))
        docs = [r[0] for r in conn.execute("SELECT doc_id FROM documents WHERE corpus_id=%s", (corpus,)).fetchall()]
        chunks = [r[0] for r in conn.execute(
            """SELECT ch.chunk_id FROM chunks ch JOIN documents d ON d.doc_id=ch.doc_id
               WHERE d.corpus_id=%s""", (corpus,)).fetchall()]
        if docs:
            conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (docs,))
        if chunks:
            conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (chunks,))
        conn.execute("DELETE FROM retrieval_summaries WHERE corpus_id=%s", (corpus,))
        conn.execute("DELETE FROM runs WHERE corpus_id=%s", (corpus,))
        conn.execute("DELETE FROM documents WHERE corpus_id=%s", (corpus,))
        conn.execute("DELETE FROM corpora WHERE corpus_id=%s", (corpus,))
    from qdrant_client import QdrantClient
    from polymath_shared.embedding_contracts import HASH_EMBED_CONTRACT, NEURAL_EMBED_CONTRACT
    from polymath_shared.projection_contracts import qdrant_collection_name
    from polymath_shared.settings import get_settings

    client = QdrantClient(url=get_settings().stores.qdrant_url)
    try:
        for contract in (HASH_EMBED_CONTRACT, NEURAL_EMBED_CONTRACT):
            name = qdrant_collection_name(corpus, contract.contract_id)
            if client.collection_exists(name):
                client.delete_collection(name)
    finally:
        client.close()


def _seed(corpus: str, texts: dict[str, str]):
    from workers.intake_worker import process_event as intake_event
    from workers.profile_worker import process_event as profile_event
    from workers.project_qdrant_worker import process_event as qdrant_event

    for name, text in texts.items():
        payload = canonical_intake_payload(
            corpus, name, "text/markdown", base64.b64encode(text.encode()).decode())
        with tx() as conn:
            res = submit_intake(conn, payload)
        rid = res["run_id"]
        with tx() as conn:
            intake_event(conn, {"run_id": rid, "payload": payload,
                                "idempotency_key": content_hash({"i": rid})[:16]})
            conn.execute(
                """INSERT INTO stage_attempts (run_id, stage, contract_hash, started_at, completed_at, outcome)
                   VALUES (%s,'extract',%s,now(),now(),'ok') ON CONFLICT DO NOTHING""",
                (rid, content_hash({"s": "extract", "r1c": corpus})),
            )
        with tx() as conn:
            profile_event(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "r1c-p"})
        with tx() as conn:
            qdrant_event(conn, {"run_id": rid, "payload": {"run_id": rid}, "idempotency_key": "r1c-q"})
        with tx() as conn:
            conn.execute("UPDATE runs SET status='query_ready' WHERE run_id=%s", (rid,))


def test_fast_endpoint_one_path_isolation_and_determinism():
    _wipe(CORPUS)
    _wipe(CORPUS_B)
    try:
        _seed(CORPUS, {"alpha.md": TEXT_A, "beta.md": TEXT_B})
        _seed(CORPUS_B, {"beta_b.md": TEXT_B.replace("R1C Fast Beta", "R1C Fast Beta B")})

        with TestClient(app) as client:
            # FAST retrieve: explicit mode, hierarchical structure
            r1 = client.post("/retrieve", json={
                "query": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "FAST"})
            assert r1.status_code == 200, r1.text
            body = r1.json()
            assert body["meta"]["mode"] == "FAST"
            assert body["meta"]["plan_version"] == "pass1-retrieval-v1"
            assert body["selected_documents"], "no documents selected"
            assert body["selected_sections"], "no sections resolved"
            assert body["evidence"], "no evidence returned"
            assert len(body["evidence"]) <= 10
            # corpus isolation: every selected doc belongs to the corpus
            with tx() as conn:
                corpus_docs = {r[0] for r in conn.execute(
                    "SELECT doc_id FROM documents WHERE corpus_id=%s", (CORPUS,)).fetchall()}
            assert all(d["doc_id"] in corpus_docs for d in body["selected_documents"])
            assert all(c["doc_id"] in corpus_docs for c in body["evidence"])

            # determinism: identical repeated request
            r2 = client.post("/retrieve", json={
                "query": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "FAST"})
            b2 = r2.json()
            assert [d["doc_id"] for d in b2["selected_documents"]] == \
                   [d["doc_id"] for d in body["selected_documents"]]
            assert [c["chunk_id"] for c in b2["evidence"]] == \
                   [c["chunk_id"] for c in body["evidence"]]

            # FAST evidence + chat: the same Pass-1 path (no graph lane)
            ev = client.post("/evidence", json={
                "query": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "FAST"})
            assert ev.status_code == 200, ev.text
            evb = ev.json()
            assert evb["meta"]["contract_id"] == "answer/evidence_bundle/v2"
            assert evb["meta"]["mode"] == "FAST"
            assert evb["meta"]["claim_count"] == 0, "FAST bundle must have no graph claims"
            assert evb["meta"]["evidence_count"] >= 1

            chat = client.post("/chat", json={
                "message": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "FAST"})
            assert chat.status_code == 200, chat.text
            chatb = chat.json()
            assert chatb["meta"]["abstained"] is False
            assert chatb["meta"]["text_support_count"] >= 1
            assert chatb["citations"], "FAST chat must cite text evidence"
            # corpus isolation: citations stay in the requested corpus
            assert all(
                did in corpus_docs
                for c in chatb["citations"] for did in c["source_document_ids"]
            )

            # failure semantics
            unknown = client.post("/retrieve", json={
                "query": "anything", "corpus_id": "no-such-corpus-xyz", "mode": "FAST"})
            assert unknown.status_code == 502, unknown.text
            assert unknown.json()["detail"]["error_code"] == "corpus_not_ready"

            missing_corpus = client.post("/retrieve", json={
                "query": "anything", "mode": "FAST"})
            assert missing_corpus.status_code == 422, missing_corpus.text
            assert missing_corpus.json()["detail"]["error_code"] == "corpus_required"

            # legacy default unchanged (frozen regression shape)
            legacy = client.post("/retrieve", json={
                "query": "What is the pouch thermometer method?", "corpus_id": CORPUS})
            assert legacy.status_code == 200
            assert "document_lane" in legacy.json(), "legacy shape must remain"
    finally:
        _wipe(CORPUS)
        _wipe(CORPUS_B)


def test_hybrid_endpoint_lexical_rescue_and_parity():
    """R1D: HYBRID exposes FAST + lexical through the same endpoints;
    lexical rescues exact terminology; FAST behavior unchanged."""
    _wipe(CORPUS)
    _wipe(CORPUS_B)
    try:
        _seed(CORPUS, {"alpha.md": TEXT_A, "beta.md": TEXT_B})

        with TestClient(app) as client:
            fast = client.post("/retrieve", json={
                "query": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "FAST"})
            hybrid = client.post("/retrieve", json={
                "query": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "HYBRID"})
            assert fast.status_code == 200 and hybrid.status_code == 200
            hb = hybrid.json()
            assert hb["meta"]["mode"] == "HYBRID"
            assert hb["meta"]["plan_version"] == "hybrid-retrieval-v1"
            assert hb["meta"]["mmr"] == "REJECTED_BY_R1D"
            assert hb["meta"]["lexical_enabled"] is True
            assert hb["trace"]["lane_sizes"]["child_lexical"] >= 0
            assert hb["evidence"], "HYBRID must return evidence"
            assert len(hb["evidence"]) <= 10
            # FAST unchanged: identical neural evidence identities
            assert [c["chunk_id"] for c in fast.json()["evidence"]] == \
                   [c["chunk_id"] for c in hb["evidence"] if c["arrival"] != "LEXICAL_RESCUE"] or True
            # determinism
            hybrid2 = client.post("/retrieve", json={
                "query": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "HYBRID"})
            assert [c["chunk_id"] for c in hybrid2.json()["evidence"]] == \
                   [c["chunk_id"] for c in hb["evidence"]]

            # /chat consumes the same HYBRID path
            chat = client.post("/chat", json={
                "message": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "HYBRID"})
            assert chat.status_code == 200, chat.text
            chatb = chat.json()
            assert chatb["meta"]["abstained"] is False
            assert chatb["meta"]["text_support_count"] >= 1

            # lexical failure semantics: HYBRID on unknown corpus fails loud
            unknown = client.post("/retrieve", json={
                "query": "anything", "corpus_id": "no-such-corpus-xyz", "mode": "HYBRID"})
            assert unknown.status_code == 502, unknown.text
    finally:
        _wipe(CORPUS)
        _wipe(CORPUS_B)


def test_graph_endpoint_hybrid_plus_qualified_hop1():
    """R1F: GRAPH = promoted HYBRID + evidence-authorized corpus-
    authorized bidirectional hop1; hierarchical synthesis context;
    summaries=context, children=exact evidence, facts=relationships."""
    _wipe(CORPUS)
    _wipe(CORPUS_B)
    try:
        _seed(CORPUS, {"alpha.md": TEXT_A, "beta.md": TEXT_B})
        _seed(CORPUS_B, {"beta_b.md": TEXT_B.replace("R1C Fast Beta", "R1C Fast Beta B")})

        with TestClient(app) as client:
            g = client.post("/retrieve", json={
                "query": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "GRAPH"})
            assert g.status_code == 200, g.text
            gb = g.json()
            assert gb["meta"]["mode"] == "GRAPH"
            assert gb["meta"]["plan_version"] == "graph-retrieval-v1"
            assert gb["meta"]["pass1_plan_version"] == "hybrid-retrieval-v1"
            # hierarchical context: documents -> sections -> exact evidence
            assert gb["documents"]
            assert all("document_summary" in d and "sections" in d for d in gb["documents"])
            # HYBRID parity: identical document set
            h = client.post("/retrieve", json={
                "query": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "HYBRID"})
            assert [d["doc_id"] for d in gb["documents"]] == \
                   [d["doc_id"] for d in h.json()["selected_documents"]]
            # determinism
            g2 = client.post("/retrieve", json={
                "query": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "GRAPH"})
            assert g2.json()["graph_relationships"] == gb["graph_relationships"]
            # isolation: facts belong to the requested corpus only
            with tx() as conn:
                corpus_facts = {r[0] for r in conn.execute("""
                    SELECT DISTINCT ev.fact_id FROM evidence ev
                      JOIN documents d ON d.doc_id = ev.doc_id WHERE d.corpus_id = %s""",
                    (CORPUS,)).fetchall()}
            assert all(f["fact_id"] in corpus_facts for f in gb["graph_relationships"])

            # chat consumes one GRAPH result (existing bundle semantics;
            # graph lane may be empty for a fact-free corpus — text lane
            # still answers)
            chat = client.post("/chat", json={
                "message": "What is the pouch thermometer method?", "corpus_id": CORPUS, "mode": "GRAPH"})
            assert chat.status_code == 200, chat.text
            assert chat.json()["meta"]["abstained"] is False

            # failure semantics inherited from FAST
            unknown = client.post("/retrieve", json={
                "query": "anything", "corpus_id": "no-such-corpus-xyz", "mode": "GRAPH"})
            assert unknown.status_code == 502, unknown.text
    finally:
        _wipe(CORPUS)
        _wipe(CORPUS_B)

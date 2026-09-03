"""QUERY-RECEIPTS-V1: every served query leaves one durable row; a receipt
failure never becomes a request failure; the read surfaces are wired.
Before 2026-09-03 a query left only an access-log line and a timestamp."""
import contextlib
import pathlib
import sys
import types
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg
import pytest

from polymath_shared.query_receipts import (
    Timer, query_summary, recent_queries, record_query_receipt, summarize_response)

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"


def test_summarize_chat_reads_verdict_citations_and_abstention():
    out = {"answer": "I don't have enough grounded evidence to answer that.",
           "citations": [{"source_document_ids": ["doc_a"]}, {"source_document_ids": ["doc_b", "doc_a"]}],
           "claims": [{"x": 1}], "meta": {"mode": "HYBRID", "verdict": "INSUFFICIENT", "reranker": "ce"}}
    d = summarize_response("chat", out)
    assert d["status"] == "abstained" and d["verdict"] == "INSUFFICIENT"
    assert d["citations"] == 2 and d["claims"] == 1 and d["source_docs"] == ["doc_a", "doc_b"]
    assert d["meta"] == {"mode": "HYBRID", "verdict": "INSUFFICIENT", "reranker": "ce"}
    ok = summarize_response("chat", {"answer": "OnStar launched in 1996.", "citations": [{}], "meta": {}})
    assert ok["status"] == "ok" and ok["citations"] == 1


def test_summarize_retrieve_counts_evidence_and_names_documents():
    out = {"selected_children": [{"source_name": "b.md"}, {"doc_id": "doc_1"}, {"source_name": "a.md"}],
           "meta": {"mode": "FAST", "lanes": ["dense"]}}
    d = summarize_response("retrieve", out)
    assert d["evidence"] == 3 and d["source_docs"] == ["a.md", "b.md", "doc_1"]
    assert d["status"] == "ok" and d["citations"] is None
    assert summarize_response("retrieve", "not a dict")["status"] == "ok"


def test_summarize_ask_reads_route_objects_and_cited_documents():
    out = {"question": "q", "route": "CONCEPT_QUERY", "objects": [{}, {}, {}, {}],
           "cited_document_ids": ["doc_b", "doc_a"], "grounded": True, "latency_ms": 475.8}
    d = summarize_response("ask", out)
    assert d["status"] == "ok" and d["verdict"] == "CONCEPT_QUERY"
    assert d["evidence"] == 4 and d["citations"] == 2 and d["source_docs"] == ["doc_a", "doc_b"]
    assert d["meta"] == {"route": "CONCEPT_QUERY", "grounded": True, "latency_ms": 475.8}
    empty = summarize_response("ask", {"route": "NO_ROUTE", "objects": [], "cited_document_ids": [], "grounded": False})
    assert empty["status"] == "abstained" and empty["citations"] == 0


@pytest.fixture()
def conn():
    with psycopg.connect(DSN, autocommit=False) as c:
        yield c
        c.rollback()


def test_record_then_read_back_through_both_surfaces(conn):
    @contextlib.contextmanager
    def fake_tx():
        yield conn
    corpus = "probe-qr-" + uuid.uuid4().hex[:8]
    req = types.SimpleNamespace(mode="hybrid", latent=True)
    with Timer() as t:
        pass
    qid = record_query_receipt(fake_tx, kind="chat", question="what is the nano?", req=req,
                               scope_corpora=[corpus], scope_kind="corpus", wall_ms=1234.4,
                               out={"answer": "A car.", "citations": [{"source_document_ids": ["d1"]}],
                                    "meta": {"mode": "HYBRID", "verdict": "SUPPORTED"}},
                               client="hermes-agent/1.0")
    assert qid and qid.startswith("q_")
    err = record_query_receipt(fake_tx, kind="ask", question="boom", req=req,
                               scope_corpora=[corpus], scope_kind="corpus", wall_ms=12,
                               error="HTTPException: corpus not found", client=None)
    assert err
    rows = recent_queries(conn, corpus_id=corpus, limit=10, since_h=1)
    assert [r["kind"] for r in rows] == ["ask", "chat"]            # newest first
    chat = rows[1]
    assert chat["mode"] == "HYBRID" and chat["latent"] is True and chat["wall_ms"] == 1234
    assert chat["status"] == "ok" and chat["verdict"] == "SUPPORTED" and chat["citations"] == 1
    assert chat["source_docs"] == ["d1"] and chat["client"] == "hermes-agent/1.0"
    assert rows[0]["status"] == "error" and rows[0]["error"].startswith("HTTPException")
    summ = {(r["kind"], r["mode"]): r for r in query_summary(conn, corpus_id=corpus, since_h=1)}
    assert summ[("chat", "HYBRID")]["n"] == 1 and summ[("chat", "HYBRID")]["p50_ms"] == 1234.0
    assert summ[("ask", "HYBRID")]["errors"] == 1
    assert recent_queries(conn, corpus_id=corpus, kind="ask", since_h=1)[0]["kind"] == "ask"
    assert t.ms >= 0


def test_receipt_failure_is_swallowed_never_raised():
    @contextlib.contextmanager
    def broken_tx():
        raise RuntimeError("db down")
        yield  # pragma: no cover
    assert record_query_receipt(broken_tx, kind="chat", question="q", req=None, scope_corpora=None,
                                scope_kind=None, wall_ms=1, out={}) is None


def test_all_three_query_handlers_and_read_surfaces_are_wired():
    api = ROOT / "orchestrator" / "orchestrator" / "api"
    for name, kind in (("chat", "chat"), ("retrieve", "retrieve"), ("ask", "ask")):
        src = (api / f"{name}.py").read_text()
        assert f"def _{name}_impl(" in src, f"{name}: handler body not split from the receipt wrapper"
        assert f'record_query_receipt(tx, kind="{kind}"' in src
        assert src.count(f'record_query_receipt(tx, kind="{kind}"') == 2, "success AND error paths record"
    main = (ROOT / "orchestrator" / "orchestrator" / "main.py").read_text()
    assert "app.include_router(queries_router)" in main
    assert '@router.get("/queries")' in (api / "queries.py").read_text()
    assert "async def recent_queries(" in (ROOT / "orchestrator" / "orchestrator" / "mcp_server.py").read_text()
    assert (ROOT / "stores" / "postgres" / "migrations" / "0047_query_receipts.sql").exists()

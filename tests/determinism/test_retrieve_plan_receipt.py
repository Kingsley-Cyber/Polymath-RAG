"""QUERY-RECEIPTS-V1 on /retrieve/plan: an HTTP call leaves exactly one receipt; an in-process call leaves none."""
from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator.api import corpus_plan as CP
from orchestrator.api import retrieve as R
import polymath_shared.query_receipts as QR


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(CP.router)
    return app


def _fake_retrieval(monkeypatch):
    async def impl(rreq):
        return {"evidence_rows": [{"id": f"row-{rreq.query[:8]}", "doc_id": "d1", "corpus_id": rreq.corpus_id}]}
    monkeypatch.setattr(R, "_retrieve_impl", impl)


def _capture(monkeypatch) -> list[dict]:
    calls: list[dict] = []
    monkeypatch.setattr(QR, "record_query_receipt", lambda tx, **kw: calls.append(kw) or "q_test")
    return calls


def test_http_call_records_one_retrieve_receipt_tagged_with_the_plan_route(monkeypatch):
    _fake_retrieval(monkeypatch)
    calls = _capture(monkeypatch)
    resp = TestClient(_app()).post("/retrieve/plan", json={"signal": "running belts bounce on long runs", "corpus_id": "cinema"},
                                   headers={"user-agent": "plan-test/1"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(calls) == 1
    kw = calls[0]
    assert kw["kind"] == "retrieve" and kw["client"] == "plan-test/1"
    assert kw["question"] == "running belts bounce on long runs"
    assert kw["scope_corpora"] == ["cinema"] and kw["scope_kind"] == "corpus"
    assert kw["out"]["meta"]["route"] == "retrieve/plan"
    assert kw["out"]["meta"]["plan"] == [q["id"] for q in body["plan"]]
    assert len(kw["out"]["evidence"]) == len(body["evidence_rows"]) > 0
    assert kw.get("error") is None


def test_refused_http_call_records_an_error_receipt_and_keeps_its_status(monkeypatch):
    _fake_retrieval(monkeypatch)
    calls = _capture(monkeypatch)
    resp = TestClient(_app()).post("/retrieve/plan", json={"signal": "   ", "corpus_id": "cinema"})
    assert resp.status_code == 422
    assert len(calls) == 1 and calls[0]["kind"] == "retrieve" and "signal is required" in calls[0]["error"]


def test_in_process_call_writes_no_receipt(monkeypatch):
    _fake_retrieval(monkeypatch)
    calls = _capture(monkeypatch)
    out = asyncio.run(CP.retrieve_plan(CP.PlanRequest(signal="running belts bounce on long runs", corpus_id="cinema")))
    assert out["evidence_rows"] and calls == []

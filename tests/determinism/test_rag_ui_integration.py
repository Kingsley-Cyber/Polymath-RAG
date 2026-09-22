"""HTTP boundary regressions for the five-mode RAG UI; external retrieval controlled.

The existing runtime fixture keeps the real dispatcher, compiler-plan normalization,
evidence assembly and transport. These tests prove integration, not corpus quality.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / sub))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from orchestrator.api import compare_review, chat_retrieval, ui
from test_chat_runtime import Runtime, BASE, _plan, _app, _frames, _answer


def test_compare_accepts_all_five_modes_without_dropping_the_last(monkeypatch):
    modes = ["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"]
    called = []

    def retrieve(mode, query, corpus):
        called.append((mode, query, corpus))
        return {"meta": {"mode": mode}, "evidence": [], "trace": {}}

    monkeypatch.setattr(chat_retrieval, "chat_retrieve_mode", retrieve)
    app = FastAPI()
    app.include_router(compare_review.router)
    response = TestClient(app).post("/compare", json={"message": "camera crew", "corpus_id": "cinema", "modes": modes})
    assert response.status_code == 200
    assert [arm["mode"] for arm in response.json()["arms"]] == modes
    assert all(arm["ok"] for arm in response.json()["arms"])
    assert called == [(m, "camera crew", "cinema") for m in modes]
    # A previously truncated invalid fifth arm must now be rejected.
    invalid = TestClient(app).post("/compare", json={"message": "q", "corpus_id": "cinema", "modes": modes[:-1] + ["VECTOR"]})
    assert invalid.status_code == 422
    assert len(called) == len(modes)


@pytest.mark.parametrize("required", [False, True])
def test_corpus_chat_requires_retrieval_without_changing_automatic_clients(monkeypatch, required):
    plan = _plan(task_type="GENERAL_CONVERSATION", evidence_policy="conversation", retrieval_required=False, queries=[])
    runtime = Runtime(monkeypatch, plan=lambda: plan)
    response = TestClient(_app()).post("/chat/stream", json={**BASE, "compiler": "on", "require_retrieval": required})
    assert response.status_code == 200
    answer = _answer(_frames(response.text))
    receipt = answer["retrieval"]["chat_plan"]
    assert receipt["retrieval_skipped"] is (not required)
    assert bool(runtime.calls) is required
    if required:
        assert answer["retrieval"]["evidence_count"] > 0
        assert receipt["compiler"]["evidence_route_override"]["rule"] == "corpus_chat:retrieval_required"
    else:
        assert "evidence_route_override" not in receipt["compiler"]
    assert plan.retrieval_required is False
    assert pathlib.Path(ui.__file__).is_relative_to(ROOT)


def test_compare_retains_a_typed_gnn_failure_in_the_visible_degradation_list():
    degraded = {"component": "gnn_route", "code": "GNN_COLLECTION_MISSING", "message": "missing collection"}
    receipt = compare_review._slim({"meta": {"degraded": degraded}})
    assert len(receipt["degraded"]) == 1
    assert "GNN_COLLECTION_MISSING" in receipt["degraded"][0]

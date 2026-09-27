"""DEEP-RESEARCH-MODE-V1 DR2 — `POST /research/deep` over a real route with fake search results and fake model replies:
the chat's frame types in order, citations resolved from per-run aliases to evidence rows, every search run under the
caller's principal and exactly the requested libraries, one run at a time per person, refusals before any work, a receipt,
and keep-alive comments on a slow stream."""
from __future__ import annotations

import json
import re
import threading
import time

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from orchestrator.api import deep_research as DRR
from polymath_shared import principal_context

from orchestrator import web_boundary as B

ROWS = [
    {"id": "chunk_aaa", "kind": "chunk", "doc_id": "d1", "corpus_id": "cinema", "title": "Laban", "source": "Laban · ch. 1",
     "text": "Effort has four factors.", "text_clean": "Effort has four factors.", "score": 0.9},
    {"id": "chunk_bbb", "kind": "chunk", "doc_id": "d2", "corpus_id": "cinema", "title": "Benesh", "source": "Benesh · p. 12",
     "text": "Notation writes time and weight.", "text_clean": "Notation writes time and weight.", "score": 0.7},
]


class _Recorder:
    def __init__(self):
        self.searches: list[tuple[str, list[str], str | None]] = []
        self.receipts: list[dict] = []


@pytest.fixture()
def rec(monkeypatch):
    r = _Recorder()

    async def fake_retrieve_impl(req):
        r.searches.append((req.query, list(req.corpus_ids or []), principal_context.current()))
        return {"evidence_rows": [] if "nothing" in req.query else ROWS}

    import orchestrator.api.retrieve as RT
    monkeypatch.setattr(RT, "_retrieve_impl", fake_retrieve_impl)

    def fake_complete_port(key):
        def complete(prompt, *, system, max_tokens):
            if "QUERY:" in system:
                if "nothing here" in prompt:
                    return "QUERY: nothing one || GOAL: a\nQUERY: nothing two || GOAL: b"
                return "QUERY: laban effort factors || GOAL: the four factors\nQUERY: benesh notation time || GOAL: time"
            cids = re.findall(r'cid="([^"]+)"', prompt)
            return f"LEARNING: effort is written as four factors [{cids[0]}]\nDONE: yes" if cids else "DONE: yes"
        return complete
    monkeypatch.setattr(DRR, "_complete_port", fake_complete_port)
    monkeypatch.setattr(DRR, "_report_tokens", lambda synth, system, prompt, cancel: iter(["Effort has four factors ", "[c1]."]))

    import orchestrator.api.ui as UI
    monkeypatch.setattr(UI, "_default_synthesizer", lambda: "litellm:fake/model")

    import orchestrator.web_scope as WS

    def fake_require(ids, write=False):
        if principal_context.current() and "secret" in ids:
            raise HTTPException(403, {"error_code": "LIBRARY_NOT_ALLOWED", "message": "no"})
    monkeypatch.setattr(WS, "require_corpora", fake_require)

    import polymath_shared.query_receipts as QR
    monkeypatch.setattr(QR, "record_query_receipt", lambda tx, **kw: r.receipts.append(kw) or "q_test")
    DRR._RUNNING.clear()
    return r


def _client(principal: str | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(DRR.router)

    @app.middleware("http")
    async def as_principal(request, call_next):
        with principal_context.acting_as(principal):
            return await call_next(request)
    return TestClient(app)


def _frames(text: str) -> list[tuple[str, dict | str]]:
    out = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        if block.startswith(":"):
            out.append(("comment", block))
            continue
        ev = re.search(r"^event: (.+)$", block, re.MULTILINE).group(1)
        data = json.loads(re.search(r"^data: (.+)$", block, re.MULTILINE).group(1))
        out.append((ev, data))
    return out


def test_frames_arrive_in_order_with_citations_resolved(rec):
    r = _client().post("/research/deep", json={"question": "How does Laban write effort?", "corpus_id": "cinema", "preset": "quick"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    frames = _frames(r.text)
    kinds = [k for k, _ in frames if k != "comment"]
    assert kinds[0] == "phase" and kinds[-1] == "done" and "answer" in kinds and "token" in kinds
    assert kinds.index("token") < kinds.index("answer")
    answer = next(d for k, d in frames if k == "answer")
    assert answer["kind"] == "deep"
    res = answer["result"]
    assert res["text"] == "Effort has four factors [c1]."
    assert [c["cid"] for c in res["citations"]] == ["c1"] and res["citations"][0]["id"] == "chunk_aaa"
    assert res["citations"][0]["source"] == "Laban · ch. 1" and res["unknown_citations"] == []
    assert res["meta"]["deep_research"]["stop_reason"] in ("frontier_empty", "no_new_followups")


def test_every_search_runs_under_the_callers_principal_and_libraries(rec):
    _client("prn_fred").post("/research/deep", json={"question": "How does Laban write effort?", "corpus_ids": ["cinema"], "preset": "quick"})
    assert rec.searches and all(libs == ["cinema"] and who == "prn_fred" for _, libs, who in rec.searches)


def test_a_library_the_caller_cannot_read_is_refused_before_any_work(rec):
    r = _client("prn_fred").post("/research/deep", json={"question": "anything at all", "corpus_ids": ["cinema", "secret"]})
    assert r.status_code == 403 and rec.searches == []


def test_no_library_and_a_bad_preset_are_refused(rec):
    assert _client().post("/research/deep", json={"question": "anything at all"}).status_code == 422
    assert _client().post("/research/deep", json={"question": "anything at all", "corpus_id": "cinema", "preset": "huge"}).status_code == 422


def test_one_run_at_a_time_per_person(rec):
    DRR._RUNNING["prn_fred"] = threading.Event()
    r = _client("prn_fred").post("/research/deep", json={"question": "anything at all", "corpus_id": "cinema"})
    assert r.status_code == 409 and r.json()["detail"]["error_code"] == "DEEP_RESEARCH_BUSY"
    assert _client("prn_ann").post("/research/deep", json={"question": "Laban effort?", "corpus_id": "cinema", "preset": "quick"}).status_code == 200
    DRR._RUNNING.clear()


def test_the_run_slot_is_released_and_a_receipt_written(rec):
    _client().post("/research/deep", json={"question": "How does Laban write effort?", "corpus_id": "cinema", "preset": "quick"})
    assert DRR._RUNNING == {}
    assert rec.receipts and rec.receipts[-1]["kind"] == "deep_research" and rec.receipts[-1]["scope_corpora"] == ["cinema"]
    assert rec.receipts[-1]["out"]["meta"]["deep_research"]["learnings"] >= 1


def test_nothing_found_ends_with_an_error_frame(rec):
    frames = _frames(_client().post("/research/deep", json={"question": "nothing here", "corpus_id": "cinema", "preset": "quick"}).text)
    errors = [d for k, d in frames if k == "error"]
    assert errors and errors[0]["error_code"] == "NOTHING_FOUND" and frames[-1][0] == "done"


def test_a_slow_stream_sends_keep_alive_comments(rec, monkeypatch):
    monkeypatch.setattr(DRR, "HEARTBEAT_S", 0.05)
    slow = DRR._report_tokens

    def slow_report(synth, system, prompt, cancel):
        time.sleep(0.3)
        return slow(synth, system, prompt, cancel)
    monkeypatch.setattr(DRR, "_report_tokens", slow_report)
    frames = _frames(_client().post("/research/deep", json={"question": "How does Laban write effort?", "corpus_id": "cinema", "preset": "quick"}).text)
    assert any(k == "comment" for k, _ in frames)


def test_the_web_boundary_opens_it_to_signed_in_users():
    assert B.classify("POST", "/research/deep") == B.USER
    assert B.classify("GET", "/research/deep") is None


def test_the_research_lanes_prefer_their_own_pin_then_the_compilers():
    pins = {"deep_research": ["lane_a"], "chat_compiler": ["lane_c"]}
    assert DRR.research_lane_names(pins.get, "chat_compiler") == ["lane_a"]
    assert DRR.research_lane_names({"chat_compiler": ["lane_c"]}.get, "chat_compiler") == ["lane_c"]
    assert DRR.research_lane_names({}.get, "chat_compiler") == []


def test_the_registry_pins_deep_research():
    import json
    import pathlib
    cfg = json.loads((pathlib.Path(__file__).resolve().parents[2] / "config" / "cloud_providers.json").read_text())
    assert cfg["stage_pins"]["deep_research"], "config/llm_accounts.yaml must pin deep_research (generated into cloud_providers.json)"


def test_an_engine_mode_search_feeds_the_research(rec, monkeypatch):
    """DR4 (live, 2026-09-26): HYBRID answers `/retrieve` with a flat `evidence` list and no `evidence_rows` (only the default
    lane builds those), so all 20 live searches came back empty. The route now builds the rows from that list, like chat."""
    import orchestrator.api.retrieve as RT
    built = []

    async def engine_shape(req):
        return {"evidence": [{"chunk_id": "chunk_aaa", "text": "Effort has four factors.", "rerank_score": 0.4},
                             {"chunk_id": "chunk_bbb", "text": "Notation writes time and weight.", "rerank_score": 0.2},
                             {"chunk_id": "chunk_aaa", "text": "Effort has four factors.", "rerank_score": 0.1}],
                "selected_documents": [{"doc_id": "d1", "corpus_id": "cinema"}], "meta": {"mode": "HYBRID"}}
    monkeypatch.setattr(RT, "_retrieve_impl", engine_shape)

    def fake_build(response, corpus_ids, limit):
        built.append(([c["chunk_id"] for c in response["child_evidence"]], list(corpus_ids), limit))
        by_id = {r["id"]: r for r in ROWS}
        return [by_id[c["chunk_id"]] for c in response["child_evidence"]]
    monkeypatch.setattr(DRR, "_build_rows", fake_build, raising=False)
    frames = _frames(_client().post("/research/deep", json={"question": "How does Laban write effort?", "corpus_id": "cinema",
                                                            "preset": "quick"}).text)
    assert [d for k, d in frames if k == "error"] == []
    answer = next(d for k, d in frames if k == "answer")
    assert answer["result"]["citations"][0]["id"] == "chunk_aaa"
    assert built and built[0][0] == ["chunk_aaa", "chunk_bbb"] and built[0][1] == ["cinema"]


def test_rows_come_from_evidence_rows_first_and_nothing_builds_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(DRR, "_build_rows", lambda *a: calls.append(a) or [], raising=False)
    assert DRR.evidence_rows_of({"evidence_rows": ROWS, "evidence": [{"chunk_id": "x"}]}, ["cinema"], 5) == ROWS
    assert DRR.evidence_rows_of({"evidence_rows": [], "evidence": []}, ["cinema"], 5) == []
    assert calls == []


def test_an_empty_report_is_an_error_not_a_blank_answer(rec, monkeypatch):
    """DR4 (live, 2026-09-26): 1 of 5 runs streamed a blank "unsupported" answer after 23 learnings — the report model
    returned nothing and no error was raised."""
    monkeypatch.setattr(DRR, "_report_tokens", lambda synth, system, prompt, cancel: iter(["", "  "]))
    frames = _frames(_client().post("/research/deep", json={"question": "How does Laban write effort?", "corpus_id": "cinema",
                                                            "preset": "quick"}).text)
    errors = [d for k, d in frames if k == "error"]
    assert errors and errors[0]["error_code"] == "REPORT_EMPTY" and errors[0]["summary"]["learnings"] >= 1
    assert not [d for k, d in frames if k == "answer"] and frames[-1][0] == "done"
    assert rec.receipts and rec.receipts[-1]["error"] == "REPORT_EMPTY"


def test_the_report_step_applies_chats_thinking_rule(monkeypatch):
    """The report is the composer model's synthesis, so it takes chat's reasoning policy (CHAT_SYNTHESIS): DeepSeek v4 with
    thinking left on can spend the whole token budget thinking and answer nothing."""
    import threading as _th

    import litellm
    import orchestrator.api.ui as UI
    from polymath_shared.reasoning_policy import CHAT_SYNTHESIS, apply_litellm
    monkeypatch.setenv("POLYMATH_REASONING_POLICY", "1")
    monkeypatch.setattr(UI, "_chat_max_tokens", lambda: 1000)
    monkeypatch.setattr(UI, "_litellm_credentials", lambda model: {})
    sent = {}

    class _Delta:
        content = "Report [c1]."

    class _Choice:
        delta = _Delta()

    class _Chunk:
        choices = (_Choice(),)

    def fake_completion(**kw):
        sent.update(kw)
        return iter([_Chunk()])
    monkeypatch.setattr(litellm, "completion", fake_completion)
    model = "anthropic/deepseek-v4-flash-0731"
    assert "".join(DRR._report_tokens("litellm:" + model, "sys", "prompt", _th.Event())) == "Report [c1]."
    expected = {"model": model, "messages": sent["messages"], "stream": True, "timeout": 300, "max_tokens": 1000}
    applied = apply_litellm(expected, CHAT_SYNTHESIS, model)
    assert applied, "the policy must say something about this model, or the test proves nothing"
    assert sent == expected

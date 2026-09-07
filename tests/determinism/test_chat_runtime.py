"""CHAT-RUNTIME-V1 (CHAT-QUERY-COMPILER-PLAN §3.7 / §4 P1.f): /chat == /chat/stream
== MCP `ask` modulo transport.

Pure: the stores (Postgres scope / resolvers / summaries), the sidecars
(embedder, judge, Qdrant, entity cards, graph expander) and the LLM are faked
exactly the way tests/determinism/test_chat_modes.py fakes them; the retrieval
composition (`chat_retrieve_mode`), the evidence bundle, carry admission, the
prompt builder and the deterministic synthesizer are REAL. `run_chat(req)` and
the drained `chat_events(req)` answer frame must then agree on every
authority: task type, resolved request, the retrieval decision, the evidence
ids in order, carry admission, the executed mode, the degraded list, the
synthesis contract — and on the receipt payload (kind / client / route are the
transport's tags). Live (skips when 127.0.0.1:7200 is unreachable): the same
request on both routes yields the same plan and the same evidence ids.
"""
from __future__ import annotations

import contextlib
import functools
import json
import pathlib
import sys
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from orchestrator.api import chat as chat_mod  # noqa: E402
from orchestrator.api import chat_retrieval as cr  # noqa: E402
from orchestrator.api import evidence as evidence_mod  # noqa: E402
from orchestrator.api import fast as fast_api  # noqa: E402
from orchestrator.api import retrieve as retrieve_mod  # noqa: E402
from orchestrator.api import ui  # noqa: E402
from polymath_shared import chat_plan as cp  # noqa: E402
from polymath_shared import query_receipts as qr  # noqa: E402
from polymath_shared.query_scope import QueryScope  # noqa: E402

QUERY = "what does RAPO say about prompts"
BASE = {"message": QUERY, "corpus_id": "cinema", "mode": "HYBRID", "compiler": "off",
        "synthesizer": "deterministic-template-v3"}
#: the real composition and carry admission, bound ONCE — a second harness in the same test must wrap
#: the originals, never the previous harness's spy (which would record every call twice)
_REAL_MODE = cr.chat_retrieve_mode
_REAL_ADMIT = ui._admit_carry
CARRY = [{"locator": "chunk:carry1@0:10", "chunk_id": "carry1", "preview": "p"},
         {"locator": "chunk:carry2@0:10", "chunk_id": "carry2", "preview": "p"}]
HISTORY = [{"role": "user", "content": "draft me a prompt"}, {"role": "assistant", "content": "DRAFT PROMPT v1"}]
UA = "parity-test/1.0"


# ---------------------------------------------------------------- fakes: stores, sidecars, LLM

class _Cursor:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _Conn:
    def execute(self, sql, params=None):
        return _Cursor()


@contextlib.contextmanager
def _fake_tx():
    yield _Conn()


def _chunk_row(cid: str):
    doc = "d3" if cid.startswith("sp_") else ("dcarry" if cid.startswith("carry") else cid.split("_")[0])
    text = f"{cid}: RAPO shapes prompt optimization with reward models, says the book."
    return {"chunk_id": cid, "doc_id": doc, "text": text, "char_start": 0, "char_end": len(text), "heading_path": ["Ch 1", cid]}


def _fact(fid: str):
    return {"fact_id": fid, "predicate": "causes", "subject_id": f"e{fid[1:]}", "object_id": f"e{int(fid[1:]) + 1}",
            "qualifiers": {}, "decision": "ACCEPT", "rule_id": "r1", "rule_version": "1.0.1",
            "provenance": {"roleset": "cause.01", "resource_contract_id": "03a513ec", "compiled_lexical_sha256": "5c58adbd"}}


class Runtime:
    """Every store and sidecar behind the chat runtime, faked deterministically; the composition is real.
    Records the engine's call arguments (spy on `chat_retrieve_mode`) and every receipt payload."""

    def __init__(self, monkeypatch, *, corpora=("cinema",), rerank_note=None, scope_error=None, engine_error=None, plan=None):
        self.calls: list[dict] = []
        self.receipts: list[dict] = []
        h = self
        monkeypatch.setenv("POLYMATH_CHAT_COMPILER", "off")            # never reach a compiler lane from a test
        monkeypatch.delenv("POLYMATH_CHAT_RETRIEVAL", raising=False)
        monkeypatch.setattr(ui, "tx", _fake_tx)

        def scope(conn, req):
            if scope_error is not None:
                raise scope_error
            return QueryScope("CORPUS" if len(corpora) == 1 else "CORPORA", tuple(corpora))
        monkeypatch.setattr(retrieve_mod, "resolve_http_scope", scope)
        monkeypatch.setattr(evidence_mod, "_resolve_chunk", _chunk_row)
        monkeypatch.setattr(evidence_mod, "_resolve_document", lambda did: {"doc_id": did, "corpus_id": "cinema", "source_name": f"{did}.md"})
        monkeypatch.setattr(evidence_mod, "_resolve_entity", lambda eid: {"entity_id": eid, "core_type": "CONCEPT", "normalized_surface": eid.upper()})
        monkeypatch.setattr(evidence_mod, "_resolve_evidence_rows", lambda fid: [
            {"evidence_id": f"ev_{fid}", "fact_id": fid, "doc_id": "d1", "chunk_id": "d1_g_c0", "span_offsets": {},
             "rule_id": "r1", "extractor_version": "1.0", "rule_version": "1.0.1"}])
        monkeypatch.setattr(evidence_mod, "_resolve_fact", _fact)

        def fake_embed(texts):
            return [[0.1 * (i + 1), 0.2] for i, _ in enumerate(texts)]

        def fake_rerank(q, rows):
            if rerank_note:
                fast_api._RERANK_DEGRADED.set(rerank_note)
            return sorted([dict(r, rerank_score=1.0 - i * 0.01) for i, r in enumerate(rows)], key=lambda r: -r["rerank_score"])

        class FakeSearcher:
            def __init__(self, client, collections, query=None):
                self.latency = {}
                self._hidden_cache = {}

            def _hidden_for(self, cid):
                return []

            def _search(self, collection, vector, filters, limit):
                kind = filters["representation_kind"]
                if kind == "routing_child":
                    parent = filters.get("parent_id")
                    docs = (filters["doc_id"],) if parent else ("d1", "d2")
                    return [{"payload": {"chunk_id": f"{d}_{parent or 'g'}_c{i}", "doc_id": d, "parent_id": parent or f"{d}_p",
                                         "text": "reward models shape prompt optimization", "corpus_id": "cinema"}, "score": 1 - i * 0.01}
                            for i in range(min(limit, 3)) for d in docs]
                if kind == "routing_document_summary":
                    return [{"payload": {"doc_id": d, "summary_id": f"s_{d}", "text": f"summary of {d}", "corpus_id": "cinema"}, "score": 0.9 - i * 0.1}
                            for i, d in enumerate(("d1", "d2"))]
                if kind == "routing_section_summary":
                    return [{"payload": {"doc_id": d, "parent_id": f"{d}_p", "summary_id": f"sec_{d}", "text": "sec", "corpus_id": "cinema"}, "score": 0.9 - i * 0.1}
                            for i, d in enumerate(("d1", "d2"))]
                return []

            def sparse_search(self, collection, sparse_query, filters, limit):
                key = "_".join(str(i) for i in sparse_query[0])
                return [{"payload": {"chunk_id": f"sp_{key}", "doc_id": "d3", "parent_id": "d3_p", "text": "RAPO", "corpus_id": "cinema"}, "score": 12.0}]

        class FakeQdrant:
            def __init__(self, *a, **k):
                pass

            def close(self):
                pass

        def fake_cards(client, collections, corpus_id, query, qvec, limit=8):
            return [{"card_id": f"card{i}", "entity_id": f"ent-{i}", "doc_ids": ["d1"], "text": "card", "score": 1 - i * 0.01, "lane": "dense"} for i in range(3)]

        def fake_graph(surfaces, corpus_ids, preferred, seed_entity_ids=None, document_ids=None, max_seeds=None):
            return [{"fact_id": f"f{i}", "predicate": "causes", "subject_id": f"e{i}", "subject": f"S{i}", "object_id": f"e{i + 1}", "object": f"O{i}"} for i in range(4)]

        monkeypatch.setattr(cr, "_embed_queries", fake_embed)
        monkeypatch.setattr(cr, "_rerank_children", fake_rerank)
        monkeypatch.setattr(cr, "FastSearcher", FakeSearcher)
        monkeypatch.setattr(cr, "QdrantClient", FakeQdrant)
        monkeypatch.setattr(cr, "entity_card_probe", fake_cards)
        monkeypatch.setattr(cr, "graph_expand_or_502", fake_graph)
        monkeypatch.setattr(cr, "_ensure_fast_ready", lambda cid: None)
        monkeypatch.setattr(cr, "_corpus_collections", lambda ids: {i: f"coll-{i}" for i in ids})
        monkeypatch.setattr(cr, "_region_lookup", lambda ids: {})
        monkeypatch.setattr(cr, "_neighbor_lookup", lambda want, d: [])
        monkeypatch.setattr(cr, "_presentation_joins", lambda cids, dids: {})

        def spy(mode, query, corpus_id, **kw):
            h.calls.append({"mode": mode, "query": query, "corpus_id": corpus_id, **kw})
            if engine_error is not None:
                raise engine_error
            return _REAL_MODE(mode, query, corpus_id, **kw)
        monkeypatch.setattr(cr, "chat_retrieve_mode", spy)

        scores = {"carry1": 0.9, "carry2": 0.1}                       # carry2 dies at the admission floor (0.25)

        def scorer(q, texts):
            return [scores.get(t.split(":")[0], 0.5) for t in texts]
        monkeypatch.setattr(ui, "_admit_carry", functools.partial(_REAL_ADMIT, scorer=scorer))

        def fake_gen(model, query, bundle, graph_facts, history, carry_context, reasoning=None, reasoning_blend=None,
                     style="neutral", plan=None, coverage=None):
            messages = ui._grounded_messages(query, bundle, graph_facts, history, carry_context, reasoning, reasoning_blend,
                                             style=style, plan=plan, coverage=coverage)
            yield {"prompt": ui._prompt_stats(messages, carry_context, 0)}
            for tok in ("RAPO shapes prompts [S1]", " and reward models matter [S2].", " Ignore [S99]."):
                yield {"token": tok}
        monkeypatch.setattr(ui, "_ollama_generate", fake_gen)
        if plan is not None:
            monkeypatch.setattr(ui, "_compile_chat_plan", lambda *a, **k: plan())

        def rec(tx_factory, **kw):
            h.receipts.append(kw)
            return "q_test"
        monkeypatch.setattr(qr, "record_query_receipt", rec)
        monkeypatch.setattr(chat_mod, "record_query_receipt", rec)


def _plan(**over) -> cp.ChatPlan:
    """A fixed compiled plan (the compiler lane is faked): two typed queries, one exact term."""
    raw = {"resolved_request": "what does RAPO say about prompts and reward models", "task_type": "GROUNDED_QA",
           "evidence_policy": "corpus_grounded", "retrieval_required": True,
           "queries": [{"id": "q0", "type": "PRIMARY", "query": "RAPO prompts", "weight": 1.0},
                       {"id": "q1", "type": "MECHANISM", "query": "reward models for prompts", "weight": 0.8}],
           "semantic_queries": [], "exact_terms": ["RAPO"], "entities": [], "must_answer": [], "user_constraints": [],
           "response_type": "answer", "antecedent": None, "graph_useful": False}
    raw.update(over)
    plan, err = cp.validate_plan(raw, QUERY)
    assert plan is not None, err
    plan.compiler = {"fallback": False, "reason": None, "model": "fake", "wall_ms": 1.0, "over_budget": False,
                     "history_turns": 0, "raw_chars": 10, "corrections": []}
    return plan


def _artifact_plan() -> cp.ChatPlan:
    return _plan(task_type="CONTINUE_PRIOR_ARTIFACT", evidence_policy="conversation", retrieval_required=False, queries=[],
                 response_type="artifact", antecedent={"turn": -1, "kind": "assistant_artifact", "summary": "draft"})


# ---------------------------------------------------------------- transports

def _frames(text: str) -> list[tuple[str, dict]]:
    out, cur = [], None
    for line in text.split("\n"):
        if line.startswith("event:"):
            cur = line[6:].strip()
        elif line.startswith("data:"):
            out.append((cur, json.loads(line[5:].strip())))
    return out


def _seq(frames) -> list[tuple[str, str | None]]:
    """(event, stage) in order, token runs collapsed to one marker."""
    out: list[tuple[str, str | None]] = []
    for ev, d in frames:
        item = (ev, d.get("stage") if ev == "phase" else None)
        if out and out[-1][0] == "token" and ev == "token":
            continue
        out.append(item)
    return out


def _stream(body: dict) -> list[tuple[str, dict]]:
    """The stream transport, drained in-process: the frames of chat_events."""
    return _frames("".join(ui.chat_events(ui.StreamChatRequest(**body))))


def _answer(frames) -> dict:
    return next(d for ev, d in frames if ev == "answer")


def _error(frames) -> dict:
    return next(d for ev, d in frames if ev == "error")


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(chat_mod.router)
    app.include_router(ui.router)
    return app


def _view(result: dict, retrieval: dict) -> dict:
    """The authorities the plan says must agree on every route (§4 P1.f), projected from one answer."""
    meta = result.get("meta") or {}
    plan = retrieval.get("chat_plan") or {}
    return {
        "task_type": meta.get("task_type"), "resolved_request": plan.get("resolved_request"),
        "retrieval_skipped": plan.get("retrieval_skipped"), "plan": plan,
        "evidence_ids": [e.get("chunk_id") for e in retrieval.get("legend") or []],
        "chunk_locators": [c["locator"] for c in retrieval.get("chunks") or []],
        "used_evidence": retrieval.get("used_evidence"), "carry": retrieval.get("carry"),
        "mode": retrieval.get("mode"), "engine": retrieval.get("engine"), "degraded": retrieval.get("degraded"),
        "prompt_contract": meta.get("prompt_contract"), "prompt": meta.get("prompt"), "meta_carry": meta.get("carry"),
        "answer": result.get("answer"), "citations": result.get("citations"), "claims": result.get("claims"),
        "verdict": meta.get("verdict"), "aspects": retrieval.get("aspects"), "composition": retrieval.get("composition"),
        "funnel": retrieval.get("funnel"), "arrivals": retrieval.get("arrivals"), "evidence_count": retrieval.get("evidence_count"),
        "graph_fact_count": retrieval.get("graph_fact_count"), "graph_bounds": retrieval.get("graph_bounds"),
        "wildcard": retrieval.get("wildcard"),
    }


def _receipt_view(r: dict) -> dict:
    """A receipt payload minus the transport's tags (kind, client, meta.route) and wall-clock numbers."""
    out = dict(r.get("out") or {})
    meta = {k: v for k, v in (out.get("meta") or {}).items() if k not in ("phase_ms", "route")}
    if out:
        out["meta"] = meta
    req = r["req"]
    return {"question": r["question"], "req": req.model_dump() if hasattr(req, "model_dump") else req,
            "scope_corpora": r["scope_corpora"], "scope_kind": r["scope_kind"], "out": out, "error": r.get("error")}


# ---------------------------------------------------------------- 1. compiler off: run_chat == the stream's answer frame

@pytest.mark.parametrize("mode", ["VECTOR", "HYBRID", "GRAPH", "WILDCARD"])
def test_run_chat_and_the_stream_answer_frame_agree_on_every_authority_with_the_compiler_off(monkeypatch, mode):
    body = dict(BASE, mode=mode, carry_context=CARRY, history=HISTORY)
    hs = Runtime(monkeypatch, rerank_note="reranker parked: sidecar unavailable")
    frames = _stream(body)
    frame = _answer(frames)
    stream_calls, stream_receipts = list(hs.calls), list(hs.receipts)
    hc = Runtime(monkeypatch, rerank_note="reranker parked: sidecar unavailable")
    out = ui.run_chat(ui.StreamChatRequest(**body))
    a, b = _view(frame["result"], frame["retrieval"]), _view(out, out["retrieval"])
    assert a == b, {k: (a[k], b[k]) for k in a if a[k] != b[k]}
    # the same engine call, the same decision: mode / compiled text / exact terms / subqueries / graph verdict
    assert hc.calls == stream_calls and len(hc.calls) == 1 and hc.calls[0]["mode"] == mode and hc.calls[0]["query"] == QUERY
    # the evidence is real and ordered; carry admitted one of two (floor), reranker degradation carried on both routes
    assert b["evidence_ids"] and b["evidence_ids"] == a["evidence_ids"] and "carry1" in b["evidence_ids"] and "carry2" not in b["evidence_ids"]
    assert b["carry"]["admitted"] == 1 and b["carry"]["dropped_floor"] == 1 and b["carry"]["admitted_ids"] == ["carry1"]
    assert [d["component"] for d in b["degraded"]] == ["reranker"] and b["prompt_contract"] == "synthesis-v2"
    assert b["mode"] == mode and b["engine"] == "chat-retrieval-v2" and b["retrieval_skipped"] is None and b["plan"] == {}
    # the /chat shape: the result keys, the retrieval block, the phases, the runtime tag, the EXECUTED mode
    assert {"answer", "citations", "claims", "meta", "retrieval", "phases", "kind", "latency_ms", "runtime"} <= set(out)
    assert out["runtime"] == "chat-runtime-v1" and out["kind"] == "chat" and out["meta"]["mode"] == mode
    assert out["meta"]["retrieval_mode"] == mode and out["meta"]["retrieval_engine"] == "chat-retrieval-v2"
    assert out["meta"]["funnel"] == frame["retrieval"]["funnel"] and out["meta"]["used_evidence"] == frame["retrieval"]["used_evidence"]
    assert [p["stage"] for p in out["phases"]] == [d["stage"] for ev, d in frames if ev == "phase"]
    # ONE receipt per route with the same payload; kind / client / route are the transport's
    assert len(stream_receipts) == 1 and len(hc.receipts) == 1
    assert _receipt_view(stream_receipts[0]) == _receipt_view(hc.receipts[0])
    assert stream_receipts[0]["kind"] == "chat_stream" and stream_receipts[0]["client"] == "ui-stream"
    assert stream_receipts[0]["out"]["meta"]["route"] == "chat/stream" and hc.receipts[0]["out"]["meta"]["route"] == "chat"
    assert hc.receipts[0]["kind"] == "chat" and hc.receipts[0]["client"] is None   # a bare run_chat: the JSON transport's kind, no client
    assert hc.receipts[0]["out"]["citations"] == out["citations"] and hc.receipts[0]["out"]["claims"] == out["claims"]


def test_engine_deadline_receipts_ride_the_degraded_list_on_both_routes_and_in_the_receipt(monkeypatch):
    """P1.d/P1.e deadline receipts (`rerank_timeout`, `<lane>_timeout`, `embed_deadline`, `graph_degraded`, `wildcard`)
    live in the engine's meta.degraded; both transports must show them in retrieval.degraded and in the query receipt —
    a judge that timed out on one route is the documented cause of a differing evidence order, never a silent one."""
    body = dict(BASE, mode="HYBRID")
    receipt = {"component": "rerank_timeout", "effect": "fusion order kept (no judge)", "reason": "judge past 8.0 s"}

    def runtime():
        h = Runtime(monkeypatch, rerank_note="reranker parked: sidecar unavailable")
        inner = cr.chat_retrieve_mode

        def with_deadline_receipt(mode, query, corpus_id, **kw):
            out = inner(mode, query, corpus_id, **kw)
            out["meta"].setdefault("degraded", []).append(dict(receipt))
            return out
        monkeypatch.setattr(cr, "chat_retrieve_mode", with_deadline_receipt)
        return h

    hs = runtime()
    frame = _answer(_stream(body))
    hc = runtime()
    out = ui.run_chat(ui.StreamChatRequest(**body))
    for retrieval in (frame["retrieval"], out["retrieval"]):
        assert [d["component"] for d in retrieval["degraded"]] == ["reranker", "rerank_timeout"], retrieval["degraded"]
        assert retrieval["degraded"][-1]["reason"] == "judge past 8.0 s"
    for r in (hs.receipts[0], hc.receipts[0]):
        assert [d["component"] for d in r["out"]["meta"]["degraded"]] == ["reranker", "rerank_timeout"], r["out"]["meta"].get("degraded")


def test_llm_synthesizer_parity_used_evidence_legend_and_prompt(monkeypatch):
    body = dict(BASE, synthesizer="ollama:fake", carry_context=CARRY, history=HISTORY, reasoning="none")
    Runtime(monkeypatch)
    frame = _answer(_stream(body))
    Runtime(monkeypatch)
    out = ui.run_chat(ui.StreamChatRequest(**body))
    a, b = _view(frame["result"], frame["retrieval"]), _view(out, out["retrieval"])
    assert a == b, {k: (a[k], b[k]) for k in a if a[k] != b[k]}
    assert out["kind"] == "llm" and out["answer"] == "RAPO shapes prompts [S1] and reward models matter [S2]. Ignore [S99]."
    assert b["used_evidence"] == b["evidence_ids"][:2] and len(b["used_evidence"]) == 2      # [S99] is outside the legend
    assert b["prompt"]["prompt_chars"] > 0 and b["prompt"]["carry_in"] == 2 and b["prompt"]["carry_in_prompt"] == 1
    assert b["meta_carry"]["admitted"] == 1 and out["meta"]["mode"] == "HYBRID" and out["model"] == "fake"


# ---------------------------------------------------------------- 2. the compiled plan is identical on both routes

def test_shadow_plan_is_identical_on_both_routes_and_changes_nothing(monkeypatch):
    body = dict(BASE, compiler="shadow")
    hs = Runtime(monkeypatch, plan=_plan)
    frames = _stream(body)
    frame = _answer(frames)
    hc = Runtime(monkeypatch, plan=_plan)
    out = ui.run_chat(ui.StreamChatRequest(**body))
    assert frame["retrieval"]["chat_plan"] == out["retrieval"]["chat_plan"]
    plan = out["retrieval"]["chat_plan"]
    assert plan["task_type"] == "GROUNDED_QA" and [q["query"] for q in plan["queries"]] == ["RAPO prompts", "reward models for prompts"]
    assert plan["resolved_request"] == "what does RAPO say about prompts and reward models" and "retrieval_skipped" not in plan
    assert _view(frame["result"], frame["retrieval"]) == _view(out, out["retrieval"])
    # shadow: receipted and shown (a trailing compile phase), retrieval still on the raw message with no subqueries
    assert hs.calls == hc.calls and hc.calls[0]["query"] == QUERY and hc.calls[0]["subqueries"] == () and hc.calls[0]["exact_terms"] == ()
    assert _seq(frames)[-3:] == [("phase", "compile"), ("answer", None), ("done", None)]
    assert out["phases"][-1]["stage"] == "compile" and out["phases"][-1]["mode"] == "shadow"
    assert hs.receipts[0]["out"]["meta"]["chat_plan"] == hc.receipts[0]["out"]["meta"]["chat_plan"] == plan


def test_compiler_on_drives_the_same_retrieval_decision_on_both_routes(monkeypatch):
    body = dict(BASE, compiler="on", synthesizer="ollama:fake")
    hs = Runtime(monkeypatch, plan=_plan)
    frame = _answer(_stream(body))
    hc = Runtime(monkeypatch, plan=_plan)
    out = ui.run_chat(ui.StreamChatRequest(**body))
    a, b = _view(frame["result"], frame["retrieval"]), _view(out, out["retrieval"])
    assert a == b, {k: (a[k], b[k]) for k in a if a[k] != b[k]}
    assert b["task_type"] == "GROUNDED_QA" and b["retrieval_skipped"] is False and b["plan"]["retrieval_query"] == "RAPO prompts"
    assert hs.calls == hc.calls == [{"mode": "HYBRID", "query": "RAPO prompts", "corpus_id": "cinema", "graph_useful": False,
                                     "exact_terms": ("RAPO",), "subqueries": (("q1", "MECHANISM", "reward models for prompts", 0.8),)}]
    assert set(b["aspects"]) == {"q0", "q1"} and out["meta"]["task_type"] == "GROUNDED_QA" and out["meta"]["retrieval_required"] is True
    # a conversation-policy plan: no retrieval fired, on either route
    body2 = dict(body, carry_context=CARRY, history=HISTORY)
    hs2 = Runtime(monkeypatch, plan=_artifact_plan)
    frames2 = _stream(body2)
    frame2 = _answer(frames2)
    hc2 = Runtime(monkeypatch, plan=_artifact_plan)
    out2 = ui.run_chat(ui.StreamChatRequest(**body2))
    a2, b2 = _view(frame2["result"], frame2["retrieval"]), _view(out2, out2["retrieval"])
    assert a2 == b2 and hs2.calls == hc2.calls == []
    # CARRY-ARTIFACT-V1: the previous answer's cited passages ride along as evidence on a no-retrieval turn
    assert b2["task_type"] == "CONTINUE_PRIOR_ARTIFACT" and b2["retrieval_skipped"] is True
    # `evidence_count` counts RETRIEVED passages (0 on a skipped turn); the carried ones are in the bundle ids + carry.admitted
    assert sorted(b2["evidence_ids"]) == ["carry1", "carry2"] and b2["evidence_count"] == 0
    # CARRY-ARTIFACT-V1 (2026-09-07): a no-retrieval turn KEEPS the previous answer's evidence (no relevance gate)
    assert b2["carry"]["in"] == 2 and b2["carry"]["mode"] == "artifact" and b2["carry"]["admitted"] == b2["carry"]["hydrated"] >= 1
    assert b2["carry"]["dropped_floor"] == 0 and b2["engine"] is None
    assert ("phase", "retrieve_skipped") in _seq(frames2) and [p["stage"] for p in out2["phases"]] == [s for ev, s in _seq(frames2) if ev == "phase"]


# ---------------------------------------------------------------- 3. errors: the stream's frame status is /chat's HTTP status

@pytest.mark.parametrize("case,status,code", [
    ("scope404", 404, "QUERY_SCOPE_UNKNOWN"),
    ("engine502", 502, "qdrant_unavailable"),
    ("engine500", 500, "RuntimeError"),
    ("multi", 422, "mode_requires_single_corpus"),
])
def test_a_runtime_error_surfaces_on_chat_with_the_same_status_as_the_stream_frame(monkeypatch, case, status, code):
    kw = {"scope404": dict(scope_error=HTTPException(404, {"error_code": "QUERY_SCOPE_UNKNOWN", "message": "corpus 'nope' not found"})),
          "engine502": dict(engine_error=HTTPException(502, {"error_code": "qdrant_unavailable", "message": "qdrant unavailable: X"})),
          "engine500": dict(engine_error=RuntimeError("boom")),
          "multi": dict(corpora=("cinema", "ecom"))}[case]
    hs = Runtime(monkeypatch, **kw)
    frames = _stream(BASE)
    err = _error(frames)
    assert err["error_code"] == code and err.get("status") == (status if case in ("scope404", "engine502") else None)
    assert frames[-1][0] == "error"                                              # the stream ends on the error frame
    hc = Runtime(monkeypatch, **kw)
    with pytest.raises(HTTPException) as ei:
        ui.run_chat(ui.StreamChatRequest(**BASE))
    assert ei.value.status_code == status and ei.value.detail == {k: v for k, v in err.items() if k != "status"}
    # both routes receipt the failed turn once, with the same error text
    assert len(hs.receipts) == 1 and len(hc.receipts) == 1 and hs.receipts[0]["out"] is None
    assert hs.receipts[0]["error"] == hc.receipts[0]["error"] and code in hc.receipts[0]["error"]
    # and over HTTP the status is the frame's
    Runtime(monkeypatch, **kw)
    r = TestClient(_app()).post("/chat", json=BASE)
    assert r.status_code == status and r.json()["detail"]["error_code"] == code


# ---------------------------------------------------------------- 4. the stream's frames: names and order unchanged by the refactor

@pytest.mark.parametrize("name,body,kw,expected", [
    ("deterministic HYBRID", dict(BASE), {},
     ["scope", "scope_ok", "retrieve", "retrieve_done", "assemble", "assemble_done", "synthesize", "answer", "done"]),
    ("deterministic VECTOR", dict(BASE, mode="VECTOR"), {},
     ["scope", "scope_ok", "retrieve", "retrieve_done", "assemble", "assemble_done", "synthesize", "answer", "done"]),
    ("deterministic GRAPH", dict(BASE, mode="GRAPH"), {},
     ["scope", "scope_ok", "retrieve", "retrieve_done", "graph", "graph_done", "assemble", "assemble_done", "synthesize", "answer", "done"]),
    ("deterministic WILDCARD", dict(BASE, mode="WILDCARD"), {},
     ["scope", "scope_ok", "retrieve", "retrieve_done", "wildcard", "assemble", "assemble_done", "synthesize", "answer", "done"]),
    ("LLM + carry", dict(BASE, synthesizer="ollama:fake", carry_context=CARRY, history=HISTORY), {},
     ["scope", "scope_ok", "retrieve", "retrieve_done", "assemble", "carry", "assemble_done", "generate", "token", "answer", "done"]),
    ("shadow compiler", dict(BASE, compiler="shadow"), dict(plan=_plan),
     ["scope", "scope_ok", "retrieve", "retrieve_done", "assemble", "assemble_done", "synthesize", "compile", "answer", "done"]),
    ("compiler on", dict(BASE, compiler="on", synthesizer="ollama:fake"), dict(plan=_plan),
     ["scope", "scope_ok", "compile", "retrieve", "retrieve_done", "assemble", "assemble_done", "generate", "token", "answer", "done"]),
    ("compiler on, no retrieval", dict(BASE, compiler="on", synthesizer="ollama:fake", carry_context=CARRY, history=HISTORY), dict(plan=_artifact_plan),
     ["scope", "scope_ok", "compile", "retrieve_skipped", "assemble", "carry", "assemble_done", "generate", "token", "answer", "done"]),
    ("multi-corpus scope", dict(BASE), dict(corpora=("cinema", "ecom")), ["scope", "scope_ok", "error"]),
    ("scope 404", dict(BASE), dict(scope_error=HTTPException(404, {"error_code": "QUERY_SCOPE_UNKNOWN", "message": "x"})), ["scope", "error"]),
    ("engine 502", dict(BASE), dict(engine_error=HTTPException(502, {"error_code": "qdrant_unavailable", "message": "x"})),
     ["scope", "scope_ok", "retrieve", "error"]),
    ("engine exception", dict(BASE), dict(engine_error=RuntimeError("boom")), ["scope", "scope_ok", "retrieve", "error"]),
])
def test_stream_frame_names_and_order_are_the_pre_runtime_sequence(monkeypatch, name, body, kw, expected):
    Runtime(monkeypatch, **kw)
    seq = _seq(_stream(body))
    assert [stage or ev for ev, stage in seq] == expected, (name, seq)
    # the stream route is the generator in a StreamingResponse; every frame is `event: …\ndata: <json>\n\n`
    Runtime(monkeypatch, **kw)
    r = TestClient(_app()).post("/chat/stream", json=body)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert [stage or ev for ev, stage in _seq(_frames(r.text))] == expected
    assert all(chunk.startswith("event: ") and "\ndata: " in chunk for chunk in r.text.split("\n\n") if chunk)


# ---------------------------------------------------------------- 5. the HTTP transports: /chat is run_chat; receipts once per call

def test_chat_route_is_the_runtime_with_the_transports_receipt_tags(monkeypatch):
    h = Runtime(monkeypatch)
    client = TestClient(_app())
    r = client.post("/chat", json=BASE, headers={"user-agent": UA})
    assert r.status_code == 200
    out = r.json()
    assert out["runtime"] == "chat-runtime-v1" and out["kind"] == "chat" and out["meta"]["mode"] == "HYBRID"
    assert {"answer", "citations", "claims", "meta", "retrieval", "phases"} <= set(out) and out["retrieval"]["engine"] == "chat-retrieval-v2"
    assert len(h.receipts) == 1 and h.receipts[0]["kind"] == "chat" and h.receipts[0]["client"] == UA
    assert h.receipts[0]["out"]["meta"]["route"] == "chat" and h.receipts[0]["out"]["meta"]["mode"] == "HYBRID"
    chat_receipt = h.receipts[0]
    # the same request on the stream route: one `chat_stream` receipt, the same payload under the stream's tags
    h2 = Runtime(monkeypatch)
    r2 = client.post("/chat/stream", json=BASE, headers={"user-agent": UA})
    frame = _answer(_frames(r2.text))
    assert len(h2.receipts) == 1 and h2.receipts[0]["kind"] == "chat_stream" and h2.receipts[0]["client"] == "ui-stream"
    assert h2.receipts[0]["out"]["meta"]["route"] == "chat/stream"
    assert _receipt_view(chat_receipt) == _receipt_view(h2.receipts[0])
    assert _view(frame["result"], frame["retrieval"]) == _view(out, out["retrieval"])
    # /chat defaults: no mode -> HYBRID; FAST reports the executed composition VECTOR; deterministic synthesizer
    Runtime(monkeypatch)
    body = {k: v for k, v in BASE.items() if k not in ("mode", "synthesizer")}
    o = client.post("/chat", json=body).json()
    assert o["meta"]["mode"] == "HYBRID" and o["kind"] == "chat" and o["claims"] is not None
    Runtime(monkeypatch)
    assert client.post("/chat", json=dict(body, mode="FAST")).json()["meta"]["mode"] == "VECTOR"
    # requests the runtime rejects before it runs: the same 422 on both routes, receipted once by /chat's transport
    for bad, code in ((dict(BASE, message="  "), None), (dict(BASE, mode="LEGACY"), "unknown_mode"),
                      (dict(BASE, synthesizer="nope:x"), "unknown_synthesizer")):
        hb = Runtime(monkeypatch)
        rc = client.post("/chat", json=bad, headers={"user-agent": UA})
        rs = client.post("/chat/stream", json=bad, headers={"user-agent": UA})
        assert rc.status_code == rs.status_code == 422 and rc.json()["detail"] == rs.json()["detail"]
        if code:
            assert rc.json()["detail"]["error_code"] == code
        assert [x["kind"] for x in hb.receipts] == ["chat"] and hb.receipts[0]["error"].startswith("HTTPException") and hb.receipts[0]["client"] == UA


def test_chat_request_maps_every_field_onto_the_runtime_request():
    req = chat_mod.ChatRequest(message="q", corpus_ids=["a", "b"], workspace=None, all_authorized=False, mode="GRAPH", latent=True,
                               utility=False, retrieval="v1", evidence=True, synthesizer="ollama:x", history=HISTORY,
                               carry_context=CARRY, compiler="shadow", reasoning="socratic", reasoning_blend=["a", "b"])
    s = chat_mod.stream_request(req)
    assert isinstance(s, ui.StreamChatRequest)
    for f in ("message", "corpus_id", "corpus_ids", "workspace", "all_authorized", "mode", "latent", "utility", "retrieval",
              "synthesizer", "compiler", "reasoning", "reasoning_blend"):
        assert getattr(s, f) == getattr(req, f), f
    assert [t.model_dump() for t in s.history] == HISTORY and [c.model_dump() for c in s.carry_context] == CARRY
    # every ChatRequest input except the /chat-only response add-on exists on the runtime request
    assert set(chat_mod.ChatRequest.model_fields) - {"evidence"} <= set(ui.StreamChatRequest.model_fields)
    # /chat defaults: HYBRID (CHAT-DEFAULT-HYBRID-V1) and the deterministic synthesizer (the historical contract)
    d = chat_mod.stream_request(chat_mod.ChatRequest(message="q", corpus_id="c"))
    assert d.mode == "HYBRID" and d.synthesizer == "deterministic-template-v3" and d.history == [] and d.carry_context == []
    assert d.compiler is None and d.utility is None and d.latent is None


def test_mcp_ask_posts_to_chat_and_therefore_runs_the_runtime():
    src = (ROOT / "orchestrator" / "orchestrator" / "mcp_server.py").read_text()
    assert '_orch("POST", "/chat", json=body)' in src
    chat_src = (ROOT / "orchestrator" / "orchestrator" / "api" / "chat.py").read_text()
    assert "run_chat(" in chat_src and "hybrid_fast_retrieve" not in chat_src and "assemble_evidence_bundle" not in chat_src


# ---------------------------------------------------------------- live (optional)

def _post(path: str, body: dict):
    req = urllib.request.Request(f"http://127.0.0.1:7200{path}", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    with urllib.request.urlopen(req, timeout=420) as r:
        raw = r.read().decode("utf-8", "replace")
    return json.loads(raw) if path == "/chat" else _answer(_frames(raw))


def test_live_chat_and_stream_agree_on_plan_and_evidence_ids():
    try:
        urllib.request.urlopen("http://127.0.0.1:7200/ready", timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"orchestrator not reachable: {exc}")
    body = {"message": "What does the book say about making your own chroma keyer?", "corpus_id": "cinema", "mode": "HYBRID",
            "compiler": "off", "synthesizer": "deterministic-template-v3"}
    a = _post("/chat", body)
    b = _post("/chat/stream", body)
    ra, rb = a["retrieval"], b["retrieval"]
    assert a["runtime"] == "chat-runtime-v1" and a["meta"]["mode"] == "HYBRID" == rb["mode"]
    assert ra.get("engine") == rb.get("engine") == "chat-retrieval-v2"
    assert ra.get("chat_plan") == rb.get("chat_plan")                           # compiler off: no plan on either route
    assert [e.get("chunk_id") for e in ra.get("legend") or []] == [e.get("chunk_id") for e in rb.get("legend") or []]
    assert [c["locator"] for c in ra["chunks"]] == [c["locator"] for c in rb["chunks"]]
    assert ra.get("used_evidence") == rb.get("used_evidence") and a["citations"] == b["result"]["citations"]

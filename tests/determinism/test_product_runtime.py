"""PRODUCT-SEARCH-E2E in the chat runtime (CHAT-RUNTIME-V1): a product request runs the ONE generator in product mode on every
route — /chat/stream frames, /chat (`run_chat`), /chat/evidence — with the stores, sidecars, LLM and supplier faked (the
test_chat_runtime harness; never CJ or a model for real). A product turn carries `product_research`, never ends as bare
insufficient_evidence, appends its finds to the answer text, steers retrieval toward hypothesis material and receipts counts only;
a non-product question keeps exactly its old shape."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_chat_runtime import BASE, QUERY, Runtime, _answer, _app, _fake_tx, _frames, _stream  # noqa: E402

from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from orchestrator.api import chat as chat_mod  # noqa: E402
from orchestrator.api import ui  # noqa: E402
from polymath_shared import chat_plan as cp  # noqa: E402
from polymath_shared import principal_context  # noqa: E402
from polymath_shared.acquisition import supplier  # noqa: E402
from polymath_shared.product_search import service as PS  # noqa: E402

PRODUCT = "Find me products I could dropship for pet owners in the US"
LLM = dict(BASE, message=PRODUCT, synthesizer="ollama:fake")
BLOCK = ('\n\n```product-hypotheses\n[{"title": "Smart pet feeder", "problem": "missed feeding times", "audience": "pet owners", '
         '"evidence_tags": ["S1"], "search_terms": ["automatic pet feeder"], "confidence": "medium"}, '
         '{"title": "Calming dog bed", "evidence_tags": ["S2"], "search_terms": ["calming dog bed"]}]\n```')
ANSWER = "Two product hypotheses from your library [S1].\n\n1. **Smart pet feeder** — feeding is a recurring friction [S1].\n" \
         "2. **Calming dog bed** — anxious dogs come up again and again [S2]."


def _items(pid: str, title: str) -> dict:
    return {"item_id": f"itm_{pid}", "kind": "listing", "source_id": f"src_{pid}", "excerpt": title,
            "listing": {"title": title, "price_as_listed": "US$19.00", "minimum_order_as_listed": "1 unit", "supplier": "Acme",
                        "discount_price_as_listed": None, "category": "Pets", "image": None, "product_id": pid, "sku": None,
                        "listed_by_stores": "88", "warehouse_inventory": "12"}}


class Product:
    """The product-mode fakes on top of the chat-runtime harness: an LLM that answers with (or without) the hypothesis block and
    records the prompt it was given, and a supplier that records every call and the principal it ran as."""

    def __init__(self, monkeypatch, *, block: bool = True, answer: str = ANSWER, **runtime):
        self.h = Runtime(monkeypatch, **runtime)
        self.calls: list[dict] = []
        self.system: list[str] = []
        me = self

        def fake_gen(model, query, bundle, graph_facts, history, carry_context, reasoning=None, reasoning_blend=None,
                     style="neutral", plan=None, coverage=None):
            messages = ui._grounded_messages(query, bundle, graph_facts, history, carry_context, reasoning, reasoning_blend,
                                             style=style, plan=plan, coverage=coverage)
            me.system.append(messages[0]["content"])
            yield {"prompt": ui._prompt_stats(messages, carry_context, 0)}
            for piece in (answer, BLOCK if block else ""):
                if piece:
                    yield {"token": piece}
        monkeypatch.setattr(ui, "_ollama_generate", fake_gen)

        def fake_search(*, principal_id, query, source="cj", limit=10, **kw):
            me.calls.append({"principal_id": principal_id, "current": principal_context.current(), "query": query,
                             "source": source, "limit": limit})
            if query == "automatic pet feeder":
                return {"status": "OK", "items": [_items("7001", "Automatic Pet Feeder 6L")], "fallback": None, "reason_code": None,
                        "sources": [{"source_id": "src_7001", "url": "https://cjdropshipping.com/product/feeder-p-7001.html"}],
                        "limitations": ["listings from the CJ Dropshipping API"]}
            return {"status": "EMPTY", "items": [], "sources": [], "reason_code": "CJ_EMPTY", "limitations": ["no product"],
                    "fallback": {"kind": "AGENT_REACH", "reason_code": "CJ_EMPTY", "commands": [{"step": 1, "run": "mcporter call x"}]}}
        monkeypatch.setattr(supplier, "search", fake_search)

    @property
    def receipts(self):
        return self.h.receipts

    @property
    def engine_calls(self):
        return self.h.calls


def _phases(frames) -> list[str]:
    return [d.get("stage") for ev, d in frames if ev == "phase"]


def _product_plan() -> cp.ChatPlan:
    """The compiled plan the reproduced bug got (CREATE_FROM_KNOWLEDGE, business-book aspects), with the compiler lane faked."""
    raw = {"resolved_request": PRODUCT, "task_type": "CREATE_FROM_KNOWLEDGE", "evidence_policy": "corpus_grounded",
           "retrieval_required": True,
           "queries": [{"type": "PRIMARY", "query": "dropshipping products for pet owners"},
                       {"type": "MECHANISM", "query": "dropshipping business model", "weight": 0.7}],
           "semantic_queries": [], "exact_terms": [], "entities": [], "must_answer": [], "user_constraints": [],
           "response_type": "artifact", "antecedent": None, "graph_useful": False}
    plan, err = cp.validate_plan(raw, PRODUCT)
    assert plan is not None, err
    plan.compiler = {"fallback": False, "reason": None, "model": "fake", "wall_ms": 1.0, "corrections": []}
    return plan


# ---------------------------------------------------------------- 1. an LLM product turn: hypotheses + CJ finds + the offer

def test_an_llm_product_turn_carries_product_research_and_never_abstains(monkeypatch):
    p = Product(monkeypatch)
    with principal_context.acting_as("prn_fred"):
        frames = _stream(LLM)
    frame = _answer(frames)
    result = frame["result"]
    assert frame["kind"] == "llm"
    block = result["product_research"]
    assert block["contract"] == "product-search-v1" and block["corpus_ids"] == ["cinema"]
    assert result["meta"]["verdict"] in (PS.VERDICT, PS.VERDICT_THIN) and "insufficient" not in result["meta"]["verdict"]
    h1, h2 = block["hypotheses"]
    assert h1["title"] == "Smart pet feeder" and h1["evidence_tags"] == ["S1"] and h1["cj"]["status"] == "OK"
    assert h1["cj"]["items"][0] == {"title": "Automatic Pet Feeder 6L", "price": "US$19.00", "discount_price": None, "moq": "1 unit",
                                    "image": None, "url": "https://cjdropshipping.com/product/feeder-p-7001.html", "product_id": "7001",
                                    "sku": None, "category": "Pets", "stores_listing": "88", "warehouse_stock": "12", "supplier": "Acme"}
    assert h2["cj"]["status"] == "EMPTY" and h2["cj"]["fallback"]["commands"] == [{"step": 1, "run": "mcporter call x"}]
    assert {h["alibaba"]["status"] for h in block["hypotheses"]} == {"AGENT_REACH_REQUIRED"}
    assert block["next"]["full_research"]["input"] == {"seed": "products for pet owners", "corpus_ids": ["cinema"], "geography": "US"}
    # the answer text: the prose, then the Markdown finds; the machine block is gone
    answer = result["answer"]
    assert answer.startswith("Two product hypotheses from your library [S1].") and "```product-hypotheses" not in answer
    assert "### Supplier finds (CJ Dropshipping)" in answer
    assert "[Automatic Pet Feeder 6L](https://cjdropshipping.com/product/feeder-p-7001.html)" in answer
    assert "offered, not started" in answer
    # the synthesizer was given the PRODUCT HYPOTHESIS contract, closing its system prompt
    assert len(p.system) == 1 and p.system[0].rstrip().endswith("confidence: high, medium or low.")
    assert "PRODUCT HYPOTHESIS CONTRACT" in p.system[0] and "doesn't recommend products" in p.system[0]
    # the principal reached supplier.search, one CJ search per hypothesis, as the turn's principal
    assert [(c["principal_id"], c["current"], c["query"], c["source"], c["limit"]) for c in p.calls] == [
        ("prn_fred", "prn_fred", "automatic pet feeder", "cj", 6), ("prn_fred", "prn_fred", "calming dog bed", "cj", 6)]
    # the frames say what happened, in order
    stages = _phases(frames)
    assert stages.index("product_intent") == stages.index("scope_ok") + 1
    assert stages[-2:] == ["product_search", "product_search_done"] and stages.index("generate") < stages.index("product_search")
    intent = next(d for ev, d in frames if ev == "phase" and d.get("stage") == "product_intent")
    assert intent["rule"] == "dropship_object" and intent["audience"] == "pet owners" and intent["geography"] == "US"
    # one receipt: the verdict and counts only — never an item's text
    assert len(p.receipts) == 1
    meta = p.receipts[0]["out"]["meta"]
    assert meta["verdict"] == result["meta"]["verdict"] and meta["product_search"]["hypotheses"] == 2
    assert meta["product_search"]["statuses"]["cj"] == {"EMPTY": 1, "OK": 1} and "Automatic Pet Feeder" not in json.dumps(meta["product_search"])
    # used_evidence counts the [S#] tags of the prose and of the finds
    assert frame["retrieval"]["used_evidence"] == [e["chunk_id"] for e in frame["retrieval"]["legend"][:2]]


def test_chat_returns_the_same_product_block_at_the_top_level(monkeypatch):
    Product(monkeypatch)
    frames = _stream(LLM)
    frame = _answer(frames)
    Product(monkeypatch)
    out = ui.run_chat(ui.StreamChatRequest(**LLM))
    assert out["product_research"] == frame["result"]["product_research"] and out["meta"]["verdict"] == frame["result"]["meta"]["verdict"]
    assert out["answer"] == frame["result"]["answer"] and out["kind"] == "llm"
    assert [p["stage"] for p in out["phases"]] == _phases(frames)


def test_a_turn_whose_block_cannot_be_read_is_thin_searches_the_intent_terms_and_says_so(monkeypatch):
    p = Product(monkeypatch, block=False)
    result = _answer(_stream(LLM))["result"]
    block = result["product_research"]
    assert result["meta"]["verdict"] == PS.VERDICT_THIN and block["hypotheses"] == []
    assert block["receipts"]["parse"] == {"status": "fallback", "reason": "no_block", "hypotheses": 0, "notes": [], "tags_dropped": 0}
    assert [f["search_term"] for f in block["term_finds"]] == ["pet products", "pet accessories"]
    assert [c["query"] for c in p.calls] == ["pet products", "pet accessories"]
    assert any("could not be read (no_block)" in x for x in block["limitations"])


def test_a_product_step_failure_is_a_typed_degradation_never_a_failed_turn(monkeypatch):
    p = Product(monkeypatch)

    def boom(self, **kw):
        raise RuntimeError("lookup layer down")
    monkeypatch.setattr(PS.ProductTurn, "finish_llm", boom)
    frames = _stream(LLM)
    frame = _answer(frames)
    assert "product_research" not in frame["result"] and frame["result"]["meta"]["verdict"] == "generated"
    deg = [d for d in frame["retrieval"]["degraded"] if d.get("component") == "product_search"]
    assert deg and deg[0]["reason"] == "RuntimeError" and "missing" in deg[0]["effect"]
    assert _phases(frames)[-1] == "product_search_done" and frames[-1][0] == "done"
    assert "product_search" not in p.receipts[0]["out"]["meta"]


# ---------------------------------------------------------------- 2. retrieval is steered toward hypothesis material

def test_with_the_compiler_on_the_plan_gets_product_aspects_inside_its_cap(monkeypatch):
    p = Product(monkeypatch, plan=_product_plan)
    frame = _answer(_stream(dict(LLM, compiler="on")))
    call = p.engine_calls[0]
    assert call["query"] == "dropshipping products for pet owners"                            # q0 still drives lane A
    sub = [(s[0], s[2]) for s in call["subqueries"]]
    assert [s[0] for s in sub] == ["ps1", "ps2", "ps3"] and all("pet owners" in s[1] for s in sub)
    assert len(sub) + 1 <= cp.MAX_QUERIES
    plan = frame["retrieval"]["chat_plan"]
    assert plan["compiler"]["product_search"]["replaced"] == ["q1"] and len(plan["compiler"]["product_search"]["added"]) == 3
    assert frame["result"]["product_research"]["receipts"]["steer"]["mode"] == "plan"


def test_with_the_compiler_off_the_retrieval_text_gets_one_deterministic_addition(monkeypatch):
    p = Product(monkeypatch)
    frame = _answer(_stream(LLM))
    assert p.engine_calls[0]["query"] == f"{PRODUCT} pet owners frustrations, workarounds and unmet needs"
    assert frame["result"]["product_research"]["receipts"]["steer"]["mode"] == "text"


# ---------------------------------------------------------------- 3. deterministic and evidence-only turns

def test_a_deterministic_product_turn_keeps_its_claims_and_points_at_a_model_or_product_search(monkeypatch):
    Product(monkeypatch)
    out = ui.run_chat(ui.StreamChatRequest(**dict(BASE, message=PRODUCT)))
    assert out["kind"] == "chat" and isinstance(out["claims"], list) and isinstance(out["citations"], list)
    assert out["meta"]["verdict"] == PS.VERDICT_TERMS and out["meta"]["grounded_verdict"] in ("supported", "insufficient_evidence")
    assert not out["answer"].startswith("I don't have enough grounded evidence") and "### Supplier finds" in out["answer"]
    block = out["product_research"]
    assert block["hypotheses"] == [] and block["term_finds"][0]["search_term"] == "pet products"
    assert block["next"]["hypotheses"]["how"] == "ask_with_model_or_product_search"


def test_an_evidence_only_product_turn_attaches_the_block_and_agent_steps(monkeypatch):
    p = Product(monkeypatch)
    out = ui.run_chat(ui.StreamChatRequest(**dict(BASE, message=PRODUCT, evidence_only=True)))
    assert out["kind"] == "evidence" and out["synthesis_performed"] is False and out["evidence_packet"]["evidence"]
    block = out["product_research"]
    assert block["hypotheses"] == [] and [f["search_term"] for f in block["term_finds"]] == ["pet products", "pet accessories"]
    assert block["next"]["hypotheses"]["how"] == "agent_forms_then_product_search"
    assert len(out["agent_steps"]) == 5 and "product_search" in out["agent_steps"][1]
    # the receipt keeps what the agent was handed: the evidence count and the packet's chunk ids, no text
    r = p.receipts[0]
    ids = list(dict.fromkeys(e["chunk_id"] for e in out["evidence_packet"]["evidence"]))
    assert r["out"]["meta"]["used_evidence"] == ids and r["out"]["meta"]["n_evidence"] == len(out["evidence_packet"]["evidence"])
    assert [e["chunk_id"] for e in r["out"]["evidence"]] == [e["chunk_id"] for e in out["evidence_packet"]["evidence"]]
    assert set().union(*(set(e) for e in r["out"]["evidence"])) == {"chunk_id", "doc_id"}
    assert r["out"]["meta"]["product_search"]["term_finds"] == 2


def test_every_evidence_only_receipt_now_counts_its_evidence(monkeypatch):
    """/chat/evidence receipts stored `evidence` as NULL: the count and the chunk ids now ride on every evidence-only turn."""
    from polymath_shared import query_receipts as qr
    p = Product(monkeypatch)
    ui.run_chat(ui.StreamChatRequest(**dict(BASE, evidence_only=True)))
    r = p.receipts[0]
    assert "product_search" not in r["out"]["meta"]
    summ = qr.summarize_response("chat", r["out"])
    assert summ["evidence"] == len(r["out"]["evidence"]) > 0 and summ["meta"]["used_evidence"] == r["out"]["meta"]["used_evidence"]
    assert summ["source_docs"] == sorted({e["doc_id"] for e in r["out"]["evidence"] if e["doc_id"]})[:32]


def test_a_governed_runs_own_evidence_call_never_runs_product_mode(monkeypatch):
    p = Product(monkeypatch)
    monkeypatch.setattr(chat_mod, "tx", _fake_tx)
    client = TestClient(_app())
    body = {"message": PRODUCT, "corpus_id": "cinema", "mode": "HYBRID", "compiler": "off"}
    adapter = client.post("/chat/evidence", json=body, headers={"user-agent": "polymath-adapter-step/adr_1/B_retrieve/1"}).json()
    assert "product_research" not in adapter and p.calls == []
    agent = client.post("/chat/evidence", json=body, headers={"user-agent": "claude-code/2.0"}).json()
    assert agent["product_research"]["contract"] == "product-search-v1" and p.calls
    explicit = client.post("/chat/evidence", json={**body, "product": True},
                           headers={"user-agent": "polymath-adapter-step/adr_1/B_retrieve/2"}).json()
    assert "product_research" in explicit                                        # an explicit request wins


def test_product_false_turns_product_mode_off(monkeypatch):
    p = Product(monkeypatch)
    result = _answer(_stream(dict(LLM, product=False)))["result"]
    assert "product_research" not in result and result["meta"]["verdict"] == "generated" and p.calls == []


# ---------------------------------------------------------------- 4. a non-product question keeps its exact shape

def test_a_non_product_question_is_unchanged_in_shape(monkeypatch):
    p = Product(monkeypatch)
    llm = _answer(_stream(dict(BASE, synthesizer="ollama:fake")))
    assert set(llm["result"]) == {"answer", "model", "meta"} and llm["result"]["meta"]["verdict"] == "generated"
    assert set(llm["result"]["meta"]) == {"verdict", "abstained", "synthesis_version", "phase_ms", "prompt_contract",
                                          "presentation_contract", "prompt", "generation", "carry"}
    assert "PRODUCT HYPOTHESIS" not in p.system[0] and "Supplier finds" not in llm["result"]["answer"]
    Product(monkeypatch)
    det = ui.run_chat(ui.StreamChatRequest(**BASE))
    assert "product_research" not in det and det["meta"]["verdict"] in ("supported", "insufficient_evidence")
    assert "grounded_verdict" not in det["meta"]
    Product(monkeypatch)
    ev = ui.run_chat(ui.StreamChatRequest(**dict(BASE, evidence_only=True)))
    assert "product_research" not in ev and "agent_steps" not in ev
    assert {"evidence_packet", "synthesis_performed", "graph_facts"} <= set(ev)
    q = Product(monkeypatch)
    frames = _stream(BASE)
    assert not any(s.startswith("product") for s in _phases(frames)) and q.calls == []
    assert "product_search" not in q.receipts[0]["out"]["meta"]


def test_the_ask_mode_never_runs_product_mode():
    src = (ROOT / "orchestrator" / "orchestrator" / "api" / "ui.py").read_text(encoding="utf-8")
    assert 'if ui_mode != "ASK" and getattr(req, "product", None) is not False:' in src


# ---------------------------------------------------------------- 5. several libraries: routed to one before retrieval

class FakeProfiles:
    """A fake Qdrant over the document profile collection: the fused ranking it was given, every call recorded."""

    def __init__(self, ranking):
        self.ranking, self.calls, self.closed = list(ranking), [], False

    def query_points(self, collection, **kw):
        from types import SimpleNamespace
        self.calls.append({"collection": collection, **kw})
        return SimpleNamespace(points=[SimpleNamespace(payload={"corpus_id": c, "doc_id": d}) for c, d in self.ranking])

    def close(self):
        self.closed = True


def _route_fakes(monkeypatch, ranking):
    from orchestrator.api import fast as fast_api
    from polymath_shared.product_search import routing as R
    q = FakeProfiles(ranking)
    embedded: list = []
    monkeypatch.setattr(R, "make_client", lambda: (q, "polymath_document_profiles_test"))
    monkeypatch.setattr(fast_api, "_embed_queries", lambda texts: embedded.extend(texts) or [[0.1, 0.2] for _ in texts])
    return q, embedded


def test_several_libraries_in_scope_are_routed_to_the_best_one_before_retrieval(monkeypatch):
    p = Product(monkeypatch, corpora=("cinema", "commerce-v1"))
    q, embedded = _route_fakes(monkeypatch, [("commerce-v1", "b1"), ("cinema", "a1"), ("commerce-v1", "b2")])
    frames = _stream(dict(LLM, corpus_id=None, all_authorized=True))
    frame = _answer(frames)
    assert embedded == [PRODUCT] and len(q.calls) == 1 and q.closed                       # one embedding, one profile query
    assert list(q.calls[0]["prefetch"][0].filter.must[0].match.any) == ["cinema", "commerce-v1"]
    assert p.engine_calls and {c["corpus_id"] for c in p.engine_calls} == {"commerce-v1"}  # retrieval ran on the chosen library
    block = frame["result"]["product_research"]
    assert block["corpus_ids"] == ["commerce-v1"] and block["next"]["full_research"]["input"]["corpus_ids"] == ["commerce-v1"]
    routing = block["receipts"]["routing"]
    assert routing["chosen"] == "commerce-v1" and routing["runner_up"] == "cinema" and routing["method"] == "profile_rrf"
    assert routing["candidates"] == ["cinema", "commerce-v1"] and routing["scores"]["commerce-v1"] > routing["scores"]["cinema"]
    stages = _phases(frames)
    assert stages[stages.index("product_intent") + 1:stages.index("product_intent") + 3] == ["product_route", "product_route_done"]
    done = next(d for ev, d in frames if ev == "phase" and d.get("stage") == "product_route_done")
    assert done["chosen"] == "commerce-v1" and done["runner_up"] == "cinema" and done["method"] == "profile_rrf"
    assert p.receipts[0]["scope_corpora"] == ["commerce-v1"]
    assert p.receipts[0]["out"]["meta"]["product_search"]["routing"] == {"method": "profile_rrf", "candidates": 2}


def test_without_profiles_routing_takes_the_library_with_the_most_query_ready_documents(monkeypatch):
    from polymath_shared.product_search import routing as R
    p = Product(monkeypatch, corpora=("cinema", "commerce-v1"))
    _route_fakes(monkeypatch, [])
    monkeypatch.setattr(R, "ready_counts", lambda cands: {"cinema": {"documents": 77, "query_ready_runs": 2},
                                                          "commerce-v1": {"documents": 12, "query_ready_runs": 1}})
    frame = _answer(_stream(dict(LLM, corpus_id=None, all_authorized=True)))
    routing = frame["result"]["product_research"]["receipts"]["routing"]
    assert routing["method"] == "most_query_ready_documents" and routing["chosen"] == "cinema" and routing["runner_up"] == "commerce-v1"
    assert {c["corpus_id"] for c in p.engine_calls} == {"cinema"}


def test_a_non_product_question_over_several_libraries_is_still_the_typed_single_corpus_refusal(monkeypatch):
    p = Product(monkeypatch, corpora=("cinema", "commerce-v1"))
    q, embedded = _route_fakes(monkeypatch, [("cinema", "a1")])
    frames = _stream(dict(BASE, corpus_id=None, all_authorized=True))
    err = next(d for ev, d in frames if ev == "error")
    assert err["error_code"] == "mode_requires_single_corpus" and q.calls == [] and embedded == [] and p.engine_calls == []


# ---------------------------------------------------------------- 6. an empty scope is a typed refusal, never an IndexError

def test_an_empty_scope_is_a_typed_refusal_on_both_routes(monkeypatch):
    Product(monkeypatch, corpora=())
    frames = _stream(dict(BASE, all_authorized=True, corpus_id=None))
    err = next(d for ev, d in frames if ev == "error")
    assert err["error_code"] == "QUERY_SCOPE_EMPTY" and "list_corpora" in (err.get("next_step") or "") + err.get("message", "")
    Product(monkeypatch, corpora=())
    with pytest.raises(HTTPException) as ei:
        ui.run_chat(ui.StreamChatRequest(**dict(BASE, all_authorized=True, corpus_id=None)))
    assert ei.value.status_code == 404 and ei.value.detail["error_code"] == "QUERY_SCOPE_EMPTY"

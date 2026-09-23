"""S1b (DOCUMENT-RAG-COMPLETION-V1 Part F, E5): the compile phase is timed step by step, and every model call on the chat
path receipts the reasoning settings it actually sent:
- the compiler: its client keeps what the policy put on the wire, and the winning attempt's plan carries it;
- the bridge / Corpus-Explore generator: which route answered, and with what;
- synthesis: LiteLLM's applied params, or the `think` value sent to Ollama."""
from __future__ import annotations

import json
import sys
import time
import types
from types import SimpleNamespace

import pytest
from orchestrator.api import ui
from polymath_shared.chat_plan import CompiledQuery
from polymath_shared.llm_extraction import client as client_mod
from polymath_shared.llm_extraction import pool as pool_mod

QUERY = "what does RAPO say about prompts"
PLAN_RAW = {"resolved_request": "what does RAPO say about prompts and reward models", "task_type": "GROUNDED_QA",
            "evidence_policy": "corpus_grounded", "retrieval_required": True,
            "queries": [{"id": "q0", "type": "PRIMARY", "query": "RAPO prompts", "weight": 1.0},
                        {"id": "q1", "type": "MECHANISM", "query": "reward models for prompts", "weight": 0.8}],
            "semantic_queries": [], "exact_terms": ["RAPO"], "entities": [], "must_answer": [], "user_constraints": [],
            "response_type": "answer", "antecedent": None, "graph_useful": False}


@pytest.fixture(autouse=True)
def _policy_receipt_in_tmp(monkeypatch, tmp_path):
    # the policy appends every applied setting to a JSONL wire receipt; a test must never write the fleet's file
    monkeypatch.setenv("POLYMATH_REASONING_RECEIPT", str(tmp_path / "reasoning.jsonl"))


class _Resp:
    def __init__(self, content):
        self._content, self.headers = content, {}

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


def _fake_post(sent, content):
    def post(url, json=None, timeout=None, headers=None):
        sent.append(json)
        return _Resp(content)
    return post


def _client(model="deepseek-v4-flash"):
    return client_mod.LLMExtractionClient("cloud", url="https://example.invalid/compatible-mode", model=model,
                                          limiter_key="t", api_key="not-a-key", cloud_opts={}, timeout_s=5,
                                          max_attempts=1)


def test_the_compiler_client_keeps_the_reasoning_it_put_on_the_wire(monkeypatch):
    monkeypatch.setenv("POLYMATH_REASONING_POLICY", "1")
    sent: list = []
    monkeypatch.setattr(client_mod.httpx, "post", _fake_post(sent, "ok"))
    c = _client()
    c.reasoning_role = "STRUCTURED_COMPILER"
    c._chat("plan this", 64, system_prompt="s")
    wire = c.last_reasoning["top_level"]
    assert wire and all(sent[0][k] == v for k, v in wire.items())       # the receipt says exactly what was sent


def _stub_compile_steps(monkeypatch, *, scout_s=0.0, constraints_s=0.0):
    def scout(message, corpus_ids):
        time.sleep(scout_s)
        return [], None, {"contract": "profile-scout-v1"}
    monkeypatch.setattr(ui, "_profile_scout", scout)
    monkeypatch.setattr(ui, "_resolve_plan_constraints", lambda *a, **k: time.sleep(constraints_s))
    monkeypatch.setattr(ui, "_add_corpus_explore_expansion", lambda *a, **k: None)


def test_every_compile_step_is_timed_on_the_plan_receipt(monkeypatch):
    _stub_compile_steps(monkeypatch, scout_s=0.02, constraints_s=0.03)
    monkeypatch.setattr(pool_mod, "cloud_endpoints", list)
    monkeypatch.setattr(pool_mod, "stage_pin", lambda stage: [])
    steps = ui._compile_chat_plan(QUERY, [], ["cinema"]).compiler["compile_ms"]
    assert {"scout", "endpoints", "profile_expansion", "bridges", "provenance", "constraints", "explorer",
            "total"} <= set(steps)
    assert steps["scout"] >= 20 and steps["constraints"] >= 30
    assert steps["total"] >= steps["scout"] + steps["constraints"]


def test_the_compiler_lanes_are_timed_and_the_winning_attempt_receipts_its_reasoning(monkeypatch):
    monkeypatch.setenv("POLYMATH_REASONING_POLICY", "1")
    _stub_compile_steps(monkeypatch)
    ep = SimpleNamespace(name="compiler_alibaba_deepseek", url="https://example.invalid/compatible-mode",
                         model="deepseek-v4-flash", limiter_key="compiler_alibaba_deepseek", api_key="not-a-key",
                         cloud_opts={})
    monkeypatch.setattr(pool_mod, "cloud_endpoints", lambda: [ep])
    monkeypatch.setattr(pool_mod, "stage_pin", lambda stage: [ep.name])
    sent: list = []
    monkeypatch.setattr(client_mod.httpx, "post", _fake_post(sent, json.dumps(PLAN_RAW)))

    def complete_one(self, user_prompt, *, system_prompt, max_tokens):      # the lane limiter is not under test
        return self._chat(user_prompt, max_tokens, system_prompt=system_prompt)[0], None
    monkeypatch.setattr(client_mod.LLMExtractionClient, "complete_one", complete_one)
    plan = ui._compile_chat_plan(QUERY, [], ["cinema"], session_key="s1b")
    assert not plan.fallback, plan.compiler
    assert "lanes" in plan.compiler["compile_ms"]
    wire = plan.compiler["reasoning"]["top_level"]
    assert wire and all(sent[-1][k] == v for k, v in wire.items())


def test_the_bridge_route_and_its_reasoning_are_receipted():
    class _Ok:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": '[{"bridge_query": "from gemma"}]'}}

    route: dict = {}
    ui._bridge_llm("make bridges", ollama_post=lambda *a, **k: _Ok(), cloud_attempts=[], route=route)
    assert route == {"route": "ollama", "model": ui._BRIDGE_MODEL, "reasoning": {"surface": "ollama", "think": False}}

    class _Cloud:
        endpoint_name, model = "compiler_alibaba_qwen", "qwen3.6-plus"

        def _chat(self, prompt, max_tokens, system_prompt=None):
            self.last_reasoning = {"role": "BRIDGE", "top_level": {"enable_thinking": False}}
            return '[{"bridge_query": "from the cloud"}]', 1, 1, {}

    def _down(*_a, **_k):
        raise ConnectionError("ollama down")

    route = {}
    ui._bridge_llm("make bridges", ollama_post=_down, cloud_attempts=[_Cloud()], route=route)
    assert route == {"route": "compiler_alibaba_qwen", "model": "qwen3.6-plus",
                     "reasoning": {"role": "BRIDGE", "top_level": {"enable_thinking": False}}}


def test_the_bridge_expansion_receipt_names_the_route(monkeypatch):
    monkeypatch.setenv("POLYMATH_CHAT_BRIDGE_COMPILER", "1")

    def fake_bridge_llm(prompt, *, route=None, **_k):
        route.update({"route": "ollama", "model": "gemma4:31b-cloud", "reasoning": {"surface": "ollama", "think": False}})
        return json.dumps([{"bridge_query": "observable facial muscle actions of genuine vs faked smiles",
                            "derived_from": "docFACS", "relation_to_q0": "distinguishes real from performed",
                            "proposed_role": "COMPLEMENTARY", "model_confidence": 0.9}])
    monkeypatch.setattr(ui, "_bridge_llm", fake_bridge_llm)
    plan = SimpleNamespace(queries=[CompiledQuery(id="q0", type="PRIMARY", query="make the fake smile readable")],
                           intent="APPLICATION", compiler={})
    nom = SimpleNamespace(doc_id="docFACS", representative_surface="Facial Action Coding expressions",
                          representative_text="Facial Action Coding expressions")
    ui._add_bridge_expansion(plan, SimpleNamespace(nominations=[nom]))
    assert plan.compiler["bridge_expansion"]["route"]["route"] == "ollama"
    assert plan.compiler["bridge_expansion"]["route"]["reasoning"] == {"surface": "ollama", "think": False}


def test_litellm_synthesis_receipts_the_reasoning_it_sent(monkeypatch):
    monkeypatch.setenv("POLYMATH_REASONING_POLICY", "1")
    calls: list = []

    def completion(**kwargs):
        calls.append(kwargs)
        delta = SimpleNamespace(content="Hi.", reasoning_content=None)
        return iter([SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason="stop")])])
    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=completion))
    monkeypatch.setattr(ui, "_litellm_credentials", lambda model: {"api_key": "x"})
    out = list(ui._litellm_generate("anthropic/deepseek-v4-flash-0731", "q", {"evidence_bundle": []}, [], [], []))
    fin = out[-1]["finish"]
    assert fin["reasoning"]["top_level"]["thinking"] == calls[0]["thinking"] == {"type": "disabled"}


class _OllamaStream:
    def __init__(self, status, lines, text=""):
        self.status_code, self._lines, self.text = status, lines, text

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b""

    def iter_lines(self):
        yield from self._lines


def test_ollama_synthesis_receipts_the_think_value_it_sent(monkeypatch):
    import httpx
    sent: list = []

    def stream(method, url, json=None, timeout=None):
        sent.append(json)
        return _OllamaStream(200, ['{"message": {"content": "Hi."}}', '{"done": true}'])
    monkeypatch.setattr(httpx, "stream", stream)
    out = list(ui._ollama_generate("gemma4:31b-cloud", "q", {"evidence_bundle": []}, [], [], []))
    fin = [p for p in out if "finish" in p][-1]["finish"]
    assert "think" in sent[0] and fin["reasoning"] == {"surface": "ollama", "think": sent[0]["think"]}


def test_ollama_synthesis_receipts_a_rejected_think(monkeypatch):
    import httpx
    sent: list = []

    def stream(method, url, json=None, timeout=None):
        sent.append(json)
        if "think" in json:
            return _OllamaStream(400, [], text='{"error": "model does not support think"}')
        return _OllamaStream(200, ['{"message": {"content": "Hi."}}', '{"done": true}'])
    monkeypatch.setattr(httpx, "stream", stream)
    out = list(ui._ollama_generate("some-model:latest", "q", {"evidence_bundle": []}, [], [], []))
    fin = [p for p in out if "finish" in p][-1]["finish"]
    assert "think" not in sent[-1] and fin["reasoning"] == {"surface": "ollama", "think": None, "think_rejected": True}

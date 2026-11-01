"""INTERACTIVE-ADMISSION-V1 — a chat turn never waits on a lane limiter.

Measured 2026-11-01 (llm_provider_attempts, 24 h): lane compiler_ollama_gemma failed 27/27 with HTTP_429, and every
compiler call left 30.1–31.0 s after the previous call's 429 — the breaker's 30 s cooldown (limiter.py BREAKER_COOLDOWN_S)
waited out by the BLOCKING admission in `LLMExtractionClient.complete_one`. 291 s across 9 of 41 chat turns.

Proof here, with the transport scripted and the REAL limiter (any limiter sleep raises, so a blocking wait fails loudly
instead of hanging):
  * a pool whose first lane's breaker is open — the chat compiler, the facet step and the deep-research port skip that
    lane without sleeping, send it nothing, plan on the next lane, and receipt the skip (lane, reason) on the plan /
    facet receipt and in the attempt ledger; the skipped lane is not cooled;
  * every lane refused — a typed fast failure: the compiler's fallback plan carries `degraded.type == ALL_LANES_REFUSED`,
    the deep-research port raises `AllLanesRefused`; zero HTTP, well under a second;
  * an extraction / enrichment client (not interactive) keeps the blocking admission: on a fake clock it waits for the
    breaker's half-open probe exactly as before.
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from orchestrator.api import deep_research as DRR
from orchestrator.api import ui
from polymath_shared import chat_plan as cp
from polymath_shared.conformance import attempts as attempts_mod
from polymath_shared.llm_extraction import client as client_mod
from polymath_shared.llm_extraction import limiter as limiter_mod
from polymath_shared.llm_extraction import pool as pool_mod

PLAN = {"resolved_request": "what does RAPO say about prompts and reward models", "task_type": "GROUNDED_QA",
        "evidence_policy": "corpus_grounded", "retrieval_required": True,
        "queries": [{"id": "q0", "type": "PRIMARY", "query": "RAPO prompts", "weight": 1.0},
                    {"id": "q1", "type": "MECHANISM", "query": "reward models for prompts", "weight": 0.8}],
        "semantic_queries": [], "exact_terms": ["RAPO"], "entities": [], "must_answer": [], "user_constraints": [],
        "response_type": "answer", "antecedent": None, "graph_useful": False}
FACETS = {"resolved_request": "What RAPO says about prompts and reward models",
          "facets": [{"id": "f1", "name": "RAPO prompt method", "query": "RAPO prompts", "type": "PRIMARY"},
                     {"id": "f2", "name": "reward models for prompts", "query": "reward models for prompts",
                      "type": "MECHANISM"}]}
QUESTION = "what does RAPO say about prompts and reward models"


class _Resp:
    status_code = 200
    headers: dict = {}

    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}}


def _ep(name: str, host: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, url=f"https://{host}.example.invalid", model="stub", limiter_key=name,
                           api_key="not-a-key", cloud_opts={})


def _lane(ep) -> limiter_mod.AdaptiveLimiter:
    """The exact limiter lane the client will use for this endpoint."""
    c = client_mod.LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key)
    return c._lane_limiter()


def _open_breaker(ep) -> None:
    lim = _lane(ep)
    lim._breaker.opened_at = limiter_mod._now()          # just opened: ~30 s to the half-open probe


@pytest.fixture()
def world(monkeypatch, tmp_path):
    """Two compiler lanes on different hosts, A preferred; scripted HTTP; the ledger and every limiter sleep captured."""
    monkeypatch.delenv("POLYMATH_PG_DSN", raising=False)          # no controller store, no ledger database
    monkeypatch.setenv("POLYMATH_REASONING_RECEIPT", str(tmp_path / "reasoning.jsonl"))
    monkeypatch.setenv(cp.CONTRACT_FLAG, "0")
    for k in ("POLYMATH_CHAT_BRIDGE_COMPILER", "POLYMATH_CHAT_PROFILE_EXPANSION", "POLYMATH_PROFILE_SCOUT"):
        monkeypatch.delenv(k, raising=False)
    tag = uuid.uuid4().hex[:8]                                    # fresh limiter lanes in the process-wide registry
    a, b = _ep(f"ia_a_{tag}", f"a{tag}"), _ep(f"ia_b_{tag}", f"b{tag}")
    monkeypatch.setattr(pool_mod, "cloud_endpoints", lambda: [a, b])
    monkeypatch.setattr(pool_mod, "stage_pin", lambda stage: [a.name, b.name])
    monkeypatch.setattr(ui, "_COMPILER_PREFERRED_LANE", a.name)
    monkeypatch.setattr(ui, "_COMPILER_LANE_FAILED_AT", {})
    monkeypatch.setattr(ui, "_profile_scout", lambda m, c, scope=None: ([], None, {"contract": "profile-scout-v1"}))
    monkeypatch.setattr(ui, "_resolve_plan_constraints", lambda *a, **k: None)
    monkeypatch.setattr(ui, "_add_corpus_explore_expansion", lambda *a, **k: None)

    @contextmanager
    def fake_tx():
        yield SimpleNamespace(execute=lambda sql, params=(): SimpleNamespace(fetchall=list))
    monkeypatch.setattr(ui, "tx", fake_tx)
    posted: list[str] = []

    def post(url, json=None, timeout=None, headers=None):
        posted.append(url)
        system = json["messages"][0]["content"]
        return _Resp(__import__("json").dumps(FACETS if "FACET NAMER" in system else PLAN))
    monkeypatch.setattr(client_mod.httpx, "post", post)
    rows: list = []
    monkeypatch.setattr(attempts_mod, "record", rows.append)
    slept: list = []

    def no_sleep(seconds):
        slept.append(seconds)
        raise AssertionError(f"an interactive call blocked in the limiter: sleep({seconds})")
    monkeypatch.setattr(limiter_mod.time, "sleep", no_sleep)
    return SimpleNamespace(a=a, b=b, posted=posted, rows=rows, slept=slept)


def _to(ep, posted) -> list[str]:
    return [u for u in posted if u.startswith(ep.url)]


def test_the_compiler_skips_an_open_breaker_lane_at_once_and_plans_on_the_next(world, monkeypatch):
    monkeypatch.setenv(cp.FACETS_FLAG, "0")
    _open_breaker(world.a)
    t0 = time.perf_counter()
    plan = ui._compile_chat_plan(QUESTION, [], ["cinema"], session_key="ia")
    elapsed = time.perf_counter() - t0
    assert world.slept == [] and elapsed < 1.0, (world.slept, elapsed)
    assert plan.compiler["compile_ms"]["lanes"] < 1000
    assert not plan.fallback, plan.compiler
    assert plan.compiler["lane"] == world.b.name and plan.compiler["attempt"] == 2
    skip = plan.compiler["lanes_skipped"]
    assert [(s["lane"], s["reason"]) for s in skip] == [(world.a.name, "BREAKER")]
    assert 0 < skip[0]["retry_after_s"] <= limiter_mod.BREAKER_COOLDOWN_S          # the time left to the probe
    assert _to(world.a, world.posted) == [] and len(_to(world.b, world.posted)) == 1
    refused = [r for r in world.rows if r.lane == world.a.name]                   # the ledger sees the skip too
    assert len(refused) == 1 and refused[0].limiter_admitted is False and refused[0].http_dispatched is False
    assert refused[0].error_class == "LIMITER_REFUSED"
    assert world.a.name not in ui._COMPILER_LANE_FAILED_AT                       # a skip never cools the lane
    assert "degraded" not in plan.compiler


def test_every_lane_refused_is_a_typed_fast_fallback(world, monkeypatch):
    monkeypatch.setenv(cp.FACETS_FLAG, "0")
    _open_breaker(world.a)
    _open_breaker(world.b)
    t0 = time.perf_counter()
    plan = ui._compile_chat_plan(QUESTION, [], ["cinema"], session_key="ia")
    elapsed = time.perf_counter() - t0
    assert world.slept == [] and elapsed < 1.0, (world.slept, elapsed)
    assert plan.fallback is True and world.posted == []                          # zero HTTP
    assert plan.queries[0].query == cp.fallback_plan(QUESTION, reason="x").queries[0].query   # the existing fallback
    deg = plan.compiler["degraded"]
    assert deg["type"] == client_mod.ALL_LANES_REFUSED and deg["http_dispatched"] is False
    assert [(s["lane"], s["reason"]) for s in deg["lanes_skipped"]] == [(world.a.name, "BREAKER"),
                                                                       (world.b.name, "BREAKER")]
    assert plan.compiler["reason"] == "transport:LIMITER_REFUSED"
    assert ui._COMPILER_LANE_FAILED_AT == {}


def test_the_facet_step_skips_an_open_breaker_lane(world, monkeypatch):
    monkeypatch.setenv(cp.FACETS_FLAG, "1")
    _open_breaker(world.a)
    t0 = time.perf_counter()
    job = ui._start_facet_step(QUESTION, [], "ia")
    rec = job.result(timeout=5)
    assert world.slept == [] and time.perf_counter() - t0 < 1.0
    assert rec["fallback"] is False and rec["n"] == 2 and rec["model"].startswith(world.b.name)
    assert [(s["lane"], s["reason"]) for s in rec["lanes_skipped"]] == [(world.a.name, "BREAKER")]
    assert _to(world.a, world.posted) == [] and "degraded" not in rec
    # both lanes refused: a receipted facets None with the typed degraded receipt, no HTTP
    _open_breaker(world.b)
    world.posted.clear()
    rec2 = ui._start_facet_step(QUESTION, [], "ia").result(timeout=5)
    assert rec2["facets"] is None and rec2["reason"] == "transport:LIMITER_REFUSED" and world.posted == []
    assert rec2["degraded"]["type"] == client_mod.ALL_LANES_REFUSED and len(rec2["lanes_skipped"]) == 2


def test_the_deep_research_port_skips_a_refused_lane_and_fails_fast_typed(world):
    _open_breaker(world.a)
    complete = DRR._complete_port("ia-research")
    t0 = time.perf_counter()
    text = complete("plan the searches", system="planner", max_tokens=200)
    assert world.slept == [] and time.perf_counter() - t0 < 1.0
    assert json.loads(text) == PLAN and _to(world.a, world.posted) == [] and len(_to(world.b, world.posted)) == 1
    _open_breaker(world.b)
    world.posted.clear()
    t0 = time.perf_counter()
    with pytest.raises(client_mod.AllLanesRefused) as ei:
        complete("plan the searches", system="planner", max_tokens=200)
    assert world.slept == [] and time.perf_counter() - t0 < 1.0 and world.posted == []
    assert ei.value.receipt["type"] == client_mod.ALL_LANES_REFUSED
    assert sorted(s.lane for s in ei.value.skips) == sorted([world.a.name, world.b.name])
    assert isinstance(ei.value, RuntimeError)                     # the engine's port-error path counts it, as before


def test_a_skip_spends_no_attempt_and_is_never_cooled():
    """Pure walk: refused lanes (zero HTTP) are skipped without cooling and without spending one of the three attempts."""
    def plan(fallback, reason=None, refusal=None):
        comp = {"fallback": fallback, "reason": reason}
        if refusal:
            comp["limiter_refusal"] = refusal
        return SimpleNamespace(fallback=fallback, compiler=comp)

    eps = [SimpleNamespace(name=n, url=f"https://{n}.invalid") for n in ("gemma", "b", "c", "d", "e")]
    refused = {"lane": "gemma", "reason": "BREAKER", "retry_after_s": 12.0}
    outcomes = {"gemma": plan(True, "transport:LIMITER_REFUSED", refused),
                "b": plan(True, "transport:ReadTimeout"), "c": plan(True, "budget_exceeded:8400ms"),
                "d": plan(True, "transport:HTTP_503")}
    called: list[str] = []

    def compile_one(ep):
        called.append(ep.name)
        return outcomes[ep.name]
    failed_at: dict = {}
    out = ui._run_compiler_lanes(eps, compile_one, failed_at=failed_at, now_fn=lambda: 5.0)
    assert called == ["gemma", "b", "c", "d"]                     # three dispatched attempts; the skip was free
    assert set(failed_at) == {"b", "c", "d"}                      # the refused lane is not cooled
    assert out.compiler["lanes_skipped"] == [refused] and "degraded" not in out.compiler
    assert out.compiler["first_failure"] == "gemma:transport:LIMITER_REFUSED"


def test_extraction_and_enrichment_keep_the_blocking_admission(monkeypatch):
    """A non-interactive client waits for the breaker's half-open probe (fake clock), then dispatches — unchanged."""
    monkeypatch.delenv("POLYMATH_PG_DSN", raising=False)
    monkeypatch.setattr(attempts_mod, "record", lambda a: None)
    clock = {"t": 1000.0}
    slept: list = []

    def fake_sleep(seconds):
        slept.append(seconds)
        clock["t"] += seconds
    monkeypatch.setattr(limiter_mod, "_now", lambda: clock["t"])
    monkeypatch.setattr(limiter_mod.time, "sleep", fake_sleep)
    posted: list = []

    def post(url, json=None, timeout=None, headers=None):
        posted.append((clock["t"], url))
        return _Resp('{"ok": true}')
    monkeypatch.setattr(client_mod.httpx, "post", post)
    ep = _ep(f"ia_x_{uuid.uuid4().hex[:8]}", "x")
    lim = _lane(ep)
    lim._breaker.opened_at = clock["t"]
    blocks: list = []
    real_admit = limiter_mod.AdaptiveLimiter.admit

    def spy_admit(self, est_tokens=0.0, block=True, **kw):
        blocks.append(block)
        return real_admit(self, est_tokens, block, **kw)
    monkeypatch.setattr(limiter_mod.AdaptiveLimiter, "admit", spy_admit)
    enrich = client_mod.LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key)
    assert enrich.interactive is False
    text, err = enrich.complete_one("u", system_prompt="s", max_tokens=50)
    assert err is None and text == '{"ok": true}' and enrich.last_refusal is None
    assert blocks == [True]                                       # the enrichment seam admits BLOCKING
    assert sum(slept) >= limiter_mod.BREAKER_COOLDOWN_S            # it waited the cooldown out, as before
    assert posted and posted[0][0] - 1000.0 >= limiter_mod.BREAKER_COOLDOWN_S
    # the extraction retry loop admits through acquire() with its blocking default — the same gate, unchanged
    blocks.clear()
    ext = client_mod.LLMExtractionClient("cloud", url=ep.url, model=ep.model, limiter_key=ep.limiter_key, max_attempts=1)
    ext.extract([("n-1", [("c-1", "Paris is in France.")])], source_bytes=10_000_000, threshold_bytes=0)
    assert blocks and all(b is True for b in blocks)

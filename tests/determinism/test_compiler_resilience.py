"""COMPILER-WORKS-WITHOUT-OLLAMA (2026-09-23, owner: "assume my Ollama subscription is complete now … I don't mind gemma
being the go-to but it should work regardless"). The chat compiler and the bridge / Corpus-Explore generator must produce
a real plan / bridges when any single provider — including Ollama — is down, slow, or returns an unusable plan."""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))

from orchestrator.api import ui


class _E:  # minimal endpoint stand-in
    def __init__(self, name: str, url: str):
        self.name, self.url = name, url


ROSTER = [_E("compiler_alibaba_deepseek", "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode"),
          _E("compiler_alibaba_qwen", "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode"),
          _E("compiler_alt", "https://openrouter.ai/api"),
          _E("compiler_ollama_gemma", "http://127.0.0.1:11434")]


def test_gemma_is_tried_first_for_every_session_and_last_while_it_is_down():
    for key in ("session-a", "session-b", "another", ""):
        order = [e.name for e in ui._compiler_attempt_order(ROSTER, key, failed_at={}, now=1000.0,
                                                           preferred="compiler_ollama_gemma")]
        assert order[0] == "compiler_ollama_gemma" and len(order) == 3
    # Ollama failed 10 s ago (e.g. the subscription ended): the backups go first
    cold = [e.name for e in ui._compiler_attempt_order(ROSTER, "session-a", failed_at={"compiler_ollama_gemma": 990.0},
                                                      now=1000.0, preferred="compiler_ollama_gemma")]
    assert cold[0] != "compiler_ollama_gemma" and "compiler_ollama_gemma" not in cold[:2]


def _plan(fallback: bool, reason: str | None = None):
    return SimpleNamespace(fallback=fallback, compiler={"fallback": fallback, "reason": reason})


def test_a_late_or_unusable_plan_moves_on_to_the_next_lane():
    outcomes = {"compiler_ollama_gemma": _plan(True, "transport:HTTPStatusError"),       # Ollama gone
                "compiler_alibaba_qwen": _plan(True, "budget_exceeded:8400ms"),          # arrived too late
                "compiler_alibaba_deepseek": _plan(False)}                               # a real plan
    failed_at: dict = {}
    attempts = [next(e for e in ROSTER if e.name == n)
                for n in ("compiler_ollama_gemma", "compiler_alibaba_qwen", "compiler_alibaba_deepseek")]
    plan = ui._run_compiler_lanes(attempts, lambda ep: outcomes[ep.name], failed_at=failed_at, now_fn=lambda: 1000.0)
    assert plan.fallback is False
    assert plan.compiler["lane"] == "compiler_alibaba_deepseek" and plan.compiler["attempt"] == 3
    assert plan.compiler["first_failure"] == "compiler_ollama_gemma:transport:HTTPStatusError"
    # the unreachable and the slow lane cool down for later turns; the lane that planned does not
    assert set(failed_at) == {"compiler_ollama_gemma", "compiler_alibaba_qwen"}


def test_an_invalid_plan_tries_another_model_without_cooling_the_lane():
    outcomes = {"compiler_alibaba_deepseek": _plan(True, "invalid_plan:no_queries_for_retrieval"),
                "compiler_alibaba_qwen": _plan(False)}
    failed_at: dict = {}
    attempts = [next(e for e in ROSTER if e.name == n) for n in ("compiler_alibaba_deepseek", "compiler_alibaba_qwen")]
    plan = ui._run_compiler_lanes(attempts, lambda ep: outcomes[ep.name], failed_at=failed_at, now_fn=lambda: 1.0)
    assert plan.fallback is False and plan.compiler["lane"] == "compiler_alibaba_qwen"
    assert failed_at == {}


def test_when_every_lane_fails_the_turn_still_gets_the_fallback_plan():
    attempts = ROSTER[:3]
    plan = ui._run_compiler_lanes(attempts, lambda ep: _plan(True, "transport:ReadTimeout"), failed_at={},
                                  now_fn=lambda: 1.0)
    assert plan.fallback is True and plan.compiler["attempt"] == 3
    assert plan.compiler["first_failure"].startswith("compiler_alibaba_deepseek:transport:")


def test_bridges_come_from_a_cloud_lane_when_ollama_is_down():
    def _ollama_down(*_a, **_k):
        raise ConnectionError("ollama subscription ended")

    class _Cloud:
        def __init__(self):
            self.calls = 0

        def _chat(self, prompt, max_tokens, system_prompt=None):
            self.calls += 1
            return '[{"bridge_query": "withheld information and suspense"}]', 10, 20, {}

    cloud = _Cloud()
    out = ui._bridge_llm("make bridges", ollama_post=_ollama_down, cloud_attempts=[cloud])
    assert "withheld information" in out and cloud.calls == 1


def test_bridges_use_ollama_first_when_it_works():
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": '[{"bridge_query": "from gemma"}]'}}

    class _Cloud:
        def _chat(self, *_a, **_k):
            raise AssertionError("the cloud lane must not be called while Ollama answers")

    out = ui._bridge_llm("make bridges", ollama_post=lambda *a, **k: _Resp(), cloud_attempts=[_Cloud()])
    assert "from gemma" in out


def test_compiler_time_limits_give_the_backup_lanes_margin():
    """Qwen / DeepSeek plan in 3.5–5.3 s with thinking disabled (11.423), too close to the old 6 s limits."""
    from polymath_shared import chat_plan
    assert ui._COMPILER_HTTP_TIMEOUT_S == 8.0 and chat_plan.COMPILER_HARD_BUDGET_S == 8.0

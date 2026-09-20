"""REASONING-BOUNDARY-V1 RB2 — role->reasoning-budget policy + provider adapter (pure, offline)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.reasoning_policy import (  # noqa: E402
    CHAT_SYNTHESIS,
    REVIEWER,
    STRUCTURED_COMPILER,
    S_CHAT_COMPLETIONS,
    S_LITELLM,
    S_RESPONSES,
    apply_chat_completions,
    apply_litellm,
    policy_enabled,
    provider_family,
    reasoning_params,
)


def test_family_detection():
    assert provider_family("qwen3.8-flash") == "qwen"
    assert provider_family("deepseek-v4-flash-0731") == "deepseek"
    assert provider_family("anthropic/claude-opus-5") == "claude"
    assert provider_family("gemini-3.8-flash") == "gemini"
    assert provider_family("openai/big-pickle") == "openai"


def test_qwen_chat_completions_uses_thinking_budget_not_effort():
    p = reasoning_params(STRUCTURED_COMPILER, "qwen3.8-flash", S_CHAT_COMPLETIONS)
    assert p["top_level"]["thinking_budget"] == 300
    assert p["top_level"]["preserve_thinking"] is False
    assert "reasoning_effort" not in p["top_level"] and "reasoning_effort" not in p["extra_body"]  # invalid combo
    # output budget is SEPARATE and larger than the reasoning ceiling
    assert p["max_output_tokens"] == 500 and p["max_output_tokens"] > 300


def test_qwen_responses_has_no_thinking_budget():
    p = reasoning_params(STRUCTURED_COMPILER, "qwen3.8-flash", S_RESPONSES)
    assert "thinking_budget" not in p["top_level"] and "thinking_budget" not in p["extra_body"]
    both = {**p["top_level"], **p["extra_body"]}
    assert both.get("enable_thinking") is False                  # disabled instead (no numeric budget on Responses)


def test_deepseek_thinking_disabled():
    p = reasoning_params(CHAT_SYNTHESIS, "deepseek-v4-flash-0731", S_LITELLM)
    assert p["extra_body"]["thinking"] == {"type": "disabled"}   # required or empty response


def test_claude_effort_low_no_manual_budget():
    p = reasoning_params(CHAT_SYNTHESIS, "anthropic/claude-sonnet-5", S_LITELLM)
    assert p["extra_body"]["effort"] == "low"
    assert "thinking_budget" not in p["extra_body"] and "budget_tokens" not in p["extra_body"]


def test_gemini_thinking_level_low():
    p = reasoning_params(STRUCTURED_COMPILER, "gemini-3.8-flash", S_LITELLM)
    assert p["extra_body"]["thinking_level"] == "low"


def test_qwen_litellm_uses_extra_body_budget():
    p = reasoning_params(STRUCTURED_COMPILER, "qwen3.8-flash", S_LITELLM)
    assert p["extra_body"].get("thinking_budget") == 300         # placed in extra_body for litellm passthrough
    assert p["top_level"] == {} or "thinking_budget" not in p["top_level"]


def test_synthesis_qwen_disables_thinking_but_keeps_big_output():
    p = reasoning_params(CHAT_SYNTHESIS, "qwen3.8-flash", S_LITELLM)
    # CHAT_SYNTHESIS has no numeric budget -> disable thinking; output stays large + separate
    assert p["extra_body"].get("enable_thinking") is False
    assert p["max_output_tokens"] == 6000


def test_output_budget_always_present_and_independent():
    for role, exp in ((STRUCTURED_COMPILER, 500), (REVIEWER, 200)):
        p = reasoning_params(role, "qwen3.8-flash", S_CHAT_COMPLETIONS)
        assert p["max_output_tokens"] == exp


def test_never_both_effort_and_budget():
    # sweep every role x a few providers/surfaces; the invariant must always hold
    for role in (STRUCTURED_COMPILER, REVIEWER, CHAT_SYNTHESIS):
        for model in ("qwen3.8-flash", "deepseek-v4", "gemini-3.8-flash", "anthropic/claude-sonnet-5", "openai/x"):
            for surf in (S_CHAT_COMPLETIONS, S_LITELLM, S_RESPONSES):
                p = reasoning_params(role, model, surf)
                for bag in (p["top_level"], p["extra_body"]):
                    assert not ("reasoning_effort" in bag and "thinking_budget" in bag)


def test_env_override(monkeypatch):
    monkeypatch.setenv("POLYMATH_REASONING_MAX_STRUCTURED_COMPILER", "150")
    monkeypatch.setenv("POLYMATH_OUTPUT_MAX_STRUCTURED_COMPILER", "400")
    p = reasoning_params(STRUCTURED_COMPILER, "qwen3.8-flash", S_CHAT_COMPLETIONS)
    assert p["top_level"]["thinking_budget"] == 150 and p["max_output_tokens"] == 400


def test_appliers_are_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("POLYMATH_REASONING_POLICY", raising=False)
    assert policy_enabled() is False
    k = {"model": "deepseek-v4", "messages": []}
    assert apply_litellm(k, CHAT_SYNTHESIS, "deepseek-v4") == {} and "extra_body" not in k   # byte-identical
    p = {"model": "qwen3.8-flash", "messages": []}
    assert apply_chat_completions(p, STRUCTURED_COMPILER, "qwen3.8-flash") == {} and "thinking_budget" not in p


def test_appliers_overlay_when_enabled(monkeypatch):
    monkeypatch.setenv("POLYMATH_REASONING_POLICY", "1")
    k = {"model": "deepseek-v4", "messages": []}
    applied = apply_litellm(k, CHAT_SYNTHESIS, "deepseek-v4")
    assert applied and k["extra_body"]["thinking"] == {"type": "disabled"}   # deepseek disabled on the wire
    p = {"model": "qwen3.8-flash", "messages": []}
    a2 = apply_chat_completions(p, STRUCTURED_COMPILER, "qwen3.8-flash")
    assert a2 and p["thinking_budget"] == 300 and p["preserve_thinking"] is False and "reasoning_effort" not in p

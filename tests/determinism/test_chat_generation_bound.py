"""GENERATION-BOUND-V1: the chat path sends its own output bound to LiteLLM providers, records the
provider's finish_reason, and retries once without the bound when a provider rejects the number.
Measured motivation (2026-09-06): LiteLLM's Anthropic-format default of 4096 tokens cut long answers
mid-sentence with no error and no receipt (deepseek-v4-flash spends most of it on reasoning)."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
for sub in ("orchestrator", "shared"):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))

from orchestrator.api import ui  # noqa: E402


def _chunk(content=None, reasoning=None, finish=None):
    delta = SimpleNamespace(content=content, reasoning_content=reasoning)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish)])


def _fake_litellm(monkeypatch, scripts):
    """Install a fake `litellm` whose completion() pops one script per call: a list of chunks, or an
    exception to raise at the call. Records every kwargs dict."""
    calls: list[dict] = []

    def completion(**kwargs):
        calls.append(kwargs)
        step = scripts.pop(0)
        if isinstance(step, BaseException):
            raise step
        return iter(step)

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=completion))
    monkeypatch.setattr(ui, "_litellm_credentials", lambda model: {"api_key": "x"})
    monkeypatch.setattr(ui, "_grounded_messages", lambda *a, **k: [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}])
    return calls


def _pieces(model="anthropic/deepseek-v4-flash-0731"):
    return list(ui._litellm_generate(model, "q", {"evidence_bundle": []}, [], [], []))


def test_the_bound_is_sent_and_the_finish_reason_is_receipted(monkeypatch):
    monkeypatch.setenv("POLYMATH_CHAT_MAX_TOKENS", "1234")
    calls = _fake_litellm(monkeypatch, [[_chunk(reasoning="thinking…"), _chunk("Hello "), _chunk("world.", finish="stop")]])
    out = _pieces()
    assert calls[0]["max_tokens"] == 1234 and calls[0]["stream"] is True
    assert out[0].keys() == {"prompt"}
    assert [p for p in out if "reasoning" in p] == [{"reasoning": "thinking…"}]
    assert "".join(p.get("token", "") for p in out) == "Hello world."
    assert out[-1] == {"finish": {"finish_reason": "stop", "max_tokens": 1234}}


def test_a_length_stop_is_named_so_the_runtime_can_flag_the_cut(monkeypatch):
    monkeypatch.setenv("POLYMATH_CHAT_MAX_TOKENS", "50")
    _fake_litellm(monkeypatch, [[_chunk("Here's a production-grade rewrite", finish="length")]])
    out = _pieces()
    assert out[-1]["finish"] == {"finish_reason": "length", "max_tokens": 50}
    assert not any(p.get("error") for p in out)


def test_a_provider_that_rejects_the_number_gets_one_retry_without_it_and_a_degraded_receipt(monkeypatch):
    monkeypatch.setenv("POLYMATH_CHAT_MAX_TOKENS", "16000")
    calls = _fake_litellm(monkeypatch, [ValueError("BadRequestError: max_tokens: 16000 > 8192, which is the maximum allowed"),
                                        [_chunk("ok", finish="stop")]])
    out = _pieces("openai/glm-5-free")
    assert "max_tokens" in calls[0] and "max_tokens" not in calls[1]
    degraded = [p["degraded"] for p in out if p.get("degraded")]
    assert len(degraded) == 1 and degraded[0]["component"] == "generation" and degraded[0]["state"] == "bound refused"
    assert degraded[0]["reason"] == "max_tokens_rejected:16000" and "8192" in degraded[0]["detail"] and "without a bound" in degraded[0]["effect"]
    assert out[-1] == {"finish": {"finish_reason": "stop", "max_tokens": None}}
    assert not any(p.get("error") for p in out)


def test_any_other_provider_error_is_still_the_typed_error_not_a_retry(monkeypatch):
    monkeypatch.setenv("POLYMATH_CHAT_MAX_TOKENS", "16000")
    calls = _fake_litellm(monkeypatch, [RuntimeError("AuthenticationError: Missing credentials")])
    out = _pieces()
    assert len(calls) == 1
    assert out[-1]["error"] is True and out[-1]["error_code"] == "litellm_error" and "Missing credentials" in out[-1]["message"]


def test_zero_disables_the_bound_and_a_bad_value_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("POLYMATH_CHAT_MAX_TOKENS", "0")
    calls = _fake_litellm(monkeypatch, [[_chunk("x", finish="stop")]])
    out = _pieces()
    assert "max_tokens" not in calls[0] and out[-1]["finish"] == {"finish_reason": "stop", "max_tokens": None}
    monkeypatch.setenv("POLYMATH_CHAT_MAX_TOKENS", "lots")
    assert ui._chat_max_tokens() == 6000
    monkeypatch.delenv("POLYMATH_CHAT_MAX_TOKENS")
    assert ui._chat_max_tokens() == 6000


@pytest.mark.parametrize("text,expected", [
    ("max_tokens: 16000 > 8192", True), ("max_completion_tokens is too large", True),
    ("The model's max output tokens is 4096", True), ("AuthenticationError: Missing credentials", False),
    ("RateLimitError: 429", False)])
def test_bound_rejection_is_recognised_by_the_provider_wording(text, expected):
    assert ui._bound_rejected(Exception(text)) is expected

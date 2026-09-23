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
    # MODEL-LIST-REASONING-V1: the litellm route prefix names the transport, not the family. `openai/big-pickle` used to be
    # classified "openai", which sent `reasoning_effort` and made litellm refuse every call to it.
    assert provider_family("openai/big-pickle") == "other"
    assert provider_family("anthropic/glm-5.2") == "glm"
    assert provider_family("anthropic/qwen3.8-max") == "qwen"
    assert provider_family("openrouter/deepseek/deepseek-chat") == "deepseek"
    assert provider_family("gpt-oss:120b-cloud") == "openai"
    assert provider_family("openai/nemotron-3-ultra-free") == "other"


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


def test_anthropic_route_sends_thinking_top_level_not_in_extra_body(monkeypatch):
    """ANTHROPIC-THINKING-TRANSPORT-V1: on litellm's `anthropic/` route `extra_body` is NOT merged into the request (it
    goes out as a literal "extra_body" key the endpoint ignores), so DeepSeek's `thinking: disabled` must go top level,
    with `thinking` in `allowed_openai_params` (litellm refuses it otherwise for models it does not map)."""
    monkeypatch.setenv("POLYMATH_REASONING_POLICY", "1")
    k = {"model": "anthropic/deepseek-v4-flash-0731", "messages": [], "allowed_openai_params": ["tools"]}
    applied = apply_litellm(k, CHAT_SYNTHESIS, "anthropic/deepseek-v4-flash-0731")
    assert k["thinking"] == {"type": "disabled"}
    assert k["allowed_openai_params"] == ["tools", "thinking"]
    assert "thinking" not in (k.get("extra_body") or {})
    assert applied["top_level"] == {"thinking": {"type": "disabled"}} and applied["extra_body"] == {}
    # the other routes keep the passthrough the OpenAI SDK merges (unchanged behaviour)
    k2 = {"model": "deepseek-v4", "messages": []}
    apply_litellm(k2, CHAT_SYNTHESIS, "deepseek-v4")
    assert k2["extra_body"]["thinking"] == {"type": "disabled"} and "thinking" not in k2


def test_anthropic_route_wire_body_carries_thinking_disabled(monkeypatch):
    """The wire itself, not the kwargs: litellm serializes the applied request to a local stand-in Anthropic endpoint
    and the captured JSON body must carry top-level `thinking: {"type": "disabled"}` and no literal `extra_body`."""
    import http.server
    import json
    import socketserver
    import threading

    import pytest
    litellm = pytest.importorskip("litellm")
    monkeypatch.setenv("POLYMATH_REASONING_POLICY", "1")
    captured: dict = {}

    class _StandIn(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("content-length", 0))
            captured["path"], captured["body"] = self.path, json.loads(self.rfile.read(n) or b"{}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error":"stand-in"}')

        def log_message(self, *a):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", 0), _StandIn)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        model = "anthropic/deepseek-v4-flash-0731"
        kw = dict(model=model, messages=[{"role": "user", "content": "hi"}], stream=True, timeout=10, max_tokens=64,
                  api_base=f"http://127.0.0.1:{srv.server_address[1]}", api_key="stand-in-not-a-key")
        apply_litellm(kw, CHAT_SYNTHESIS, model)
        try:
            for _ in litellm.completion(**kw):
                break
        except Exception:  # noqa: BLE001 — the stand-in answers 500 on purpose; only the request matters
            pass
    finally:
        srv.shutdown()
        srv.server_close()
    body = captured.get("body") or {}
    assert captured.get("path", "").endswith("/v1/messages"), captured
    assert body.get("thinking") == {"type": "disabled"}, sorted(body)
    assert "extra_body" not in body, sorted(body)


def test_every_catalog_route_gets_a_sendable_reasoning_control(monkeypatch):
    """MODEL-LIST-REASONING-V1, the kwargs half: every family on the Alibaba Anthropic route ends with the Messages API's own
    `thinking: disabled` top level (+ allow-listed); an unknown model on an OpenAI-compatible route gets NO reasoning param
    (litellm would refuse `reasoning_effort` for it); DeepSeek on the OpenAI route keeps the passthrough the SDK merges."""
    monkeypatch.setenv("POLYMATH_REASONING_POLICY", "1")
    for model in ("anthropic/deepseek-v4-flash-0731", "anthropic/qwen3.8-max", "anthropic/qwen3.6-flash", "anthropic/glm-5.2"):
        k = {"model": model, "messages": []}
        apply_litellm(k, CHAT_SYNTHESIS, model)
        assert k.get("thinking") == {"type": "disabled"}, model
        assert "thinking" in k.get("allowed_openai_params", []), model
        assert not (k.get("extra_body") or {}), (model, k.get("extra_body"))
        assert "enable_thinking" not in k and "reasoning_effort" not in k, model
    for model in ("openai/big-pickle", "openai/nemotron-3-ultra-free", "openai/mimo-v2.5-free"):
        k = {"model": model, "messages": []}
        apply_litellm(k, CHAT_SYNTHESIS, model)
        assert "reasoning_effort" not in k and "thinking" not in k and not k.get("extra_body"), (model, k)
    k = {"model": "openai/deepseek-v4-flash-free", "messages": []}
    apply_litellm(k, CHAT_SYNTHESIS, "openai/deepseek-v4-flash-free")
    assert k["extra_body"] == {"thinking": {"type": "disabled"}}


def test_every_catalog_route_wire_body(monkeypatch):
    """The wire half: litellm serializes each representative catalog model to a local stand-in; the Anthropic-route bodies
    carry top-level `thinking: disabled` and no literal `extra_body`, and the unknown OpenAI-route model's request is SENT
    (before the fix litellm raised UnsupportedParamsError and nothing left the process)."""
    import http.server
    import json
    import socketserver
    import threading

    import pytest
    litellm = pytest.importorskip("litellm")
    monkeypatch.setenv("POLYMATH_REASONING_POLICY", "1")
    captured: dict = {}

    class _StandIn(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("content-length", 0))
            captured["body"] = json.loads(self.rfile.read(n) or b"{}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error":"stand-in"}')

        def log_message(self, *a):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", 0), _StandIn)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def wire(model: str) -> dict:
        captured.clear()
        kw = dict(model=model, messages=[{"role": "user", "content": "hi"}], stream=True, timeout=10, max_tokens=64,
                  api_base=f"http://127.0.0.1:{srv.server_address[1]}", api_key="stand-in-not-a-key")
        apply_litellm(kw, CHAT_SYNTHESIS, model)
        try:
            for _ in litellm.completion(**kw):
                break
        except Exception:  # noqa: BLE001 — the stand-in answers 500 on purpose
            pass
        return captured.get("body") or {}

    try:
        for model in ("anthropic/deepseek-v4-flash-0731", "anthropic/qwen3.8-max", "anthropic/glm-5.2"):
            body = wire(model)
            assert body.get("thinking") == {"type": "disabled"}, (model, sorted(body))
            assert "extra_body" not in body and "enable_thinking" not in body, (model, sorted(body))
        body = wire("openai/big-pickle")
        assert body, "the unknown-model request never left litellm"
        assert "reasoning_effort" not in body and "thinking" not in body, sorted(body)
    finally:
        srv.shutdown()
        srv.server_close()


def test_ollama_think_gpt_oss_low_others_off(monkeypatch):
    from polymath_shared.reasoning_policy import ollama_think

    monkeypatch.delenv("POLYMATH_CHAT_THINK", raising=False)
    assert ollama_think("gpt-oss:120b-cloud") == "low" and ollama_think("gpt-oss:20b-cloud") == "low"
    assert ollama_think("gemma4:31b-cloud") is False and ollama_think("nemotron-3-super:cloud") is False
    monkeypatch.setenv("POLYMATH_CHAT_THINK", "on")
    assert ollama_think("gpt-oss:20b-cloud") == "high" and ollama_think("gemma4:31b-cloud") is True


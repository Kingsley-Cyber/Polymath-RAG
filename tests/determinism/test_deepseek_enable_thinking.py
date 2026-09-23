"""DEEPSEEK-ENABLE-THINKING-V1. The owner (2026-09-23): "this is the provider I use, the token plan", pointing to Alibaba
Model Studio's "OpenAI compatible - Chat" reference (updated 2026-09-21).
- On that API, DeepSeek-V4 thinking is switched with `enable_thinking`, top level for raw HTTP. Its `thinking` object is
  documented for MiniMax only.
- The compiler / bridge DeepSeek lane (`deepseek-v4-flash-0731` on the token plan's compatible-mode endpoint) was sent only
  `thinking`, so the owner's rule (thinking off wherever the provider allows it) did not reach it.
- The compiler / bridge client now also records whether the model actually thought (the `reasoning_content` it returned),
  so every call proves the switch at $0."""
from __future__ import annotations

import http.server
import json
import socketserver
import threading

import pytest
from polymath_shared.llm_extraction import client as client_mod
from polymath_shared.reasoning_policy import (
    BRIDGE,
    CHAT_SYNTHESIS,
    S_CHAT_COMPLETIONS,
    S_LITELLM,
    STRUCTURED_COMPILER,
    apply_chat_completions,
    reasoning_params,
)

DS = "deepseek-v4-flash-0731"


@pytest.fixture(autouse=True)
def _policy_on_receipt_in_tmp(monkeypatch, tmp_path):
    monkeypatch.setenv("POLYMATH_REASONING_POLICY", "1")
    # the policy appends every applied setting to a JSONL wire receipt; a test must never write the fleet's file
    monkeypatch.setenv("POLYMATH_REASONING_RECEIPT", str(tmp_path / "reasoning.jsonl"))


def _client(url):
    return client_mod.LLMExtractionClient("cloud", url=url, model=DS, limiter_key="t", api_key="stand-in-not-a-key",
                                          cloud_opts={}, timeout_s=5, max_attempts=1)


def test_deepseek_on_the_openai_compatible_api_gets_the_documented_switch():
    for role in (STRUCTURED_COMPILER, BRIDGE):
        extra = reasoning_params(role, DS, S_CHAT_COMPLETIONS)["extra_body"]
        assert extra["enable_thinking"] is False and extra["thinking"] == {"type": "disabled"}


def test_the_litellm_route_is_unchanged():
    assert reasoning_params(CHAT_SYNTHESIS, DS, S_LITELLM)["extra_body"] == {"thinking": {"type": "disabled"}}


def test_the_switch_lands_at_the_top_level_of_the_raw_payload():
    payload = {"model": DS, "messages": []}
    applied = apply_chat_completions(payload, BRIDGE, DS)
    assert payload["enable_thinking"] is False and applied["top_level"]["enable_thinking"] is False
    assert "extra_body" not in payload


def test_on_the_wire_through_the_real_client_and_a_local_stand_in():
    captured: dict = {}

    class _StandIn(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("content-length", 0))
            captured["path"], captured["body"] = self.path, json.loads(self.rfile.read(n) or b"{}")
            out = json.dumps({"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                              "usage": {"prompt_tokens": 5, "completion_tokens": 2}}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", 0), _StandIn)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = _client(f"http://127.0.0.1:{srv.server_address[1]}/compatible-mode")
        c.reasoning_role = STRUCTURED_COMPILER
        c._chat("plan this", 64, system_prompt="s")
    finally:
        srv.shutdown()
        srv.server_close()
    body = captured["body"]
    assert captured["path"].endswith("/v1/chat/completions")
    assert body["enable_thinking"] is False and "extra_body" not in body


def test_the_client_records_whether_the_model_actually_thought(monkeypatch):
    class _Resp:
        def __init__(self, body):
            self._body, self.headers = body, {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._body

    def post(url, json=None, timeout=None, headers=None):
        return _Resp({"choices": [{"message": {"content": "{}", "reasoning_content": "let me think"},
                                   "finish_reason": "stop"}],
                      "usage": {"prompt_tokens": 5, "completion_tokens": 40}})
    monkeypatch.setattr(client_mod.httpx, "post", post)
    c = _client("https://example.invalid/compatible-mode")
    c.reasoning_role = BRIDGE
    c._chat("make bridges", 64, system_prompt="s")
    assert c.last_reasoning["observed"] == {"reasoning_chars": 12, "completion_tokens": 40, "finish_reason": "stop"}
    assert c.last_reasoning["top_level"]["enable_thinking"] is False               # what was sent, beside what came back

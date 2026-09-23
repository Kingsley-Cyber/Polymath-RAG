---
change_id: MODEL-LIST-REASONING-V1
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "reasoning_policy: model family is classified from the model name (not the litellm route prefix); the Alibaba Anthropic route gets the Messages API's own `thinking: disabled` for Qwen and GLM too; unknown models on litellm get no guessed reasoning parameter; gpt-oss on Ollama gets `think: \"low\"`. Catalog: the 8 OpenCode free models (none answers) are removed and the provider disabled."
last_reviewed: 2026-09-23
---

# Every chat model: the reasoning control reaches the wire, and models that cannot answer leave the list

## Contract
Owner, 2026-09-23: "what about the entire provider model list", then "gpt oss may have low reasoning. every model that doesn't
work in each provider remove it." Expected: every offered chat model receives a reasoning control it actually honours (off,
or the lowest level the model allows), and every model left in the catalog answers.

Found (stand-in wire audit of all 17 litellm models, $0):
- Only the 3 DeepSeek models on Alibaba and `openai/deepseek-v4-flash-free` carried a working control.
- The 5 Qwen models on Alibaba: `enable_thinking: false` sat inside the literal `extra_body` key, and was dropped.
- `anthropic/glm-5.2` was classified "claude" (`provider_family` matched "anthropic" in the route prefix); its `effort: low`
  was dropped too.
- The 7 other OpenCode models were classified "openai" (the "openai" route prefix), so the policy sent `reasoning_effort`,
  which litellm refuses before any request (`UnsupportedParamsError`). None of them could answer.
- The Ollama path does not use the policy. It sends `think: false` unless `POLYMATH_CHAT_THINK` is on.

## Changes
- `shared/polymath_shared/reasoning_policy.py`:
  - `provider_family` classifies `_model_name(model)`, i.e. the string after a known litellm route prefix, and gains a
    `glm` family.
  - `reasoning_params`: GLM gets `thinking: {type: disabled}` (Zhipu's own field). Unknown families get NO guessed
    parameter on the litellm surface.
  - `apply_litellm` on the anthropic route translates Qwen's DashScope switches to `thinking: disabled`, then sends
    `thinking` top level with `allowed_openai_params`.
  - New `ollama_think(model)`: gpt-oss → "low" ("high" if `POLYMATH_CHAT_THINK` is on); other models keep the existing
    switch.
- `orchestrator/orchestrator/api/ui.py` `_ollama_generate_inner`: `think` comes from `ollama_think`.
- `tests/determinism/test_reasoning_policy.py`: `test_family_detection` asserted `openai/big-pickle` → "openai". That
  assertion pinned the bug that made the model unusable; it now expects "other" and covers routed names. 3 new tests:
  kwargs per catalog route; the wire body per representative model through a local stand-in; `ollama_think`.
- Catalog (runtime config, `llm_providers` row `opencode-free`): models → `[]`, `enabled` → false; the stored key is kept.
- `docs/wiki/experiments/model-list-2026-09-23/`: the live canary harness and its 23 rows.

## Proof
- Wire (stand-in, after the fix): Alibaba DeepSeek, Qwen and GLM bodies carry top-level `thinking: {"type": "disabled"}`
  and no `extra_body`; the unknown OpenCode model's request is now sent (no refusal); policy tests 18 / 18.
- Live canary: one "Reply with exactly: OK" per model through the fixed transport, real credentials.
  - Alibaba: 9 / 9 answered in 1.0–2.1 s with 0 reasoning characters.
  - OpenCode free: 0 / 8. Seven answer "OpenCode's free tier can only be used from within OpenCode"; one answers
    "Model is unavailable".
  - Ollama: gemma4, gpt-oss 120b / 20b (accepted `think: "low"`; 85 / 27 reasoning characters), nemotron-3-nano and
    -super answered.
  - nemotron-3-ultra: 503 "temporarily overloaded" twice and 200 once (kept; flagged as flaky capacity).
- Regression: synthesis / telemetry / generation-bound / RAG-UI / model-catalog tests on both trees; see the register row.

## Rejected claims
- "OpenCode failed because of our reasoning bug": only partly. Removing the bad parameter lets the request out; the
  provider itself now refuses its free tier outside OpenCode (memory, 2026-09-21: the same 403 hit the graphify proxy).
- "nemotron-3-ultra is broken": no, it is intermittently overloaded (2 of 3 tries); kept.
- "Claude-family `effort` is fixed on the anthropic route": no Claude model is offered. The route drops `extra_body` for
  every key except those translated to `thinking`; recorded, not fixed.

## Open contract gaps
- REASONING-BOUNDARY-V1 semantics: UPDATED (family classification; unknown-family behaviour on litellm).
- Chat synthesizer catalog: UPDATED (runtime config; 23 → 15 offered models).
- Ollama synthesis request: UPDATED (`think` per model).
- Token accounting for `chat_synth` attempts: DEFERRED (still null).

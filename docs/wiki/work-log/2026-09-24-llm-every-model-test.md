---
change_id: LLM-BACKEND-EVERY-MODEL-TEST
owner: "@king"
date: 2026-09-24
status: complete
status_note: "Every model answered. The only failures were capacity events that cleared on retry or later calls (Mistral upstream 429 on OpenRouter, Google 503 on gemini-3.1-flash-lite for accounts 3 and 4). One L3 regression found by CI was fixed here."
architecture_impact: "Tests + evidence only. One L3 config-snapshot test fixed (test_control_plane_status). 44 real model calls recorded in llm_provider_attempts with stage model_canary (2 more raw diagnostic calls were not recorded)."
last_reviewed: 2026-09-24
---

# Every model tested; one L3 CI regression fixed

## Contract
- The owner, 2026-09-24: "ensure all models works with a tests". Scope:
  - every active provider lane not already covered by the L4a canary (11.468);
  - every chat answer model offered in the UI (`GET /synthesizers`).
- CI on the owner's push `8c2bbfe8` showed one failure not present on `a7e3e388`.

## Changes
- `docs/wiki/experiments/llm-backend-l4-canary-2026-09-24/model_canary.py` → `model_canary.json`, plus
  `model_canary_retest.json`.
  - Provider lanes go through `LLMExtractionClient.complete_one`: the L2 reservation, the call, settle, and an attempt
    row with `stage=model_canary`.
  - Chat models use the chat path's own request shape: `ui._litellm_credentials`, the `CHAT_SYNTHESIS` reasoning policy
    and `ui._chat_max_tokens()` for LiteLLM models; `/api/chat` with `ollama_think` for Ollama. Each call is recorded
    with function `CHAT`, stage `model_canary`.
  - The same one-word prompt everywhere, with a JSON hint for JSON-mode lanes.
- `tests/determinism/test_control_plane_status.py::test_pool_lanes_detail_is_secret_free_and_model_grouped`: 5 → 6
  pMAP lanes per model, with the account set checked (GROQ_API_KEY_1..6). It is a pre-L3 snapshot. L3's impacted list
  missed it because it reads the lanes through `control_plane_status` → `lane_registry`, not the config files.

## Proof
- Provider lanes: 44 active. 23 passed at 02:44 UTC (11.468). The other 21 were called here (EXECUTED 03:3x UTC):
  - OK on the first call (15): compiler_alibaba_deepseek, compiler_ollama_gemma, gemini1, gemini1b, gemini2, gemini2b,
    gemini3b, gemini4b, gemini5, gemini5b, gemini6, gemini6b, openrouter2, openrouter3, openrouter5.
  - HTTP 429 (4), all on `mistralai/mistral-small-2603` across three OpenRouter accounts: compiler_alt, openrouter1,
    profile_fallback_openrouter, map_fallback_openrouter. Other models on the same accounts answered, so the keys are
    fine. On one retest, 3 of the 4 answered. map_fallback_openrouter's raw error body was OpenRouter's "Provider
    returned error" wrapping the upstream `"Rate limit exceeded"` (type `rate_limited`, code 1300): Mistral capacity.
  - HTTP 503 (2): gemini3 and gemini4 on `gemini-3.1-flash-lite` (the same model worked on accounts 1, 2, 5 and 6).
    They were still 503 on one retest; a later raw call on gemini3 answered 200 "OK". Google overload, transient.
- Chat answer models: 15 / 15 answered "OK":
  - 9 Alibaba Model Studio models via LiteLLM: deepseek-v4-flash-0731, qwen3.7-plus, qwen3.6-flash, glm-5.2,
    qwen3.7-max, deepseek-v4-pro, deepseek-v4-pro-0813, qwen3.8-flash, qwen3.8-max;
  - 6 Ollama free-cloud models: gemma4:31b-cloud, gpt-oss:120b-cloud, gpt-oss:20b-cloud, nemotron-3-nano:30b-cloud,
    nemotron-3-super:cloud, nemotron-3-ultra:cloud.
- Calls: 36 first pass + 6 retests, all in the ledger; plus 2 raw diagnostic calls (not in the ledger: raw httpx).
- CI comparison (`8c2bbfe8` against `a7e3e388`, by test name): the same 13 pre-existing determinism failures plus the
  one fixed here. `repo-governance`, `agent-preflight` and `contracts` passed.
- After the fix, locally (safe recipe): `test_control_plane_status`, `test_effective_capacity`, `test_lane_registry`,
  `test_cloudflare_provider` and `test_synthesis_attempt_telemetry` gave 57 tests, 0 failures.

## Rejected claims
- "The OpenRouter keys for mistral-small-2603 are broken": other models on the same three accounts answered, and 3 of 4
  lanes answered on retest.
- "Gemini accounts 3 and 4 are broken": the same account answered a later call. Google's 503 is overload.
- "Use `/llm/test` for the chat models": it sends 20 tokens with no reasoning policy, and reasoning models return empty
  text under that bound. The test used the chat path's own request shape instead.

## Open contract gaps
- None mapped by `contract_impact.py` (tests + evidence only).
- Capacity follow-ups:
  - mistral-small-2603 sits on four lanes (the compiler's cross-family lane, one extraction/enrichment lane and both
    fallbacks), and its upstream 429s repeat. Watch its 429 rate in the ledger. A second fallback model is a candidate
    if it persists.
  - gemini-3.1-flash-lite 503s are Google-side. The limiter's AIMD / breaker already paces them.

---
change_id: DEEPSEEK-ENABLE-THINKING-V1
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "shared code on branch fix/deepseek-enable-thinking (NOT merged, NOT live). On the OpenAI-compatible chat-completions surface, DeepSeek now gets `enable_thinking: false` (top level) beside `thinking: {type: disabled}`. That surface serves the compiler / bridge lanes on Alibaba Model Studio's token plan. The compiler / bridge client records what the model returned (reasoning chars, completion tokens, finish reason) beside what was sent. The litellm route and extraction clients are unchanged."
last_reviewed: 2026-09-23
---

# DeepSeek on the token plan's OpenAI-compatible API gets its documented thinking switch

## Contract
- Owner rule (2026-09-23): thinking off wherever the provider allows it, otherwise ≤ 100.
- Owner, 2026-09-23: "this is the provider I use, the token base plan", pointing to Alibaba Model Studio's "OpenAI
  compatible - Chat" reference (updated 2026-09-21; READ with the in-app browser). It says:
  - `enable_thinking` switches thinking on "the DeepSeek-V4.1-Flash, DeepSeek-V4-Pro/V4-Flash series …". For raw HTTP it
    goes at the top level of the body, not in `extra_body`.
  - The `thinking` object "controls the thinking mode of MiniMax/MiniMax-M3".
  - For `deepseek-v4-flash-0731`, `max_tokens` counts chain-of-thought plus answer, so a bounded compiler call that keeps
    thinking can run out on reasoning.
- The live wire receipt (`/private/tmp/polymath_fleet/reasoning_policy.jsonl`, READ; 686 rows):
  - the compiler lane `deepseek-v4-flash-0731` was sent `{"thinking": {"type": "disabled"}}` only (14 recent rows,
    STRUCTURED_COMPILER, chat_completions);
  - the Qwen lane (`qwen3.8-flash`) was sent `enable_thinking: false` at the top level, which matches the doc.
- The compiler lanes in `config/cloud_providers.json` stage_pins.chat_compiler: `compiler_alibaba_qwen` = qwen3.8-flash and
  `compiler_alibaba_deepseek` = deepseek-v4-flash-0731, both at
  `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode`. The DeepSeek lane is also a bridge backup.

## Changes
- `shared/polymath_shared/reasoning_policy.py` (`reasoning_params`): for `fam == "deepseek"` on `S_CHAT_COMPLETIONS`, add
  `enable_thinking: False`. `apply_chat_completions` puts it at the top level. `thinking: {type: disabled}` stays (DeepSeek's
  own API shape). The litellm surface is unchanged. GLM is deliberately NOT changed: the doc says glm-5.3 accepts only
  `enable_thinking: true`, so `false` would fail those requests, and no compiler / bridge lane is GLM.
- `shared/polymath_shared/llm_extraction/client.py` (`_chat`), for clients with a `reasoning_role` only:
  - `last_reasoning` is reset before each call;
  - after the response, `last_reasoning["observed"]` = `{reasoning_chars, completion_tokens, finish_reason}` from the
    response. `reasoning_chars` is the length of the `reasoning_content` the model returned.
  - With S1b, this reaches `chat_plan.compiler.reasoning` and the bridge `route` receipt, so every call proves at $0
    whether the model thought.
- Tests: NEW `tests/determinism/test_deepseek_enable_thinking.py` (5 tests; the policy is on and its JSONL goes to
  `tmp_path`).
  - The documented switch for STRUCTURED_COMPILER and BRIDGE.
  - The litellm route is unchanged.
  - The switch lands at the top level of the raw payload.
  - **On the wire:** the real client posts to a local HTTP stand-in; the body carries `enable_thinking: false` at the top
    level and no `extra_body`.
  - The client records the model's returned thinking beside what it sent.

## Proof
- **Red first:** 4 of the 5 failed on `517f3dc` (KeyError `enable_thinking` / `observed`). The litellm guard passed by
  design.
- test_deepseek_enable_thinking + test_reasoning_policy + test_compile_steps_and_emitted_reasoning +
  test_compiler_resilience: 42 passed.
- **Lint:** ruff finds the same findings as production on the touched files. The new test file is clean.
- **Contract impact:** none (no changed file maps to an architecture contract).
- **Broad run (EXECUTED):** 51 suites (the S1b list, which includes every `LLMExtractionClient` suite, plus the new
  file), with the worktree PYTHONPATH, no `.env` and `-k "not test_live_"`.
  - Branch: 616 passed, 4 failed.
  - Production `517f3dc` (throwaway detached worktree): 611 passed, the SAME 4 failed. These are the 3 known pre-existing
    failures plus the no-`.env` telemetry PoolTimeout.
  - The +5 are the new tests.

## Rejected claims
- "`thinking: {type: disabled}` already turns DeepSeek's thinking off on the token plan": the provider documents that field
  for MiniMax only. The wire receipt shows it was the only switch sent. Whether the provider honoured it was never recorded,
  which is why the client now records the returned reasoning.
- "Send `enable_thinking: false` to GLM too": no. glm-5.3 rejects it, and GLM is not a compiler / bridge lane.

## Open contract gaps
- LIVE proof: one compiler call on the DeepSeek lane must show `observed.reasoning_chars == 0`. The lane is a fallback
  (gemma goes first), so ordinary turns rarely reach it. A direct one-call probe is a (tiny) live spend, on the owner's word.
- BLOCKED: merge + bounce, on the owner's word.

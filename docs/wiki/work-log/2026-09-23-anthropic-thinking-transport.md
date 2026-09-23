---
change_id: ANTHROPIC-THINKING-TRANSPORT-V1
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "reasoning_policy.apply_litellm: on litellm's `anthropic/` route the policy's `thinking` setting is sent as a top-level request field (with `allowed_openai_params`) instead of inside `extra_body`, which that route serializes as a literal, ignored key. Chat synthesis and the answer reviewer on DeepSeek v4 (Alibaba's Anthropic API) finally get the thinking-disabled request REASONING-BOUNDARY-V1 always specified."
last_reviewed: 2026-09-23
---

# DeepSeek answers stop thinking at full length: `thinking: disabled` reaches the wire

## Contract
Owner, 2026-09-23: "the recent queries took too much reasoning; it took too long to generate an answer."
REASONING-BOUNDARY-V1 (flag `POLYMATH_REASONING_POLICY=1`, on in `.env` and the running orchestrator) already specifies
CHAT_SYNTHESIS on DeepSeek v4 = thinking disabled. Expected: the synthesis request carries it and DeepSeek answers
without a long reasoning phase.

Evidence (all $0):
- The answer-model call dominates each turn: `llm_provider_attempts` lane `chat_synth:anthropic` shows 34–61 s per call
  on the owner's recent "write me a prompt" turns (14–34 s on short factual answers yesterday). The one 134 s call ran
  with 3 chats at once. The ledger records no token counts for this lane.
- The policy WAS applied: `/private/tmp/polymath_fleet/reasoning_policy.jsonl` has CHAT_SYNTHESIS entries with
  `extra_body: {"thinking": {"type": "disabled"}}` on the recent turns.
- It never reached the provider. The chat path's exact kwargs were sent through litellm 1.98 to a local stand-in
  Anthropic endpoint. The captured body keys were `extra_body, max_tokens, messages, model, stream` and `thinking` was
  null. The route serializes `extra_body` as a literal field that an Anthropic-format endpoint ignores.
- Top-level `thinking` alone raises `UnsupportedParamsError` (litellm does not map this model). Top-level `thinking`
  plus `allowed_openai_params=["thinking"]` puts `"thinking": {"type": "disabled"}` in the body.

## Changes
- `shared/polymath_shared/reasoning_policy.py` `apply_litellm`: for `anthropic/` models whose policy sets `thinking`,
  move it top level and add `thinking` to `allowed_openai_params`, keeping any values already there. Other routes are
  unchanged: the OpenAI SDK merges `extra_body` there. The applied-params receipt now records what is actually sent.
  Callers: chat synthesis (`ui._litellm_generate`) and the answer reviewer (`compare_review`).
- `tests/determinism/test_reasoning_policy.py`: 2 new tests.
  1. Kwargs shape for the anthropic route (plus the unchanged non-anthropic route).
  2. A wire test: litellm sends the applied request to a local stand-in server, and the captured JSON must carry
     top-level `thinking: disabled` and no literal `extra_body`. It is skipped when litellm is absent (CI).

## Proof
- Before, on production code with the same stand-in: body has a literal `extra_body` and `thinking` is null.
- After: `test_reasoning_policy.py` 15 / 15. Synthesis / review / telemetry / generation-bound / RAG-UI tests: 50 / 50 on
  this tree, against 48 / 48 on production (the 2 new tests are the difference).
- Deployed proof (after the bounce) is in the register row. The owner's next DeepSeek answer should stream no
  reasoning, and its `chat_synth` attempt latency should drop.

## Rejected claims
- "The Reasoning dropdown controls this": no. It only adds prompt templates (none / step by step / …); provider
  thinking is the backend policy.
- "The flag was off": no. `POLYMATH_REASONING_POLICY=1` in `.env` and in the running orchestrator's env; the transport
  dropped it.
- "Every extra_body policy key is fixed on the anthropic route": no. Only `thinking` is handled. A Claude-family
  `effort` sent through `extra_body` on this route would also be ignored. No offered chat model uses it today, so it is
  recorded, not fixed.

## Open contract gaps
- REASONING-BOUNDARY-V1 policy semantics: TESTED_UNCHANGED (same decision per role and family); transport: UPDATED.
- Chat synthesis output: UPDATED in behaviour (no DeepSeek reasoning phase, as the policy always specified). The UI
  reasoning pane stays empty for DeepSeek answers.
- Answer reviewer (`compare_review`, REVIEWER role): UPDATED through the same function.
- Token accounting for `chat_synth` attempts (tokens_in / tokens_out null): DEFERRED.

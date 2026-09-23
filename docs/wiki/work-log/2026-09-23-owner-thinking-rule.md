---
change_id: OWNER-THINKING-RULE
owner: "@king"
date: 2026-09-23
status: complete
architecture_impact: "shared/ code on branch fix/document-rag-easy-wins (NOT merged, NOT live): the reasoning policy applies the owner's rule. Thinking is disabled wherever the provider allows it, otherwise ≤ 100 tokens, and gpt-oss runs low. The compiler lanes were re-qualified live with one tiny compile call each."
last_reviewed: 2026-09-23
---

# Owner thinking rule: disabled where possible, otherwise ≤ 100 tokens, gpt-oss low; keep only models that work

## Contract
Owner, 2026-09-23: "If we can turn thinking off or greatly reduce it, I don't mind thinking maybe 100 max… I have a lot of
models from different providers, so I just want to keep the models from the providers that work… the Alibaba models have
different params, with Ollama free. So I only want to keep the models that work, and they should be configured with the
lowest-token thinking, no more than 100, or thinking disabled if plausible, or for OSS low."

## Changes
- `shared/polymath_shared/reasoning_policy.py`:
  - `OWNER_MAX_REASONING_TOKENS = 100`;
  - role budgets BRIDGE / STRUCTURED_COMPILER / REVIEWER go from 200 / 300 / 200 to 100;
  - env reasoning overrides are capped at 100;
  - Qwen: hybrid models get `enable_thinking: false` (+ `preserve_thinking: false`) on every surface and for every role;
    thinking-only Qwen models ("thinking" in the name, or `qwq`) get `thinking_budget` ≤ 100, and nothing on the Responses
    API, where neither control exists;
  - the module docstring is updated;
  - unchanged: DeepSeek / GLM disabled; gpt-oss `reasoning_effort` / Ollama `think` "low"; Gemma / Mistral no params.
- `tests/determinism/test_reasoning_policy.py`, changed to the owner's new contract (these were deliberate REASONING-BOUNDARY-V1
  pins, and the owner has now replaced that decision):
  - the Qwen chat-completions and litellm tests now assert disabled, not a 300 budget;
  - the env-override test uses a thinking-only model and asserts the 100 cap;
  - the overlay test and the E1 wire test assert `enable_thinking: false` for Qwen.
- Tests added:
  - a thinking-only Qwen gets a budget ≤ 100;
  - every role budget is ≤ 100;
  - Gemma never receives `reasoning_effort`.
- The compiler stage pin is unchanged. All four lanes qualify; see the proof.

## Proof
- EXECUTED on local Ollama 0.34.2 (free), gemma4:31b-cloud via `/v1/chat/completions` (`/api/show` capabilities include
  "thinking"):
  - no param: 0 reasoning characters, 0.5 s, 28 tokens;
  - `reasoning_effort: "none"` and `think: false`: the same;
  - `reasoning_effort: "low"`: 1,145 reasoning characters, 300 tokens exhausted, EMPTY content.
- EXECUTED live compiler canary (branch code, policy on, the real `compile_plan` prompt, 6 s timeout like production, 2
  questions per lane, the client called directly so no limiter or ledger rows were written):

  | Lane | Before (7 days) | Now |
  |---|---|---|
  | deepseek-v4-flash | 7 / 13 fallbacks | 4.7 s and 3.5 s, valid plans |
  | qwen3.8-flash | 22 / 23 fallbacks | 4.9 s and 4.8 s, valid plans |
  | gemma4:31b-cloud | 2.8% fallbacks | 2.7 s and 2.0 s, valid |
  | mistral-small (OpenRouter) | 8% fallbacks | HTTP 429 twice |

  The mistral 429 is "Rate limit exceeded" from the owner's own Mistral account (BYOK, `limit_source`
  upstream_provider_account). That is a capacity event under the owner's qualification rule: the lane is kept, and the
  compiler's failover + cool-down paces it.
- `test_reasoning_policy.py` 22 / 22 green (branch).
- Guards: see the commit.

## Rejected claims
- "Remove the Alibaba compiler lanes": they work once thinking is disabled on the wire.
- "Remove mistral": a 429 is capacity, not breakage (the owner's rule). It served 110 plans in 7 days.
- "Send `reasoning_effort=low` to every model for safety": on Gemma 4 it turns thinking ON and empties the answer.

## Open contract gaps
- The reasoning policy (compiler / bridge / reviewer / synthesis families): UPDATED, with tests.
- The live effect is measured after merge + bounce (compiler lane fallback rates from receipts): DEFERRED to the merge.
- The chat-synthesis catalog was re-qualified in 11.412 (Alibaba 9 / 9 thinking-off; Ollama 6 usable, gpt-oss low;
  nemotron-3-ultra intermittently overloaded = capacity, kept): NOT_AFFECTED.

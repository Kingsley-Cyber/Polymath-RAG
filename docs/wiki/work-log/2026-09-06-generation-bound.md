---
title: "WORK LOG — GENERATION-BOUND-V1: the chat path owns its output bound; a cut answer is receipted, never silent"
change_id: GENERATION-BOUND-V1
date: 2026-09-06
owner: governance (found while proving PRESENTATION-V1: a live artifact test returned a 66-character answer with no error)
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.106
package: orchestrator/orchestrator/api/ui.py (_litellm_generate, _chat_max_tokens, _bound_rejected, chat_events consumer), tests/determinism/test_chat_generation_bound.py, tests/determinism/test_chat_synthesis.py (abstention wording), .env.example
architecture_impact: "Chat generation layer only (LiteLLM path; the Ollama path is unchanged). LiteLLM sends Anthropic-format providers DEFAULT_MAX_TOKENS = 4096 when the caller gives no bound (litellm/constants.py; the Anthropic transformation requires one). deepseek-v4-flash on Alibaba Model Studio spends most of that on reasoning, so long answers ended mid-sentence with no error, no finish_reason and no receipt. Now: the chat path sends POLYMATH_CHAT_MAX_TOKENS (default 16000; 0 = none), records the provider's finish_reason in result.meta.generation and the query receipt, appends `generation / truncated:max_tokens` to the degraded list when the provider stops at the bound (visible on the answer event, the /chat JSON and the receipt, rendered by the existing degraded note in the UI), and retries ONCE without the bound when a provider rejects the number itself (`generation / max_tokens_rejected:<n>` receipted). Any other provider error stays the typed `litellm_error`."
---

# WORK LOG — GENERATION-BOUND-V1

## Contract

A generated answer is either complete or visibly marked as cut. The chat path decides the output bound (not a library default), the provider's stop reason is part of the answer receipt, and a provider that refuses the bound is retried once without it with a receipt of that too. Nothing about prompts, evidence or authority changes.

## Changes

- `_litellm_generate`: `max_tokens=_chat_max_tokens()` on the completion call; `finish_reason` captured from the streamed choice; final piece `{"finish": {"finish_reason", "max_tokens"}}`; on an exception before the first chunk whose text names the bound (`_bound_rejected`: "max_tokens", "max_completion_tokens", "max output tokens") one retry without the bound and a `{"degraded": {...}}` piece; other exceptions unchanged (`litellm_error`).
- `chat_events` consumer: `degraded` pieces append to `retrieval["degraded"]`; the `finish` piece becomes `meta.generation` and, on `length`, a `generation / truncated:max_tokens` degraded entry; both ride the answer event, the /chat JSON (same runtime) and the query receipt (`meta.generation`).
- `.env.example`: `POLYMATH_CHAT_MAX_TOKENS=16000`.
- `test_chat_synthesis.py`: the live abstention test now checks the SYNTHESIS-V2 invariant instead of a wording list — the opening 400 characters name the absent term with a negation ("never mentions a Zorblax-9 …, I won't invent them"; "contains **no mention of** …"), Markdown emphasis stripped first; the model abstained correctly on every run, the old regex knew only "not in the corpus" and was blind to bold.

## Proof

- Measured cause: LiteLLM 1.98 `constants.DEFAULT_MAX_TOKENS = 4096` is applied by the Anthropic transformation when the caller sets none (`anthropic/chat/transformation.py`: "anthropic requires a default value for max_tokens"); the chat path set none. Observed on `anthropic/deepseek-v4-flash-0731` (Alibaba Model Studio, reasoning streamed as `reasoning_content`): the brainrot artifact fixture returned a 66-character answer twice in a row (full suite + re-run) and, on a third run, 5,773 answer characters after 12,972 reasoning characters ending at "which is what separates" — no `error` event, no finish reason anywhere; in the presentation probes 1 of 10 before-answers ended mid-table ("Not covered in the retrieved pages — the") and 3 of 10 draft-A after-answers were EMPTY after 47–51 s of reasoning (the longer system prompt lengthened the reasoning, so the 4096 budget was spent before the first answer token).
- Offline: `tests/determinism/test_chat_generation_bound.py` (10 tests: bound sent and finish receipted; `length` named; rejection → one retry without the bound + degraded receipt; other errors stay typed; 0 disables; bad value → default; wording matrix) green; chat synthesis / runtime suites green.
- Live (after the respawn with the bound): the brainrot artifact fixture (the 66-character failure) now returns 6,981 characters ending in a full sentence after 26,119 reasoning characters, `meta.generation = {finish_reason: stop, max_tokens: 16000}`, no degraded generation entry; both artifact live tests PASS; the JSON route with the LLM synthesizer carries the same receipt (412-character answer, `stop`, 16000); a short stream turn shows `finish_reason: stop`; the shipped-wording probe answered 10 / 10 with 0 cut answers where draft A without the bound had 3 empty.

## Rejected claims

- "Disable thinking for the chat path instead" — rejected: the reasoning card (REASONING-STREAM-V1) is an owner-visible feature and the cut also happens to long plain answers; the bound is the cause, so the bound is the fix.
- "Pick a bound per model" — rejected for now: a provider that rejects the number is retried without it and receipted; a per-provider `max_tokens` column can follow if a rejection is ever seen in receipts.

## Open contract gaps

- Providers that silently clamp the bound (no `length` finish) still cannot be detected; only the provider's own stop reason is receipted.
- The Ollama path has no bound and no finish receipt (its `done` chunk carries `done_reason`; not wired).

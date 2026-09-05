---
title: "WORK LOG — P0.b CHAT-INTENT-PLAN-V1 in shadow: every streaming turn is compiled and receipted, nothing downstream changes yet"
change_id: CHAT-INTENT-PLAN-V1
date: 2026-09-05
owner: governance (executing CHAT-QUERY-COMPILER-PLAN §4 P0.b)
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.87
package: shared/polymath_shared/chat_plan.py, orchestrator/orchestrator/api/ui.py, config/cloud_providers.json, config/extraction_models/limiter.yaml, scripts/chat_compiler_canary.py, eval/fixtures/chat_conversations/*.json, tests/determinism/{test_chat_compiler.py,test_chat_hygiene.py}
architecture_impact: "New deterministic policy module shared/polymath_shared/chat_plan.py (contract chat-intent-plan-v1: validation, task-class guard, corrections, fallback, prompt). New stage pin `chat_compiler` with five dedicated lanes (compiler1–4 = Gemini keys 1–4 @ gemini-3.1-flash-lite; compiler_alt = OpenRouter mistral-small-2603) on their own local limiter keys; the extraction roster is unchanged. The streaming handler compiles every turn behind POLYMATH_CHAT_COMPILER (off | shadow | on, default shadow): in shadow the compile runs beside retrieval and is only receipted and shown; `on` (P0.c) makes it the serial stage 0. No retrieval, prompt or budget behavior changes in this phase."
---

# WORK LOG — P0.b compiler in shadow

Plan gate: *fallback rate < 5 % on B; task verb preserved on 100 % of fixtures; p50 compile ≤ 2.5 s.*

## Contract

- `chat_plan.compile_plan(message, history, corpus_ids, complete)` → `ChatPlan` (§3.1 fields incl. `semantic_queries` + verbatim `exact_terms`, `must_answer`, `antecedent`, `graph_useful`, `response_type`). `validate_plan` enforces the enums, ≤ 4 queries of ≤ 32 topical words with exactly one PRIMARY, no queries for no-retrieval tasks, and **law 1**: the resolved request keeps the original's task class (compare / list / decide / rewrite / create / explain / summarize / continue / convert) or the plan is rejected.
- **Corrections (CHAT-PLAN-CORRECTIONS-V1)**, lane-independent, each recorded in `compiler.corrections`: an explicit corpus reference ("use everything my cinema books know…") forces retrieval and forbids the no-retrieval task types; "the final prompt/version" with an assistant turn to refer to and no corpus reference is `CONTINUE_PRIOR_ARTIFACT` with no retrieval.
- **Fallback** = today's behavior (GROUNDED_QA, retrieval required, PRIMARY = raw message), flagged with a reason; a soft budget (2.5 s, receipted as `over_budget`) and a hard budget (6 s → fallback).
- **Lanes:** `_compiler_attempt_order` — home lane by session key, then a lane of a different provider family, then the ring neighbour; a lane that failed on transport cools for 120 s; HTTP timeout 6 s; up to 3 attempts, transport failures only.
- Receipts: `meta.chat_plan` on every `chat_stream` receipt; the answer event carries `retrieval.chat_plan`; a `compile` phase event shows task_type / retrieval_required / fallback / wall.

## Changes

- `shared/polymath_shared/chat_plan.py` (new). `orchestrator/api/ui.py`: `_compiler_flag`, `_compile_chat_plan`, `_compiler_attempt_order`, shadow compile beside retrieval, join before the answer event.
- `config/cloud_providers.json`: providers compiler1–4, compiler_alt (dedicated, json); `stage_pins.chat_compiler`. `config/extraction_models/limiter.yaml`: matching lanes (conc 2).
- `eval/fixtures/chat_conversations/`: brainrot_transform, followup_creativity, cinema_improve_prompt, authors_agree, exact_terms_rapo (+ video_prompt_final from P0.0).
- `scripts/chat_compiler_canary.py`: readiness canary + gate tool → `docs/wiki/experiments/chat-compiler-p0b-shadow.{json,md}`.
- Tests: `test_chat_compiler.py` (10: contract, fallback paths, soft/hard budget, law 1 incl. the artifact-continuation exception, two query representations with verbatim exact terms, topical/short/bounded queries, no queries for no-retrieval tasks, history window, fixtures' expectations, corrections); `test_chat_hygiene.py` +1 (attempt order: family-diverse, deterministic, cooldown, never empty).

## Proof (gate numbers, canary on the shipped code, 2026-09-05)

| gate | required | measured |
|---|---|---|
| fallback rate on B (n = 30) | < 5 % | **0.0 %** |
| task verb preserved | 100 % of fixtures | **6 / 6** (and 30 / 30 on B) |
| p50 compile wall | ≤ 2.5 s | **2.01 s** (p90 4.26 s) |
| fixtures classified as expected | (readiness canary) | **6 / 6**: TRANSFORM (no retrieval), CONTINUE (no retrieval), CREATE_FROM_KNOWLEDGE, GROUNDED_SYNTHESIS ×2, GROUNDED_QA with `exact_terms = ["RAPO"]` |

Path to the numbers (recorded, not hidden): attempt 1 of the gate canary measured 6.7 % fallback (2 × 12 s ReadTimeouts: two Gemini attempts in a row) and one lane hang of 24 s; fixes were the 6 s HTTP timeout, the cross-family second attempt and the lane cooldown. Attempt 2 met the gate (0 %) but the cross-family lane swapped CREATE_FROM_KNOWLEDGE and CONTINUE_PRIOR_ARTIFACT on 2 fixtures; the deterministic corrections closed that lane-quality gap; attempt 3 (final code) is the table above. Gemini 503s were frequent today (78 in enrichment logs), which is why most canary calls landed on `compiler_alt`.

- Live: the streaming path compiles every turn in shadow with no added latency (the compile runs beside retrieval; `phase_ms.compile_joined` on receipts). Full determinism suite green; chat test files green.

## Rejected claims

- "Fall back whenever a compile exceeds 2.5 s." Rejected: turns latency variance into lost plans; the soft budget is measured, the hard budget (6 s) falls back.
- "Walk the ring to the next Gemini lane on failure." Rejected: a provider-wide 503 storm eats both attempts; the second attempt crosses families.
- "Trust the lane's task_type as-is." Rejected: measured swap on 2 of 6 fixtures; two deterministic rules (corpus reference, prior artifact) make the classification lane-independent where it matters for P0.c.
- "Pin the compiler to gemini5/6 (enrichment lanes)." Rejected: rpd 500 per key is already consumed by enrichment; keys 1–4 host extraction, idle between ingests, plus one cross-family lane.

## Open contract gaps

- Task-type accuracy is measured only on 6 fixtures + the B question style; P1.g grows the conversation suite.
- The shadow join waits up to 8 s for a slow compile before the answer event; in `on` mode the hard budget bounds it at 6 s per attempt (P0.c will cap total attempts by wall).
- Google's per-key per-model quota is shared with the extraction lanes on keys 1–4 (documented in the provider notes).

---
change_id: PMAP-FORENSIC-AUDIT-V1
date: 2026-09-13
last_reviewed: 2026-09-13
status: evidence (frozen)
architecture_impact: none (read-only forensic audit of the Parent-MAP production request path; production request byte-identical; evidence preserved with raw provider bodies; no production change made — the deterministic fix is specified, not applied)
---

# POLYMATH PARENT-MAP FORENSIC AUDIT — 2026-09-13

Repository `Kingsley-Cyber/Polymath-RAG`, branch `architecture/evidence-first-v5`. Every claim below
cites file:symbol, constant, commit, or a captured runtime record. Raw provider bodies are preserved in
`run1-*.json` / `run2-*.json` in this directory (captured via an `httpx.post` interception that recorded
the outbound payload and full response without altering what was sent; credential scan clean).

## 1. BLUF

**The 15-parent cap is not an inherent Compound-Mini ceiling, and the primary hypothesis (an artificial
output-token limit) is disproven.** With the production request byte-identical, on Groq lanes that still had
daily budget, **batch 40 mapped 40/40 (`finish_reason=stop`, 0 compiler rejections, 40 persisted)**.

Parents disappear at the **provider stage**, for two measured reasons:

1. **Daily TOKEN exhaustion (HTTP 429).** `groq/compound-mini` runs on `llama-3.3-70b-versatile`, whose
   binding limit per org is **100,000 tokens/day** (429 body: `Limit 100000, Used 99497, Requested 3547`);
   RPD 250 and TPM 70,000 were both slack when it fired. A 15-parent request costs ~6.1k tokens (4,041 prompt
   + 2,051 completion), so one org supports **~16 requests/day** — this, not a model ceiling, is what stalls
   cinema.
2. **Intermittent EMPTY 200s.** Captured live: `HTTP 200, finish_reason=stop, completion_tokens=3420,
   content=""` on a **21-alias** request, on a lane at 98,114/100,000 TPD. Not size-driven, not truncation,
   not tools. Empties cluster as an org approaches TPD exhaustion (09-08 was "exhausted today's Groq budget";
   Phase 2's empties ran under heavy burn; today's on a 98k lane; fresh-budget lanes mapped 40/40 clean).

Both are accelerated by two local defects: **compound-mini's completion is ~5× its visible text** (billed
hidden orchestration; the `reasoning` field is present but empty) and **local admission counts ~1/5 of real
tokens** (`len(user_prompt)/4`, no system prompt, no completion — `client.py:474`), so the limiter never
paces and slams into 429/EMPTY. The 15-cap "helped" on 09-08 only because smaller requests fit more
attempts into a dying budget. A **real** model cliff does exist between 40 and 50: at N=50 the model emitted
a strict positional run P0001–P0030 and stopped (`finish=stop`) — a partial, not a truncation.

## 2. Exact Production Request Path

```
map_batches.plan_batches (shared/polymath_shared/document_profile/map_batches.py:mapping_only_capacity → min(target 60, theoretical ~68, reliability_cap 15))
→ doc_parent_map_worker.run_document_mapping (workers/workers/doc_parent_map_worker.py:run_document_mapping; batches sequential: `for batch in plan.batches`)
→ build_map_prompt (shared/polymath_shared/document_profile/map_prompt.py:build_map_prompt → (MAP_SYSTEM 1572 chars, user prompt))
→ infer closure
    worker:   workers/workers/doc_parent_map_stage_worker.py:143 → client.complete_one(user, system_prompt=system, max_tokens=MAX_MAP_TOKENS)   [MAX_MAP_TOKENS = 2400, :54]
    backfill: scripts/parent_map_backfill.py:_routed_infer:89   → client.complete_one(user, system_prompt=system, max_tokens=2400)
→ LLMExtractionClient.complete_one (shared/polymath_shared/llm_extraction/client.py:466) — limiter.admit(est_tokens=len(user_prompt)/4.0) (:474) → §15 Attempt record
→ LLMExtractionClient._chat (client.py:351) — builds payload, httpx.post(f"{base_url}/v1/chat/completions") (:403)
→ HTTP POST https://api.groq.com/openai/v1/chat/completions   (Groq DIRECT; lane spec config/cloud_providers.json:434+)
→ _chat parses choices[0].message.content, finish_reason → self._last_finish_reason (:411, NEVER persisted or read on the map path), usage.prompt_tokens/completion_tokens (:421-422)
→ map_compiler.compile_maps (shared/polymath_shared/document_profile/map_compiler.py:201)
→ persist document_parent_maps / document_parent_map_batches (doc_parent_map_worker.py:298-320; only raw_response_hash is stored, never the body)
→ backfill accounting (parent_map_backfill.py:summarize; §15 ledger llm_provider_attempts)
```

## 3. Actual Outbound Groq Request

Captured payload keys, every request, both runs: **exactly `['max_tokens', 'model', 'stream', 'temperature']` + `messages`.**

| field | actual value | source |
| --- | --- | --- |
| model | `groq/compound-mini` | lane spec `config/cloud_providers.json` (`map_groq2..6`) |
| messages | `[{system: MAP_SYSTEM (1572 chars)}, {user: skeletons}]` | `map_prompt.py:MAP_SYSTEM`, `build_map_user_prompt` |
| temperature | `0.0` | `client.py:46 GENERATION_CONFIG["temperature"]` |
| max_tokens | **`2400`** | worker `doc_parent_map_stage_worker.py:54 MAX_MAP_TOKENS`; backfill literal `parent_map_backfill.py:89` |
| stream | `false` | `client.py:361` |
| max_completion_tokens | **omitted** | — |
| top_p | **omitted** | — |
| reasoning_effort | **omitted** (`cloud_opts.reasoning_effort=None`, `client.py:379`) | lane spec `reasoning_effort: null` — **Groq rejects it for this model: HTTP 400 "`reasoning_effort` is not supported with this model"** (run2 arm C) |
| response_format | **omitted** (`json_mode=false`, `structured=text`, `client.py:391-402`) | lane spec |
| enable_thinking | **omitted** | `client.py:385` |
| tools / tool_choice / compound_custom | **omitted** — no tool-control parameter exists anywhere in the map path | grep: none |
| timeout | 90 s (client-side httpx) | `timeout_s=90.0` at both call sites |

The planner's `COMPLETION_ENVELOPE_TOKENS=6500` **never reaches the request** — it is a planning constant
only (`map_batches.py`). The lane's `request_char_budget=18000` is **inert on the map path** (enforced only in
the extraction path, `workers/llm_provider.py:328-377`; `complete_one`/`_chat` never check it).

## 4. Token Budget Findings — planner vs runtime

| quantity | planner assumes | measured at runtime (run1/run2) |
| --- | --- | --- |
| completion cap sent | 6500 (`COMPLETION_ENVELOPE_TOKENS`) | **2400** |
| does `max_tokens` bound completion? | implicitly yes | **No.** `completion_tokens` exceeded 2400 with `finish=stop` at N=20 (2723), 30 (3033), 40 (3628), 50 (4010). Never `finish=length`. |
| input tokens / parent | 135.7 (`DensityModel`) | **~250–270** (N=15: 4041/15; N=20: 4898/20; N=40: 8982/40; N=50: 10886/50) |
| billed completion / parent | 87 | **~90–137** (N=15: 2051/15=137; N=40: 3628/40=91) |
| visible / billed | 29 / 87 (3×) | **~1 : 5** (N=15: ~404 visible vs 2051 billed); `message.reasoning` present but **empty** — the overhead is hidden orchestration |
| chars→tokens | chars/4 (`skeleton_prompt_tokens`, `client.py:474`) | **~1.56 chars/token** (6295 chars → 4041 tokens): the estimate undercounts prompt **2.6×** |
| admission estimate vs real request | `len(user_prompt)/4` | N=15: est ~1181 vs actual total 6092 → **~5× undercount**; system prompt (393 tok) and all completion excluded |
| provider limits (per org) | none declared — lane spec has no `rpm/rpd/tpm`; `config/limiter.yaml` has no map entries | **RPD 250, TPM 70,000, TPD 100,000** (headers + 429 body) |

## 5. Batch Qualification Results — 15 / 20 / 30 / 40 / 50 / 60

Production request, real skeletons, production compiler+persistence. Run1 sizes 15/20 landed on `map_groq2`
before its TPD ran out; run2 sizes 30–60 rotated across `map_groq3..6` (TPD room). **Single sample per size —
this establishes feasibility and mechanism, NOT stability; repeats are required before promotion.**

| N | HTTP | finish | max_tokens | prompt_tok | comp_tok | MAP lines | compiled | rejected | persisted | requests | note |
| -: | --- | --- | -: | -: | -: | -: | -: | --- | -: | -: | --- |
| 15 | 200 | stop | 2400 | 4041 | 2051 | 15 | 15 | — | 15 | 1 | complete |
| 20 | 200 | stop | 2400 | 4898 | 2723 | 19 | 19 | — | 19 | 1 | model omitted 1 |
| 30 | 200 | stop | 2400 | 6672 | 3033 | 29 | 29 | — | 29 | 1 | model omitted 1 |
| **40** | 200 | stop | 2400 | 8982 | 3628 | **40** | **40** | — | **40** | 1 | **complete** |
| 50 | 200 | stop | 2400 | 10886 | 4010 | 30 | 29 | `empty_signature`:1 | 29 | 2 | positional cutoff P0001–P0030; repair req → **EMPTY** (200/stop/3420 tok/0 content) |
| 60 | 429 | — | 2400 | — | — | — | — | — | 0 | 1 | TPD: `Limit 100000, Used 98114, Requested 7005` (historically HTTP 413 at 60 when budget exists) |

Run1's 30–60 and all of arm B are **void** (every request landed on the TPD-exhausted `map_groq2` because
that harness rebuilt the round-robin closure per size — recorded as a harness defect, corrected in run2).

## 6. Raw Response Yield — requested vs provider MAP lines

| N | requested | MAP-looking lines returned | provider loss (E/D) |
| -: | -: | -: | --- |
| 15 | 15 | 15 | 0 |
| 20 | 20 | 19 | 1 omitted (E) |
| 30 | 30 | 29 | 1 omitted (E) |
| 40 | 40 | 40 | 0 |
| 50 | 50 | 30 (+ repair 0) | 20 omitted (E, positional), repair EMPTY (D) |

## 7. Compiler Yield — exact rejection reasons

Across all 2xx responses: `not_a_map_line` 0 · `malformed_too_few_fields` 0 · `alias_unknown` 0 ·
`alias_ambiguous` 0 · **`empty_signature` 1** (N=50) · `duplicate_alias` 0. MAP lines → compiled maps was
1:1 except that single line. **The compiler is not where parents disappear** (category G ≈ 0).

## 8. Persistence Yield — compiled vs durable

compiled == persisted (readback) == backfill-credited at every size: 15/15, 19/19, 29/29, 40/40, 29/29.
Categories H and I = 0.

## 9. Provider Quota Reconciliation — map_groq1..6

Compound-mini is served by `llama-3.3-70b-versatile`; the org limits observed are **RPD 250 · TPM 70,000 ·
TPD 100,000**. `map_groq1` is held out of the map pool (`stage_pin` = groq2..6 + openrouter). Per-key 1-token
probes returned **distinct** `remaining-requests` (208/223/231/234/234 of 250) and **distinct** reset clocks
(4h02m / 2h36m / 1h49m / 1h32m / 1h32m) → **the keys are separate budgets; the "six capacity domains"
assumption holds.** §15 ledger, last 24h:

| lane | dispatched | 200 | 429 | other | LIMITER_REFUSED | refused-but-dispatched | avg comp tok |
| --- | -: | -: | -: | -: | -: | -: | -: |
| map_groq2 | 51 | 30 | 20 | 1 | 0 | **0** | 2410 |
| map_groq3 | 43 | 30 | 12 | 1 | 0 | **0** | 2358 |
| map_groq4 | 35 | 34 | 1 | 0 | 0 | **0** | 2088 |
| map_groq5 | 32 | 29 | 3 | 0 | 0 | **0** | 2334 |
| map_groq6 | 32 | 30 | 2 | 0 | 0 | **0** | 2341 |
| map_fallback_openrouter | 29 | 29 | 0 | 0 | 0 | **0** | **431** |

**Critical invariant holds: LIMITER_REFUSED consumed zero provider requests** (0 refusals; 0
refused-and-dispatched). Local `day_count` cannot be reconciled to provider TPD because the local limiter
declares no token budget for these lanes at all. The uneven 429s reflect uneven TPD consumption (groq2 was the
first lane of every fresh closure). mistral-small's 431 avg completion for identical work is the control
that isolates compound-mini's ~2,300 hidden overhead.

## 10. Retry Waste / Duplicate Dispatch

- Repair semantics are correct: the N=50 repair re-issued **only the 21 missing aliases** (user prompt 6779
  chars vs 16617), and `duplicate_parent_maps=0` across all runs (structural — disjoint slices, `map_hash`).
- Waste observed: the immediate repair after a partial returned **EMPTY and billed 3,420 tokens** — ~3.4% of
  an org's daily budget for nothing. Historically the worker retried EMPTY batches up to 16 times
  (`document_parent_map_batches.attempt_count` avg 16 on 938 partial batches) — under TPD pressure that is
  pure quota burn.
- Harness defect (run1) mis-routed 12 consecutive requests to one key; flagged, not a production path.

## 11. Failure Classification (this audit's requests)

| category | count | evidence |
| --- | -: | --- |
| A. never admitted locally | 0 | ledger `limiter_admitted=false` = 0 |
| B. admitted, never dispatched | 0 | `refused-but-dispatched` = 0; every admitted attempt has `http_dispatched=true` |
| C. HTTP/provider failure | 13 | run1: 10×429 (groq2 TPD `Used 99497`); run2: 1×429 (N=60, `Used 98114`); arm C: 3×400 (`reasoning_effort` unsupported) |
| D. provider returned EMPTY content | 1 | run2 N=50 repair: 200/stop/3420 tok/0 chars — plus Phase 2's 5+2 empties (low tokens 26–1370) |
| E. provider returned PARTIAL content | 3 | N=20 (19/20), N=30 (29/30), N=50 (30/50 positional) — all `finish=stop` |
| F. generation hit token/output limit | **0** | `finish=length` never observed; completion > `max_tokens` with `stop` at 20/30/40/50 |
| G. compiler rejected records | 1 | `empty_signature` ×1 (N=50) |
| H. persistence lost accepted maps | 0 | compiled == readback |
| I. backfill accounting mismatch | 0 | credited == persisted |
| J. retry duplicated/wasted | 1 | the EMPTY repair (3,420 tokens) |
| K. unresolved | 0 | — |

## 12. Root Cause

**PROVEN**
- The outbound request is `{model, messages, temperature 0.0, max_tokens 2400, stream false}` and nothing else.
- `max_tokens` does **not** bound compound-mini's billed completion; `finish_reason=length` never occurs. **Output truncation is not the cause.**
- Compound-mini is served by llama-3.3-70b-versatile; the binding provider limit is **100k tokens/day/org**.
- Compound-mini bills ~5× its visible output as hidden completion; it **rejects `reasoning_effort`** (400).
- **Batch 40 maps 40/40 with the production request** under fresh budget → 15 is not an inherent ceiling.
- The compiler, persistence, backfill crediting, and the local limiter lose ~nothing (G≈0, H=I=0, A=B=0).
- Local admission undercounts real tokens ~5×; the lane spec declares no provider budget; `finish_reason` is dropped on the map path; the body is never stored.
- Tools are not the mechanism (`executed_tools` absent on every response, including the EMPTY one). `json_mode` is correctly off.

**STRONGLY SUPPORTED (needs repeats to prove)**
- EMPTY 200s (D) are a compound-orchestration failure that clusters as an org nears TPD exhaustion; they are not batch-size-driven (a 21-alias request went empty).
- The model has a structured-output cliff between 40 and 50 (positional cutoff at 30 of 50).

**DISPROVEN**
- Artificial ~1200–2400 output ceiling as the 15-limit's cause · tool-router firing · JSON-mode mismatch · compiler over-rejection · persistence loss · local admission starvation · shared org across the six keys · "≥25 aliases is inherently unreliable".

## 13. Deterministic Fix (smallest change that corrects the actual problem)

1. **Account for real tokens and pace to the provider's daily budget.** In `complete_one` (`client.py:474`) admit
   on `(len(system)+len(user))/1.56 + expected_completion` instead of `len(user)/4`; on every 2xx feed
   `usage.prompt_tokens+completion_tokens` into the lane limiter (it already receives headers via
   `record_success(headers=hdrs)`), and give each `map_groq*` lane a declared **`tpd: 100000`** (new lane field,
   `lane_registry.py` + `config/cloud_providers.json`) that the limiter enforces with pacing/backoff. This turns
   429/EMPTY storms into deterministic waiting.
2. **Raise the cap to the qualified size — in both places.** `MAP_RELIABILITY_CAP` (`map_batches.py`) **and**
   every lane's `map_batch_cap` (`config/cloud_providers.json`; pool cap = min over lanes,
   `lane_registry.py:86-95`) → **40**, bumping `BATCH_PLANNER_VERSION`, **after** repeats confirm stability.
3. **Make failures visible.** Persist `finish_reason`, `content_empty`, and `usage` on the §15 `Attempt`
   (migration), and classify `200 + empty content` as a **provider fault with backoff**, not a compiler
   "invalid" — never immediately repair-retry an EMPTY (it burned 3,420 tokens for nothing).
4. **Hygiene:** source `max_tokens` from the planner constant (2400 → `COMPLETION_ENVELOPE_TOKENS`) so the
   planner is the real bound (non-binding today, but the two must not diverge); enforce
   `request_char_budget` on the map path to pre-empt the 413 at ~60.

## 14. Regression Tests

- Admission estimate includes the system prompt and uses the measured ratio; asserts ≥0.8× actual `prompt_tokens` on a recorded fixture.
- Limiter refuses/paces when `tpd_remaining < estimated_total_tokens`; refusal consumes zero HTTP (existing invariant, extend to TPD).
- §15 `Attempt` carries `finish_reason`/`content_empty`; an EMPTY 200 is classified `PROVIDER_EMPTY` and schedules backoff, not an immediate repair.
- `test_map_batches` pins updated to cap 40 (40→[40]; 60→[40,20]; 150→[40,40,40,30]) **and** `lane_registry` pool-cap test asserts min over lanes = 40.
- `max_tokens` on the map request equals the planner constant (contract test on the captured payload).
- Payload guard: a 60-alias prompt exceeding `request_char_budget` is split before dispatch (no 413).

## 15. Safe Production Settings

- **Batch size:** 40 once repeats confirm (≥5 samples/lane, EMPTY ≤5%, missing ≤2%); use **30** as the interim conservative cap (29/30 measured).
- **Completion budget:** `max_tokens=6500` (planner-aligned; non-binding — `finish=stop` everywhere).
- **RPM/TPM/TPD:** enforce **TPD 100,000/org** locally (the real ceiling), RPM ≤4, TPM 70k; at 40-batch ≈ 12k tokens/request → **~8 requests/day/org ≈ 320 parents/day/org ≈ 1,600/day across 5 orgs**. To finish cinema (~4,600) faster you need **more Groq orgs or a higher tier**, not more batch or concurrency.
- **Retry policy:** 429 → honor `retry-after`, no burst; EMPTY 200 → back off (TPD pressure), re-issue later; PARTIAL (`finish=stop`, missing aliases) → one repair of only the missing aliases.

**MAP_RELIABILITY_CAP=15 should be RAISED (to 40, after repeats) and become dynamically derived from
measured per-lane yield under budget state — not remain, and not be removed.** It must move together with
the lane-level `map_batch_cap`.

## What this audit did NOT do
- No production code/config was changed (interception recorded only). No JSON/schema/function-calling proposed; the DSL and compiler are untouched and vindicated.
- Repeats for stability were not possible today: the active lanes' TPD is spent (groq2 `Used 99497`, run2 lane `Used 98114`). Re-run the qualification with ≥5 repeats/size across fresh-budget lanes before promoting 40.

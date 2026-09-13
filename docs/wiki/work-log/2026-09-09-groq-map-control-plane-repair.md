---
title: "WORK LOG — Groq Parent-MAP control-plane forensic repair (offline; instrumented conservation chain)"
change_id: GROQ-MAP-CONTROL-PLANE-REPAIR-V1
date: 2026-09-09
owner: governance (control-plane observability + accounting; no MAP architecture change)
last_reviewed: 2026-09-09
last_touched: 2026-09-09
status: complete (offline repair) — live-probe gate OPEN, awaiting owner authorization
register: 11.185
package: shared/polymath_shared/llm_extraction/limiter.py, shared/polymath_shared/llm_extraction/client.py, config/extraction_models/limiter.yaml, workers/workers/doc_parent_map_worker.py, scripts/parent_map_backfill.py, tests/determinism/test_limiter_control_plane.py, tests/determinism/test_groq_account_isolation.py, tests/determinism/test_offline_conservation_replay.py, tests/determinism/test_doc_parent_map_worker.py, tests/determinism/test_parent_map_backfill_spread.py, tests/determinism/test_fleet_v3_limits.py, scripts/scaffold_polymath_v4.py
architecture_impact: "Turns the Parent-MAP control plane into an instrumented, testable conservation chain (local scheduling → limiter admission → actual HTTP dispatch → provider quota → MAP compiler → persisted maps). NO change to the frozen MAP architecture: ParentSkeleton → plaintext MAP DSL → deterministic map_compiler → durable maps → projection; no JSON/schema/function-calling; compiler untouched; chunker + parent boundaries untouched; strict parent identity preserved. NO provider quota spent. Backfill remains STOPPED — resume is gated behind a bounded, owner-authorized live probe."
---

> **Ledger rows:** `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` **S12** (forensic hold → repaired control plane) + `PLAN-AUTHORITY-REGISTER.md` **11.185**. This work-log is the evidence.

# WORK LOG — Groq Parent-MAP control-plane forensic repair

## Contract

Owner directive (2026-09-09): the offline evidence-first repair of the Parent-MAP control plane.
Make every local scheduling event reconcilable against actual provider consumption BEFORE any further
Groq spend. Investigation-first; fixes only for defects with direct evidence, each with a failing→
passing regression. Do NOT resume cinema, run the benchmark, or spend provider quota. STOP at the
offline acceptance gate and present a bounded live-probe budget for authorization.

## Changes (five semantically-separated commits)

1. **`eba6889` limiter reasoned admission + header repair.** `AdaptiveLimiter.admit()` returns a
   `LimiterDecision(admitted, reason, retry_after)` naming the gate (FAMILY_GATE / BREAKER /
   CONCURRENCY / RPM / TPM / RPD / PROVIDER_RPD / RETRY_AFTER); `acquire()` kept as a bool wrapper so
   every existing caller is unchanged. `_chat` now returns the SUCCESS-path response headers and
   `complete_one` feeds them to `record_success` (**Target B** — provider RPD/TPM truth was observable
   only on 429). `_sync_headers` no longer feeds `x-ratelimit-*-requests` (a Groq DAILY/RPD budget)
   into the per-minute `_rpm` bucket (**Target A**); requests headers now drive a distinct provider-RPD
   representation reconciled conservatively (min within a reset epoch; fresh only on a proven epoch
   boundary), and a `PROVIDER_RPD` gate refuses a provider-declared-spent day without charging the
   local cap.
2. **`68708a0` per-account Groq family isolation.** `config/extraction_models/limiter.yaml`:
   `profile_groqN` + `map_groqN` now share `family: groq_acct_N` (six isolated circuits) instead of one
   shared `family: groq`. Completes the S7 wiring the routing policy of record specified but the config
   never applied (**Target H**).
3+4. **`0bbf160` conservation observability + evidence-based retry.** The backfill infer closure raises
   a typed `MapInferError` (reason + dispatched) and counts LANE SELECTION and PROVIDER HTTP DISPATCH
   separately (**Target G**); `MappingOutcome` gains conservation counters; each 2xx is classified
   COMPLETE/PARTIAL/EMPTY/INVALID and a zero/partial-yield batch records a durable `COMPILER_<class>`
   marker; `summarize()` surfaces `documents_with_internal_errors` and every class and gates PASS on
   all-complete AND zero-internal-failures (**Target E**). Retry policy: a LOCAL refusal or a dispatched
   HTTP fault DEFERS (resumable next run) instead of spinning `max_attempts`; only PARTIAL retries
   (productive §18.4 repair) (**Target F / Phase 11**).
5. **(this commit) offline conservation replay + docs.** `test_offline_conservation_replay.py` drives
   the real `complete_one` across a scripted six-lane mix and asserts the conservation identities;
   ledger/register/continuity updated.

## Proof

- **Regressions (offline, no provider spend):** new `test_limiter_control_plane.py` (17),
  `test_groq_account_isolation.py` (2), `test_offline_conservation_replay.py` (1); extended
  `test_doc_parent_map_worker.py` (empty/invalid/refusal accounting + retry-does-not-spin +
  partial-still-repairs) and `test_parent_map_backfill_spread.py` (selection≠dispatch, summarize
  invariant, PASS-only-when-clean); `test_fleet_v3_limits` ceiling tests superseded to the token
  channel. Adjacency sweep (18 files importing the changed surfaces) **195/195 green**; `repo_guard` ok.
- **Offline conservation replay reconciles (MEASURED):**
  `selections=12 == admitted 9 + refused 3`; `dispatches=9 == admitted`;
  `dispatches 9 == 2xx 7 + 429 1 + transport 1`; refusals dispatched 0 HTTP; compiler
  complete=3/partial=1/empty=2/invalid=1; `persisted ≤ compiler-valid`. `lane_selected` even (2/lane),
  `provider_http_dispatch` uneven — selection is provably not dispatch.
- **Historical cause, now MEASURED (read-only census, no spend):** cinema durable state —
  1,064 batches (done 121 / partial 937 / leased 6); 15,773 total claims, **95.2% on zero-yield
  batches**; terminal `last_error` = **`LIMITER_REFUSED` on 926 batches**, HTTP_429 11, HTTP_413 3, one
  empty-200. Zero persisted `day_count` rows (fresh each run). A `LIMITER_REFUSED` dispatches zero HTTP
  (`client.py:425`, pre-`_chat`), so the disputed `+0 / 0-errors` pass was a LOCAL refusal cascade —
  **provider RPD exhaustion is contradicted, not proven.**

## Rejected claims

- **DISPUTED → now MEASURED-against:** "`+0` parents / `0` errored_docs proved the six Groq accounts
  exhausted daily RPD." The dominant terminal state was `LIMITER_REFUSED` (LOCAL, 0 HTTP); only 14 real
  HTTP faults exist in the whole cinema campaign. The claim is superseded by request-level evidence; it
  is NOT rewritten out of history (11.178/11.184 record that it was made, then downgraded).
- **NOT overclaimed:** WHICH local gate (family vs breaker) produced each historical refusal is
  **UNOBSERVABLE with the old telemetry** (day_count/family state were never persisted). The repair
  makes it observable if it recurs; local-RPD-230 is RULED OUT within a run (per-run admissions ≪ 230,
  no persisted counter).
- **UNVERIFIED (needs the bounded live probe):** the real Groq per-account daily request quota and
  whether `compound` and `compound-mini` share it. Config comments ("RPD 250/account") are assumptions,
  never reconciled to a header. Provider evidence must win before any resume.

## Open contract gaps

- **Live-probe gate OPEN.** The offline acceptance gate is green (refusals reasoned + zero-HTTP;
  success headers retained; RPD≠RPM; provider-RPD represented; admission vs dispatch separated;
  MappingOutcome + compiler classes surfaced; retry no longer spins; per-account isolation;
  regressions + offline replay green; guards green). Two gate items require live calls and are NOT
  done: **provider quota topology (Phase 1/18)** and **MAP batch 15/20/30/40/60 benchmark (Phase 19)**.
  A bounded, owner-authorized probe (minimum calls, headers captured, abort conditions) is the next
  step — then a bounded canary → owner review → only then resume. **Backfill stays STOPPED.**
- **Do NOT** resume on a quota reset; **do NOT** run the benchmark or canary without authorization;
  architecture remains frozen (no JSON mode, no compiler bypass, chunker untouched).

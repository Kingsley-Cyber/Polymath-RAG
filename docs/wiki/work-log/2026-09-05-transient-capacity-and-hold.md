---
title: "WORK LOG — PROVIDER-CAPACITY-IS-TRANSIENT-V1 + TRANSIENT-HOLD-V1: 429s burned retry budgets; sweep-lock waits starved the summary lane"
change_id: PROVIDER-CAPACITY-IS-TRANSIENT-V1
date: 2026-09-05
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.78
package: shared/polymath_shared/worker_runtime.py, workers/workers/summary_worker_impl.py
architecture_impact: "worker runtime failure classification only: an ExtractionTransportError carrying HTTP 429 / lane refused / LIMITER_REFUSED, and the new TransientStageHold, are handed back READY without consuming an attempt (60 s backoff for capacity events). The summary sweep lock yields with TransientStageHold after 30 s instead of blocking the lane slot. No schema, contract or API change."
---

# WORK LOG — PROVIDER-CAPACITY-IS-TRANSIENT-V1 + TRANSIENT-HOLD-V1

Owner (2026-09-05, 5 h into the 63-document `cinema` ingest): "it's been 5 hrs, it should've been fully complete but I see a whole lot of errors."

## Contract

- A provider capacity event is never an execution failure of the document. `worker_runtime._is_sidecar_unavailable` (the transient classifier both `except` arms consult) now also returns true for an `ExtractionTransportError` whose message carries `HTTP 429`, `429 Too Many Requests`, `lane refused` or `LIMITER_REFUSED` anywhere in the cause chain; the ticket is released READY with `attempt` untouched and the worker backs off 60 s (`transient_backoff_s`) instead of 15 s.
- A stage may yield: raising `TransientStageHold` hands the ticket back READY (no attempt) so the worker claims other work. `summary_worker_impl._sweep_lock` raises it after `POLYMATH_SUMMARY_SWEEP_WAIT_S` (default now 30 s) instead of blocking for up to 30 minutes.
- Genuine transport garbage and ordinary exceptions still fail the attempt.

## Why

Measured during the ingest: seven extraction tickets went `failed` after three consecutive Gemini 429s inside ten minutes each (`stage extract failed … failure receipt committed` 04:32, 04:36, 04:37; again 06:12–06:34); the runtime's retry budget "counts executions that failed", but here nothing executed — the provider pool was pacing. Separately, after SUMMARY-SWEEP-SERIALIZATION-V1 the second summaries worker sat in `pg_try_advisory_xact_lock` polling for the sweep while a `parent_summary` ticket was `READY_UNCLAIMED` for 15,253 s: serialization was correct, blocking the slot was not.

## Changes

- `shared/polymath_shared/worker_runtime.py`: `TransientStageHold`, `_is_provider_capacity`, `_is_transient_hold`, `transient_backoff_s`; `_is_sidecar_unavailable` extended; both release sites use the per-kind backoff.
- `workers/workers/summary_worker_impl.py`: `_sweep_lock` yields with `TransientStageHold`; default wait cap 30 s.
- `tests/determinism/test_transient_capacity_and_hold.py`: 429 / lane-refused transport errors are transient with the capacity backoff (also through a cause chain); garbage transport errors and ValueErrors still fail; `TransientStageHold` is transient; on the dev Postgres the sweep lock yields with `TransientStageHold` when a peer holds it.
- TREE rows; register 11.78.

## Proof

- New tests + neighbours (`test_summary_sweep_serialization.py`, `test_sidecar_readiness_gate.py`, `test_lease_renewal.py`): 12 passed.
- Live: extract and summary workers restarted onto the new code (supervisor respawn); the three `failed` extraction tickets re-armed by id (`run_6136d4ca7e`, `run_086fdd5c91`, `run_c3eb7f9f74`) and picked up within two minutes (extract: done 60, leased 2, ready 1, failed 0).

## Rejected claims

- "Raise the attempt cap" — rejected: the cap is right; 429 pacing must not count against it.
- "Keep the second summaries worker waiting so it is first in line" — rejected: the sweep is idempotent and the waiting slot starved another stage for four hours.

## Open contract gaps

- Throughput of a bulk ingest is embedder-bound: the projection stage embeds every child chunk twice (dense collection + routing lane `ROUTING_KIND_CHILD`) plus entities, procedures, concepts and summaries — measured ticket 1: 97,319 routing texts in 3.4 h at ~7 texts/s, ticket 2: the 68k chunk projection at ~8 chunks/s. About 165k texts for this corpus ≈ 6.5 h on the local MLX sidecar. Capacity (the RTX lane) or fewer routing representations are the levers; nothing here changes that.
- Provider pacing: three extract workers still hammer throttled Gemini lanes; the AIMD limiter halves on each 429 but the burst-then-fail pattern recurs; the capacity classification now protects the tickets, not the throughput.

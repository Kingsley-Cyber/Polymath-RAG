---
title: "WORK LOG — SUMMARY-SWEEP-SERIALIZATION-V1: summary workers deadlocked across processes on summary_jobs"
change_id: SUMMARY-SWEEP-SERIALIZATION-V1
date: 2026-09-05
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.75
package: workers/, shared/polymath_shared/worker_runtime.py
architecture_impact: "summary worker only: bounded lock wait on summary_jobs upserts, one sweep per (stage, corpus) via a transaction-scoped advisory lock, SIGUSR1 stack dump for every worker. No schema, contract, API, or extraction change."
---

# WORK LOG — SUMMARY-SWEEP-SERIALIZATION-V1

Owner (2026-09-05): "start the deadlock fix, commit and merge to github."

## Contract

- **Law 1 — bounded waits.** `_ensure_job` (summary_jobs upsert keyed on `(stage, input_hash)`) executes `SET LOCAL lock_timeout` (`POLYMATH_SUMMARY_LOCK_TIMEOUT_MS`, default 60 000) before its statements. A peer transaction holding the key is surfaced as `psycopg.errors.LockNotAvailable` (the ticket fails its attempt with a typed reason) — never an unbounded wait.
- **Law 2 — one sweep per (stage, corpus).** Every sweeping handler (`_do_parents`, `_do_document`, `_do_corpus`, `_do_vocabulary`, `_do_enrichment`) calls `_sweep_lock(conn, stage, corpus)` immediately after the corpus is resolved and BEFORE any write: `pg_try_advisory_xact_lock` on the outer ticket transaction, polled every 5 s while holding no row lock (so the wait can never be an edge of a deadlock; the lease keeper keeps the ticket alive), capped by `POLYMATH_SUMMARY_SWEEP_WAIT_S` (default 1 800, then a typed RuntimeError). The lock dies with the holder's commit or rollback. The second worker finds the work done (SUMMARY-JOB-IDEMPOTENCY-V1) when its turn comes.
- **Law 3 — dumpable workers.** `run_worker` registers `faulthandler` on `SIGUSR1` (all threads): `kill -USR1 <pid>` prints every Python stack to the worker's log. This deadlock was diagnosable only through `pg_stat_activity` because the Mac has no py-spy.

## Why

Measured 2026-09-05 02:03Z and 02:18Z (corpus `cinema`, four documents uploaded together): both summary workers stopped logging inside `parent_enrichment`; `/fleet` reported them `healthy` holding a `current_ticket`; control's stall tracer reported the tickets `READY_UNCLAIMED … claim gate refuses it`. `pg_stat_activity`: per worker one session `idle in transaction` (last statement the `parent_enrichments` cache lookup on the OUTER ticket connection) and one session `active, Lock/transactionid` on `INSERT INTO summary_jobs … ON CONFLICT (stage, input_hash)`; `pg_blocking_pids` crosswise. Root cause: `_run_docs` makes enrichment a CORPUS sweep (every document of the corpus), so two tickets of one corpus enrich the same parents; the outer transaction holds uncommitted `summary_jobs` upserts for the whole sweep; the per-batch short transactions (and the peer) upsert the same keys. Postgres cannot detect the cycle because one edge is a Python wait. A `kill -TERM` of both workers cleared it and it recurred within two minutes. Single-document uploads never hit it; the earlier 1,514-chunk novel went through cleanly.

## Changes

- `workers/workers/summary_worker_impl.py`: `_lock_timeout_ms`, `_sweep_lock_key`, `_try_sweep_lock`, `_sweep_lock`; `_ensure_job` sets the local lock timeout; the five handlers take the sweep lock.
- `shared/polymath_shared/worker_runtime.py`: faulthandler on SIGUSR1 at `run_worker` start.
- `tests/determinism/test_summary_sweep_serialization.py` (new, real dev Postgres, skips without it): Law 1 (peer holds the key uncommitted → our upsert raises `LockNotAvailable` within the timeout instead of hanging), Law 2 (second connection refused per (stage, corpus), independent per stage, released with the transaction), Law 3 structural (every sweeping handler contains the sweep-lock call).
- `scripts/scaffold_polymath_v4.py` TREE rows; `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` row 11.75.

## Proof

- Regression written first and run RED against the pre-fix code: all three tests failed (`_do_parents sweeps the corpus without the per-(stage, corpus) sweep lock`; no `_try_sweep_lock`; the peer upsert hung).
- After the fix: `pytest tests/determinism/test_summary_sweep_serialization.py tests/determinism/test_summary_job_idempotency.py tests/determinism/test_lease_renewal.py` → 5 passed; every determinism test importing `summary_worker_impl` or `worker_runtime` (11 files) → 65 passed.
- Live proof (2026-09-05 02:42–02:47Z): three ~48 KB documents uploaded concurrently to corpus `d7-h1-test` with both summary workers active on the fixed code. Monitor (15 s cadence, 14 samples): all 42 tickets of the three runs `done` at 02:47:01Z (4.5 min from upload); `pg_stat_activity` lock waits max **0** throughout (the pre-fix run showed 2 within 4 minutes and needed 3 restarts); `idle in transaction` max age 43 s (an in-flight LLM call, under the 60 s lock timeout); worker logs: exactly one `sweep lock busy: another worker is sweeping parent_enrichment for corpus d7-h1-test` and one `sweep lock acquired after 25s`; zero `LockNotAvailable`. The four `cinema` documents that exposed the defect finished under the watchdog before the fix (23/23, 21/21, 20/20, 19/19 parents enriched).

## Rejected claims

- "The workers were starved by the LLM lane limiter" — rejected: no HTTP socket was open in either process; the wait was on Postgres (`poll` on the 5432 sockets, `transactionid` lock).
- "The stall tracer's `claim gate refuses it` was right" — rejected: the tickets had been claimed in-process; the tracer cannot see database lock waits (open gap below).
- "Restarting the workers is the fix" — rejected: it recurred within two minutes; only serialization plus bounded waits removes the cycle.

## Open contract gaps

- `control/control/stall_tracer.py` still cannot distinguish a database lock wait from a claim-gate refusal for a live worker; adding `pg_stat_activity` lock waits to the READY_UNCLAIMED diagnosis is the next tracer improvement.
- The outer ticket transaction still spans the whole sweep (by design of the lease/receipt model); the advisory lock makes that safe per corpus, but two corpora sharing identical parent content could still contend on `(stage, input_hash)` — bounded now by the 60 s lock timeout (attempt burned, ticket retried), not eliminated.
- Corpus `d7-h1-test` used for the live proof has no `corpora` row (intake accepts uploads regardless); a separate hygiene item.

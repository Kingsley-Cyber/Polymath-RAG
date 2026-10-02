# unit: control/control/stall_tracer.py
anchor: control/control/stall_tracer.py:1-452

## purpose
STALL-TRACER-V1: the control plane's periodic "why is this stuck" pass. Every tick it walks the stallable units — stage tickets, runs, summary jobs — and for each one older than the threshold writes one diagnosis row into `stall_traces` naming what it waits on, using the same predicates the scheduler uses to advance work. Detection and evidence only; it never mutates the stalled unit. — control/control/stall_tracer.py:1-21 [DERIVED]
Imported by `control/control/main.py` (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| Stall | dataclass | unit_kind, unit_id, stalled_since, age_s, diagnosis, detail, run_id, stage, corpus_id + `key` property | control/control/stall_tracer.py:43-56 | — |
| fleet_slots_alive | def | (path: Path = SUPERVISOR_STATE) -> dict[str, bool] \| None | control/control/stall_tracer.py:61-67 | — |
| lane_slots | def | (stage: str) -> tuple[str \| None, set[str]] | control/control/stall_tracer.py:70-75 | — |
| diagnose_ready | def | (row: dict, slots_alive: dict[str, bool] \| None) -> tuple[str, dict] \| None | control/control/stall_tracer.py:84-110 | — |
| diagnose_leased | def | (row: dict, now: datetime) -> tuple[str, dict] | control/control/stall_tracer.py:113-129 | — |
| diagnose_pending | def | (conn, row: dict, chain: dict, threshold_s=STALL_THRESHOLD_S, saturated=None) -> tuple[str, dict] \| None | control/control/stall_tracer.py:132-184 | — |
| diagnose_run | def | (row: dict, census_gaps: list[str]) -> tuple[str, dict] | control/control/stall_tracer.py:214-227 | — |
| collect_stalls | def | (conn, *, census=None, threshold_s=STALL_THRESHOLD_S, slots_alive=None) -> list[Stall] | control/control/stall_tracer.py:237-405 | — |
| persist_traces | def | (conn, stalls: list[Stall]) -> list[Stall] | control/control/stall_tracer.py:410-436 | — |
| trace_stalls | def | (conn, census=None, *, threshold_s=STALL_THRESHOLD_S, fleet_state_path=SUPERVISOR_STATE) -> dict | control/control/stall_tracer.py:439-451 | control/control/main.py (module import) |

## contracts

**trace_stalls** — control/control/stall_tracer.py:439-451
- in: db conn; optional `census` (only `census.gaps` is read, each gap needing `.run_id`, `.stage`, `.reason`) — control/control/stall_tracer.py:353-354
- out: `{"stalls": len(stalls), "new": len(new)}` — control/control/stall_tracer.py:451
- post: every first-time stall this tick is `log.warning`-ed with `error_code` = diagnosis — control/control/stall_tracer.py:444-450

**collect_stalls** — control/control/stall_tracer.py:237-405
- in: candidates are open tickets / non-terminal runs / unfinished summary_jobs with `updated_at` (or `created_at` for jobs) older than `threshold_s` — control/control/stall_tracer.py:276-279, 369-373, 389-393
- out: one `Stall` per diagnosed unit; units waiting on live work return None from the diagnosers and are skipped — control/control/stall_tracer.py:300-301, 342-343, 376-377
- pre: `SELECT now()` from the db sets the clock — control/control/stall_tracer.py:239

**persist_traces** — control/control/stall_tracer.py:410-436
- out: the stalls traced for the FIRST time this tick (insert detected via `xmax = 0`) — control/control/stall_tracer.py:424-429
- post: upsert key is `(unit_kind, unit_id, stalled_since)`; retraced episodes get `resolved_at = NULL` reset; episodes absent from the current set get `resolved_at = now()` — control/control/stall_tracer.py:420-424, 430-435

**diagnose_ready** (ordered) — control/control/stall_tracer.py:84-110
- no undelivered claim event -> `READY_NO_CLAIM_EVENT` regardless of lane load — control/control/stall_tracer.py:95-99
- `slots_alive is not None` and no slot of the lane alive -> `READY_NO_LIVE_SLOT` — control/control/stall_tracer.py:100-103
- `cap > 0 and busy >= cap` -> None (claimable, queued behind a saturated lane) — control/control/stall_tracer.py:104-105
- else -> `READY_UNCLAIMED` — control/control/stall_tracer.py:106-110

**diagnose_leased** (ordered) — control/control/stall_tracer.py:113-129
- `lease_expires_in_s < 0` -> `LEASED_EXPIRED_NOT_RELEASED` — control/control/stall_tracer.py:121-124
- heartbeat None or age > `OWNER_STALE_S` -> `LEASED_OWNER_GONE` — control/control/stall_tracer.py:125-127
- else -> `LEASED_LONG_RUNNING` — control/control/stall_tracer.py:128-129

**diagnose_pending** (ordered) — control/control/stall_tracer.py:132-184
- stage not in `DAG_ORDER` -> `PENDING_OWNER_STAGE` — control/control/stall_tracer.py:144-146
- first not-ok predecessor: holder alive and status in `("leased", "ready")` -> None; else `PENDING_ON_PREDECESSOR` — control/control/stall_tracer.py:147-157
- missing artifacts -> `PENDING_ADVANCE_BLOCKED` (missing="artifacts") — control/control/stall_tracer.py:157-161
- missing receipts: `scope == "corpus"` and live sibling runs exist -> None; else `PENDING_ADVANCE_BLOCKED` (missing="receipts") — control/control/stall_tracer.py:162-181
- else -> `PENDING_ADVANCE_NOT_REACHED` — control/control/stall_tracer.py:182-184

**diagnose_run** — control/control/stall_tracer.py:214-227
- `n_tickets == 0` -> `RUN_NO_TICKET_CHAIN`; status `"degraded"` -> `RUN_DEGRADED_AWAITING_DECISION`; else `RUN_SETTLED_NOT_PROMOTED` — control/control/stall_tracer.py:220-227

**fleet_slots_alive** — best-effort JSON read of supervisor state; `{name: bool(alive)}` per slot, None on any failure — control/control/stall_tracer.py:61-67

## effect surface
- Postgres read: `stage_tickets`, `worker_registrations`, `outbox_events` (claim-event EXISTS), `runs`, `corpora` (EXISTS), `summary_jobs` — control/control/stall_tracer.py:247-275, 356-374, 383-394 [DERIVED]
- Postgres write: `stall_traces` (INSERT ... ON CONFLICT DO UPDATE, plus resolved_at UPDATE) — control/control/stall_tracer.py:415-435
- File read: `/tmp/polymath_fleet/supervisor_state.json` (`SUPERVISOR_STATE`) — control/control/stall_tracer.py:38, 64
- Logging: logger `"control.stall_tracer"`, `log.warning("stall traced: ...")` with `error_code` extra — control/control/stall_tracer.py:30, 447-450
- No subprocess, network, or env flags in this file.

## invariants
INVARIANT: STALL_THRESHOLD_S == 180 — control/control/stall_tracer.py:32 [DERIVED]
  fails-if: units newer than 180 s are never traced; raising the value delays every diagnosis.
INVARIANT: OWNER_STALE_S == 90, mirrors `_release_expired_leases` — control/control/stall_tracer.py:33-35 [DERIVED]
  fails-if: tracer and lease release disagree on when a worker is dead -> false or missed LEASED_OWNER_GONE.
INVARIANT: per-kind candidate cap == _LIMIT == 500 (tickets, runs, jobs each) — control/control/stall_tracer.py:39, 279, 373, 393 [DERIVED]
  fails-if: >500 stalled tickets push runs/jobs out of the trace set (each query is independently LIMITed).
INVARIANT: episode identity == (unit_kind, unit_id, stalled_since) — control/control/stall_tracer.py:420 [DERIVED]
  fails-if: duplicate rows per tick or episodes never resolve.
INVARIANT: `Stall.key` format `f"{unit_kind}:{unit_id}"` == SQL `(unit_kind || ':' || unit_id)` — control/control/stall_tracer.py:55-56, 434 [DERIVED]
  fails-if: resolution predicate never matches -> resolved_at stays NULL forever.
INVARIANT: saturation skip only when `cap > 0 and busy >= cap` — control/control/stall_tracer.py:104-105 [DERIVED]
  fails-if: cap == 0 falls through to READY_UNCLAIMED, mislabeling a capacity queue as a defect (the V1.3 incident, 86-90, 281-284).

## determinism & idempotency
determinism: NONDETERMINISTIC (db clock `SELECT now()` — control/control/stall_tracer.py:239; DB heartbeats/updated_at — control/control/stall_tracer.py:276-277; supervisor state file — control/control/stall_tracer.py:64)
idempotency: SAFE (upsert keyed on (unit_kind, unit_id, stalled_since) refreshes age_s/diagnosis/detail and re-nulls resolved_at on every tick — control/control/stall_tracer.py:420-424)

## failure behaviour
- `fleet_slots_alive`: any `Exception` swallowed, returns None — control/control/stall_tracer.py:66-67. Caller effect: the `READY_NO_LIVE_SLOT` branch is disabled (`slots_alive is not None` guard) and ready tickets fall through to saturation/READY_UNCLAIMED checks — control/control/stall_tracer.py:100-110.
- No exceptions raised by design; output channels are `stall_traces` rows and `log.warning` with `error_code` = diagnosis — control/control/stall_tracer.py:447-450.
- The stalled unit itself is never mutated; the fix is a code change in the writer the diagnosis names — control/control/stall_tracer.py:7-10.

## dumb-code flags
- Hardcoded `90` in four SQL literals (control/control/stall_tracer.py:199, 261, 326, 332) while `OWNER_STALE_S` is parameterized as `%s` in three other queries (control/control/stall_tracer.py:273+280, 290+291, 316+340): changing the constant desyncs the predicates.
- `TERMINAL_RUN_STATUSES` (line 36) and `OPEN_TICKET_STATUSES` (line 37) are defined but never referenced in this file; the same value lists are inlined as SQL literals — control/control/stall_tracer.py:36-37 vs 197, 209, 276, 363, 370, 391.
- `saturated: set | None = None` parameter of `diagnose_pending` is unused in the body — control/control/stall_tracer.py:136.
- Worker type is inferred as `split_part(lease_owner, '-', 1)` in six subquery copies across two queries (b/b2/b3 aliases) — control/control/stall_tracer.py:262-271, 327-336; worker ids must be `"<type>-..."` shaped.
- `summary_jobs` join assumes the stage ticket id is the prefix before `:` in `j.ticket_id` — control/control/stall_tracer.py:388.
- Detail JSON truncated to 400 chars in the log line — control/control/stall_tracer.py:449; sibling run ids capped at 8 — control/control/stall_tracer.py:211.
- `GREATEST(1, ...)` forces a minimum lane capacity of 1 in the chains saturation test — control/control/stall_tracer.py:331.
- The LANES third element is used both as supervisor slot names (checked against `slots_alive`) and as worker_type keys into `lane_load` — control/control/stall_tracer.py:100-101 vs 296-298 [INFERRED: one tuple serves two namespaces, so slot names must equal worker types].

## refactor notes
- `trace_stalls` return keys `{"stalls", "new"}` and its signature are the module's entry point for `control/control/main.py` (FACTS.importers) — control/control/stall_tracer.py:439-451.
- `stall_traces` schema coupling: conflict target `(unit_kind, unit_id, stalled_since)` and columns `last_traced_at`, `age_s`, `diagnosis`, `detail`, `resolved_at` — control/control/stall_tracer.py:417-424, 432.
- Diagnosis code strings (READY_*, LEASED_*, PENDING_*, RUN_*, SUMMARY_JOB_*) are a published taxonomy: they ride `log.error_code` — control/control/stall_tracer.py:13-20, 450.
- Private cross-module imports: `control.tickets` (`DAG_ORDER`, `_STAGE_SPEC`, `_artifacts_present`, `_receipts_present`, `_stage_attempt_ok`, `receipt_scope_for`) and lazy `control.fleet_autopilot.LANES` — control/control/stall_tracer.py:71, 140-142; semantic drift there silently changes diagnoses.
- `OWNER_STALE_S` must stay in lockstep with `_release_expired_leases` — control/control/stall_tracer.py:33-34; and the four hardcoded SQL `90`s must move with it — control/control/stall_tracer.py:199, 261, 326, 332.
- `persist_traces` resolution depends on `Stall.key` string format matching the SQL concatenation — control/control/stall_tracer.py:55-56, 434.

## VERIFY
```verify
grep -Fq 'STALL_THRESHOLD_S = 180' control/control/stall_tracer.py
grep -Fq 'OWNER_STALE_S = 90' control/control/stall_tracer.py
grep -Fq 'make_interval(secs => 90)' control/control/stall_tracer.py
grep -Fq 'ON CONFLICT (unit_kind, unit_id, stalled_since)' control/control/stall_tracer.py
grep -Fq '/tmp/polymath_fleet/supervisor_state.json' control/control/stall_tracer.py
grep -Fq 'READY_NO_CLAIM_EVENT' control/control/stall_tracer.py
grep -Fq 'return {"stalls": len(stalls), "new": len(new)}' control/control/stall_tracer.py
```

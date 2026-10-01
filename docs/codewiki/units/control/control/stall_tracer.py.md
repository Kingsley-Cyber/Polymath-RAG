# unit: control/control/stall_tracer.py
anchor: control/control/stall_tracer.py:1-431

## purpose
STALL-TRACER-V1: the control plane's periodic "why is this stuck" pass. Each tick it walks stallable units — stage tickets, runs, summary jobs — and for each one that has not advanced for `STALL_THRESHOLD_S = 180` seconds writes one diagnosis row into `stall_traces` naming what it waits on, using the same predicates the scheduler uses to advance work (control/control/stall_tracer.py:3-10). Detection and evidence only; it never mutates the unit — the fix is a code change in the writer the diagnosis names (control/control/stall_tracer.py:8-10). Diagnosis codes are fixed strings listed in the module docstring: `READY_NO_CLAIM_EVENT`, `READY_NO_LIVE_SLOT`, `READY_UNCLAIMED`, `LEASED_EXPIRED_NOT_RELEASED`, `LEASED_OWNER_GONE`, `LEASED_LONG_RUNNING`, `PENDING_OWNER_STAGE`, `PENDING_ON_PREDECESSOR`, `PENDING_ADVANCE_BLOCKED`, `PENDING_ADVANCE_NOT_REACHED`, `RUN_NO_TICKET_CHAIN`, `RUN_DEGRADED_AWAITING_DECISION`, `RUN_SETTLED_NOT_PROMOTED`, `SUMMARY_JOB_INFLIGHT_STALLED`, `SUMMARY_JOB_FAILED_TICKET_OPEN` (control/control/stall_tracer.py:12-20).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `trace_stalls` | def | `(conn, census=None, *, threshold_s=STALL_THRESHOLD_S, fleet_state_path=SUPERVISOR_STATE) -> dict` | control/control/stall_tracer.py:418-430 | control/control/main.py [INFERRED: only importer in FACTS] |
| `collect_stalls` | def | `(conn, *, census=None, threshold_s=STALL_THRESHOLD_S, slots_alive=None) -> list[Stall]` | control/control/stall_tracer.py:237-384 | — |
| `persist_traces` | def | `(conn, stalls: list[Stall]) -> list[Stall]` | control/control/stall_tracer.py:389-415 | — |
| `fleet_slots_alive` | def | `(path: Path = SUPERVISOR_STATE) -> dict[str, bool] \| None` | control/control/stall_tracer.py:61-67 | — |
| `lane_slots` | def | `(stage: str) -> tuple[str \| None, set[str]]` | control/control/stall_tracer.py:70-75 | — |
| `diagnose_ready` | def | `(row: dict, slots_alive: dict[str, bool] \| None) -> tuple[str, dict] \| None` | control/control/stall_tracer.py:84-110 | — |
| `diagnose_leased` | def | `(row: dict, now: datetime) -> tuple[str, dict]` | control/control/stall_tracer.py:113-129 | — |
| `diagnose_pending` | def | `(conn, row: dict, chain: dict, threshold_s: int = STALL_THRESHOLD_S, saturated: set \| None = None) -> tuple[str, dict] \| None` | control/control/stall_tracer.py:132-184 | — |
| `diagnose_run` | def | `(row: dict, census_gaps: list[str]) -> tuple[str, dict]` | control/control/stall_tracer.py:214-227 | — |
| `Stall` | dataclass | fields: `unit_kind, unit_id, stalled_since, age_s, diagnosis, detail, run_id=None, stage=None, corpus_id=None`; property `key -> str` | control/control/stall_tracer.py:42-56 | — |

## contracts

**trace_stalls** — control/control/stall_tracer.py:418-430
- in: Postgres conn (`%s` placeholders), optional `census` object exposing `.gaps` with `.run_id`, `.stage`, `.reason` (control/control/stall_tracer.py:332-334).
- out: `{"stalls": len(stalls), "new": len(new)}` (control/control/stall_tracer.py:430).
- post: one `log.warning` per first-time stall this tick, with `error_code` = the diagnosis string (control/control/stall_tracer.py:423-429).
- reads supervisor state file via `fleet_slots_alive(fleet_state_path)` (control/control/stall_tracer.py:421).

**collect_stalls** — control/control/stall_tracer.py:237-384
- in: `now` taken from the DB clock, `SELECT now()` (control/control/stall_tracer.py:239).
- out: at most one `Stall` per unit per tick; each of the three collector queries is capped `LIMIT _LIMIT` = 500 (control/control/stall_tracer.py:273, 352, 370, 39).
- pre (tickets): status `IN ('pending','ready','leased')` AND `updated_at < now() - threshold` (control/control/stall_tracer.py:270-271).
- pre (runs): `superseded_by_run_id IS NULL` AND status not in `('query_ready','failed','superseded')` AND stale (control/control/stall_tracer.py:348-350); runs with open tickets are skipped as already explained by ticket traces (control/control/stall_tracer.py:354-356).
- pre (jobs): `created_at` stale AND (`state NOT IN ('COMPLETE','FAILED')` OR `FAILED` with an open ticket) (control/control/stall_tracer.py:368-370).

**persist_traces** — control/control/stall_tracer.py:389-415
- out: only the stalls traced for the first time this tick, detected via `RETURNING (xmax = 0) AS inserted` (control/control/stall_tracer.py:392, 403-407).
- post: upsert keyed `ON CONFLICT (unit_kind, unit_id, stalled_since)` re-nulls `resolved_at` (control/control/stall_tracer.py:399-402); episodes absent from the current `stalls` list get `resolved_at = now()` (control/control/stall_tracer.py:409-414).

**diagnose_ready** — control/control/stall_tracer.py:84-110
- ordered checks: no undelivered claim event → `READY_NO_CLAIM_EVENT` regardless of lane load (control/control/stall_tracer.py:95-99); claim pending but no live slot of the lane → `READY_NO_LIVE_SLOT` (control/control/stall_tracer.py:100-103); `cap > 0 and busy >= cap` → `None` (queued behind a saturated lane, control/control/stall_tracer.py:104-105); otherwise `READY_UNCLAIMED` (control/control/stall_tracer.py:106-110).

**diagnose_leased** — control/control/stall_tracer.py:113-129
- always returns a code, in order: `lease_expires_in_s < 0` → `LEASED_EXPIRED_NOT_RELEASED` (control/control/stall_tracer.py:121-124); heartbeat age `None` or `> OWNER_STALE_S` → `LEASED_OWNER_GONE` (control/control/stall_tracer.py:125-127); else `LEASED_LONG_RUNNING` (control/control/stall_tracer.py:128-129).

**diagnose_pending** — control/control/stall_tracer.py:132-184
- returns `None` (not a stall) when a predecessor is leased by a live holder, or ready+claimable+queued behind a saturated lane (control/control/stall_tracer.py:152-153); and when receipts are missing at `scope == "corpus"` while live sibling runs exist in the same corpus (control/control/stall_tracer.py:177-178).
- else returns one of `PENDING_OWNER_STAGE` (stage not in DAG_ORDER, control/control/stall_tracer.py:146), `PENDING_ON_PREDECESSOR` (control/control/stall_tracer.py:156-158), `PENDING_ADVANCE_BLOCKED` (artifacts or receipts missing, control/control/stall_tracer.py:159-181), `PENDING_ADVANCE_NOT_REACHED` (control/control/stall_tracer.py:182-184).

**fleet_slots_alive** — control/control/stall_tracer.py:61-67
- out: `{s["name"]: bool(s.get("alive"))}` from the supervisor state JSON, or `None` (control/control/stall_tracer.py:64-65).

## effect surface

| surface | detail | anchor |
|---|---|---|
| table read | `stage_tickets` | control/control/stall_tracer.py:194, 244-274, 294-318, 340-345 |
| table read | `worker_registrations` | control/control/stall_tracer.py:195, 253, 261, 269, 317 |
| table read | `outbox_events` | control/control/stall_tracer.py:247-251, 297-303 |
| table read | `runs` | control/control/stall_tracer.py:337-352 |
| table read | `corpora` | control/control/stall_tracer.py:346 |
| table read | `summary_jobs` | control/control/stall_tracer.py:363-372 |
| table written | `stall_traces` (INSERT upsert + UPDATE resolve) | control/control/stall_tracer.py:396-414 |
| file read | `/tmp/polymath_fleet/supervisor_state.json` (`SUPERVISOR_STATE`) | control/control/stall_tracer.py:38, 64 |

FACTS.tables_written also lists `set`; no table `set` is written in SOURCE — `set` occurs only as a type annotation (control/control/stall_tracer.py:70, 134) [INFERRED: static-analysis misread]. No network calls, subprocesses, or env flags appear in SOURCE.

## invariants

INVARIANT: `OWNER_STALE_S` == 90 == every SQL heartbeat literal `make_interval(secs => 90)` — control/control/stall_tracer.py:35, 199, 255, 261, 305, 311 [DERIVED]
  fails-if: Python-side and SQL-side liveness disagree → `LEASED_OWNER_GONE` and the live-work suppressions (`None` returns) fire on different clocks.
INVARIANT: `TERMINAL_RUN_STATUSES` == `("query_ready", "failed", "superseded")` == runs SQL `NOT IN` list — control/control/stall_tracer.py:36, 348-349 [DERIVED]
  fails-if: terminal runs get traced as stalled, or settled runs escape tracing.
INVARIANT: `OPEN_TICKET_STATUSES` == `("pending", "ready", "leased")` == tickets `WHERE` list, runs `n_open` subquery, jobs ticket filter — control/control/stall_tracer.py:37, 270, 342, 370 [DERIVED]
  fails-if: run-skip rule (`n_open`) and ticket collector disagree → same run traced twice or not at all.
INVARIANT: episode key `(unit_kind, unit_id, stalled_since)` in `ON CONFLICT` == resolution predicate `unit_kind || ':' || unit_id` == `Stall.key` format `f"{self.unit_kind}:{self.unit_id}"` — control/control/stall_tracer.py:399, 413, 55-56 [DERIVED]
  fails-if: episodes never resolve or duplicate every tick.
INVARIANT: `claim_event_pending` EXISTS predicate in ticket query == same predicate in chain query — control/control/stall_tracer.py:247-251, 297-303 [DERIVED]
  fails-if: a pending ticket suppressed as "live work" while its ready predecessor has no claim event.
INVARIANT: writes touch only `stall_traces`; `stage_tickets`, `runs`, `summary_jobs` are read-only — control/control/stall_tracer.py:8-9, 396-414 [DERIVED]
  fails-if: the tracer mutates scheduler state, violating the detection-only owner rule.
INVARIANT: each collector query `LIMIT` == `_LIMIT` == 500 — control/control/stall_tracer.py:39, 273, 352, 370 [DERIVED]
  fails-if: more than 500 stalled units of a kind → the tail is untraced and, being absent from the tick's list, gets `resolved_at` set while still stalled [INFERRED: resolve marks everything not collected].

## determinism & idempotency
determinism: NONDETERMINISTIC (DB clock `SELECT now()` control/control/stall_tracer.py:239 and `now()` inside SQL; supervisor state file read control/control/stall_tracer.py:64; concurrent worker heartbeats in `worker_registrations`)
idempotency: SAFE (upsert on `(unit_kind, unit_id, stalled_since)` re-nulls `resolved_at`, so re-running the same tick inserts no new episodes and logs nothing new — control/control/stall_tracer.py:399-407)

## failure behaviour
- `fleet_slots_alive`: `except Exception: return None` — any read/parse failure is swallowed (control/control/stall_tracer.py:66-67). Caller then sees `slots_alive = None`, which disables the `READY_NO_LIVE_SLOT` branch and the `slots_alive` detail (control/control/stall_tracer.py:100, 106-107) [INFERRED: consequence of the `is not None` guards].
- No exceptions are raised deliberately; diagnoses surface as log `error_code` extras (control/control/stall_tracer.py:429) and as `stall_traces.diagnosis` values (control/control/stall_tracer.py:398).

## dumb-code flags
- `saturated: set | None = None` parameter of `diagnose_pending` is never used in the body; `collect_stalls` calls it without `saturated` (control/control/stall_tracer.py:134, 320).
- Heartbeat staleness `90` is a hardcoded SQL literal in 5 places while `OWNER_STALE_S` is bound as a parameter in 2 others (control/control/stall_tracer.py:199, 255, 261, 305, 311 vs 526, 571).
- `TERMINAL_RUN_STATUSES` / `OPEN_TICKET_STATUSES` constants exist but the same literals are re-hardcoded in SQL instead of bound (control/control/stall_tracer.py:36-37 vs 270, 342, 348-349, 370).
- `claim_event_pending` EXISTS clause duplicated verbatim between ticket query and chain query (control/control/stall_tracer.py:247-251, 297-303).
- `stage_busy_live` / `stage_capacity_live` subqueries duplicated (control/control/stall_tracer.py:252-265 vs 302-315) with asymmetric empty-capacity handling: Python guard `cap > 0` vs SQL `GREATEST(1, ...)` (control/control/stall_tracer.py:104, 310).
- worker type recovered via `split_part(lease_owner, '-', 1)` in 4 subqueries (control/control/stall_tracer.py:256-259, 262-265, 306-309, 312-315); summary-job → ticket join via `split_part(j.ticket_id, ':', 1)` (control/control/stall_tracer.py:367).
- FACTS lists `polymath_fleet` under collections; it is the directory of the supervisor state file path, not a collection (control/control/stall_tracer.py:38).

## refactor notes
- Diagnosis code strings are a stored/logged contract (`stall_traces.diagnosis`, log `error_code`) — renaming them breaks every consumer of the table and logs (control/control/stall_tracer.py:398, 429).
- Episode identity `(unit_kind, unit_id, stalled_since)` and `Stall.key` format `"{kind}:{id}"` are load-bearing for the upsert conflict target and the resolve predicate (control/control/stall_tracer.py:55-56, 399, 413).
- Module imports private symbols of `control.tickets`: `_STAGE_SPEC`, `_artifacts_present`, `_receipts_present`, `_stage_attempt_ok`, plus `DAG_ORDER`, `receipt_scope_for` (control/control/stall_tracer.py:140-144) and `control.fleet_autopilot.LANES` (control/control/stall_tracer.py:71) — refactors of those internals break this module.
- Any extraction of the duplicated liveness subqueries must keep the SQL literal `90` in sync with `OWNER_STALE_S` (control/control/stall_tracer.py:35, 199, 255, 261, 305, 311).
- Sole known importer is control/control/main.py (FACTS.importers); signature changes to `trace_stalls` touch it (control/control/stall_tracer.py:418).

## VERIFY
```verify
grep -Fq 'STALL_THRESHOLD_S = 180' control/control/stall_tracer.py
grep -Fq 'OWNER_STALE_S = 90' control/control/stall_tracer.py
grep -Fq 'return {"stalls": len(stalls), "new": len(new)}' control/control/stall_tracer.py
grep -Fq 'ON CONFLICT (unit_kind, unit_id, stalled_since)' control/control/stall_tracer.py
grep -Fq 'make_interval(secs => 90)' control/control/stall_tracer.py
! grep -Fq 'UPDATE stage_tickets' control/control/stall_tracer.py
```

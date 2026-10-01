# unit: control/control/medic.py
anchor: control/control/medic.py:1-151

## purpose
MEDIC-V1 auto-healing pass for the control loop (owner quote dated 2026-09-05) — control/control/medic.py:1-5 [DERIVED]. Acts on two failure classes measured on the 63-document `cinema` ingest: (1) provider capacity events → re-arm FAILED tickets to READY; (2) idle-in-transaction lock blockers → terminate — control/control/medic.py:7-16 [DERIVED]. Every action is bounded, idempotent and receipted in `medic_actions` (migration 0053) — control/control/medic.py:5-6 [DERIVED]. Sole importer: `control/control/main.py` (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| is_capacity_error | def | (text: str \| None) -> bool | control/control/medic.py:34-36 | — |
| record | def | (conn, kind: str, target: str, detail: dict \| None = None) -> None | control/control/medic.py:39-42 | — |
| rearms_today | def | (conn, ticket_id: str) -> int | control/control/medic.py:45-49 | — |
| find_capacity_failed_tickets | def | (conn, limit: int = 20) -> list[dict] | control/control/medic.py:52-72 | — |
| rearm_ticket | def | (conn, ticket: dict, per_ticket_daily_cap: int = 5) -> bool | control/control/medic.py:75-93 | — |
| find_deadlocks | def | (conn, wait_s: int = 120) -> list[dict] | control/control/medic.py:96-118 | — |
| break_deadlock | def | (conn, dl: dict) -> bool | control/control/medic.py:121-127 | — |
| medic_pass | def | (conn, \*, rearm_per_tick: int = 20, deadlock_wait_s: int = 120, per_ticket_daily_cap: int = 5, enabled: bool = True) -> dict[str, Any] | control/control/medic.py:130-143 | control/control/main.py [INFERRED: sole importer, pass entry point] |
| recent_actions | def | (conn, minutes: int = 15) -> list[dict] | control/control/medic.py:146-150 | — |
| CAPACITY_MARKERS | const | tuple, 4 strings | control/control/medic.py:30 | — |
| REARM_NOTE | const | str | control/control/medic.py:31 | — |

Per-symbol usage by main.py is not in FACTS; only the module import is.

## contracts

**is_capacity_error** — control/control/medic.py:34-36
- in: `text: str | None`; None coerced to `""` (:35).
- out: `any(m in t for m in CAPACITY_MARKERS)` — substring match over the 4 markers (:30, :36).

**record** — control/control/medic.py:39-42
- out: `INSERT INTO medic_actions (kind, target, detail)` with `json.dumps(detail or {}, default=str)` (:40-42).
- post: exactly one row per call, regardless of action outcome (:40-42).

**rearms_today** — control/control/medic.py:45-49
- out: `count(*)` of rows `kind = 'CAPACITY_REARM' AND target = %s AND at > now() - interval '24 hours'` (:47-48).

**find_capacity_failed_tickets** — control/control/medic.py:52-72
- in: `limit = 20`; SQL fetches `(limit * 4,)` rows (:63).
- pre: candidates have `status = 'failed' AND archived_at IS NULL`, ordered `updated_at ASC` (:61-62); last attempt error = newest `stage_attempts.error` by `started_at DESC` for same `run_id`+`stage` (:57-59).
- out: dicts `{ticket_id, run_id, stage, attempt, error}`; capacity = `is_capacity_error(err) or is_capacity_error(note)`; `error = (err or note or "")[:200]`; loop breaks at `len(out) >= limit` (:66-71).

**rearm_ticket** — control/control/medic.py:75-93
- pre: `prior = rearms_today(conn, tid)`; if `prior >= per_ticket_daily_cap` → records `CAPACITY_REARM_REFUSED` with reason `"{prior} re-arms in 24h reached the cap"`, returns `False` (:77-81).
- post: `UPDATE stage_tickets SET status = 'ready', attempt = 0, lease_owner = NULL, lease_expires_at = NULL, last_error_note = %s ... WHERE ticket_id = %s AND status = 'failed'`; note = `REARM_NOTE + " (#{prior + 1} today)"` (:82-87).
- out: `bool(n)` of rowcount; rowcount > 0 also records `CAPACITY_REARM` with `rearm_no: prior + 1` and logs `MEDIC_CAPACITY_REARM` (:88-93).

**find_deadlocks** — control/control/medic.py:96-118
- in: `wait_s = 120`; both thresholds use the same value (:111-113).
- pre: waiter `wait_event_type = 'Lock'`, `now() - w.query_start > wait_s`; blocker `b.state LIKE 'idle in transaction%%'`, `now() - b.state_change > wait_s`; both `<> pg_backend_pid()`; join via `unnest(pg_blocking_pids(w.pid))` LATERAL on `pg_stat_activity` (:100-114).
- out: dicts `{waiter_pid, blocker_pid, wait_event, waiter_wait_s, blocker_idle_s, waiter_query, blocker_query, blocker_app}`; queries whitespace-normalized and cut to 160 chars (:103-104, :116-118).

**break_deadlock** — control/control/medic.py:121-127
- out: `bool` of `SELECT pg_terminate_backend(%s)` on `blocker_pid` (:122).
- post: `DEADLOCK_BREAK` recorded unconditionally with `terminated=bool(ok)`; logs `MEDIC_DEADLOCK_BREAK` (:123-126).

**medic_pass** — control/control/medic.py:130-143
- in: all params keyword-only (the `*` at :130).
- out: disabled → exactly `{"enabled": False}` with no DB access (:132-133); enabled → `{"enabled": True, "rearmed": n, "rearm_refused": n, "deadlocks_broken": n}` (:134, :143).
- post: rearm loop over `find_capacity_failed_tickets(conn, limit=rearm_per_tick)` then deadlock loop over `find_deadlocks(conn, wait_s=deadlock_wait_s)` (:135-141).

**recent_actions** — control/control/medic.py:146-150
- out: up to 20 rows from `medic_actions` where `at > now() - make_interval(mins => %s)`, `ORDER BY at DESC`; `at` stringified via `str(a)` (:147-150).

## effect surface
- Postgres reads: `stage_tickets` (:56-63); `stage_attempts` (correlated subquery, :57-59); `medic_actions` (:47-48, :147-149); `pg_stat_activity` + `pg_blocking_pids` (:100-108); `current_database()` (:109).
- Postgres writes: `stage_tickets` UPDATE (:83-87); `medic_actions` INSERT (:40-42); backend termination via `pg_terminate_backend` (:122).
- Env flags: `POLYMATH_CONTROL_MEDIC_*` via ControlSettings (docstring :18). In-module defaults: `rearm_per_tick=20` (:130), `deadlock_wait_s=120` (:130), `per_ticket_daily_cap=5` (:75, :131), `enabled=True` (:131), `limit=20` (:52), `wait_s=120` (:96), `minutes=15` (:146).
- No files, network calls, Qdrant, or subprocesses appear in SOURCE.
- FACTS.tables_read also lists `lateral` and `now` — those are the SQL `LATERAL` keyword and `now()` function, not tables [INFERRED: extractor noise].

## invariants
INVARIANT: len(CAPACITY_MARKERS) == 4 (`"HTTP 429"`, `"429 Too Many Requests"`, `"lane refused"`, `"LIMITER_REFUSED"`) — control/control/medic.py:30 [DERIVED]
  fails-if: a new provider capacity string is not a substring of any marker → ticket treated as a document failure, never re-armed.
INVARIANT: rearm UPDATE matches rows only when `status = 'failed'` — control/control/medic.py:85-87 [DERIVED]
  fails-if: without the guard, a concurrent lease/state change gets silently reset to READY with attempt 0.
INVARIANT: successful rearm sets `attempt = 0` and `status = 'ready'` atomically in one UPDATE — control/control/medic.py:83-86 [DERIVED]
  fails-if: split operations allow a READY ticket with a stale attempt count.
INVARIANT: daily-cap window is rolling `interval '24 hours'`, cap checked as `prior >= per_ticket_daily_cap` before the UPDATE — control/control/medic.py:47-48, :77-78 [DERIVED]
  fails-if: semantics drift from docstring "Per-ticket cap per day" (:10) or cap off-by-one (5 vs 6 re-arms).
INVARIANT: waiter_wait > wait_s AND blocker_idle > wait_s, same `wait_s` argument for both — control/control/medic.py:111-113 [DERIVED]
  fails-if: asymmetric thresholds terminate blockers too eagerly or miss real cycles.
INVARIANT: candidate fetch size == `limit * 4` — control/control/medic.py:63 [DERIVED]
  fails-if: when >75% of FAILED tickets are capacity errors, fewer than `limit` re-arms happen per tick.
INVARIANT: `rearmed + rearm_refused == len(find_capacity_failed_tickets(...))` per pass — control/control/medic.py:135-139 [DERIVED]
  fails-if: a capacity-failed ticket is skipped without a receipt.
INVARIANT: every action AND every refusal writes a `medic_actions` row (`CAPACITY_REARM`, `CAPACITY_REARM_REFUSED`, `DEADLOCK_BREAK`) — control/control/medic.py:79, :89, :123 [DERIVED]
  fails-if: healing happens unaudited; `rearms_today` undercounts and the cap loosens.

## determinism & idempotency
determinism: NONDETERMINISTIC (db clock `now()` at :48, :101-102, :111-113, :148; live `pg_stat_activity` snapshot :100-114; `pg_terminate_backend` outcome :122; concurrent `stage_tickets` status changes affect UPDATE rowcount :82-87).
idempotency: SAFE for the rearm state change (the `status = 'failed'` guard makes a repeat UPDATE hit 0 rows, :85-87); UNSAFE for receipts — `record()` always INSERTs (:40-42), so replaying a pass duplicates `medic_actions` rows [INFERRED]. Docstring claims "bounded, idempotent and receipted" (:5); the idempotency comes from the status guard, not receipt dedup.

## failure behaviour
- No `try`/`except` anywhere in this module — exceptions propagate to the control-tick caller [DERIVED, by absence].
- Caller guarantee (docstring): "Evidence-only failures of the medic never abort the control tick (it runs in its own savepoint)" — control/control/medic.py:19-20. The savepoint lives in the caller, not here.
- `enabled=False` short-circuits to `{"enabled": False}` before any DB access — control/control/medic.py:132-133.
- Cap refusal is recorded as `CAPACITY_REARM_REFUSED` and returned as `False`, never raised — control/control/medic.py:79-81.
- Failed termination still receipts `DEADLOCK_BREAK` with `terminated=False` and returns `False` — control/control/medic.py:122-127.
- Log error codes: `MEDIC_CAPACITY_REARM` (warning, :91), `MEDIC_DEADLOCK_BREAK` (error, :125). FACTS contains no `fallbacks` field.

## dumb-code flags
- Magic overfetch factor `4` in `(limit * 4,)`, unexplained — control/control/medic.py:63.
- Two different truncation sizes with no rationale: `[:200]` for errors (:69) vs `left(... 160)` for queries (:103-104).
- `recent_actions` hardcodes `LIMIT 20` independent of its `minutes` parameter — control/control/medic.py:148.
- `DEADLOCK_BREAK` receipt written even when termination returned false — control/control/medic.py:122-123.
- `'CAPACITY_REARM'` literal duplicated in Python (:89) and inside SQL (:48) — a rename must touch both.
- `b.state LIKE 'idle in transaction%%'` uses `%%` driver escaping, coupling the file to a %-paramstyle DB-API — control/control/medic.py:112 [INFERRED].
- Docstring "per-ticket cap per day" (:10) vs rolling `interval '24 hours'` (:48) — near-synonyms that can drift.
- Disabled return shape `{"enabled": False}` lacks the counter keys present in the enabled shape — control/control/medic.py:133 vs :134.

## refactor notes
- Sole importer is `control/control/main.py` (FACTS.importers); changing `medic_pass`'s signature or return shape ripples only there — but the savepoint contract (:19-20) also lives in that caller.
- `medic_actions` schema is migration 0053 (:5-6); `record()`'s column list (:41) and the queries in `rearms_today`/`recent_actions` (:47-48, :148) depend on columns `kind, target, detail, at`.
- `CAPACITY_MARKERS` is the single classification point; markers are matched by substring (:35-36), so a new provider error string must appear verbatim inside stored error text — control/control/medic.py:30.
- `REARM_NOTE` text is persisted into `stage_tickets.last_error_note` and is operator-facing — control/control/medic.py:31, :86.
- In-file defaults (20 / 120 / 5 / True) are the fallback for `POLYMATH_CONTROL_MEDIC_*` settings (:18, :130-131); keep them aligned with ControlSettings.

## VERIFY
```verify
grep -Fq 'CAPACITY_MARKERS = ("HTTP 429", "429 Too Many Requests", "lane refused", "LIMITER_REFUSED")' control/control/medic.py
grep -Eq 'attempt = 0, lease_owner = NULL' control/control/medic.py
grep -Fq 'SELECT pg_terminate_backend(%s)' control/control/medic.py
grep -Fq 'per_ticket_daily_cap: int = 5' control/control/medic.py
grep -Fq 'CAPACITY_REARM_REFUSED' control/control/medic.py
! grep -Fq 'except' control/control/medic.py
test "$(grep -c -F 'medic_actions' control/control/medic.py)" -ge 4
grep -Fq 'MEDIC_DEADLOCK_BREAK' control/control/medic.py
```

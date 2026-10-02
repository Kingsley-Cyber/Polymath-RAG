# unit: control/control/stall_tracer.py
anchor: control/control/stall_tracer.py:1-436

## purpose
Detection-only pass of the control plane's tick: any unit (stage ticket, run, summary_job) that has not advanced for `180`s is traced, not waited out — one `stall_traces` row per episode naming what it waits on, using the same predicates the scheduler uses to advance work. It never mutates the traced unit; the fix belongs in the writer the diagnosis names. control/control/stall_tracer.py:1-21 [DERIVED]. Sole importer: control/control/main.py (FACTS.importers).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `trace_stalls` | def | `(conn, census=None, *, threshold_s=STALL_THRESHOLD_S=180, fleet_state_path=SUPERVISOR_STATE)` -> `{"stalls": int, "new": int}` | control/control/stall_tracer.py:424-436 | control/control/main.py |
| `collect_stalls` | def | `(conn, *, census=None, threshold_s=180, slots_alive=None)` -> `list[Stall]` | control/control/stall_tracer.py:237-390 | `trace_stalls` (internal) |
| `persist_traces` | def | `(conn, stalls: list[Stall])` -> `list[Stall]` (first-time stalls) | control/control/stall_tracer.py:395-421 | `trace_stalls` (internal) |
| `fleet_slots_alive` | def | `(path: Path = SUPERVISOR_STATE)` -> `dict[str, bool] \| None` | control/control/stall_tracer.py:61-67 | `trace_stalls` (internal) |
| `lane_slots` | def | `(stage: str)` -> `tuple[str \| None, set[str]]` | control/control/stall_tracer.py:70-75 | `diagnose_ready` (internal) |
| `Stall` | dataclass | fields `unit_kind, unit_id, stalled_since, age_s, diagnosis, detail, run_id=None, stage=None, corpus_id=None`; property `key` -> `str` | control/control/stall_tracer.py:43-56 | — |

## contracts

**trace_stalls** — control/control/stall_tracer.py:424-436
- in: `census.gaps` read via `getattr(census, "gaps", None)` (control/control/stall_tracer.py:339) [DERIVED]
- out: literal `{"stalls": len(stalls), "new": len(new)}` (control/control/stall_tracer.py:436) [DERIVED]
- pre: `stall_traces` has unique key `(unit_kind, unit_id, stalled_since)` — the `ON CONFLICT` target (control/control/stall_tracer.py:405) [DERIVED]
- post: episodes absent from the current list get `resolved_at = now()`; present ones re-upserted with `resolved_at = NULL` (control/control/stall_tracer.py:405-420) [DERIVED]; `log.warning` only for first-seen episodes (control/control/stall_tracer.py:429-435) [DERIVED]

**collect_stalls** — control/control/stall_tracer.py:237-390
- in: clock is DB `now()` (control/control/stall_tracer.py:239) [DERIVED]
- out: candidates are tickets `status IN ('pending','ready','leased')` with `updated_at` older than `threshold_s` (control/control/stall_tracer.py:276-277); each collector capped `LIMIT 500` (control/control/stall_tracer.py:279,358,378) [DERIVED]
- post: no writes to the traced units — detection/evidence only (control/control/stall_tracer.py:8-10) [DERIVED]; `None` returns from `diagnose_ready` (lane saturated, control/control/stall_tracer.py:104-105) and `diagnose_pending` (live predecessor control/control/stall_tracer.py:152-153; corpus-scope receipts with live siblings control/control/stall_tracer.py:177-178) are excluded as live work [DERIVED]

**persist_traces** — control/control/stall_tracer.py:395-421
- out: stalls whose insert was fresh, via `RETURNING (xmax = 0) AS inserted` (control/control/stall_tracer.py:409-414) [DERIVED]

**fleet_slots_alive** — control/control/stall_tracer.py:61-67
- out: `{s["name"]: bool(s.get("alive"))}` from `data["slots"]`; `None` when file absent/unreadable (control/control/stall_tracer.py:64-67) [DERIVED]

Diagnosis codes emitted: ready `READY_NO_CLAIM_EVENT`/`READY_NO_LIVE_SLOT`/`READY_UNCLAIMED`; leased `LEASED_EXPIRED_NOT_RELEASED`/`LEASED_OWNER_GONE`/`LEASED_LONG_RUNNING`; pending `PENDING_OWNER_STAGE`/`PENDING_ON_PREDECESSOR`/`PENDING_ADVANCE_BLOCKED`/`PENDING_ADVANCE_NOT_REACHED`; run `RUN_NO_TICKET_CHAIN`/`RUN_DEGRADED_AWAITING_DECISION`/`RUN_SETTLED_NOT_PROMOTED`; job `SUMMARY_JOB_INFLIGHT_STALLED`/`SUMMARY_JOB_FAILED_TICKET_OPEN` (control/control/stall_tracer.py:13-20, 381-382) [DERIVED].

## effect surface

| surface | detail | anchor |
|---|---|---|
| Postgres read | `stage_tickets`, `worker_registrations`, `outbox_events`, `runs`, `corpora`, `summary_jobs` (FACTS.tables_read; queries at 242-280, 300-324, 343-358, 370-378) | control/control/stall_tracer.py:242-378 [DERIVED] |
| Postgres write | `stall_traces` — upsert (402-412) and resolve `UPDATE ... SET resolved_at = now()` (415-420) | control/control/stall_tracer.py:402-420 [DERIVED] |
| File read | `/tmp/polymath_fleet/supervisor_state.json` best-effort | control/control/stall_tracer.py:38, 64 [DERIVED] |
| Log | logger `"control.stall_tracer"`, one `log.warning` per new stall, detail JSON truncated `[:400]` | control/control/stall_tracer.py:30, 432-435 [DERIVED] |
| Qdrant / subprocess / env flags | none in SOURCE; FACTS "collections" entry `polymath_fleet` is the `/tmp` path, not a store | control/control/stall_tracer.py:38 [DERIVED] |

## invariants

INVARIANT: `STALL_THRESHOLD_S` (180) = owner-rule "three minutes" (180 s) — control/control/stall_tracer.py:3-5, 32 [DERIVED]
  fails-if: threshold drift makes the tracer flag units earlier/later than the stated owner rule.
INVARIANT: SQL heartbeat literal `90` (4 sites) = `OWNER_STALE_S` (90) — control/control/stall_tracer.py:35, 199, 261, 311, 317 [DERIVED]
  fails-if: changing only the constant splits "worker gone" verdicts between Python and SQL paths.
INVARIANT: `Stall.key` = `f"{self.unit_kind}:{self.unit_id}"` = SQL `(unit_kind || ':' || unit_id)` — control/control/stall_tracer.py:55, 419 [DERIVED]
  fails-if: episode resolution marks wrong/all rows resolved.
INVARIANT: episode upsert key = `(unit_kind, unit_id, stalled_since)` — control/control/stall_tracer.py:405 [DERIVED]
  fails-if: duplicate episodes per tick or resolution of live episodes.
INVARIANT: each collector `LIMIT 500` (`_LIMIT`) — control/control/stall_tracer.py:39, 279, 358, 378 [DERIVED]
  fails-if: >500 stalled units of one kind are silently untraced.
INVARIANT: runs with `n_open > 0` emit no run trace (their tickets carry the diagnosis) — control/control/stall_tracer.py:360-362 [DERIVED]
  fails-if: duplicate/conflicting run + ticket diagnoses for the same run.
INVARIANT: `_open_sibling_runs` capped `[:8]` run ids; log detail capped `[:400]` chars — control/control/stall_tracer.py:211, 434 [DERIVED]
  fails-if: unbounded detail payloads in log lines / sibling lists.

## determinism & idempotency
determinism: NONDETERMINISTIC (DB `now()` clock control/control/stall_tracer.py:239; supervisor state file read control/control/stall_tracer.py:64; concurrent `updated_at`/`heartbeat_at` writes feeding every query control/control/stall_tracer.py:244-279) [DERIVED]
idempotency: SAFE per episode (keyed upsert resets `resolved_at = NULL`, control/control/stall_tracer.py:405-408); but `persist_traces(conn, [])` resolves every open episode, since resolution is "not in the passed list" (control/control/stall_tracer.py:415-420) [DERIVED]

## failure behaviour
- `fleet_slots_alive`: `except Exception: return None` (control/control/stall_tracer.py:66-67) — supervisor state unreadable means `slots_alive is None`, which skips the `READY_NO_LIVE_SLOT` branch and the `slots_alive` detail (control/control/stall_tracer.py:100, 106) [DERIVED]
- No other handler in SOURCE; SQL/logging errors propagate to the tick caller in main.py (control/control/stall_tracer.py:1-436) [INFERRED — no try/except besides line 66]

## dumb-code flags
- `90` hardcoded in SQL at 4 sites while `OWNER_STALE_S` is passed as a param elsewhere — control/control/stall_tracer.py:199, 261, 311, 317 vs 280, 325 [DERIVED]
- `'pending', 'ready', 'leased'` re-listed in SQL ×3 though `OPEN_TICKET_STATUSES` exists — control/control/stall_tracer.py:276, 348, 376 vs 37 [DERIVED]
- `'query_ready', 'failed', 'superseded'` re-listed in SQL though `TERMINAL_RUN_STATUSES` exists — control/control/stall_tracer.py:355 vs 36 [DERIVED]
- Unused import `timedelta` — control/control/stall_tracer.py:27 [DERIVED]
- Worker type inferred from `split_part(lease_owner, '-', 1)` of the latest lease holder on the stage; job→ticket join via `split_part(j.ticket_id, ':', 1)` — two string-split identity conventions — control/control/stall_tracer.py:262-271, 373 [DERIVED]
- `GREATEST(1, capacity)` treats a stage with 0 live workers as capacity 1, so a ready ticket there is never "queued" — control/control/stall_tracer.py:316 [DERIVED]
- `holder_alive` merges two states: leased-with-fresh-heartbeat OR ready-and-queued (`bool(r[2]) or bool(r[3])`) — control/control/stall_tracer.py:299 [DERIVED]
- Claim-event match also fires for `payload->>'ticket_id' IS NULL` (broadcast events count for any ticket) — control/control/stall_tracer.py:250-251 [DERIVED]
- FACTS static-analysis artifacts: `tables_written` lists `"set"`, `collections` lists `polymath_fleet` — neither is a real object (FACTS; line 38) [DERIVED]

## refactor notes
- Episode identity is `stalled_since = updated_at` (tickets/runs) or `created_at` (jobs): any writer that bumps `updated_at` mints a new episode and re-logs it — control/control/stall_tracer.py:333, 364, 383, 405 [DERIVED]
- Changing `Stall.key` format or the SQL `(unit_kind || ':' || unit_id)` independently breaks episode resolution — control/control/stall_tracer.py:55, 419 [DERIVED]
- `diagnose_pending` imports private names from `control.tickets` (`DAG_ORDER`, `_STAGE_SPEC`, `_artifacts_present`, `_receipts_present`, `_stage_attempt_ok`, `receipt_scope_for`) — renaming those breaks this module — control/control/stall_tracer.py:140-142 [DERIVED]
- `lane_slots` consumes `control.fleet_autopilot.LANES` tuple shape `(lane, stages, slots)` lazily — control/control/stall_tracer.py:71-74 [DERIVED]
- Changing `OWNER_STALE_S` requires editing the 4 SQL `90` literals or the tracer's liveness picture splits — control/control/stall_tracer.py:35, 199, 261, 311, 317 [DERIVED]
- Sole integration point is `trace_stalls` in control/control/main.py; signature changes touch only that caller (FACTS.importers) [DERIVED]
- SQL is Postgres-dialect (`make_interval`, `->>`, `jsonb` cast `%s::jsonb`); `%s` placeholders imply a psycopg-style driver — control/control/stall_tracer.py:199, 250, 404 [INFERRED — placeholders + dialect visible]

## VERIFY
```verify
grep -Fq 'STALL_THRESHOLD_S = 180' control/control/stall_tracer.py
grep -Fq 'OWNER_STALE_S = 90' control/control/stall_tracer.py
grep -Fq 'make_interval(secs => 90)' control/control/stall_tracer.py
grep -Fq 'INSERT INTO stall_traces' control/control/stall_tracer.py
grep -Fq 'return {"stalls": len(stalls), "new": len(new)}' control/control/stall_tracer.py
grep -Eq 'READY_NO_CLAIM_EVENT|READY_NO_LIVE_SLOT|READY_UNCLAIMED' control/control/stall_tracer.py
! grep -Fq 'UPDATE stage_tickets' control/control/stall_tracer.py
```

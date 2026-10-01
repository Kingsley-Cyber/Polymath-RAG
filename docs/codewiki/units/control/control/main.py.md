# unit: control/control/main.py
anchor: control/control/main.py:1-251

## purpose
Separate control-plane process (ADR-0004): owns census, scheduling, recovery, heartbeat; never inference or user requests — control/control/main.py:1-5 [DERIVED]. Runs a tick cycle (lease → census → gap scheduling → promotions/failures → heartbeat) inside one Postgres transaction — control/control/main.py:7-13 [DERIVED]. Entry point is `run_forever()` under `__main__` — control/control/main.py:249-250 [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `tick` | def | `() -> dict` | control/control/main.py:40-156 | `run_forever` (213) |
| `run_forever` | def | `() -> None` | control/control/main.py:205-246 | `__main__` (249-250) |
| `_ensure_tickets_backpressure_gated` | def | `(conn) -> int` | control/control/main.py:159-169 | `tick` (72) |
| `_barrier_or_none` | def | `(conn, census) -> dict \| None` | control/control/main.py:171-176 | — (no call site in this file) |
| `_corpora_with_open_barriers` | def | `(conn, census) -> dict` | control/control/main.py:179-197 | `tick` (102), `_barrier_or_none` (175) |
| `_corpus_of_run` | def | `(conn, run_id: str) -> str` | control/control/main.py:200-202 | `tick` (110), `_corpora_with_open_barriers` (183) |

## contracts

**tick()** — control/control/main.py:40-156
- in: no params; reads `get_settings()` — 41.
- out: skipped form `{"tick": "skipped", "reason": "lease not held"}` — 46; ok form keys `tick, medic, owner, gaps, scheduled, promoted, failed, degraded, stalls, reconciled, phase_ms` — 144-155.
- pre: lease acquired via `acquire_lease(conn, lease_ttl_s=settings.control.lease_ttl_s)` — 43-44.
- post: `record_heartbeat(conn, owner, tick_ok=True, census_size=len(census.gaps))` before return — 143.
- everything runs inside one `with tx() as conn` — 43.

**run_forever()** — control/control/main.py:205-246
- in: none; `configure_logging("polymath-control")` — 206.
- out: `None`; infinite `while True` — 205-208.
- post: `time.sleep(settings.control.tick_interval_s)` each iteration — 246.

**_ensure_tickets_backpressure_gated(conn)** — control/control/main.py:159-169
- out: int from `fair_ensure_tickets_backpressure_gated(conn, window=32)` — 169.

**_corpora_with_open_barriers(conn, census)** — control/control/main.py:179-197
- out: dict keyed by corpus_id, values are verdicts with a `"passed"` key — 192-196.

## effect surface

| effect | detail | anchor |
|---|---|---|
| Postgres read | table `runs`: `SELECT corpus_id FROM runs WHERE run_id=%s` | control/control/main.py:201 |
| Postgres write | none direct in this file (FACTS `tables_written` = []); writes occur via imported helpers inside `tx()` — [INFERRED: schedule/apply/heartbeat calls mutate] | control/control/main.py:43, 96-118, 143 |
| file write (append) | `/tmp/polymath_fleet/tick_phases.jsonl` (FACTS lists `polymath_fleet` at 227; source shows it is a filesystem path, not a store collection) | control/control/main.py:227-228 |
| env flag | `POLYMATH_DOC_PARENT_MAP_ENABLED` — unset = no-op, "default off" | control/control/main.py:78-80 |
| settings (getattr defaults) | `stall_threshold_s` = `180`; `medic_rearm_per_tick` = `20`; `medic_deadlock_wait_s` = `120`; `medic_per_ticket_daily_cap` = `5`; `medic_enabled` = `True`; `extraction_drop_tolerance` = `None` | control/control/main.py:127, 137-140, 86 |
| settings (direct) | `lease_ttl_s`, `max_attempts`, `extraction_coverage_floor`, `tick_interval_s` | control/control/main.py:44, 84-85, 246 |
| network/subprocess | none visible; "qdrant"/"neo4j" appear only as projection label strings | control/control/main.py:190 |

## invariants

INVARIANT: ticket creation window per tick == `32` — control/control/main.py:169 [DERIVED]
  fails-if: fairness/throughput of new ticket chains changes silently.
INVARIANT: barrier projections == `("qdrant", "neo4j")` — control/control/main.py:190 [DERIVED]
  fails-if: a store projection is added without updating the barrier set → promotions run incomplete.
INVARIANT: backpressure resume threshold == `watermark/2` (pause at `>= watermark`) — control/control/main.py:162-163 [DERIVED]
  fails-if: hysteresis collapses; corpora flap between paused and creating.
INVARIANT: barrier set computed exactly once per tick — control/control/main.py:97-102 [DERIVED]
  fails-if: return to double anti-join cost (comment cites 3.8-4.8s per tick) — control/control/main.py:97-100.
INVARIANT: `owner` in result is `owner[:12]` — control/control/main.py:147 [DERIVED]
  fails-if: longer owners change log/result shape.
INVARIANT: phase timings rounded to 1 decimal ms — control/control/main.py:62, 116, 216 [DERIVED]
  fails-if: sidecar/JSONL consumers see different precision.
INVARIANT: stall tracer and medic each run inside `conn.transaction()` savepoints — control/control/main.py:125, 135 [DERIVED]
  fails-if: their faults abort the whole tick transaction.
INVARIANT: skip path returns before any heartbeat write — control/control/main.py:45-46 [DERIVED]
  fails-if: non-primary replicas would stamp heartbeats they don't own.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: `time.monotonic` — control/control/main.py:209, 240; `perf_counter` — control/control/main.py:60, 101, 212, 231; db state/lease contention — control/control/main.py:43-44; settings/env — control/control/main.py:41, 44)
idempotency: SAFE — whole tick is one transaction (control/control/main.py:43, 7-13) and legacy scheduler events are "idempotent against ticket events by content hash" — control/control/main.py:94-95 [DERIVED]; sidecar JSONL append at 227-234 is append-only, not idempotent across reruns — [INFERRED: file append has no dedup].

## failure behaviour
- stall tracer exception: swallowed → `log.error("stall tracer failed", ...)`, `stalls` stays `{}` so result shows `stalls: 0` — control/control/main.py:123-129 [DERIVED]
- medic exception: swallowed → `log.error("medic failed", ...)`, `medic` stays `{}` — control/control/main.py:132-142 [DERIVED]
- sidecar JSONL write exception: swallowed with bare `pass`, no log — control/control/main.py:235-236 [DERIVED]
- `psycopg.errors.OperationalError` in loop: `log.warning("postgres unavailable; backing off", ...)` with error code `pg_unavailable`, loop continues — control/control/main.py:242-243 [DERIVED]
- any other tick exception: `log.exception("control tick failed", ...)` with error code = exception class name; loop continues — control/control/main.py:244-245 [DERIVED]
- lease not acquired: returns `{"tick": "skipped", "reason": "lease not held"}`, no raise — control/control/main.py:45-46 [DERIVED]

## dumb-code flags
- hardcoded path `/tmp/polymath_fleet/tick_phases.jsonl` — control/control/main.py:227 [DERIVED]
- magic number `window=32` inline — control/control/main.py:169 [DERIVED]
- `_barrier_or_none` defined but never called in this file; `tick` calls `_corpora_with_open_barriers` directly — control/control/main.py:171-176 vs 102 [DERIVED]
- `ensured`, `advanced`, `supervised` assigned but never read (not in return dict) — control/control/main.py:72, 74, 82 [DERIVED]
- `json` imported twice under different aliases (`_json` at 211, `_j2` at 226); `time` re-imported as `_t` (56) and `_perf` (211) — control/control/main.py:56, 211, 226 [DERIVED]
- `exc` bound but unused in the OperationalError handler — control/control/main.py:242 [DERIVED]
- log fields duplicated across two `log.info` calls per ok tick (`tick completed` at 214 and `control tick` at 238) — control/control/main.py:214-221, 237-241 [DERIVED]

## refactor notes
- Census rebuild via `census.__class__(gaps=..., promote=..., fail=..., degrade=...)` assumes exact field set — adding a Census field silently drops it here — control/control/main.py:112-113.
- `phase_ms` key names are a wire contract: they flow into the log `detail` JSON and the sidecar JSONL — renaming breaks both consumers — control/control/main.py:88-93, 115, 217-221, 229-233.
- Deferred imports inside `tick` (`control.tickets`, `control.worker_supervisor`, `control.reconciliation`, `control.medic`) — hoisting them may reintroduce import-order problems — control/control/main.py:52-53, 69, 134, 167, 180, 187 [INFERRED: mid-function imports usually guard cycles].
- Order matters: `reconcile_contract_drift` must run BEFORE ticket creation so stranded runs mint successors under the current contract — control/control/main.py:65-70.
- Per-corpus barrier filtering (109-114) must keep the "blocked corpus must not freeze healthy corpora" property — control/control/main.py:106-108.
- Savepoint wrappers around tracer/medic are required so their faults never abort the tick — control/control/main.py:121-122, 130-131.
- `run_forever` catch-all must keep looping; removing it turns one bad tick into process death — control/control/main.py:242-246.

## VERIFY
```verify
grep -Fq 'fair_ensure_tickets_backpressure_gated(conn, window=32)' control/control/main.py
grep -Fq '/tmp/polymath_fleet/tick_phases.jsonl' control/control/main.py
grep -Fq 'SELECT corpus_id FROM runs WHERE run_id=%s' control/control/main.py
grep -Fq '("qdrant", "neo4j")' control/control/main.py
grep -Fq 'return {"tick": "skipped", "reason": "lease not held"}' control/control/main.py
grep -Fq 'stall_threshold_s", 180' control/control/main.py
test "$(grep -c -F 'except Exception' control/control/main.py)" -ge 4
```

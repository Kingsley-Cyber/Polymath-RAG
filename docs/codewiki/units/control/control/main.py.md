# unit: control/control/main.py
anchor: control/control/main.py:1-254

## purpose
Separate control-plane process (ADR-0004) owning census, scheduling, recovery, and heartbeat; never inference, user requests, or non-scheduling workflow writes (main.py:2-5). Runs one `tick()` per Postgres transaction in a `while True` loop; survives orchestrator crashes and vice versa (main.py:5-6, 8-13, 211).

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `tick` | def | () -> dict | control/control/main.py:41-159 | `run_forever` (main.py:216) |
| `run_forever` | def | () -> None | control/control/main.py:208-249 | `__main__` (main.py:252-253) |

Private helpers (no external importers in FACTS): `_ensure_tickets_backpressure_gated` (162-172), `_barrier_or_none` (174-179), `_corpora_with_open_barriers` (182-200), `_corpus_of_run` (203-205).

## contracts

**tick()** — control/control/main.py:41-159
- in: none; all config via `get_settings()` (main.py:42)
- out: `{"tick": "skipped", "reason": "lease not held"}` when lease lost (main.py:47), else ok-dict with keys `tick, medic, owner, gaps, scheduled, promoted, failed, degraded, stalls, reconciled, phase_ms` (main.py:147-158)
- pre: primary lease acquired with `lease_ttl_s=settings.control.lease_ttl_s` (main.py:45)
- post: `record_heartbeat(conn, owner, tick_ok=True, census_size=len(census.gaps))` before return (main.py:146)
- all phases execute inside one `tx()` connection/transaction (main.py:44)

**run_forever()** — control/control/main.py:208-249
- in: none; out: `None`
- loop body: `tick()`, log `tick completed` with `duration_ms` + `phase_ms` JSON detail (main.py:216-224), then `time.sleep(settings.control.tick_interval_s)` (main.py:249)

**_ensure_tickets_backpressure_gated(conn)** -> int — wraps `fair_ensure_tickets_backpressure_gated(conn, window=32)` (main.py:170-172)

**_corpora_with_open_barriers(conn, census)** -> dict — computes missing-receipt sets once for projections `"qdrant"`, `"neo4j"`, then per-corpus `generation_barrier` verdicts (main.py:190-199)

**_corpus_of_run(conn, run_id: str)** -> str — `SELECT corpus_id FROM runs WHERE run_id=%s`; returns `""` if no row (main.py:204-205)

## effect surface

| kind | target | anchor |
|---|---|---|
| Postgres read | table `runs` (corpus_id lookup) | control/control/main.py:204 |
| Postgres write | none directly in this unit (FACTS `tables_written` empty); writes delegated to imported phase functions | control/control/main.py:44 |
| file write (append) | `/tmp/polymath_fleet/tick_phases.jsonl` | control/control/main.py:230-237 |
| network | Postgres via `tx()` / psycopg | control/control/main.py:20, 44 |
| settings/env | `settings.control.lease_ttl_s`, `max_attempts`, `extraction_coverage_floor`, `extraction_drop_tolerance` (getattr default `None`), `tick_interval_s` | control/control/main.py:45, 85-87, 249 |
| settings/env (getattr defaults) | `stall_threshold_s` = `180`, `medic_rearm_per_tick` = `20`, `medic_deadlock_wait_s` = `120`, `medic_per_ticket_daily_cap` = `5`, `medic_enabled` = `True` | control/control/main.py:130, 140-143 |
| env flag (comment) | `POLYMATH_DOC_PARENT_MAP_ENABLED` — unset = feature off, no-op | control/control/main.py:79-81 |

## invariants

```
INVARIANT: new-ticket creation window == 32 — control/control/main.py:172 [DERIVED]
  fails-if: per-tick mint rate and round-robin fairness change silently.
INVARIANT: backpressure pauses at >= watermark, resumes only at <= watermark/2 — control/control/main.py:165-166 [DERIVED, docstring]
  fails-if: creation flaps on/off at the watermark instead of sticking.
INVARIANT: barrier receipt projections == {"qdrant", "neo4j"} — control/control/main.py:191-193 [DERIVED]
  fails-if: a projection added elsewhere is never receipt-checked before promotion.
INVARIANT: promote list after barrier filter ⊆ census.promote (gaps/fail/degrade preserved) — control/control/main.py:112-116 [DERIVED]
  fails-if: a blocked corpus gets promoted or healthy corpora freeze.
INVARIANT: result owner == owner[:12] — control/control/main.py:150 [DERIVED]
  fails-if: log consumers keyed on the 12-char prefix break.
INVARIANT: phase_ms omits entries whose value is None — control/control/main.py (line out of range) [DERIVED]
  fails-if: sidecar JSONL gains null columns; downstream parsers see schema drift.
INVARIANT: stall tracer and medic each run in their own conn.transaction() and cannot abort tick — control/control/main.py:128, 138 [DERIVED]
  fails-if: a tracer/medic fault rolls back the whole tick transaction.
INVARIANT: inter-tick sleep == settings.control.tick_interval_s — control/control/main.py:249 [DERIVED]
  fails-if: tick rate diverges from configured cadence.
```

## determinism & idempotency
determinism: NONDETERMINISTIC (clock `time.monotonic` control/control/main.py:212, 243 and `_t.perf_counter` 62, 104, 215; db read of `runs` 204; settings/env 42, 85-87, 130, 140-143; concurrency via lease acquisition 45)
idempotency: SAFE — tick is lease-gated (only the lease holder mutates, control/control/main.py:45-47) and legacy scheduler events are "idempotent against ticket events by content hash" (control/control/main.py:95-96)

## failure behaviour

| site | handler | swallowed as | caller sees | anchor |
|---|---|---|---|---|
| stall tracer | `except Exception` -> `log.error("stall tracer failed", ...)` | log | tick continues, `stalls` stays `{}` | control/control/main.py:131-132 |
| medic pass | `except Exception` -> `log.error("medic failed", ...)` | log | tick continues, `medic` stays `{}` | control/control/main.py:144-145 |
| sidecar JSONL append | `except Exception: pass` | silent pass | no signal at all; phase table silently missing rows | control/control/main.py:238-239 |
| Postgres down | `except psycopg.errors.OperationalError` -> warning, error_code `pg_unavailable` | log | loop backs off and retries next interval | control/control/main.py:245-246 |
| any other tick error | `except Exception` -> `log.exception("control tick failed", ...)` | log | loop continues | control/control/main.py:247-248 |
| lease lost | early return | — | `{"tick": "skipped", "reason": "lease not held"}` | control/control/main.py:46-47 |

## dumb-code flags
- Hardcoded sidecar path `/tmp/polymath_fleet/tick_phases.jsonl` — control/control/main.py:230
- Magic number `window=32` with no named constant — control/control/main.py:172
- `_barrier_or_none` (174-179) is defined but never called anywhere in this unit — control/control/main.py:174-179 [INFERRED dead-within-file: no call site visible in SOURCE or FACTS]
- Census rebuilt via `census.__class__(gaps=..., promote=..., fail=..., degrade=...)` — couples to the exact census field set — control/control/main.py:115-116
- Redundant local imports: `import time as _t` (57), `import time as _perf, json as _json` (214), `import json as _j2` (229) although `time` is already module-level (18)
- Truncation literals `12` (owner) and `40` (reason) inline, uncommented — control/control/main.py:150, 222
- Defaults live in getattr fallbacks, separate from the typed settings object (`stall_threshold_s` 180, medic 20/120/5/True) — control/control/main.py:130, 140-143

## refactor notes
- `tick()` runs 10+ phases in one transaction (control/control/main.py:44-159); any exception outside the tracer/medic savepoints rolls back heartbeat too — splitting phases changes atomicity guarantees consumers rely on.
- Census class must keep constructor fields `gaps, promote, fail, degrade`; the barrier branch rebuilds positionally-by-keyword — control/control/main.py:115-116.
- Ok-dict keys are consumed by `run_forever` logging (`tick_result`, `reason`, `gaps`, `phase_ms`) and the sidecar writer — control/control/main.py:220-224, 232-237.
- Projection strings `"qdrant"`/`"neo4j"` are shared with `control.tickets._corpora_with_missing_chunk_receipts` — control/control/main.py:191-193.
- Barrier set must be computed exactly once per tick; the prior double-computation cost "3.8-4.8s of every tick" — control/control/main.py:100-105, 188-189.
- Module boundary: this process must never gain inference, user-request, or non-scheduling workflow writes — control/control/main.py:3-5.

## VERIFY
```verify
grep -Fq 'fair_ensure_tickets_backpressure_gated(conn, window=32)' control/control/main.py
grep -Fq 'SELECT corpus_id FROM runs WHERE run_id=%s' control/control/main.py
grep -Fq '/tmp/polymath_fleet/tick_phases.jsonl' control/control/main.py
grep -Fq 'return {"tick": "skipped", "reason": "lease not held"}' control/control/main.py
grep -Fq 'getattr(settings.control, "medic_enabled", True)' control/control/main.py
test "$(grep -c -F 'time.monotonic' control/control/main.py)" -ge 2
```

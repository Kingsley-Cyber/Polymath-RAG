# unit: shared/polymath_shared/pipeline_health.py
anchor: shared/polymath_shared/pipeline_health.py:1-216

## purpose
Single authority for fleet-health verdicts: distinguishes BLOCKED (work exists or could exist but workers cannot do it, cause attached) from IDLE (alive, nothing queued) — shared/polymath_shared/pipeline_health.py:1-18, 100-107. Also folds sidecar readiness plus fleet state into one CONTROL READY verdict so callers render, not derive it — shared/polymath_shared/pipeline_health.py:182-187, 193. Consumers: orchestrator health API and control plane status (FACTS.importers).

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| `pipeline_health` | def | `(conn, live_seconds: int = LIVE_HEARTBEAT_SECONDS) -> dict[str, Any]` | shared/polymath_shared/pipeline_health.py:98-179 | orchestrator/orchestrator/api/health.py; shared/polymath_shared/control_plane_status.py (module importers, FACTS) |
| `control_ready` | def | `(conn, *, sidecars: dict[str, bool] \| None = None, live_seconds: int = LIVE_HEARTBEAT_SECONDS) -> dict[str, Any]` | shared/polymath_shared/pipeline_health.py:191-215 | same module importers (FACTS) |
| `_degradation` | def | `(conn) -> dict[str, Any]` | shared/polymath_shared/pipeline_health.py:65-95 | internal — called by `pipeline_health` at :159 |

## contracts

**`pipeline_health`** — shared/polymath_shared/pipeline_health.py:98-179
- in: `conn`; `live_seconds` default `LIVE_HEARTBEAT_SECONDS` = `120` — :98, :35 [DERIVED]
- in (SQL): live workers = `heartbeat_at > now() - make_interval(secs => %s)` — :109-116 [DERIVED]
- in (SQL): queued = `stage_tickets` with `status IN ('ready','leased') AND archived_at IS NULL` — :124-127 [DERIVED]
- pre: tables `worker_registrations` (heartbeat_at/status/last_error), `stage_tickets` exist — [INFERRED, SQL at :109-127 requires those columns]
- post: `state` ∈ `{"HEALTHY","IDLE","BLOCKED","DEGRADED"}`; every return carries `state`, `blocked_workers`, `live_workers`, `causes`, `detail`, `queued_tickets`, `workers` — :131-143, :146-153, :161-164, :166-172, :176-179 [DERIVED]
- post: BLOCKED detail names quarantined count, causes, and queued tickets — :136-140 [DERIVED]
- post: `stalls_open`/`stalls_active`/`stalls_dormant`/`stall_diagnoses`/`medic_actions_15m` merged into every live-worker return — :159, :164, :172, :179 [DERIVED]

**`control_ready`** — shared/polymath_shared/pipeline_health.py:191-215
- in: `sidecars` = name -> readiness bool from the `/ready` map; `cloud-modal` optional and never blocks — :195-198, :201 [DERIVED]
- post: returns `{state, label, detail?, pipeline}` with `state` literal ∈ `{"blocked","degraded","ready"}` — :205-215 [DERIVED]
- post: any down sidecar other than `cloud-modal` forces `"blocked"` regardless of fleet state — :200-207 [DERIVED]
- post: fleet `HEALTHY` or `IDLE` both yield `"ready"` — :214-215 [DERIVED]

**`_degradation`** — shared/polymath_shared/pipeline_health.py:65-95
- in (SQL): unresolved `stall_traces` with `last_traced_at > now() - interval '10 minutes'`, grouped by diagnosis — :76-80 [DERIVED]
- in (SQL): `medic_actions` in last 15 minutes, `LIMIT 10` — :87-91 [DERIVED]
- pre: `stall_traces`/`medic_actions` created by migrations 0046+/0053; absence degrades to zeros — :67 [DERIVED]
- post: keys `stalls_open`, `stalls_active`, `stalls_dormant`, `stall_diagnoses` (≤6 `"d×n"` strings), `medic_actions_15m` (≤10) — :73-74, :84, :91 [DERIVED]

## effect surface
| surface | op | anchor |
|---|---|---|
| Postgres `worker_registrations` | SELECT (heartbeat window, status, last_error) | shared/polymath_shared/pipeline_health.py:109-116 |
| Postgres `stage_tickets` | SELECT count | shared/polymath_shared/pipeline_health.py:124-127 |
| Postgres `stall_traces` | SELECT (read inside `conn.transaction()`) | shared/polymath_shared/pipeline_health.py:76-80 |
| Postgres `medic_actions` | SELECT (read inside `conn.transaction()`) | shared/polymath_shared/pipeline_health.py:87-91 |
| Postgres writes | none (FACTS `tables_written: []`) | — |
| env flags / files / network / subprocess | none visible | — |

## invariants
INVARIANT: `stalls_active` = `stalls_open` − `stalls_dormant` — shared/polymath_shared/pipeline_health.py:81-83 [DERIVED]
  fails-if: dormant split stops summing to the raw total; UI counts disagree.
INVARIANT: `DORMANT_STALL_DIAGNOSES` = exactly 4 diagnoses (`PENDING_ON_PREDECESSOR`, `PENDING_ADVANCE_BLOCKED`, `PENDING_OWNER_STAGE`, `RUN_SETTLED_NOT_PROMOTED`) — shared/polymath_shared/pipeline_health.py:59-62 [DERIVED]
  fails-if: a dormant backlog diagnosis is left out and stale stall rows pin state to DEGRADED (the GAP-6 failure the split exists to prevent, :47-58).
INVARIANT: live workers ⇒ `heartbeat_at` within `live_seconds` (default `120`) — shared/polymath_shared/pipeline_health.py:35, :109-116 [DERIVED]
  fails-if: window removed ⇒ 981/1310 stale registrations pin fleet to BLOCKED forever, per comment :31-34.
INVARIANT: state = BLOCKED ⟺ (≥1 live worker with `status == "quarantined"`) OR (0 live workers AND queued > 0) — shared/polymath_shared/pipeline_health.py:118-129, :145-153 [DERIVED]
  fails-if: BLOCKED/IDLE collapse — the exact regression the module docstring forbids, :14-17.
INVARIANT: `cloud-modal` never appears in `dark` — shared/polymath_shared/pipeline_health.py:201 [DERIVED]
  fails-if: an optional sidecar starts blocking the CONTROL READY verdict.
INVARIANT: `control_ready` state ∈ `CONTROL_READY_STATES` = `{"ready","blocked","degraded"}` — shared/polymath_shared/pipeline_health.py:188, :206-215 [DERIVED]

## determinism & idempotency
determinism: NONDETERMINISTIC (SQL `now()` clock at shared/polymath_shared/pipeline_health.py:79, :91, :113; live DB contents)
idempotency: SAFE (read-only — FACTS `tables_written: []`; no writes in SOURCE)

## failure behaviour
- `except Exception: pass` at shared/polymath_shared/pipeline_health.py:85 and :93 (FACTS.fallbacks, both `SWALLOWED: pass`) — stall_traces or medic_actions query failure yields zeros/empty lists.
- Consequence: with a swallowed stall read, `queued and stalls_active == 0 and not medic_actions_15m` returns HEALTHY at :160-164 — degraded signal silently lost — [INFERRED, zeros flow into the HEALTHY branch].
- `pipeline_health`'s own queries (:109-116, :124-127) are unguarded — DB errors propagate to the caller — shared/polymath_shared/pipeline_health.py:109-127 [DERIVED].
- No error codes raised by this module.

## dumb-code flags
- `DORMANT_RUN_AGE_SECONDS = 180` defined but referenced by no code in this file; the GAP-4 comment (:37-41) claims it is "reused here" — shared/polymath_shared/pipeline_health.py:42 [DERIVED]
- `CONTROL_READY_STATES` (:188) unused in-file; `control_ready` writes literals `"blocked"`/`"degraded"`/`"ready"` directly (:206, :208, :211, :215) — duplicated values, drift risk — shared/polymath_shared/pipeline_health.py:188 vs :206-215 [DERIVED]
- Magic literals: `interval '10 minutes'` (:79), `interval '15 minutes'` + `LIMIT 10` (:91), slice caps `[:6]` (:84), `[:20]` (:142), `[:3]` (:169).
- `conn.transaction()` wraps pure SELECTs — shared/polymath_shared/pipeline_health.py:76, :88 [DERIVED]
- `NULL` worker status coerced to `""` before compare — `(w[2] or "") == BLOCKING_WORKER_STATUS` — shared/polymath_shared/pipeline_health.py:121 [DERIVED]

## refactor notes
- Two importers depend on this module: orchestrator/orchestrator/api/health.py and shared/polymath_shared/control_plane_status.py (FACTS.importers) — signature/key changes hit both.
- Return keys (`state`, `blocked_workers`, `live_workers`, `causes`, `detail`, `queued_tickets`, `workers`, `stalls_open`, `stalls_active`, `stalls_dormant`, `stall_diagnoses`, `medic_actions_15m`) are the caller contract; callers render, they do not derive — shared/polymath_shared/pipeline_health.py:184-187.
- `stalls_open` must stay the raw total for "existing readers" — shared/polymath_shared/pipeline_health.py:69-71.
- Do not recompose the CONTROL READY verdict in the UI — single-authority rule cites design law 11.187 — shared/polymath_shared/pipeline_health.py:182-187.
- `control_ready`'s `sidecars` map comes from the caller's `/ready` `is_ready()` computation; the module cannot read it from Postgres — shared/polymath_shared/pipeline_health.py:195-198.

## VERIFY
```verify
grep -Fq 'BLOCKING_WORKER_STATUS = "quarantined"' shared/polymath_shared/pipeline_health.py
grep -Fq 'LIVE_HEARTBEAT_SECONDS = 120' shared/polymath_shared/pipeline_health.py
grep -Fq 'DORMANT_RUN_AGE_SECONDS = 180' shared/polymath_shared/pipeline_health.py
grep -Fq 'CONTROL_READY_STATES = frozenset({"ready", "blocked", "degraded"})' shared/polymath_shared/pipeline_health.py
grep -Fq 'out["stalls_active"] = out["stalls_open"] - out["stalls_dormant"]' shared/polymath_shared/pipeline_health.py
grep -Fq 'name != "cloud-modal"' shared/polymath_shared/pipeline_health.py
test "$(grep -c -F 'except Exception:  # noqa: BLE001' shared/polymath_shared/pipeline_health.py)" -ge 2
! grep -Fq 'INSERT INTO' shared/polymath_shared/pipeline_health.py
```

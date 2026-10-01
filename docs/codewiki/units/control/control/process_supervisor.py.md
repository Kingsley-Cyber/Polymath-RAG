# unit: control/control/process_supervisor.py
anchor: control/control/process_supervisor.py:1-723

## purpose
CP2.1 fleet process parent: spawns and supervises every long-lived component (workers, neural sidecars, orchestrator, MCP), detects death and hang-wedges, restarts under a bounded budget, quarantines crash-loopers, and parks/unparks slots on measured demand (autopilot). Health = fresh DB registration heartbeat for workers, HTTP readiness for services, tick heartbeat for control itself. [DERIVED] control/control/process_supervisor.py:1-21, 36-40

## public surface
| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| lane_offset_env | function | (slot_name: str) -> dict[str, str] | control/control/process_supervisor.py:151-158 | — |
| Slot | dataclass | name, module, argv, cwd, health_url, readiness_interval_s, readiness_failures_before_restart, proc, parked, exits, restarts, quarantined … | control/control/process_supervisor.py:161-178 | — |
| _dotenv_overlay | function | (path) -> dict | control/control/process_supervisor.py:181-202 | — |
| control_heartbeat_stale | function | (heartbeat_age_s: float\|None, uptime_s: float, threshold_s: float) -> bool | control/control/process_supervisor.py:205-218 | — |
| _release_leases_of_pid | function | (dsn: str, pid: int, note: str) -> int | control/control/process_supervisor.py:221-244 | — |
| Supervisor | class | _fleet_filter, __init__, _spawn, _restart_allowed, _quarantine, verify_health, tick, _check_control_heartbeat, _check_readiness, _autopilot_reconcile, state, _write_state, run_forever, _on_term | control/control/process_supervisor.py:247-708 | — |
| main | function | () -> None | control/control/process_supervisor.py:711-719 | — |

Imports consumed: control.fleet_autopilot.desired_slots (643), polymath_shared.runtime_budget.{export_env, preflight, profile_slots} (259, 366, 685), polymath_shared.settings.get_settings (315), polymath_shared.logging.configure_logging (712). control/control/process_supervisor.py:259,315,366,643,685,712

## contracts
**lane_offset_env(slot_name)** — in: slot name string; out: `{env: index}` for owning stages, `{}` otherwise; post: `doc_parent_map` -> `{"POLYMATH_DOC_PARENT_MAP_LANE_OFFSET": "1"}`, `doc_parent_map3` -> `"3"` (suffix `""` or digits only). [DERIVED] control/control/process_supervisor.py:151-158, 145-148

**control_heartbeat_stale(heartbeat_age_s, uptime_s, threshold_s)** — pre: none; out bool; post: `False` while `uptime_s < threshold_s` (boot grace); after grace, stale iff `heartbeat_age_s is None or > threshold_s`. [DERIVED] control/control/process_supervisor.py:216-218

**_release_leases_of_pid(dsn, pid, note)** — in: pid of a worker the supervisor itself is stopping; out: count of released leases; post: matching `stage_tickets` rows go `status='ready', lease_owner=NULL, lease_expires_at=NULL` with note, no attempt consumed; any Exception -> `return 0`. [DERIVED] control/control/process_supervisor.py:231-244

**Supervisor.verify_health(slot)** — out bool; HTTP slot: status 200 AND body `ready is not False` within `health_timeout_s`; worker slot: `MAX(EXTRACT(EPOCH FROM heartbeat_at)) >= slot.started_at` (fresh registration, not mere process existence); control slot: `slot.proc.poll() is None`. [DERIVED] control/control/process_supervisor.py:410-450

**Supervisor.tick()** — out: state dict; post: quarantined/parked slots skipped, dead slots respawned under budget, live service slots readiness-probed, state JSON rewritten. [DERIVED] control/control/process_supervisor.py:453-484, 674-679

## effect surface
| kind | item | anchor |
|---|---|---|
| PG read | worker_registrations — MAX heartbeat_at per worker_type | control/control/process_supervisor.py:440-445 |
| PG read | worker_registrations — quarantined-by-pid count (heartbeat fresh 30 s) | control/control/process_supervisor.py:558-563 |
| PG read | control_owners — `EXTRACT(EPOCH FROM now() - MAX(last_seen_at))` | control/control/process_supervisor.py:492-495 |
| PG write | stage_tickets — leased→ready lease handback | control/control/process_supervisor.py:231-241 |
| PG write | worker_registrations — `status='quarantined'` + last_error | control/control/process_supervisor.py:402-405 |
| files | /tmp/polymath_fleet/{slot.name}.log (append), supervisor_state.json | control/control/process_supervisor.py:302-303, 342, 674-679 |
| files | repo-root .env read and overlaid on every spawn | control/control/process_supervisor.py:363-364 |
| network | httpx.get health URLs — 127.0.0.1:8742, :8743, :7200, :8930 | control/control/process_supervisor.py:56,60,67,75,419,596 |
| subprocess | Popen per slot, `start_new_session=True`; terminate→wait(15)→kill on restarts | control/control/process_supervisor.py:384-387, 510-517, 580-587, 618-625 |
| env read | POLYMATH_FLEET_DIR = None | control/control/process_supervisor.py:718 |
| env read | POLYMATH_PG_DSN = 'postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath' | control/control/process_supervisor.py:323-325 |
| env read | POLYMATH_FLEET_ONLY = '' (unknown names -> ValueError) | control/control/process_supervisor.py:255, 274 |
| env read | POLYMATH_PROFILE = '' (-> profile_slots allowlist) | control/control/process_supervisor.py:257-260 |
| env read | POLYMATH_AUTOPILOT = '' ('1' enables) | control/control/process_supervisor.py:331 |
| env set (child) | POLYMATH_EXTRACT_AFFINITY: 'local' for `extract`, 'cloud' for `extract*` | control/control/process_supervisor.py:375-378 |
| env set (child) | POLYMATH_DOC_PROFILE_LANE_OFFSET / POLYMATH_DOC_PARENT_MAP_LANE_OFFSET + export_env(slot.name) budget caps | control/control/process_supervisor.py:145-148, 366-367, 382-383 |

## invariants
INVARIANT: restart allowed ⟺ `len(slot.exits) <= max_restarts` (default 5) inside `window_s` (default 300.0) — control/control/process_supervisor.py:391-394, 277-279 [DERIVED]
  fails-if: crash-looper is hammered forever, or a healthy slot gets quarantined early.
INVARIANT: `control_heartbeat_stale` returns False while `uptime_s < threshold_s` (default 180, settings `control.stall_threshold_s`) — control/control/process_supervisor.py:216-218, 312-319 [DERIVED]
  fails-if: control restarted during boot before it can take the lease and tick.
INVARIANT: worker health requires heartbeat epoch `>= slot.started_at` — control/control/process_supervisor.py:443-445 [DERIVED]
  fails-if: a previous process's stale registration passes as healthy.
INVARIANT: HTTP health = status 200 AND body `ready is not False` — control/control/process_supervisor.py:419-429, 596-601 [DERIVED]
  fails-if: a sidecar answering 200 with `{"ready": false}` is treated as wedged/healthy incorrectly.
INVARIANT: orchestrator readiness override = interval 20.0 s, failures 3, vs fleet default 120.0 s / 5 — control/control/process_supervisor.py:68, 286-287 [DERIVED]
  fails-if: default 5×120 s policy = ~10 min API outage on a SIGTERM-hung uvicorn.
INVARIANT: autopilot parks every slot except `control`, `orchestrator`, `intake` at boot — control/control/process_supervisor.py:334-337 [DERIVED]
  fails-if: over-committed fleet on a shared workstation.
INVARIANT: lease handback sets `status='ready'`, `lease_owner=NULL`, no attempt field touched — control/control/process_supervisor.py:231-239 [DERIVED]
  fails-if: two fence restarts consume 2 of a ticket's 3 attempts without any real failure.

## determinism & idempotency
determinism: NONDETERMINISTIC (clock: time.time at 388, 392, 416-417, 436-437, 473, 531, 636; network: httpx.get 419, 596; subprocess.Popen 384; Postgres reads/writes 231-241, 402-405, 440-445, 492-495, 558-563; env: FLEET_ONLY/PROFILE/AUTOPILOT/PG_DSN/FLEET_DIR 255, 257, 323, 331, 718)
idempotency: SAFE — tick/_write_state re-runnable; lease release only touches rows `status='leased'` matching pid, second call returns 0 (231-241). UNSAFE — `_spawn` has no lock: two supervisor instances on one fleet double-spawn slots unless split via POLYMATH_FLEET_DIR (714-718). [INFERRED from absent locking + the two-instance comment]

## failure behaviour
- `_release_leases_of_pid`: any Exception swallowed, `return 0` — caller sees "no leases" and cannot distinguish DB outage; expiry sweep then charges attempt+1. control/control/process_supervisor.py:243-244, 224-227
- `_quarantine` DB update failure: `log.exception("could not record quarantine in DB")`, slot still quarantined in memory. control/control/process_supervisor.py:407-408
- `_check_control_heartbeat` DB probe failure: silent `return` — no watchdog while Postgres is unreachable. control/control/process_supervisor.py:490-498
- readiness probe exception -> `ready = False`, counts toward `readiness_failures`; fence-heal SQL block: `pass` on Exception. control/control/process_supervisor.py:602-603, 590-591
- `_spawn` without budget: `log.warning("no runtime budget for slot %s; starting uncapped", ...)`. control/control/process_supervisor.py:368-370
- autopilot observe failure: `log.warning("autopilot observe failed (keeping fleet): %s")`. control/control/process_supervisor.py:647-649
- `_write_state` failure: swallowed `pass` — state file can silently go stale. control/control/process_supervisor.py:678-679
- `run_forever` preflight: `BudgetExceeded` -> `log.error("REFUSING TO START: %s")` + raise; any other Exception -> warning, fleet continues. control/control/process_supervisor.py:684-695

## dumb-code flags
- `_quarantine` updates `worker_registrations WHERE worker_type=%s (slot.name)`, but the code's own comment says slot names do NOT match worker_type strings ("profile" vs "profile_document") — the quarantine row likely never matches for most slots. control/control/process_supervisor.py:402-405 vs 556-558 [DERIVED]
- Two liveness definitions for control: `verify_health` = process alive only (434-435), `_check_control_heartbeat` = control_owners last_seen_at (492-495). control/control/process_supervisor.py:434-435, 492-495 [DERIVED]
- Four near-identical terminate→wait(15)→kill→respawn blocks: 510-519, 580-589, 618-627, 702-704. [DERIVED]
- `run_forever` uses `raise RuntimeError("autopilot: per-tick budget gating")` as control flow to skip preflight — caught two lines later by `except Exception`. control/control/process_supervisor.py:686-691 [DERIVED]
- `time.sleep(self.backoff_s * len(slot.exits))` inside tick blocks supervision of all other slots (backoff_s=2.0; 5 exits -> 10 s freeze). control/control/process_supervisor.py:480, 288 [INFERRED: single-threaded loop, sleep is inline]
- `_release_leases_of_pid` returns 0 for both "nothing to release" and "DB down". control/control/process_supervisor.py:243-244 [DERIVED]
- Retired-slot rollback argv (GLiNER/spaCy, local_extractor) lives only in comments — greps for `sidecar_gliner` still hit the file. control/control/process_supervisor.py:42-53 [DERIVED]
- Default DSN hardcodes dev credentials in source. control/control/process_supervisor.py:323-325 [DERIVED]

## refactor notes
- Slot names are load-bearing: `lane_offset_env` matches `startswith(stage)` + digit suffix (151-156); extract affinity keys off `name == "extract"` vs `startswith("extract")` (375-378). Renaming or renumbering doc_profile/doc_parent_map slots breaks lane ownership — the registry `slots.doc_parent_map.owners` count must match, per the L3 comment (one slot per Groq account; rollback = drop doc_parent_map5/6 and set count 4). control/control/process_supervisor.py:127-136, 151-158, 375-378
- FLEET membership changes ripple to: runtime budget export_env per slot name (366-367), autopilot desired_slots universe (643-646), POLYMATH_FLEET_ONLY validation (274 — unknown names raise ValueError for external callers).
- Ops consumers of `/tmp/polymath_fleet/supervisor_state.json` and `{name}.log` layout: a second (serving) supervisor instance requires POLYMATH_FLEET_DIR or the two clobber each other's state. control/control/process_supervisor.py:302-303, 342, 714-718
- Every restart path must keep calling `_release_leases_of_pid` before terminate, or deliberate restarts start consuming ticket attempts. control/control/process_supervisor.py:541-547, 573-579
- Readiness budgets are per-slot overridable (`readiness_interval_s`, `readiness_failures_before_restart` in FLEET dicts); orchestrator's 20.0/3 override exists because of a measured 10-minute outage — do not "normalize" it to the fleet defaults. control/control/process_supervisor.py:62-68, 296-298

## VERIFY
```verify
grep -Fq 'CONTROL-HEARTBEAT-WATCHDOG-V1' control/control/process_supervisor.py
grep -Fq 'postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath' control/control/process_supervisor.py
grep -Fq 'POLYMATH_DOC_PARENT_MAP_LANE_OFFSET' control/control/process_supervisor.py
grep -Fq 'max_restarts: int = 5, window_s: float = 300.0' control/control/process_supervisor.py
test "$(grep -c -F 'time.time' control/control/process_supervisor.py)" -ge 8
! grep -Fq 'import psycopg2' control/control/process_supervisor.py
```

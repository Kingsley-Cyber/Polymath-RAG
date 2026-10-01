# flow: fleet-boot
How the system starts and restarts: scripts/bounce_fleet.sh, scripts/boot_polymath.sh, the process supervisor, the sidecars, the bundle fence, readiness.

## hops
| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | bounce resolves `ROOT="${POLYMATH_FLEET_ROOT:-/Users/king/Documents/polymath-rebuild/polymath-v4}"`, `EXPECT_WORKERS=26`, `EXPECT_TYPES=13`; `cd "$ROOT"` else exit 1 | scripts/bounce_fleet.sh:7-10 [DERIVED] | env -> cwd | checkout missing -> exit 1 |
| 2 | takes lock dir `/private/tmp/polymath_fleet/bounce.lock`; lock older than 10 min is rmdir'd as leftover; `mkdir` failure -> exit 3; trap rmdir on EXIT | scripts/bounce_fleet.sh:12-21 [DERIVED] | none -> lock dir | second click while one runs -> exit 3 |
| 3 | TERMs every supervisor: `pgrep -f "control\.process_supervisor" \| xargs kill -TERM` | scripts/bounce_fleet.sh:25 [DERIVED] | process names -> SIGTERM | supervisor ignores TERM (orchestrator limbo, process_supervisor.py:62-64) |
| 4 | waits ≤90 × 2s until 0 processes (`count()` ps grep) and 0 listeners (`listeners()` lsof on 7200/8742/8743/8930); else `ABORT: still alive` exit 1 | scripts/bounce_fleet.sh:22-23,27-37 [DERIVED] | ps/lsof -> counts | survivors -> exit 1 |
| 5 | `nohup bash scripts/boot_polymath.sh > /private/tmp/polymath_fleet/boot.log 2>&1 &` + disown | scripts/bounce_fleet.sh:38-39 [DERIVED] | none -> background boot, boot.log | boot.log is the only boot trace |
| 6 | boot `cd "$(dirname "$0")/.."`, exports `POLYMATH_PG_DSN` default, sources `.env` with `set -a` (the ONLY execution contract; no knob defaults beyond it) | scripts/boot_polymath.sh:5-15 [DERIVED] | .env -> exported env | a non-.env contract would silently pin old knobs |
| 7 | `docker compose up -d postgres redis qdrant neo4j \|\| true`; waits ≤60 × 2s for psycopg connect | scripts/boot_polymath.sh:18-24 [DERIVED] | none -> stores up | compose failure ignored by `\|\| true` |
| 8 | bundle fence: `bundle_integrity.py --strict`; violation -> `boot: FATAL — semantic runtime integrity violated`, refuses to start, exit 1 (re-freeze deliberately with `--freeze`) | scripts/boot_polymath.sh:46-52 [DERIVED] | frozen bundle vs runtime -> pass/exit 1 | semantic drift blocks boot by design |
| 9 | budget: `POLYMATH_AUTOPILOT=1` -> static preflight skipped (per-tick gating); else `runtime_budget.preflight`, over-commit -> exit 1 | scripts/boot_polymath.sh:57-67 [DERIVED] | config/runtime_budget.yaml -> committed/ceiling GB | over-committed working set refuses to start |
| 10 | `exec .venv/bin/python -m control.process_supervisor` (boot PID replaced by supervisor) | scripts/boot_polymath.sh:71-72 [DERIVED] | env -> supervisor process | — |
| 11 | `_fleet_filter`: `POLYMATH_FLEET_ONLY` allowlist, else `POLYMATH_PROFILE` -> `profile_slots`; unknown slot names -> `ValueError` | control/control/process_supervisor.py:253-275,290 [DERIVED] | env -> slot list | typo'd slot name aborts with ValueError |
| 12 | autopilot on: every slot starts `parked` except `control`, `orchestrator`, `intake` | control/control/process_supervisor.py:331-337 [DERIVED] | POLYMATH_AUTOPILOT -> parked flags | — |
| 13 | `run_forever`: budget preflight again (skipped under autopilot); `BudgetExceeded` -> `REFUSING TO START` raise; SIGTERM/SIGINT -> `_on_term` | control/control/process_supervisor.py:681-698 [DERIVED] | budget plan -> start/refuse | refuses rather than thrashing the workstation |
| 14 | `tick` loop (`poll_s=2.0`): spawns unstarted slots; `_spawn` rewrites `{python}` to `repo/.venv/bin/python`, logs to `/tmp/polymath_fleet/{name}.log`, `start_new_session=True` | control/control/process_supervisor.py:340-347,384-388,699-700 [DERIVED] | slot spec -> child Popen | — |
| 15 | child env per spawn: `os.environ.copy()` + `_dotenv_overlay(.env)` (rotated keys visible per respawn) + `export_env(slot.name)` memory caps; `extract`->`POLYMATH_EXTRACT_AFFINITY=local`, `extractN`->cloud; `lane_offset_env` sets e.g. `POLYMATH_DOC_PARENT_MAP_LANE_OFFSET=3` | control/control/process_supervisor.py:356-383 [DERIVED] | .env + budget + slot name -> child env | no budget found -> "starting uncapped" warning |
| 16 | service slots: embedder `127.0.0.1:8742/ready`, reranker `8743/ready`, orchestrator `7200/health` (`readiness_interval_s: 20.0`, `readiness_failures_before_restart: 3`), mcp `8930/health`; `local_extractor`, `sidecar_gliner`, `sidecar_spacy` slots are retired/removed | control/control/process_supervisor.py:54-75 [DERIVED] | argv slots -> HTTP services | GLiNER/spaCy/local_extractor absent by design |
| 17 | `verify_health` at spawn: HTTP 200 AND body `ready is not False`; worker slots need fresh `worker_registrations` heartbeat `>= slot.started_at`; control slot = `poll() is None` | control/control/process_supervisor.py:410-450 [DERIVED] | health_url / DB -> bool | alive process without fresh heartbeat = unhealthy |
| 18 | live-loop `_check_readiness`: control on fast 30s cadence via `control_owners` `last_seen_at` (stale > `control_stall_threshold_s`, default 180 -> restart); services on slow cadence (default 120s, 5 strikes, probe timeout 60s) -> wedge restart | control/control/process_supervisor.py:312-319,486-519,521-535 [DERIVED] | DB age / HTTP -> keep/restart | wedged-but-alive slot restarted like a dead one |
| 19 | worker exit: append exit time, backoff `backoff_s * len(slot.exits)`, respawn; more than `max_restarts=5` inside `window_s=300.0` -> `_quarantine` (`worker_registrations SET status='quarantined'`) | control/control/process_supervisor.py:391-394,462-482,396-408 [DERIVED] | exit code -> restart/quarantine | crash-loop quarantined, CRITICAL logged |
| 20 | fence autoheal: slot's pid `status='quarantined'` in `worker_registrations` with heartbeat <30s old -> `_release_leases_of_pid` (leases -> `ready`, no attempt consumed) + respawn onto current code | control/control/process_supervisor.py:221-244,543-589 [DERIVED] | pid -> released leases + respawn | budget still applies (quarantine law) |
| 21 | `_autopilot_reconcile` every 15s: `desired_slots(conn, slot_names)` decides wake/park; parking TERMINATES the process (only reliable way to return MPS/Metal memory) | control/control/process_supervisor.py:629-664 [DERIVED] | Postgres backlog/query recency -> slot set | observe failure -> keep fleet |
| 22 | every tick writes slot state to `/tmp/polymath_fleet/supervisor_state.json` | control/control/process_supervisor.py:302-303,483,674-679 [DERIVED] | slot fields -> json file | write errors swallowed (pass) |
| 23 | bounce polls 72 × 5s: `curl 127.0.0.1:7200/ready` needs `'"ready":true'` AND healthy=`26` AND distinct `worker_type`=`13` AND distinct `left(execution_bundle_hash,12)`=`1` -> `READY` exit 0; else `NOT READY after 360s`, `tail -25 boot.log`, exit 2 | scripts/bounce_fleet.sh:41-58 [DERIVED] | /ready + worker_registrations -> exit 0/2 | split-bundle fleet never reports READY |

## state written
| store | what | anchor |
|---|---|---|
| `/private/tmp/polymath_fleet/bounce.lock` | lock dir; rmdir'd on EXIT | scripts/bounce_fleet.sh:13,17-21 [DERIVED] |
| `/private/tmp/polymath_fleet/boot.log` | boot script stdout/stderr | scripts/bounce_fleet.sh:38 [DERIVED] |
| `/tmp/polymath_fleet/{slot.name}.log` | per-slot child stdout+stderr (append) | control/control/process_supervisor.py:341-342 [DERIVED] |
| `/tmp/polymath_fleet/supervisor_state.json` | per-tick slot state (name, pid, alive, restarts, quarantined, last_exit_code) | control/control/process_supervisor.py:302-303,667-679 [DERIVED] |
| `worker_registrations` | `status='quarantined'`, `last_error` on quarantine; fresh heartbeat rows written by the workers themselves via the `run_worker` registration path | control/control/process_supervisor.py:399-405,9-14 [DERIVED] |
| `stage_tickets` | supervisor-stopped worker's leases -> `status='ready'`, `lease_owner=NULL`, `lease_expires_at=NULL`, note set, no attempt consumed | control/control/process_supervisor.py:231-239 [DERIVED] |
| docker containers `postgres redis qdrant neo4j` | stores brought up detached | scripts/boot_polymath.sh:18 [DERIVED] |

## flags that change this flow
| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_FLEET_ROOT` | `/Users/king/Documents/polymath-rebuild/polymath-v4` | checkout bounce boots from (never the copied worktree) | scripts/bounce_fleet.sh:4,7 [DERIVED] |
| `POLYMATH_EXPECT_WORKERS` | `26` | required healthy worker count for READY | scripts/bounce_fleet.sh:8,51 [DERIVED] |
| `POLYMATH_EXPECT_TYPES` | `13` | required distinct `worker_type` count | scripts/bounce_fleet.sh:9,51 [DERIVED] |
| `POLYMATH_PG_DSN` | `postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath` | Postgres DSN for boot, supervisor, bounce health query | scripts/boot_polymath.sh:6; control/control/process_supervisor.py:323-325 [DERIVED] |
| `POLYMATH_PROFILE` | unset (full fleet) | slot set via `profile_slots`; `serve` = ceiling-checked standing state; never leave a build profile after a build | control/control/process_supervisor.py:256-260; scripts/boot_polymath.sh:29-36 [DERIVED] |
| `POLYMATH_FLEET_ONLY` | `""` | explicit slot allowlist; unknown names -> `ValueError` | control/control/process_supervisor.py:255,270-274 [DERIVED] |
| `POLYMATH_AUTOPILOT` | unset | `"1"` parks all but control/orchestrator/intake, moves budget gating to per-tick, skips static preflight | scripts/boot_polymath.sh:57-59; control/control/process_supervisor.py:331-337,469 [DERIVED] |
| `POLYMATH_EXTRACT_AFFINITY` | setdefault: `local` for `extract`, `cloud` for `extractN` | lane affinity; both steal the other lane when dry | control/control/process_supervisor.py:371-378 [DERIVED] |
| `POLYMATH_DOC_PROFILE_LANE_OFFSET` / `POLYMATH_DOC_PARENT_MAP_LANE_OFFSET` | 1-based slot index | slot N owns its account's lanes (`slots.<stage>.owners`) | control/control/process_supervisor.py:143-158,379-383 [DERIVED] |
| `POLYMATH_DOC_PARENT_MAP_ENABLED` | off | flag off => no pMAP work, slot just parks | control/control/process_supervisor.py:110-113 [DERIVED] |

## failure modes
1. `A restart is already running` exit 3 -> lock dir exists from a live bounce -> scripts/bounce_fleet.sh:17-20; a lock older than 10 minutes is auto-removed as a killed-run leftover (scripts/bounce_fleet.sh:14-16).
2. `ABORT: still alive` exit 1 -> TERM'd fleet left processes or listeners after ~180s; SIGTERM could leave uvicorn alive with the port closed for minutes (measured ORCHESTRATOR-LIMBO-V1) -> scripts/bounce_fleet.sh:31-37; control/control/process_supervisor.py:62-64.
3. `NOT READY after 360s` exit 2 -> fleet never reached `"ready":true` + 26/13/1 within 72 × 5s; `tail -25 /private/tmp/polymath_fleet/boot.log` is the diagnostic -> scripts/bounce_fleet.sh:41-58.
4. `boot: FATAL — semantic runtime integrity violated` -> runtime semantic surface differs from the frozen bundle contract; boot refuses to start (fix the invariant or re-freeze with `--freeze`) -> scripts/boot_polymath.sh:46-52.
5. Refuses to start on budget -> committed GB over ceiling at boot preflight (exit 1) or in `run_forever` (`REFUSING TO START`, `BudgetExceeded` raised) -> scripts/boot_polymath.sh:60-67; control/control/process_supervisor.py:684-694.
6. Slot `QUARANTINED` (CRITICAL log) -> more than `max_restarts=5` exits inside `window_s=300.0` (crash loop, readiness failures, or control-heartbeat restarts) -> control/control/process_supervisor.py:391-394,476-479,644-648,396-408.
7. Silent wedge: fence-quarantined worker keeps heartbeating while refusing every claim — looks alive to every check, never exits -> autoheal detects pid-quarantined registration, hands leases back ready (no retry consumed), respawns onto current code -> control/control/process_supervisor.py:543-589,221-244.
8. Restart storms on busy sidecars: readiness probe queues behind real inference (embedder ~0.3s idle vs ~7s loaded) -> mitigated by `probe_timeout_s=60.0`, 120s cadence, 5 strikes -> control/control/process_supervisor.py:280-287.
9. Silent fallback: autopilot observe exception -> `log.warning("autopilot observe failed (keeping fleet)")`, fleet unchanged -> control/control/process_supervisor.py:647-649.
10. Silent fallbacks that swallow errors so the loop never dies: `_release_leases_of_pid` returns 0 on exception; quarantine DB record failure only logs; readiness probes `except Exception: pass`; non-JSON 200 body counted ready; `_write_state` pass -> control/control/process_supervisor.py:243-244,407-408,563-566,590-591,598-601,675-679.
11. Stale secrets: children inherit env at spawn; a rotated `.env` key was invisible until respawn — every spawn/respawn re-overlays `.env` -> control/control/process_supervisor.py:357-364.
12. `docker compose up ... || true` -> store startup failure ignored; the psycopg wait then spins 60 × 2s before bundle checks -> scripts/boot_polymath.sh:18-24.

## invariants
- INVARIANT: one bounce at a time — the lock is a directory, rmdir'd on EXIT, leftovers older than 10 minutes removed — scripts/bounce_fleet.sh:11-21 [DERIVED]
- INVARIANT: bounce always boots from the fleet checkout (`POLYMATH_FLEET_ROOT`), never from the worktree the script was copied into — scripts/bounce_fleet.sh:4,7 [DERIVED]
- INVARIANT: `.env` is the ONLY execution contract; boot exports it and every spawn/respawn re-overlays it onto children — scripts/boot_polymath.sh:8-15; control/control/process_supervisor.py:357-364 [DERIVED]
- INVARIANT: health = fresh registration heartbeat after spawn (or HTTP 200 with body `ready` not false), never mere process existence — control/control/process_supervisor.py:410-450 [DERIVED]
- INVARIANT: more than `max_restarts=5` exits inside `window_s=300.0` quarantines the slot and records it in `worker_registrations` — control/control/process_supervisor.py:279-287,391-394,399-405 [DERIVED]
- INVARIANT: a supervisor-initiated stop returns the worker's leases to `ready` without consuming an attempt — control/control/process_supervisor.py:221-239 [DERIVED]
- INVARIANT: READY requires `'"ready":true'` AND 26 healthy AND 13 types AND exactly 1 distinct `left(execution_bundle_hash,12)` — the whole fleet on ONE bundle — scripts/bounce_fleet.sh:44-54 [DERIVED]
- INVARIANT: parking terminates the process — exit is the only reliable way to return MPS/Metal memory — control/control/process_supervisor.py:632-635 [DERIVED]
- INVARIANT: service probes run on a slow cadence because they are real forward passes; the control probe is one cheap SQL read on a 30s cadence — control/control/process_supervisor.py:523-535 [DERIVED]

## VERIFY
```verify
grep -Fq 'bounce.lock' scripts/bounce_fleet.sh
grep -Fq 'execution_bundle_hash' scripts/bounce_fleet.sh
grep -Fq 'bundle_integrity.py --strict' scripts/boot_polymath.sh
grep -Fq 'POLYMATH_AUTOPILOT' scripts/boot_polymath.sh
grep -Fq 'readiness_failures_before_restart": 3' control/control/process_supervisor.py
grep -Fq 'POLYMATH_DOC_PARENT_MAP_LANE_OFFSET' control/control/process_supervisor.py
test "$(grep -c -F 'doc_parent_map' control/control/process_supervisor.py)" -ge 8
```

# flow: fleet-boot
How the system starts and restarts: scripts/bounce_fleet.sh, scripts/boot_polymath.sh, the process supervisor, the sidecars, the bundle fence, readiness.

Chain: owner click → `bounce_fleet.sh` (stop old fleet, single-run lock) → `boot_polymath.sh` (stores, bundle fence, budget preflight) → `control.process_supervisor` (spawns+supervises every slot) → bounce polls `/ready` + DB until READY. Exit codes of the bounce: `0` READY · `1` old fleet would not stop · `2` not ready within 6 minutes · `3` another bounce is already running (scripts/bounce_fleet.sh:5 [DERIVED]).

## hops

| # | what happens | where (anchor) | data in -> data out | can fail how |
|---|---|---|---|---|
| 1 | Owner runs bounce; `ROOT="${POLYMATH_FLEET_ROOT:-/Users/king/Documents/polymath-rebuild/polymath-v4}"`; `cd "$ROOT"` fails → exit 1. Always boots the fleet checkout, never the worktree the script was copied into | scripts/bounce_fleet.sh:7-10 [DERIVED] | env `POLYMATH_FLEET_ROOT` -> cwd | bad ROOT → "fleet checkout not found", exit 1 |
| 2 | Resolve durable `FLEET_LOG_DIR` by sourcing `.env`: `POLYMATH_FLEET_LOG_DIR` > `POLYMATH_FLEET_DIR` > `~/PolymathRuntime/logs/fleet`; `mkdir -p`. `/private/tmp/polymath_fleet` is deliberately NOT pre-created (a real dir would stop the supervisor's link) | scripts/bounce_fleet.sh:11-17 [DERIVED] | `.env` -> `FLEET_LOG_DIR` path | unset env silently falls to default (intended) |
| 3 | Single-bounce lock: `LOCK="$FLEET_LOG_DIR/bounce.lock"`; a lock dir older than 10 min is `rmdir`'d (leftover from a killed run); `mkdir` fails → print "A restart is already running", exit 3; `trap 'rmdir ...' EXIT` | scripts/bounce_fleet.sh:18-27 [DERIVED] | none -> lock dir | second click while one runs → exit 3 instead of a second fleet |
| 4 | `count()` = ps matching `control\.process_supervisor\|workers.\|uvicorn orchestrator`; `listeners()` = lsof LISTEN on ports 7200, 8742, 8743, 8930 | scripts/bounce_fleet.sh:28-29 [DERIVED] | ps/lsof -> two integers | grep patterns are the definition of "fleet alive" |
| 5 | TERM the supervisor: `pgrep -f "control\.process_supervisor" \| xargs kill -TERM`; wait ≤ 90 × `sleep 2` (180 s) for 0 processes AND 0 listeners | scripts/bounce_fleet.sh:31-36 [DERIVED] | pgrep -> SIGTERM | children that ignore TERM hold listeners |
| 6 | Still alive → "ABORT: still alive", dump ps + lsof, exit 1 | scripts/bounce_fleet.sh:37-43 [DERIVED] | ps/lsof -> stdout | exit 1 = old fleet would not stop |
| 7 | `nohup bash scripts/boot_polymath.sh > "$FLEET_LOG_DIR/boot.log" 2>&1 &` + `disown`; bounce sources `.env` itself | scripts/bounce_fleet.sh:44-46 [DERIVED] | none -> boot.log | boot output visible only in boot.log |
| 8 | boot: `cd "$(dirname "$0")/.."`; `export POLYMATH_PG_DSN` default `postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath`; `set -a; . ./.env; set +a` — "`.env` is the ONLY execution contract", no knob defaults beyond it | scripts/boot_polymath.sh:5-15 [DERIVED] | `.env` -> exported fleet env | a manual start without `.env` pins a different contract |
| 9 | `docker compose up -d postgres redis qdrant neo4j \|\|/ true`; poll psycopg connect ≤ 60 × 2 s | scripts/boot_polymath.sh:18-23 [DERIVED] | docker -> reachable Postgres | compose failure swallowed (`2>/dev/null \||\| true`), only the connect loop waits |
| 10 | Bundle fence: `.venv/bin/python shared/polymath_shared/bundle_integrity.py --strict`; failure → "FATAL — semantic runtime integrity violated", "refusing to start", exit 1; deliberate change re-freezes with `--freeze` | scripts/boot_polymath.sh:38-51 [DERIVED] | declared semantic contract vs runtime -> pass/exit 1 | runtime surface drift blocks boot until fixed or re-frozen |
| 11 | Unless `POLYMATH_AUTOPILOT=1` (per-tick budget gating, static preflight skipped): run `polymath_shared.runtime_budget.preflight()`; prints "committed_gb GB committed of ceiling_gb GB ceiling"; failure → exit 1 | scripts/boot_polymath.sh:57-67 [DERIVED] | config/runtime_budget.yaml -> committed/ceiling print | over-committed working set refuses to start |
| 12 | `mkdir -p` fleet log dir; `exec .venv/bin/python -m control.process_supervisor` — everything else lives under ONE supervisor | scripts/boot_polymath.sh:69-76 [DERIVED] | none -> supervisor process (replaces boot shell) | supervisor exit = fleet exit |
| 13 | Supervisor init `_fleet_filter`: `POLYMATH_FLEET_ONLY` allowlist; else `POLYMATH_PROFILE` → `profile_slots(prof)`; unknown slot names → `ValueError` | control/control/process_supervisor.py:380-401 [DERIVED] | env -> slot subset | misnamed slot aborts the supervisor |
| 14 | Slots built from `FLEET`: argv slots with `health_url` — `sidecar_embedder` :8742, `sidecar_reranker` :8743, `orchestrator` :7200 (`readiness_interval_s: 20.0`, `readiness_failures_before_restart: 3`), `mcp` :8930 — plus module tuples (control, intake, profile, extract/extract2/extract3, canonicalize, project_canonical, neo4j, qdrant, verify, compile_objects, summaries/summaries2, doc_profile1-6, doc_parent_map1-6, adapter_step) | control/control/process_supervisor.py:40-140, 417-427 [DERIVED] | FLEET list -> `Slot` objects | retired slots (gliner/spacy sidecars, local_extractor) only exist as comments |
| 15 | Durable log dirs `resolve_fleet_dirs`: explicit `log_dir` > `POLYMATH_FLEET_LOG_DIR` > `POLYMATH_FLEET_DIR` > `~/PolymathRuntime/logs/fleet`; run dir = `POLYMATH_FLEET_DIR` else `/private/tmp/polymath_fleet`; mkdir failure → slot logs fall back to the run dir (receipted `mode: "fallback"`) | control/control/process_supervisor.py:187-206, 429-444 [DERIVED] | env -> `(log_dir, run_dir)` | silent fallback to /tmp if durable dir unusable |
| 16 | `link_run_dir`: keep `/private/tmp/polymath_fleet` resolving to the log dir — modes `created_link\|linked\|relinked\|per_entry\|blocked\|error`, atomic `os.replace`, never deletes; `per_entry` → `link_run_entry` adopts/links the state file and each slot log (outcomes `linked\|created\|adopted\|kept_aside\|relinked\|blocked\|error:<type>`) | control/control/process_supervisor.py:209-249, 252-284, 445-451 [DERIVED] | run_dir+log_dir -> symlink + receipt dict | `blocked`/`error` only warned (log.warning), boot continues |
| 17 | Autopilot init: `POLYMATH_AUTOPILOT == "1"` → every slot except `control`, `orchestrator`, `intake` starts `parked`; tick calls `_autopilot_reconcile()` | control/control/process_supervisor.py:479-486, 605-607 [DERIVED] | env -> parked flags | parked slots spawn nothing until demand |
| 18 | `tick()`: spawn slots with `proc is None`. `_spawn`: append-open `<slot>.log`; argv `{python}` → `repo/.venv/bin/python`; `child_env = os.environ.copy()` + `_dotenv_overlay(.env)` (ENV-OVERLAY-ON-SPAWN-V1) + `export_env(slot.name)` memory caps; `extract` → `POLYMATH_EXTRACT_AFFINITY=local`, `extractN` → `cloud` (setdefault); `lane_offset_env` slot index; `Popen(..., start_new_session=True)` | control/control/process_supervisor.py:488-541, 608-613 [DERIVED] | slot spec -> child process + slot log | `export_env` failure → warning "no runtime budget for slot %s; starting uncapped" |
| 19 | Live slot → `_check_readiness` on cadence: control 30.0 s, else per-slot `readiness_interval_s` or 120.0 s. Rationale: probe is a real forward pass; alive-but-wedged answered liveness for 16 h (HANG-DEATH P0-B) | control/control/process_supervisor.py:460-461, 616-622, 673-688 [DERIVED] | probe -> wedged verdict | probe hangs bounded by `probe_timeout_s=60.0` |
| 20 | control slot → `_check_control_heartbeat`: `SELECT EXTRACT(EPOCH FROM now() - MAX(last_seen_at)) FROM control_owners`; `control_heartbeat_stale` = no successful tick for `control_stall_threshold_s` (default 180, settings `control.stall_threshold_s`) after boot grace → terminate (kill fallback) + respawn under the same restart budget | control/control/process_supervisor.py:331-344, 461-467, 638-671 [DERIVED] | control_owners -> control restart | DB probe failure swallowed (`return`) — never kills the loop |
| 21 | Exited slot: record exit code + timestamp; `_restart_allowed` = exits within `window_s=300.0` ≤ `max_restarts=5`; sleep `backoff_s * len(slot.exits)`; respawn; over budget → `_quarantine` (log CRITICAL + `UPDATE worker_registrations SET status='quarantined'`) | control/control/process_supervisor.py:624-634, 543-546, 548-560 [DERIVED] | exit code -> respawn/quarantine | crash-looping slot stops being restarted (defect surfaced, not hammered) |
| 22 | `verify_health`: `health_url` → HTTP 200 AND JSON body `ready` is not `False`; control → `poll() is None`; worker → `MAX(heartbeat_at) >= slot.started_at` (fresh registration after spawn) | control/control/process_supervisor.py:562-602 [DERIVED] | child -> healthy bool | 200-with-`{"ready": false}` correctly fails |
| 23 | Bounce polls 72 × `sleep 5` (360 s): `curl -s -m 3 127.0.0.1:7200/ready` must contain `"ready":true` AND psycopg over `worker_registrations` (`heartbeat_at > now()-interval '60 seconds'`, `status='healthy'`) must return `EXPECT_WORKERS`=26, `EXPECT_TYPES`=13 distinct types, 1 distinct `left(execution_bundle_hash,12)` → "READY", exit 0 | scripts/bounce_fleet.sh:8-9, 47-61 [DERIVED] | /ready + SQL counts -> exit 0 | any gate unmet keeps looping |
| 24 | Timeout → "NOT READY after 360s: ready=$r \| healthy/types/bundles=$s"; `tail -25 boot.log`; exit 2 | scripts/bounce_fleet.sh:62-64 [DERIVED] | boot.log -> stdout | exit 2 = not ready within 6 minutes |

## state written

- `FLEET_LOG_DIR/bounce.lock` — lock dir, removed by EXIT trap; stale >10 min auto-`rmdir`'d. scripts/bounce_fleet.sh:19-27 [DERIVED]
- `FLEET_LOG_DIR/boot.log` — boot script stdout/stderr. scripts/bounce_fleet.sh:44 [DERIVED]
- `<slot>.log` per slot, opened append-binary at each spawn; `per_entry` mode first links/adopts the old-path log. control/control/process_supervisor.py:489-494, 252-284 [DERIVED]
- `supervisor_state.json` (`STATE_FILE`) in the log dir, written by `_write_state()` each tick. control/control/process_supervisor.py:168, 445, 635 [DERIVED]
- `/private/tmp/polymath_fleet` symlink → durable log dir (atomic `os.replace`); per-entry links inside a legacy real dir. control/control/process_supervisor.py:226-231, 239-241 [DERIVED]
- Link receipts: `self.log_compat` dict (`mode`, `previous`, `error`, per-entry `state` outcome) logged at init. control/control/process_supervisor.py:218-247, 441-451 [DERIVED]
- Postgres `worker_registrations.status='quarantined'` + `last_error` on quarantine. control/control/process_supervisor.py:552-557 [DERIVED]
- Postgres `stage_tickets`: `_release_leases_of_pid` sets `status='ready'`, `lease_owner=NULL`, `lease_expires_at=NULL` when the supervisor itself stops a worker — no attempt consumed. control/control/process_supervisor.py:347-370 [DERIVED]
- Docker containers `postgres redis qdrant neo4j` via `docker compose up -d`. scripts/boot_polymath.sh:18 [DERIVED]

## flags that change this flow

| flag | default | effect | read at |
|---|---|---|---|
| `POLYMATH_FLEET_ROOT` | `/Users/king/Documents/polymath-rebuild/polymath-v4` | fleet checkout the bounce boots from | scripts/bounce_fleet.sh:7 [DERIVED] |
| `POLYMATH_EXPECT_WORKERS` | `26` | READY gate: healthy worker count | scripts/bounce_fleet.sh:8, 57 [DERIVED] |
| `POLYMATH_EXPECT_TYPES` | `13` | READY gate: distinct `worker_type` count | scripts/bounce_fleet.sh:9, 57 [DERIVED] |
| `POLYMATH_PG_DSN` | `postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath` | Postgres DSN for boot, supervisor, bounce poll | scripts/boot_polymath.sh:6; control/control/process_supervisor.py:471-474; scripts/bounce_fleet.sh:46,53 [DERIVED] |
| `.env` file | — | "the ONLY execution contract"; sourced by boot and overlaid on every child spawn | scripts/boot_polymath.sh:15; control/control/process_supervisor.py:508-516 [DERIVED] |
| `POLYMATH_PROFILE` | unset | echoes profile at boot; selects slot subset via `profile_slots` when no `POLYMATH_FLEET_ONLY` | scripts/boot_polymath.sh:35-37; control/control/process_supervisor.py:382-386 [DERIVED] |
| `POLYMATH_AUTOPILOT` | unset (`"1"` enables) | `"1"` skips the static budget preflight; supervisor parks all slots except control/orchestrator/intake | scripts/boot_polymath.sh:57-59; control/control/process_supervisor.py:479-486 [DERIVED] |
| `POLYMATH_FLEET_ONLY` | `""` | slot allowlist; unknown names raise `ValueError` | control/control/process_supervisor.py:381, 396-401 [DERIVED] |
| `POLYMATH_FLEET_LOG_DIR` | unset → `~/PolymathRuntime/logs/fleet` | durable slot-log/state dir (bounce and supervisor resolve identically) | scripts/bounce_fleet.sh:15-16; control/control/process_supervisor.py:191-203, 171-173 [DERIVED] |
| `POLYMATH_FLEET_DIR` | unset | second instance's own dir; else the legacy run-dir path readers know | control/control/process_supervisor.py:191-203 [DERIVED] |
| `POLYMATH_EXTRACT_AFFINITY` | set per slot: `extract`→`local`, `extractN`→`cloud` (setdefault; both steal the other lane when dry) | lane affinity of extract slots | control/control/process_supervisor.py:523-530 [DERIVED] |
| `POLYMATH_DOC_PROFILE_LANE_OFFSET` / `POLYMATH_DOC_PARENT_MAP_LANE_OFFSET` | slot 1-based index (`"1"`, `"2"`, …) via setdefault | owning slot calls its own account's lanes; without it, run-hash rotation | control/control/process_supervisor.py:143-158, 531-535 [DERIVED] |
| `POLYMATH_DOC_PARENT_MAP_ENABLED` | off | flag off ⇒ no `doc_parent_map.v1` events, the slot simply parks (per FLEET comment; reader is outside SOURCE) | control/control/process_supervisor.py:110-113 [DERIVED] |
| settings `control.stall_threshold_s` | `180` | control-heartbeat staleness threshold (owner law: 3 min) | control/control/process_supervisor.py:461-467 [DERIVED] |

## failure modes

1. Bounce exits 3, "A restart is already running" → a live bounce holds `bounce.lock` (only locks >10 min old are auto-removed) → scripts/bounce_fleet.sh:20-26.
2. Bounce exits 1, "ABORT: still alive" → TERM'd fleet still has processes/listeners after ~180 s; SIGTERM limbo measured on uvicorn orchestrator (alive with port closed for minutes, a 10-minute outage under the old 5×120 s policy) → scripts/bounce_fleet.sh:37-43; control/control/process_supervisor.py:62-68.
3. Bounce exits 2, "NOT READY after 360s" → `/ready` or the 26/13/1 DB gate unmet for 72×5 s; `tail -25 boot.log` is the evidence → scripts/bounce_fleet.sh:47-64.
4. Boot exits 1, "semantic runtime integrity violated" → `bundle_integrity.py --strict` failed (contract drift, or admission boundaries with no production caller); fix the invariant or re-freeze deliberately with `--freeze` → scripts/boot_polymath.sh:38-51.
5. Boot exits 1 at budget preflight → static preflight refuses an over-committed working set rather than thrashing (skipped when `POLYMATH_AUTOPILOT=1`) → scripts/boot_polymath.sh:60-67.
6. Silent log fallback → durable log dir `mkdir` fails → slot logs land in the run dir (`/private/tmp/polymath_fleet`); only a `log.error` and `log_compat` mode `"fallback"` record it → control/control/process_supervisor.py:434-444.
7. Silent uncapped spawn → `export_env(slot.name)` raises → warning "no runtime budget for slot %s; starting uncapped"; child runs without memory caps (the embedder once held 41.58 GiB of Metal pool uncapped) → control/control/process_supervisor.py:504-522.
8. Slot quarantined, work stops → >`max_restarts=5` exits within `window_s=300.0` (or control-heartbeat restarts over budget) → CRITICAL log + `worker_registrations.status='quarantined'`; supervisor stops restarting → control/control/process_supervisor.py:543-560, 628-631, 656-660.
9. Alive-but-wedged sidecar/orchestrator → readiness probe is a real forward pass; needs consecutive failures before restart (default 5 at 120 s; orchestrator 3 at 20 s); probe timeout 60 s. Single slow response under load must not restart (a 10 s/3-strike policy restarted healthy-but-loaded sidecars 11 times) → control/control/process_supervisor.py:57-68, 406-415, 673-687.
10. Control alive but not ticking → `control_owners.last_seen_at` older than 180 s after grace (record_heartbeat runs only on tick_ok; measured 1,864 consecutive failed ticks) → terminate/kill + respawn → control/control/process_supervisor.py:331-344, 638-671.
11. Quarantine invisible to liveness → a fence-quarantined worker keeps heartbeating while refusing every claim and never exits (WORKER-QUARANTINE-AUTOHEAL-V1; handling is in `_check_readiness` past the visible SOURCE) → control/control/process_supervisor.py:694-700.
12. Rotated key invisible to children → children used to inherit the supervisor's boot snapshot (measured: openrouter lanes 401'd on a replaced key and struck a document); every spawn now overlays current `.env` → control/control/process_supervisor.py:508-516.
13. Live logs unlinked under /tmp → macOS periodic cleaner deleted 26 live worker logs (2026-11-01, lsof link count 0); durable dir + `link_run_dir`/`link_run_entry` (adopt or keep aside, never delete) are the mitigation → control/control/process_supervisor.py:161-164, 252-257.

## invariants

- INVARIANT: one bounce at a time — a second click finds `bounce.lock` and exits 3 rather than booting a second fleet. scripts/bounce_fleet.sh:18-27 [DERIVED]
- INVARIANT: the bounce always boots from the fleet checkout (`POLYMATH_FLEET_ROOT`), never from the worktree the script was copied into. scripts/bounce_fleet.sh:3-7 [DERIVED]
- INVARIANT: READY means `"ready":true` from `127.0.0.1:7200/ready` AND `EXPECT_WORKERS` AND `EXPECT_TYPES` AND exactly 1 distinct `left(execution_bundle_hash,12)`, over healthy registrations heartbeating within 60 s. scripts/bounce_fleet.sh:50-60 [DERIVED]
- INVARIANT: `.env` is the ONLY execution contract; boot adds no knob defaults beyond it. scripts/boot_polymath.sh:7-15 [DERIVED]
- INVARIANT: boot refuses to start a runtime whose semantic surface differs from the declared contract (`bundle_integrity.py --strict`); re-freeze only deliberately with `--freeze`. scripts/boot_polymath.sh:38-51 [DERIVED]
- INVARIANT: every long-lived runtime component (sidecars, orchestrator, MCP, control, workers) lives under ONE supervisor with bounded restart + quarantine + health checks. scripts/boot_polymath.sh:69-70; control/control/process_supervisor.py:36-40 [DERIVED]
- INVARIANT: slot logs and the state file live in a durable dir; the legacy `/private/tmp/polymath_fleet` path keeps resolving to it at every boot; nothing is deleted. control/control/process_supervisor.py:161-164, 209-217 [DERIVED]
- INVARIANT: `/private/tmp/polymath_fleet` is not pre-created by the scripts — a real directory there would stop the supervisor's link. scripts/bounce_fleet.sh:11-14; scripts/boot_polymath.sh:71-74 [DERIVED]
- INVARIANT: a restarted slot is healthy only on proof — HTTP 200 with body `ready` not `false`, or a fresh DB heartbeat at/after `started_at`. control/control/process_supervisor.py:562-602 [DERIVED]
- INVARIANT: more than `max_restarts=5` exits inside `window_s=300.0` quarantines the slot — a tight crash loop is a defect to surface, not a process to hammer. control/control/process_supervisor.py:16-20, 543-546 [DERIVED]
- INVARIANT: every spawn/respawn overlays the current `.env` onto the child environment. control/control/process_supervisor.py:509-516 [DERIVED]
- INVARIANT: nothing sits stuck >3 min unnoticed — control liveness is a successful tick, judged stale after `control.stall_threshold_s` (default 180) with a boot grace. control/control/process_supervisor.py:331-344, 460-467 [DERIVED]
- INVARIANT: supervisor-stopped workers get their leases returned to `ready` without consuming an attempt. control/control/process_supervisor.py:347-365 [DERIVED]

## VERIFY

```verify
grep -Fq 'bounce.lock' scripts/bounce_fleet.sh
grep -Fq '127.0.0.1:7200/ready' scripts/bounce_fleet.sh
grep -Fq 'bundle_integrity.py --strict' scripts/boot_polymath.sh
grep -Fq 'exec .venv/bin/python -m control.process_supervisor' scripts/boot_polymath.sh
grep -Fq 'start_new_session=True' control/control/process_supervisor.py
grep -Fq 'supervisor_state.json' control/control/process_supervisor.py
test "$(grep -c -F 'doc_parent_map' control/control/process_supervisor.py)" -ge 8
grep -Eq 'POLYMATH_AUTOPILOT.*== "1"' control/control/process_supervisor.py
```

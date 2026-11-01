# unit: control/control/process_supervisor.py
anchor: control/control/process_supervisor.py:1-882

## purpose
CP2.1 — automatic worker recovery: `worker death -> detection -> lease handling -> bounded restart -> health verification -> capability re-registration` (control/control/process_supervisor.py:1-21) [DERIVED]. The supervisor is the fleet's process parent (control/control/process_supervisor.py:9) and supervises every long-lived runtime component — sidecars, orchestrator, MCP, control and workers (control/control/process_supervisor.py:36-39, 40-140) [DERIVED].

## public surface

| symbol | kind | signature (params -> return) | anchor | used by |
|---|---|---|---|---|
| lane_offset_env | def | (slot_name: str) -> dict[str, str] | control/control/process_supervisor.py:151-158 | — |
| default_fleet_log_dir | def | () -> Path | control/control/process_supervisor.py:171-173 | — |
| resolve_fleet_dirs | def | (log_dir: str \| None, run_dir: str \| None, env=None) -> tuple[Path, Path \| None] | control/control/process_supervisor.py:187-206 | — |
| link_run_dir | def | (run_dir: Path, log_dir: Path) -> dict | control/control/process_supervisor.py:209-249 | — |
| link_run_entry | def | (run_dir: Path, log_dir: Path, name: str) -> str | control/control/process_supervisor.py:252-284 | — |
| Slot | dataclass | 16 fields incl. name, module, argv, health_url, exits, quarantined | control/control/process_supervisor.py:288-304 | — |
| control_heartbeat_stale | def | (heartbeat_age_s: float \| None, uptime_s: float, threshold_s: float) -> bool | control/control/process_supervisor.py:331-344 | — |
| Supervisor | class | `__init__(fleet=FLEET, *, python=None, log_dir=None, state_path=None, run_dir=None, max_restarts=5, window_s=300.0, probe_timeout_s=60.0, readiness_interval_s=120.0, readiness_failures_before_restart=5, backoff_s=2.0, health_timeout_s=30.0, dsn=None)` | control/control/process_supervisor.py:403-416, 373-864 | — |
| main | def | () -> None | control/control/process_supervisor.py:867-877 | — |

No FACTS.importers data. Downstream imports of this module's deps: `polymath_shared.runtime_budget.profile_slots` (control/control/process_supervisor.py:385), `.export_env` (control/control/process_supervisor.py:518), `polymath_shared.settings.get_settings` (control/control/process_supervisor.py:463); FACTS.imports also lists `control.fleet_autopilot.desired_slots`, `polymath_shared.logging.configure_logging`, `polymath_shared.runtime_budget.preflight` — their call sites lie in the untruncated tail control/control/process_supervisor.py:707-882 [INFERRED: beyond line 706 in FACTS].

## contracts

**lane_offset_env** (control/control/process_supervisor.py:151-158)
- in: any slot name string.
- out: `{env: suffix or "1"}` when the name is exactly a `LANE_OFFSET_ENV` stage or stage + digit suffix; `{}` otherwise (control/control/process_supervisor.py:154-158).
- post: keys can only be `POLYMATH_DOC_PROFILE_LANE_OFFSET` / `POLYMATH_DOC_PARENT_MAP_LANE_OFFSET` (control/control/process_supervisor.py:145-148).

**resolve_fleet_dirs** (control/control/process_supervisor.py:187-206)
- in: `env` mapping, defaults to `os.environ` (control/control/process_supervisor.py:195).
- out: log-dir precedence explicit `log_dir` > `POLYMATH_FLEET_LOG_DIR` > `POLYMATH_FLEET_DIR` > `default_fleet_log_dir()` (control/control/process_supervisor.py:191-192, 201-202); run dir = `POLYMATH_FLEET_DIR` else `/private/tmp/polymath_fleet` (control/control/process_supervisor.py:192-193, 203).
- post: run is `None` when `_same_path(run, log_path)` (control/control/process_supervisor.py:203-205); explicit `log_dir` without `run_dir` -> run `None` (control/control/process_supervisor.py:198-199).

**link_run_dir** (control/control/process_supervisor.py:209-249)
- out: receipt dict with `mode` in {`created_link`, `linked`, `relinked`, `per_entry`, `blocked`, `error`}; `relinked` adds `previous` (control/control/process_supervisor.py:210-216, 224-225); `error` can be `"raced"` after 2 attempts (control/control/process_supervisor.py:219, 247-248).
- post: never deletes anything (control/control/process_supervisor.py:217); symlink swap is atomic via `os.replace(tmp, run_dir)` (control/control/process_supervisor.py:229-230).

**link_run_entry** (control/control/process_supervisor.py:252-284)
- out: exactly one of `linked | created | adopted | kept_aside | relinked | blocked | error:<type>` (control/control/process_supervisor.py:256-257).
- post: a legacy regular file is `os.rename`d into the durable dir when absent there (`adopted`), else kept as `<name>.pre-durable-<epoch>` (control/control/process_supervisor.py:268-276).

**control_heartbeat_stale** (control/control/process_supervisor.py:331-344)
- post: returns False while `uptime_s < threshold_s` (boot grace) (control/control/process_supervisor.py:342-343); stale iff `heartbeat_age_s is None or heartbeat_age_s > threshold_s` (control/control/process_supervisor.py:344).

**Supervisor.\_\_init\_\_** (control/control/process_supervisor.py:403-486)
- pre: `POLYMATH_FLEET_ONLY`/`POLYMATH_PROFILE` names must exist in the fleet, else `ValueError` (control/control/process_supervisor.py:396-400).
- post: slot logs + state live in the durable dir; old run dir linked, receipt in `self.log_compat` (control/control/process_supervisor.py:429-451); `state_path` defaults to `log_dir/supervisor_state.json` (control/control/process_supervisor.py:445); with `POLYMATH_AUTOPILOT=="1"` every slot except `control`, `orchestrator`, `intake` starts `parked = True` (control/control/process_supervisor.py:479-485).

**Supervisor.verify_health** (control/control/process_supervisor.py:562-602)
- post (health_url slot): True iff `r.status_code == 200` and `body.get("ready") is not False` (control/control/process_supervisor.py:574-580); post (control slot): True iff `slot.proc.poll() is None` (control/control/process_supervisor.py:585-586); post (worker slot): True iff `MAX(EXTRACT(EPOCH FROM heartbeat_at)) >= slot.started_at` (control/control/process_supervisor.py:593-597).

**Supervisor.tick** (control/control/process_supervisor.py:605-636)
- out: returns `self.state()` (control/control/process_supervisor.py:636).
- post: spawns unspawned non-quarantined/non-parked slots (control/control/process_supervisor.py:608-612); exited slot -> append exit timestamp, restart after `time.sleep(self.backoff_s * len(slot.exits))` or quarantine when budget exhausted (control/control/process_supervisor.py:624-634); state written every tick (control/control/process_supervisor.py:635).

## effect surface
- Postgres (dsn = `POLYMATH_PG_DSN` or `'postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath'`, control/control/process_supervisor.py:470-473):
  - read: `worker_registrations` heartbeat (control/control/process_supervisor.py:593-595), joined by pid (control/control/process_supervisor.py:361-363); `control_owners` `MAX(last_seen_at)` (control/control/process_supervisor.py:645-647).
  - write: `stage_tickets` -> `status='ready', lease_owner=NULL, lease_expires_at=NULL` (control/control/process_supervisor.py:358-361); `worker_registrations` -> `status='quarantined'` where `worker_type=%s AND status <> 'quarantined'` (control/control/process_supervisor.py:554-556).
- Qdrant: none. FACTS `collections` entry `polymath_fleet` (control/control/process_supervisor.py:165) is `LEGACY_FLEET_DIR = Path("/private/tmp/polymath_fleet")`, a filesystem dir, not a vector store [DERIVED].
- Files: append `<log_dir>/<slot>.log` (control/control/process_supervisor.py:494); state file `supervisor_state.json` (control/control/process_supervisor.py:168, 445); repo-root `.env` read (control/control/process_supervisor.py:515-516); durable default `~/PolymathRuntime/logs/fleet` (control/control/process_supervisor.py:171-173).
- Network: `httpx.get` health probes (control/control/process_supervisor.py:571; second site control/control/process_supervisor.py:748 per FACTS) against `http://127.0.0.1:8742/ready` (control/control/process_supervisor.py:56), `http://127.0.0.1:8743/ready` (control/control/process_supervisor.py:60), `http://127.0.0.1:7200/health` (control/control/process_supervisor.py:68), `http://127.0.0.1:8930/health` (control/control/process_supervisor.py:75).
- Subprocess: `subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, env=child_env, start_new_session=True)` (control/control/process_supervisor.py:536-539); argv slots substitute `{python}` with `repo/.venv/bin/python` (control/control/process_supervisor.py:496-498).
- Env read (name = default): `POLYMATH_PG_DSN` = `'postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath'` (control/control/process_supervisor.py:471-473); `POLYMATH_FLEET_ONLY` = `''` (control/control/process_supervisor.py:381); `POLYMATH_PROFILE` = `''` (control/control/process_supervisor.py:383); `POLYMATH_AUTOPILOT` = `''`, enabled by `== "1"` (control/control/process_supervisor.py:479); `POLYMATH_FLEET_DIR` (control/control/process_supervisor.py:196); `POLYMATH_FLEET_LOG_DIR` (control/control/process_supervisor.py:201).
- Env written into children (setdefault): `POLYMATH_EXTRACT_AFFINITY` = `"local"` for slot `extract`, `"cloud"` for `extract*` (control/control/process_supervisor.py:526-529); lane-offset vars (control/control/process_supervisor.py:534-535); all `.env` keys (control/control/process_supervisor.py:514-516); runtime-budget `export_env(slot.name)` caps (control/control/process_supervisor.py:517-519).

## invariants
INVARIANT: default restart budget = `max_restarts: int = 5` within `window_s: float = 300.0` — control/control/process_supervisor.py:406 [DERIVED]
  fails-if: a 6th exit inside 5 minutes quarantines the slot instead of restarting it.
INVARIANT: restart allowed ⟺ `len(slot.exits) <= self.max_restarts` after window filter — control/control/process_supervisor.py:544-546 [DERIVED]
  fails-if: budget off-by-one restarts a tight death loop forever or quarantines a healthy flapper.
INVARIANT: backoff sleep = `backoff_s * len(slot.exits)` with `backoff_s: float = 2.0` — control/control/process_supervisor.py:632, 414 [DERIVED]
  fails-if: rapid flapping respawns instantly, hammering the defect the quarantine law exists to surface.
INVARIANT: worker healthy ⟺ `float(row[0]) >= slot.started_at` for max heartbeat epoch — control/control/process_supervisor.py:596-597 [DERIVED]
  fails-if: stale pre-crash registration counts as recovery; work never resumes.
INVARIANT: sidecar healthy ⟺ `status_code == 200` AND `body.get("ready") is not False` — control/control/process_supervisor.py:574-580 [DERIVED]
  fails-if: a 200-answering-but-wedged sidecar passes and stalls the corpus (the exact wedge this gate exists for).
INVARIANT: control stale ⟺ `uptime_s >= threshold_s` AND (`heartbeat_age_s is None` OR `> threshold_s`) — control/control/process_supervisor.py:342-344 [DERIVED]
  fails-if: boot grace skipped -> control killed before it can take the lease; or a wedged-but-alive control never restarted.
INVARIANT: control stall threshold default 180 s in both the getattr default and the except fallback — control/control/process_supervisor.py:464-467 [DERIVED]
  fails-if: divergence breaks the owner law "nothing may sit stuck > 3 min unnoticed" (control/control/process_supervisor.py:333-334).
INVARIANT: log-dir precedence explicit > `POLYMATH_FLEET_LOG_DIR` > `POLYMATH_FLEET_DIR` > `~/PolymathRuntime/logs/fleet` — control/control/process_supervisor.py:191-192, 201-202 [DERIVED]
  fails-if: a second supervisor instance's dir silently wins and slot logs split across dirs.
INVARIANT: `link_run_dir`/`link_run_entry` delete nothing — control/control/process_supervisor.py:217, 256 [DERIVED]
  fails-if: old-path readers (Metal lease, rerank wake, stall tracer, conformance) lose their files.
INVARIANT: autopilot parks every slot whose name is not in {"control", "orchestrator", "intake"} — control/control/process_supervisor.py:482-485 [DERIVED]
  fails-if: a renamed always-on slot gets parked and the pipeline stalls at intake.

## determinism & idempotency
determinism: NONDETERMINISTIC — `time.time` (control/control/process_supervisor.py:276, 540, 544, 568-569, 588-589, 625, 683, 788), `httpx.get` (control/control/process_supervisor.py:571, 748), `subprocess.Popen` (control/control/process_supervisor.py:536), psycopg DB reads (control/control/process_supervisor.py:593-595, 645-647), `os.environ` (control/control/process_supervisor.py:381, 383, 471, 479), filesystem race handled by a 2-attempt loop (control/control/process_supervisor.py:219).
idempotency: UNSAFE — `tick`/`_spawn` create processes and append exits (control/control/process_supervisor.py:536, 624); only the dir-linking helpers are re-run safe with receipted outcomes and no deletions (control/control/process_supervisor.py:210-217).

## failure behaviour
- `_release_leases_of_pid`: `except Exception: return 0` — "never block a stop on bookkeeping" (control/control/process_supervisor.py:368-370); caller sees 0 leases handed back, and the expiry sweep later charges attempt+1.
- `__init__` settings load failure -> `control_stall_threshold_s = 180.0` (control/control/process_supervisor.py:463-467).
- `__init__` log dir unusable: falls back to the run dir, logs an error, `log_compat = {"mode": "fallback", ...}`; raises only when `run_dir is None` (control/control/process_supervisor.py:434-444).
- `_spawn` without runtime budget: warning `no runtime budget for slot %s; starting uncapped`, child starts uncapped (control/control/process_supervisor.py:517-522).
- `_quarantine` DB write failure: `log.exception("could not record quarantine in DB")`; in-memory `quarantined = True` already set (control/control/process_supervisor.py:548-560).
- `verify_health`: HTTP and DB errors swallowed (`pass`), retried every 1.0 s until `health_timeout_s`, then returns False (control/control/process_supervisor.py:566-585, 588-601); JSON parse failure -> `body = {}` -> passes the ready gate (control/control/process_supervisor.py:576-580).
- `_check_control_heartbeat`: probe failure -> `return`; "the probe must never kill the loop" (control/control/process_supervisor.py:648-650); restart path terminate -> `wait(timeout=15)` -> kill, all swallowed (control/control/process_supervisor.py:662-669).
- Only explicit raise: `ValueError(f"POLYMATH_FLEET_ONLY names unknown slots: {sorted(missing)}")` (control/control/process_supervisor.py:399-400).
- Tail handlers (FACTS, beyond line 706): handled/assign :752, :754; try :735, :773; swallowed pass :738, :742, :776, :834; swallowed log + return None :799; handled if+log :847 [DERIVED from FACTS.fallbacks].

## dumb-code flags
- Ready gate only fails on literal `"ready": false`; `{}` or non-JSON body counts healthy (control/control/process_supervisor.py:576-580).
- Orchestrator readiness overrides inline in FLEET (`readiness_interval_s: 20.0, readiness_failures_before_restart: 3`) vs class defaults `120.0` / `5` — two tuning sites (control/control/process_supervisor.py:68 vs 413-414).
- Stall threshold 180 written twice: getattr default `180` and except fallback `180.0` (control/control/process_supervisor.py:464-467).
- Magic retry count `range(2)` and error string `"raced"` in `link_run_dir` (control/control/process_supervisor.py:219, 247-248).
- Hardcoded poll sleep `time.sleep(1.0)` in both verify loops (control/control/process_supervisor.py:584, 601).
- Quarantine note truncated `[:200]` (control/control/process_supervisor.py:556).
- Lane affinity by string match: `slot.name == "extract"` vs `startswith("extract")` (control/control/process_supervisor.py:526-529).
- `{python}` placeholder and hardcoded `.venv/bin/python` relative to repo root (control/control/process_supervisor.py:496-498).
- Retired slots kept as comment blocks with rollback recipes (sidecar_gliner/spacy control/control/process_supervisor.py:42-45; local_extractor control/control/process_supervisor.py:49-53).

## refactor notes
- Slot names are protocol: `extract`/`extractN` drive affinity (control/control/process_supervisor.py:526-529); `doc_profileN`/`doc_parent_mapN` drive lane ownership against `config/llm_accounts.yaml` `slots.<stage>.owners`, with a test keeping registry and `LANE_OFFSET_ENV` equal (control/control/process_supervisor.py:127-130, 143-148); the autopilot exempt set is hardcoded (control/control/process_supervisor.py:484); `POLYMATH_FLEET_ONLY` validates against these names (control/control/process_supervisor.py:396-400). Renaming any slot breaks all four consumers.
- The legacy run dir `/private/tmp/polymath_fleet` is resolved by external readers (Metal lease, rerank wake, stall tracer, conformance) and must stay linked, never deleted (control/control/process_supervisor.py:192-194, 217).
- Health ports/URLs 8742/8743/7200/8930 are hardcoded in FLEET and probed externally (control/control/process_supervisor.py:56, 60, 68, 75).
- The `.env` overlay at spawn is the fix for MCP booting keyless under launchd (macOS TCC denies `~/Documents` to bash) — removing it re-opens a measured public-mirror exposure (control/control/process_supervisor.py:69-75, 509-516).
- `_autopilot_reconcile` (post-line-706) uses `control.fleet_autopilot.desired_slots` (FACTS.imports); parking semantics depend on it (control/control/process_supervisor.py:475-479) [INFERRED: call site in untruncated tail].
- File names `supervisor_state.json` and `<slot>.log` are the `link_run_entry` keys for per_entry adoption — renaming orphans old-path readers (control/control/process_supervisor.py:448-449, 491-494).
- Default DSN embeds dev credentials `polymath:polymath-dev@127.0.0.1:5432` (control/control/process_supervisor.py:471-473).

## VERIFY
```verify
grep -Fq 'max_restarts: int = 5, window_s: float = 300.0' control/control/process_supervisor.py
grep -Fq 'STATE_FILE = "supervisor_state.json"' control/control/process_supervisor.py
grep -Fq 'LEGACY_FLEET_DIR = Path("/private/tmp/polymath_fleet")' control/control/process_supervisor.py
grep -Eq 'def (lane_offset_env|control_heartbeat_stale|link_run_entry)\(' control/control/process_supervisor.py
grep -Fq 'start_new_session=True' control/control/process_supervisor.py
grep -Fq 'POLYMATH_AUTOPILOT' control/control/process_supervisor.py
test "$(grep -c -F 'httpx.get' control/control/process_supervisor.py)" -ge 2
```

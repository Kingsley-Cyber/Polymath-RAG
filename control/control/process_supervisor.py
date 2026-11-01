"""CP2.1 — automatic worker recovery (the missing half of supervision).

The control tick already MARKS: stale workers, revoked leases, quarantine on
lease expiry. What was missing is the lifecycle after death:

    worker death -> detection -> lease handling -> bounded restart
    -> health verification -> capability re-registration -> work resumes

Detection and restart live HERE, as the fleet's process parent. Lease
handling needs nothing new: a dead worker stops heartbeating, the control
tick marks it stale and returns its leases to READY; the restarted process
registers a fresh worker_id and re-advertises capability (including the
semantic bundle) through the existing `run_worker` registration path, so a
restarted-but-stale BINARY still cannot claim incompatible work.

Restart policy is bounded and observable: more than `max_restarts` exits
inside `window_s` quarantines the SLOT (supervisor stops restarting it,
logs CRITICAL, records it in the state file and in worker_registrations),
because a worker that dies in a tight loop is a defect to surface, not a
process to hammer.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("cp21")

# A slot is either a worker module (health = fresh DB registration heartbeat)
# or a service spec dict (health = HTTP 200 on health_url). PHASE A extends
# supervision to EVERY long-lived runtime component: sidecars and the
# orchestrator die and restart under the same bounded policy as workers.
FLEET: list = [
    # ---- neural sidecars ------
    # sidecar_gliner + sidecar_spacy REMOVED (owner directive 2026-08-30:
    # "never come up again") — GLiNER retired in llm_live, spaCy's slice
    # interpreter skipped in llm mode; their GPU residency cost the batched
    # 4B ~3x decode throughput. Rollback = revert this commit.
    # LLM-DIRECT-CANON (2026-09-03): the local extraction lane — the privacy
    # path for every document at or under the cloud floor — had run as a
    # hand-started process outside the supervisor and the budget for days.
    # FLEET-MEMORY-REBALANCE-V1 (owner, 2026-09-22): the local_extractor slot is RETIRED. Under CLOUD-FIRST-V1
    # (floor 0 B) it received no extraction request, yet held 2.76 GB and 11.5 GB of the budget; that memory now goes
    # to the reranker and embedder caps (config/runtime_budget.yaml). Rollback = restore this entry:
    #   {"name": "local_extractor", "argv": ["{python}", "sidecars/local_extractor/batched_server.py", "8755"],
    #    "cwd": ".", "health_url": "http://127.0.0.1:8755/ready"},
    {"name": "sidecar_embedder", "argv": ["{python}", "-m", "uvicorn",
        "server:app", "--host", "127.0.0.1", "--port", "8742"],
     "cwd": "sidecars/embedder", "health_url": "http://127.0.0.1:8742/ready"},
    {"name": "sidecar_reranker", "argv": ["{python}", "-m", "uvicorn",
        "server:app", "--host", "127.0.0.1", "--port", "8743",
        "--app-dir", "sidecars/reranker"],
     "cwd": ".", "health_url": "http://127.0.0.1:8743/ready"},
    # ---- orchestrator ----------------------------------------------------
    # ORCHESTRATOR-LIMBO-V1 (measured 2026-09-05): SIGTERM left uvicorn alive with
    # the port closed for minutes; the default 5 × 120 s readiness policy is a
    # 10-minute API outage. The API probe is one cheap GET — probe fast, restart fast.
    {"name": "orchestrator", "argv": ["{python}", "-m", "uvicorn",
        "orchestrator.main:app", "--host", "127.0.0.1", "--port", "7200"],
     "cwd": "orchestrator", "health_url": "http://127.0.0.1:7200/health",
     "readiness_interval_s": 20.0, "readiness_failures_before_restart": 3},
    # ---- MCP (POLYMATH-MCP-V2) -------------------------------------------
    # Supervised here, NOT by launchd: under launchd, bash is denied
    # ~/Documents (macOS TCC) so `. .env` fails and the server booted
    # keyless for two days (measured 2026-09-02: public mirror answered
    # tools/call to anyone). The supervisor's spawn overlays .env itself.
    {"name": "mcp", "argv": ["{python}", "-m", "orchestrator.mcp_server"],
     "cwd": "orchestrator", "health_url": "http://127.0.0.1:8930/health"},
    # ---- control + workers (health = fresh registration heartbeat) ------
    ("control", "control.main"),
    ("intake", "workers.intake_worker"),
    ("profile", "workers.profile_worker"),
    ("extract", "workers.extract_worker"),
    # Second extract slot: lanes run in parallel (cloud books are remote —
    # no GPU contention; local books queue at the one GPU window at the
    # sidecar). Measured 2026-08-30: a local book sat 'ready' ~1 min with
    # no claimer while the single slot held the cloud book.
    ("extract2", "workers.extract_worker"),
    # Third extract slot (MULTI-PROVIDER-AUTH-V1): a second cloud-affinity
    # worker so a multi-provider pool gets real cloud parallelism, not
    # just sharding. Costs one queue-poller when the pool is one deep.
    ("extract3", "workers.extract_worker"),
    ("canonicalize", "workers.canonicalize_worker"),
    ("project_canonical", "workers.project_canonical_worker"),
    ("neo4j", "workers.project_neo4j_worker"),
    ("qdrant", "workers.project_qdrant_worker"),
    ("verify", "workers.verify_worker"),
    ("compile_objects", "workers.compile_objects_worker"),
    ("summaries", "workers.summary_worker"),
    # SUMMARIES-SCALE-OUT-V1: second summaries worker, demand-driven by the autopilot
    ("summaries2", "workers.summary_worker"),
    # DOCUMENT-PROFILE-V1: the document retrieval profile stage (its own LLM pool; demand-driven)
    ("doc_profile", "workers.doc_profile_worker"),
    # DOC-PROFILE-SCALE-OUT-V1 (2026-09-07): the pool is six independent accounts and the runtime executes
    # tickets serially, so ONE slot meant one document a minute on a 67-document backfill (owner: "those are
    # different api accounts, one document at a time is stupid"). One worker per open doc_profile ticket,
    # capped at six — one in flight per key; the run-hash lane rotation spreads them.
    ("doc_profile2", "workers.doc_profile_worker"),
    ("doc_profile3", "workers.doc_profile_worker"),
    ("doc_profile4", "workers.doc_profile_worker"),
    ("doc_profile5", "workers.doc_profile_worker"),
    ("doc_profile6", "workers.doc_profile_worker"),
    # DOC-PARENT-MAP AUTO-MINT (RAG-PIPELINE-FINISH): the pMAP stage worker. Idle until
    # POLYMATH_DOC_PARENT_MAP_ENABLED mints doc_parent_map.v1 events (flag off => no work,
    # the slot simply parks).
    #
    # PMAP-SCALE-OUT-V1 (2026-09-11, MEASURED). One slot was chosen on the assumption that
    # the pool is the constraint — "the worker's own infer closure fails over across the
    # map_groq accounts in-run, so one slot drains the pool". The cinema backfill measured
    # otherwise: 40 dispatches in ~70 minutes against 5 lanes x 2 rpm = 10/min available,
    # i.e. ~6% provider utilisation. The constraint is the WORKER — one slot maps one
    # document at a time and pays skeleton-build, batch-planning and projection-embed
    # serially between dispatches.
    #
    # Four slots claim four DOCUMENTS concurrently (tickets are leased per document, so
    # there is no double-mapping), which fits inside the lane budget rather than straining
    # it. Autopilot still parks them all when no pMAP ticket is open, so the idle cost is
    # unchanged. MAP_RELIABILITY_CAP is untouched.
    #
    # LLM-BACKEND L3 (register 11.467): SIX slots, one per Groq account — slot N owns
    # map_groqN + map_groqNq (config/llm_accounts.yaml `slots.doc_parent_map.owners`), so each
    # (key, model) pair has one calling process. Rollback: drop doc_parent_map5 / 6 here and
    # set `slots.doc_parent_map.count: 4` (+ owners) in the registry, then run the writer.
    ("doc_parent_map", "workers.doc_parent_map_stage_worker"),
    ("doc_parent_map2", "workers.doc_parent_map_stage_worker"),
    ("doc_parent_map3", "workers.doc_parent_map_stage_worker"),
    ("doc_parent_map4", "workers.doc_parent_map_stage_worker"),
    ("doc_parent_map5", "workers.doc_parent_map_stage_worker"),
    ("doc_parent_map6", "workers.doc_parent_map_stage_worker"),
    # COGNITIVE-ADAPTER-V1 (ADR-0018, E2): durable automatic-step executor for adapter runs; health = its own
    # `adapter_step` registration heartbeat (register_worker/heartbeat in the worker loop).
    ("adapter_step", "workers.adapter_step_worker"),
]


#: LLM-BACKEND L3 (register 11.467): the stages whose slots OWN lanes, and the variable that carries a slot's
#: 1-based index (config/llm_accounts.yaml `slots.<stage>.lane_offset_env`; a test keeps the two equal).
LANE_OFFSET_ENV = {
    "doc_profile": "POLYMATH_DOC_PROFILE_LANE_OFFSET",
    "doc_parent_map": "POLYMATH_DOC_PARENT_MAP_LANE_OFFSET",
}


def lane_offset_env(slot_name: str) -> dict[str, str]:
    """The slot-index variable for an owning stage's slot: `doc_parent_map` -> {…: "1"}, `doc_parent_map3` -> "3";
    {} for every other slot."""
    for stage, env in LANE_OFFSET_ENV.items():
        suffix = slot_name[len(stage):] if slot_name.startswith(stage) else None
        if suffix == "" or (suffix and suffix.isdigit()):
            return {env: suffix or "1"}
    return {}


# FLEET-LOG-DURABLE-V1 (measured 2026-11-01): 26 worker logs under /private/tmp/polymath_fleet were unlinked while
# their processes still wrote to them (lsof link count 0) — macOS's periodic /tmp cleaner deletes files whose access
# time is over 3 days old, and a log opened once in append mode is written, never read. Slot logs (and the state file)
# now live in a durable directory; the old path stays readable through a link (`link_run_dir`).
LEGACY_FLEET_DIR = Path("/private/tmp/polymath_fleet")
FLEET_LOG_DIR_ENV = "POLYMATH_FLEET_LOG_DIR"
FLEET_DIR_ENV = "POLYMATH_FLEET_DIR"
STATE_FILE = "supervisor_state.json"


def default_fleet_log_dir() -> Path:
    """~/PolymathRuntime/logs/fleet — the durable default (scripts/boot_polymath.sh and bounce_fleet.sh use the same)."""
    return Path.home() / "PolymathRuntime" / "logs" / "fleet"


def _same_dir(a: Path, b: Path) -> bool:
    """Both resolve to one directory (symlinks followed all the way)."""
    return os.path.realpath(a) == os.path.realpath(b)


def _same_path(a: Path, b: Path) -> bool:
    """The same path (parents resolved, e.g. /tmp -> /private/tmp; the last component NOT followed): a run dir that is
    already our link stays distinct from the log dir, so every boot re-checks and receipts it."""
    return (Path(os.path.realpath(a.parent)) / a.name) == (Path(os.path.realpath(b.parent)) / b.name)


def resolve_fleet_dirs(log_dir: str | None = None, run_dir: str | None = None,
                       env=None) -> tuple[Path, Path | None]:
    """(slot-log dir, run dir to keep linked to it — or None).

    Log dir: an explicit `log_dir` (tests, tools) > POLYMATH_FLEET_LOG_DIR > POLYMATH_FLEET_DIR (a second instance's own
    dir, SERVE-SUPERVISOR-V1, unchanged) > ~/PolymathRuntime/logs/fleet. Run dir: the path existing readers know
    (POLYMATH_FLEET_DIR, else /private/tmp/polymath_fleet — the Metal lease, rerank wake, stall tracer and conformance
    readers all resolve it); None when it IS the log dir, and None for an explicit `log_dir` unless `run_dir` is given."""
    env = os.environ if env is None else env
    instance = (env.get(FLEET_DIR_ENV) or "").strip()
    if log_dir:
        log_path = Path(log_dir).expanduser()
        run = Path(run_dir).expanduser() if run_dir else None
    else:
        chosen = (env.get(FLEET_LOG_DIR_ENV) or "").strip() or instance
        log_path = Path(chosen).expanduser() if chosen else default_fleet_log_dir()
        run = Path(run_dir).expanduser() if run_dir else (Path(instance).expanduser() if instance else LEGACY_FLEET_DIR)
    if run is not None and _same_path(run, log_path):
        run = None
    return log_path, run


def link_run_dir(run_dir: Path, log_dir: Path) -> dict:
    """Keep `run_dir` resolving to `log_dir`, at every boot. Receipt `mode`:
      created_link  the path was absent (a reboot clears /private/tmp): it is now a symlink to the log dir — every
                    old-path reader AND writer (Metal lease files, receipts, tick phases) lands in the durable dir;
      linked        already that symlink;  relinked  a symlink to another dir, repointed (`previous` names it);
      per_entry     a real directory from before: left in place (another component may hold files in it), and the
                    supervisor links ITS entries inside it instead (`link_run_entry`: the state file, each slot log);
      blocked       a non-directory sits at the path — left alone;  error  the link could not be made.
    Never deletes anything."""
    rec: dict = {"run_dir": str(run_dir), "log_dir": str(log_dir)}
    for _ in range(2):                         # one retry: a creator racing us turns "absent" into "exists"
        try:
            if run_dir.is_symlink():
                if _same_dir(run_dir, log_dir):
                    rec["mode"] = "linked"
                    return rec
                rec["previous"] = os.path.realpath(run_dir)
                tmp = run_dir.with_name(f".{run_dir.name}.link.{os.getpid()}")
                if tmp.is_symlink() or tmp.exists():
                    tmp.unlink()
                os.symlink(log_dir, tmp, target_is_directory=True)
                os.replace(tmp, run_dir)       # atomic: a reader never finds the path missing
                rec["mode"] = "relinked"
                return rec
            if run_dir.is_dir():
                rec["mode"] = "per_entry"
                return rec
            if run_dir.exists():
                rec["mode"] = "blocked"
                return rec
            run_dir.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(log_dir, run_dir, target_is_directory=True)
            rec["mode"] = "created_link"
            return rec
        except FileExistsError:
            continue
        except OSError as exc:
            rec.update(mode="error", error=f"{type(exc).__name__}: {exc}")
            return rec
    rec.update(mode="error", error="raced")
    return rec


def link_run_entry(run_dir: Path, log_dir: Path, name: str) -> str:
    """per_entry mode: `run_dir/name` becomes a symlink to `log_dir/name`, so an old-path reader follows the live file.
    A regular file already there (the previous process's log, the stale state file) is ADOPTED into the durable dir when
    that has no such file — one rename on the same volume, so the inode and any writer still holding it move along —
    else kept beside it as `<name>.pre-durable-<epoch>`. Nothing is deleted. Returns the outcome (receipt-only):
    linked | created | adopted | kept_aside | relinked | blocked | error:<type>."""
    legacy, durable = run_dir / name, log_dir / name
    try:
        outcome = "created"
        if legacy.is_symlink():
            if _same_dir(legacy, durable):
                return "linked"
            outcome = "relinked"
        elif legacy.exists():
            if not legacy.is_file():
                return "blocked"
            outcome = "kept_aside"
            if not durable.exists():
                try:
                    os.rename(legacy, durable)
                    outcome = "adopted"
                except OSError:                # another volume: keep it beside the link instead
                    pass
            if outcome == "kept_aside":
                os.rename(legacy, legacy.with_name(f"{name}.pre-durable-{int(time.time())}"))
        tmp = legacy.with_name(f".{name}.link.{os.getpid()}")
        if tmp.is_symlink() or tmp.exists():
            tmp.unlink()
        os.symlink(durable, tmp)
        os.replace(tmp, legacy)
        return outcome
    except OSError as exc:
        return f"error:{type(exc).__name__}"


@dataclass
class Slot:
    name: str
    module: str            # module name, script path, or "" for argv slots
    argv: list | None = None
    cwd: str | None = None
    health_url: str | None = None
    readiness_interval_s: float | None = None          # per-slot override (ORCHESTRATOR-LIMBO-V1)
    readiness_failures_before_restart: int | None = None
    last_probe_at: float = 0.0
    readiness_failures: int = 0
    proc: subprocess.Popen | None = None
    parked: bool = False   # FLEET-AUTOPILOT-V1: not currently desired
    started_at: float = 0.0
    exits: list[float] = field(default_factory=list)   # exit timestamps
    restarts: int = 0
    quarantined: bool = False
    last_exit_code: int | None = None


def _dotenv_overlay(path) -> dict:
    """KEY=VALUE lines of a .env file (comments/blank skipped, optional
    surrounding quotes stripped). Pure; missing file -> {}."""
    out: dict = {}
    try:
        text = Path(path).read_text()
    except (FileNotFoundError, OSError):
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def control_heartbeat_stale(heartbeat_age_s: float | None, uptime_s: float,
                            threshold_s: float) -> bool:
    """CONTROL-HEARTBEAT-WATCHDOG-V1 (owner law 2026-09-02: nothing may sit
    stuck > 3 min unnoticed). The control plane's own liveness is a
    successful tick (record_heartbeat runs only on tick_ok), so a control
    process that is alive but not ticking — lease never acquired, every
    tick failing (measured 2026-08-31: 1,864 consecutive failed ticks), a
    wedged connection — is a stall the stall tracer cannot see about
    itself. Stale = no successful tick for threshold_s, judged only after
    the process has had threshold_s to boot and take the lease. A missing
    heartbeat row (None) counts as stale once the grace has passed."""
    if uptime_s < threshold_s:
        return False
    return heartbeat_age_s is None or heartbeat_age_s > threshold_s


def _release_leases_of_pid(dsn: str, pid: int, note: str) -> int:
    """GRACEFUL-LEASE-HANDBACK-V1 (2026-09-02): when the supervisor
    itself stops a worker (fence restart onto current code, shutdown),
    the worker did not vanish — so its leases go back to `ready` WITHOUT
    consuming an attempt. Left alone, the heartbeat stops, the expiry
    sweep marks the owner stale and charges attempt+1: two fence
    restarts cost Blue Ocean two of its three attempts."""
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            cur = conn.execute(
                """UPDATE stage_tickets t
                      SET status = 'ready', lease_owner = NULL,
                          lease_expires_at = NULL,
                          last_error_note = %s, updated_at = now()
                     FROM worker_registrations w
                    WHERE w.pid = %s AND t.lease_owner = w.worker_id
                      AND t.status = 'leased'""",
                (note, pid))
            n = cur.rowcount
            conn.commit()
            return n
    except Exception:  # noqa: BLE001 — never block a stop on bookkeeping
        return 0


class Supervisor:
    #: Optional slot allowlist, e.g. POLYMATH_FLEET_ONLY="control,qdrant,
    #: sidecar_embedder". A targeted run should not hold models it will
    #: never call: a projection needs the embedder, not GLiNER, spaCy or
    #: the reranker, and each of those keeps a model resident. Used to
    #: bound Polymath's footprint on a shared workstation.
    @staticmethod
    def _fleet_filter(fleet):
        only = os.environ.get("POLYMATH_FLEET_ONLY", "").strip()
        if not only:
            prof = os.environ.get("POLYMATH_PROFILE", "").strip()
            if prof:
                from polymath_shared.runtime_budget import profile_slots
                only = ",".join(profile_slots(prof))
        if not only:
            return fleet
        def _name(entry):
            if isinstance(entry, dict):
                return entry["name"]
            if isinstance(entry, (tuple, list)):
                return entry[0]
            return entry

        wanted = {n.strip() for n in only.split(",") if n.strip()}
        kept = [e for e in fleet if _name(e) in wanted]
        missing = wanted - {_name(e) for e in fleet}
        if missing:
            raise ValueError(f"POLYMATH_FLEET_ONLY names unknown slots: {sorted(missing)}")
        return kept

    def __init__(self, fleet=FLEET, *, python: str | None = None,
                 log_dir: str | None = None, state_path: str | None = None,
                 run_dir: str | None = None,
                 max_restarts: int = 5, window_s: float = 300.0,
                 # A BUSY sidecar queues the readiness probe behind real
                 # inference: the embedder answers in ~0.3s idle but ~7s
                 # under load, and a 10s budget with 3 strikes restarted
                 # healthy-but-loaded sidecars 11 times. Budget generously
                 # and require a longer silence before calling it wedged.
                 probe_timeout_s: float = 60.0,
                 readiness_interval_s: float = 120.0,
                 readiness_failures_before_restart: int = 5,
                 backoff_s: float = 2.0, health_timeout_s: float = 30.0,
                 dsn: str | None = None):
        fleet = self._fleet_filter(fleet)
        self.slots = []
        for entry in fleet:
            if isinstance(entry, dict):
                self.slots.append(Slot(entry["name"], "", argv=entry["argv"],
                                       cwd=entry.get("cwd"),
                                       health_url=entry.get("health_url"),
                                       readiness_interval_s=entry.get("readiness_interval_s"),
                                       readiness_failures_before_restart=entry.get("readiness_failures_before_restart")))
            else:
                self.slots.append(Slot(entry[0], entry[1]))
        self.python = python or sys.executable
        # FLEET-LOG-DURABLE-V1: slot logs + state in a durable dir (created here), and the run dir existing readers
        # know (/private/tmp/polymath_fleet by default) kept resolving to it — see resolve_fleet_dirs / link_run_dir
        self.log_dir, self.run_dir = resolve_fleet_dirs(log_dir, run_dir)
        self.log_compat: dict | None = None
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            if self.run_dir is None:
                raise
            # never block the fleet on its log directory: write where the readers look, and say so (state + log)
            log.error("fleet log dir %s unusable (%s: %s); slot logs fall back to %s",
                      self.log_dir, type(exc).__name__, exc, self.run_dir)
            self.log_compat = {"mode": "fallback", "log_dir": str(self.log_dir), "run_dir": str(self.run_dir),
                               "error": f"{type(exc).__name__}: {exc}"}
            self.log_dir, self.run_dir = self.run_dir, None
            self.log_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = Path(state_path or (self.log_dir / STATE_FILE))
        if self.run_dir is not None:
            self.log_compat = link_run_dir(self.run_dir, self.log_dir)
            if self.log_compat["mode"] == "per_entry" and state_path is None:
                self.log_compat["state"] = link_run_entry(self.run_dir, self.log_dir, STATE_FILE)
            (log.warning if self.log_compat["mode"] in ("blocked", "error") else log.info)(
                "fleet logs: %s (old path %s: %s)", self.log_dir, self.run_dir, self.log_compat["mode"])
        self.max_restarts = max_restarts
        # Bounds a wedged inference probe: the forward pass in /ready hangs
        # when the model is stuck, and the timeout is what turns that hang
        # into an actionable unhealthy verdict instead of a hung supervisor.
        self.probe_timeout_s = probe_timeout_s
        # Slow cadence: the probe is a real forward pass.
        self.readiness_interval_s = readiness_interval_s
        self.readiness_failures_before_restart = readiness_failures_before_restart
        # CONTROL-HEARTBEAT-WATCHDOG-V1 knobs (owner law: 3 minutes).
        self.control_probe_interval_s = 30.0
        try:
            from polymath_shared.settings import get_settings
            self.control_stall_threshold_s = float(
                getattr(get_settings().control, "stall_threshold_s", 180))
        except Exception:  # noqa: BLE001
            self.control_stall_threshold_s = 180.0
        self.window_s = window_s
        self.backoff_s = backoff_s
        self.health_timeout_s = health_timeout_s
        self.dsn = dsn or os.environ.get(
            "POLYMATH_PG_DSN",
            "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
        self._stop = False
        # FLEET-AUTOPILOT-V1: demand-driven membership. When enabled,
        # every slot starts PARKED and the reconcile loop spawns only
        # what the measured demand policy asks for; the static
        # POLYMATH_FLEET_ONLY/profile filter still bounds the universe.
        self.autopilot = os.environ.get("POLYMATH_AUTOPILOT", "").strip() == "1"
        self._autopilot_last = 0.0
        self._autopilot_reasons: dict = {}
        if self.autopilot:
            for slot in self.slots:
                if slot.name not in ("control", "orchestrator", "intake"):
                    slot.parked = True

    # ------------------------------------------------------------------ ops
    def _spawn(self, slot: Slot) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # FLEET-LOG-DURABLE-V1: the old path is a real directory from before → link this slot's log inside it first
        # (adopting the previous process's log into the durable dir), so `<old path>/<slot>.log` follows the live file
        if (getattr(self, "log_compat", None) or {}).get("mode") == "per_entry" and self.run_dir is not None:
            link_run_entry(self.run_dir, self.log_dir, f"{slot.name}.log")
        out = open(self.log_dir / f"{slot.name}.log", "ab")
        if slot.argv is not None:
            repo = Path(__file__).resolve().parents[2]
            argv = [a.replace("{python}", str(repo / ".venv/bin/python"))
                    for a in slot.argv]
            cwd = str(repo / slot.cwd) if slot.cwd else None
        else:
            argv = ([self.python, slot.module] if slot.module.endswith(".py")
                    else [self.python, "-m", slot.module])   # scripts, for tests
            cwd = None
        # RUNTIME BUDGET: a slot is started with its own memory caps, so
        # the limit binds at the process that actually allocates. The
        # embedder once held 41.58 GiB of Metal pool on a 32 GB machine
        # because nothing capped it.
        child_env = os.environ.copy()
        # ENV-OVERLAY-ON-SPAWN-V1 (2026-09-02): children used to inherit
        # the supervisor's BOOT snapshot, so a rotated key in .env was
        # invisible until a full fleet restart — measured: openrouter
        # lanes 401'd on a replaced key and struck a document. Every
        # spawn/respawn now overlays the current .env; the fence restart
        # onto current code therefore also picks up current secrets.
        child_env.update(_dotenv_overlay(
            Path(__file__).resolve().parents[2] / ".env"))
        try:
            from polymath_shared.runtime_budget import export_env
            child_env.update(export_env(slot.name))
        except Exception:
            log.warning("no runtime budget for slot %s; starting uncapped",
                        slot.name)
        # LANE-AFFINITY-STEAL-V1: the first extract slot works the local
        # lane, every further extract slot works the cloud lane (extra
        # cloud providers scale by adding extractN slots). Both steal
        # the other lane when their own backlog is dry.
        if slot.name == "extract":
            child_env.setdefault("POLYMATH_EXTRACT_AFFINITY", "local")
        elif slot.name.startswith("extract"):
            child_env.setdefault("POLYMATH_EXTRACT_AFFINITY", "cloud")
        # DOC-PROFILE-SCALE-OUT-V1 + LLM-BACKEND L3: each profile / pMAP slot learns its 1-based index
        # (doc_profile → 1, doc_profile2 → 2, …) and calls ITS OWN account's lanes (registry `owners`);
        # without the index a worker falls back to the run-hash rotation (single slot, tests).
        for key, value in lane_offset_env(slot.name).items():
            child_env.setdefault(key, value)
        slot.proc = subprocess.Popen(
            argv, cwd=cwd,
            stdout=out, stderr=subprocess.STDOUT,
            env=child_env, start_new_session=True)
        slot.started_at = time.time()
        log.info("spawned %s (%s) pid=%s", slot.name, slot.module, slot.proc.pid)

    def _restart_allowed(self, slot: Slot) -> bool:
        now = time.time()
        slot.exits = [t for t in slot.exits if now - t <= self.window_s]
        return len(slot.exits) <= self.max_restarts

    def _quarantine(self, slot: Slot, why: str) -> None:
        slot.quarantined = True
        log.critical("QUARANTINED slot %s: %s", slot.name, why)
        try:
            import psycopg
            with psycopg.connect(self.dsn, connect_timeout=5) as conn:
                conn.execute(
                    "UPDATE worker_registrations SET status='quarantined',"
                    " last_error=%s WHERE worker_type=%s AND status <> 'quarantined'",
                    (f"cp2.1 restart budget exhausted: {why}"[:200], slot.name))
                conn.commit()
        except Exception:
            log.exception("could not record quarantine in DB")

    def verify_health(self, slot: Slot) -> bool:
        """A restarted worker is healthy when a FRESH registration for its
        worker_type heartbeats after the spawn — proof it re-registered and
        re-advertised capability, not merely that the process exists."""
        if slot.health_url:
            import httpx
            deadline = time.time() + self.health_timeout_s
            while time.time() < deadline:
                try:
                    r = httpx.get(slot.health_url, timeout=self.probe_timeout_s)
                    # Status code AND body. A sidecar that answers 200 while
                    # reporting {"ready": false} is exactly the wedge this
                    # gate exists to catch, and older builds do that.
                    if r.status_code == 200:
                        try:
                            body = r.json()
                        except Exception:
                            body = {}
                        if body.get("ready") is not False:
                            return True
                except Exception:
                    pass
                time.sleep(1.0)
            return False
        if slot.name == "control":
            return slot.proc is not None and slot.proc.poll() is None
        deadline = time.time() + self.health_timeout_s
        while time.time() < deadline:
            try:
                import psycopg
                with psycopg.connect(self.dsn, connect_timeout=5) as conn:
                    row = conn.execute(
                        "SELECT MAX(EXTRACT(EPOCH FROM heartbeat_at)) FROM"
                        " worker_registrations WHERE worker_type=%s",
                        (slot.name,)).fetchone()
                if row and row[0] and float(row[0]) >= slot.started_at:
                    return True
            except Exception:
                pass
            time.sleep(1.0)
        return False

    # ----------------------------------------------------------------- loop
    def tick(self) -> dict:
        if getattr(self, "autopilot", False):
            self._autopilot_reconcile()
        for slot in self.slots:
            if slot.quarantined or slot.parked:
                continue
            if slot.proc is None:
                self._spawn(slot)
                continue
            code = slot.proc.poll()
            if code is None:
                # HANG-DEATH (P0-B). A process that exited is easy; a
                # process that is alive while its inference path is wedged
                # answered every liveness check for 16 hours and stalled a
                # whole corpus. Readiness is therefore probed periodically,
                # not only at spawn, and a slot that fails repeatedly is
                # restarted exactly like one that died.
                self._check_readiness(slot)
                continue
            slot.last_exit_code = code
            slot.exits.append(time.time())
            log.warning("worker %s exited code=%s (exit %d in window)",
                        slot.name, code, len(slot.exits))
            if not self._restart_allowed(slot):
                self._quarantine(
                    slot, f"{len(slot.exits)} exits within {self.window_s}s")
                continue
            time.sleep(self.backoff_s * len(slot.exits))
            slot.restarts += 1
            self._spawn(slot)
        self._write_state()
        return self.state()

    def _check_control_heartbeat(self, slot: Slot, now: float) -> None:
        """CONTROL-HEARTBEAT-WATCHDOG-V1: restart control when it has not
        completed a tick for stall_threshold_s (see control_heartbeat_stale).
        Restart budget applies exactly as for a crashed slot."""
        try:
            import psycopg
            with psycopg.connect(self.dsn, connect_timeout=5) as conn:
                row = conn.execute(
                    "SELECT EXTRACT(EPOCH FROM now() - MAX(last_seen_at)) "
                    "FROM control_owners").fetchone()
            age = float(row[0]) if row and row[0] is not None else None
        except Exception:  # noqa: BLE001 — the probe must never kill the loop
            return
        if not control_heartbeat_stale(age, now - slot.started_at,
                                       self.control_stall_threshold_s):
            return
        log.error("control heartbeat stale (%s s without a completed tick, "
                  "threshold %s s): restarting control",
                  "none" if age is None else int(age),
                  int(self.control_stall_threshold_s))
        slot.exits.append(now)
        if not self._restart_allowed(slot):
            self._quarantine(slot, "control heartbeat restarts exceeded budget")
            return
        try:
            slot.proc.terminate()
            slot.proc.wait(timeout=15)
        except Exception:
            try:
                slot.proc.kill()
            except Exception:
                pass
        slot.restarts += 1
        self._spawn(slot)

    def _check_readiness(self, slot: Slot) -> None:
        """Probe a live service slot's readiness on a slow cadence.

        Deliberately infrequent: the probe runs a real forward pass, so
        probing every tick would itself contend for the GPU. Consecutive
        failures are required before restarting so a single slow response
        under load never causes a restart storm.
        """
        if slot.proc is None:
            return
        now = time.time()
        # The control probe is one cheap SQL read, so it runs on its own
        # fast cadence; service probes cost a forward pass and stay slow.
        interval = (self.control_probe_interval_s if slot.name == "control"
                    else (slot.readiness_interval_s or self.readiness_interval_s))
        if now - slot.last_probe_at < interval:
            return
        slot.last_probe_at = now
        if slot.name == "control":
            self._check_control_heartbeat(slot, now)
            return
        if not slot.health_url:
            # WORKER-QUARANTINE-AUTOHEAL-V1 (measured 2026-08-30 22:03):
            # a fence-quarantined worker (BUNDLE_STALE_CODE_DRIFT) keeps
            # heartbeating while refusing every claim, so it looks alive
            # to every existing check and NEVER exits — after a fenced
            # commit, every non-crashed slot sat refusing claims and an
            # owner upload "disappeared" (intake events undelivered, no
            # corpus row). The code on disk is exactly what the fence is
            # protecting; a respawn loads it. Restart budget still applies
            # via the exit window, so a genuinely flapping slot follows
            # the normal quarantine law.
            try:
                import psycopg
                with psycopg.connect(self.dsn, connect_timeout=5) as conn:
                    # pid alone identifies THIS slot's child (slot names
                    # do not match worker_type strings, e.g. "profile"
                    # vs "profile_document")
                    row = conn.execute(
                        """SELECT COUNT(*) FROM worker_registrations
                            WHERE pid = %s AND status = 'quarantined'
                              AND heartbeat_at > now() - interval '30 seconds'""",
                        (slot.proc.pid,)).fetchone()
                if row and row[0]:
                    log.error(
                        "slot %s fence-quarantined (stale bundle): "
                        "restarting onto current code", slot.name)
                    slot.exits.append(now)
                    if not self._restart_allowed(slot):
                        self._quarantine(
                            slot, "fence-quarantine restarts exceeded budget")
                        return
                    released = _release_leases_of_pid(
                        self.dsn, slot.proc.pid,
                        "released: fence restart onto current code "
                        "(no retry consumed)")
                    if released:
                        log.info("slot %s: %d lease(s) handed back before "
                                 "fence restart", slot.name, released)
                    try:
                        slot.proc.terminate()
                        slot.proc.wait(timeout=15)
                    except Exception:
                        try:
                            slot.proc.kill()
                        except Exception:
                            pass
                    slot.restarts += 1
                    self._spawn(slot)
            except Exception:  # noqa: BLE001 — health probe must never kill the loop
                pass
            return
        ready = False
        try:
            import httpx
            r = httpx.get(slot.health_url, timeout=self.probe_timeout_s)
            if r.status_code == 200:
                try:
                    ready = r.json().get("ready") is not False
                except Exception:
                    ready = True
        except Exception:
            ready = False
        if ready:
            slot.readiness_failures = 0
            return
        slot.readiness_failures += 1
        _limit = slot.readiness_failures_before_restart or self.readiness_failures_before_restart
        log.warning("slot %s not ready (%d/%d)", slot.name, slot.readiness_failures, _limit)
        if slot.readiness_failures < _limit:
            return
        log.error("slot %s wedged: restarting on readiness failure", slot.name)
        slot.readiness_failures = 0
        slot.exits.append(now)
        if not self._restart_allowed(slot):
            self._quarantine(slot, "readiness failures exceeded restart budget")
            return
        try:
            slot.proc.terminate()
            slot.proc.wait(timeout=15)
        except Exception:
            try:
                slot.proc.kill()
            except Exception:
                pass
        slot.restarts += 1
        self._spawn(slot)

    def _autopilot_reconcile(self, interval_s: float = 15.0) -> None:
        """OBSERVE → COMPUTE DESIRED → RECONCILE (FLEET-AUTOPILOT-V1).

        Deterministic: backlog + query recency in Postgres decide which
        slots exist. Parking terminates the process — exit is the only
        reliable way to return MPS/Metal memory. A parked slot spawns
        again the moment demand returns (fresh budget env per spawn)."""
        now = time.time()
        if now - self._autopilot_last < interval_s:
            return
        self._autopilot_last = now
        try:
            import psycopg

            from control.fleet_autopilot import desired_slots
            with psycopg.connect(self.dsn, connect_timeout=5) as conn:
                desired, reasons = desired_slots(
                    conn, {s.name for s in self.slots})
        except Exception as exc:
            log.warning("autopilot observe failed (keeping fleet): %s", exc)
            return
        self._autopilot_reasons = reasons
        for slot in self.slots:
            if slot.quarantined:
                continue
            want = slot.name in desired
            alive = slot.proc is not None and slot.proc.poll() is None
            if want and slot.parked:
                slot.parked = False
                log.info("autopilot: waking %s (%s)", slot.name,
                         reasons.get(slot.name, "?"))
            elif not want and not slot.parked:
                slot.parked = True
                if alive:
                    log.info("autopilot: parking %s (no demand)", slot.name)
                    slot.proc.terminate()
                    slot.proc = None

    def state(self) -> dict:
        log_dir = getattr(self, "log_dir", None)
        return {"slots": [{
            "name": s.name, "pid": s.proc.pid if s.proc else None,
            "alive": bool(s.proc and s.proc.poll() is None),
            "restarts": s.restarts, "quarantined": s.quarantined,
            "last_exit_code": s.last_exit_code} for s in self.slots],
            # FLEET-LOG-DURABLE-V1: where the slot logs are, and what the old path does
            "log_dir": str(log_dir) if log_dir is not None else None,
            "log_compat": getattr(self, "log_compat", None)}

    def _write_state(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self.state(), indent=1))
        except Exception:
            pass

    def run_forever(self, poll_s: float = 2.0) -> None:
        # Refuse to start an over-committed fleet rather than discover it
        # by thrashing the workstation.
        try:
            from polymath_shared.runtime_budget import preflight
            if self.autopilot:
                raise RuntimeError("autopilot: per-tick budget gating")
            plan = preflight()
            log.info("runtime budget: %.2f GB committed of %.2f GB ceiling",
                     plan["committed_gb"], plan["ceiling_gb"])
        except Exception as exc:
            if type(exc).__name__ == "BudgetExceeded":
                log.error("REFUSING TO START: %s", exc)
                raise
            log.warning("runtime budget preflight unavailable: %s", exc)
        signal.signal(signal.SIGTERM, self._on_term)
        signal.signal(signal.SIGINT, self._on_term)
        log.info("cp2.1 supervisor: %d slots", len(self.slots))
        while not self._stop:
            self.tick()
            time.sleep(poll_s)
        for slot in self.slots:
            if slot.proc and slot.proc.poll() is None:
                slot.proc.terminate()
        log.info("supervisor stopped")

    def _on_term(self, *_):
        self._stop = True


def main() -> None:
    from polymath_shared.logging import configure_logging
    configure_logging("cp21-supervisor")
    # SERVE-SUPERVISOR-V1 (audit F9): a second supervisor instance runs
    # the query-serving slots (POLYMATH_FLEET_ONLY=orchestrator,
    # sidecar_reranker); POLYMATH_FLEET_DIR gives it its own state file
    # and slot logs so the two instances never clobber each other.
    # FLEET-LOG-DURABLE-V1: resolve_fleet_dirs reads POLYMATH_FLEET_DIR
    # (unchanged meaning) and POLYMATH_FLEET_LOG_DIR; with neither set the
    # logs go to ~/PolymathRuntime/logs/fleet, linked from the old path.
    Supervisor().run_forever()


if __name__ == "__main__":
    main()

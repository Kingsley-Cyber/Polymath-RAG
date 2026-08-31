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
    {"name": "sidecar_embedder", "argv": ["{python}", "-m", "uvicorn",
        "server:app", "--host", "127.0.0.1", "--port", "8742"],
     "cwd": "sidecars/embedder", "health_url": "http://127.0.0.1:8742/ready"},
    {"name": "sidecar_reranker", "argv": ["{python}", "-m", "uvicorn",
        "server:app", "--host", "127.0.0.1", "--port", "8743",
        "--app-dir", "sidecars/reranker"],
     "cwd": ".", "health_url": "http://127.0.0.1:8743/ready"},
    # ---- orchestrator ----------------------------------------------------
    {"name": "orchestrator", "argv": ["{python}", "-m", "uvicorn",
        "orchestrator.main:app", "--host", "127.0.0.1", "--port", "7200"],
     "cwd": "orchestrator", "health_url": "http://127.0.0.1:7200/health"},
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
    ("canonicalize", "workers.canonicalize_worker"),
    ("project_canonical", "workers.project_canonical_worker"),
    ("neo4j", "workers.project_neo4j_worker"),
    ("qdrant", "workers.project_qdrant_worker"),
    ("verify", "workers.verify_worker"),
    ("compile_objects", "workers.compile_objects_worker"),
    ("summaries", "workers.summary_worker"),
]


@dataclass
class Slot:
    name: str
    module: str            # module name, script path, or "" for argv slots
    argv: list | None = None
    cwd: str | None = None
    health_url: str | None = None
    last_probe_at: float = 0.0
    readiness_failures: int = 0
    proc: subprocess.Popen | None = None
    parked: bool = False   # FLEET-AUTOPILOT-V1: not currently desired
    started_at: float = 0.0
    exits: list[float] = field(default_factory=list)   # exit timestamps
    restarts: int = 0
    quarantined: bool = False
    last_exit_code: int | None = None


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
                                       health_url=entry.get("health_url")))
            else:
                self.slots.append(Slot(entry[0], entry[1]))
        self.python = python or sys.executable
        self.log_dir = Path(log_dir or "/tmp/polymath_fleet")
        self.state_path = Path(state_path or (self.log_dir / "supervisor_state.json"))
        self.max_restarts = max_restarts
        # Bounds a wedged inference probe: the forward pass in /ready hangs
        # when the model is stuck, and the timeout is what turns that hang
        # into an actionable unhealthy verdict instead of a hung supervisor.
        self.probe_timeout_s = probe_timeout_s
        # Slow cadence: the probe is a real forward pass.
        self.readiness_interval_s = readiness_interval_s
        self.readiness_failures_before_restart = readiness_failures_before_restart
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
        if now - slot.last_probe_at < self.readiness_interval_s:
            return
        slot.last_probe_at = now
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
        log.warning("slot %s not ready (%d/%d)", slot.name,
                    slot.readiness_failures, self.readiness_failures_before_restart)
        if slot.readiness_failures < self.readiness_failures_before_restart:
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
        return {"slots": [{
            "name": s.name, "pid": s.proc.pid if s.proc else None,
            "alive": bool(s.proc and s.proc.poll() is None),
            "restarts": s.restarts, "quarantined": s.quarantined,
            "last_exit_code": s.last_exit_code} for s in self.slots]}

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
    fleet_dir = os.environ.get("POLYMATH_FLEET_DIR")
    Supervisor(log_dir=fleet_dir).run_forever()


if __name__ == "__main__":
    main()

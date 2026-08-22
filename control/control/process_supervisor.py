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
    # ---- neural sidecars (started FIRST: workers verify their pins) ------
    {"name": "sidecar_gliner", "argv": ["{python}", "-m", "uvicorn",
        "server:app", "--host", "127.0.0.1", "--port", "8740"],
     "cwd": "sidecars/gliner_runtime", "health_url": "http://127.0.0.1:8740/ready"},
    {"name": "sidecar_spacy", "argv": [".venv/bin/python", "-m", "uvicorn",
        "server:app", "--host", "127.0.0.1", "--port", "8744"],
     "cwd": "sidecars/spacy_runtime", "health_url": "http://127.0.0.1:8744/ready"},
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
    ("canonicalize", "workers.canonicalize_worker"),
    ("project_canonical", "workers.project_canonical_worker"),
    ("neo4j", "workers.project_neo4j_worker"),
    ("qdrant", "workers.project_qdrant_worker"),
    ("verify", "workers.verify_worker"),
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
    started_at: float = 0.0
    exits: list[float] = field(default_factory=list)   # exit timestamps
    restarts: int = 0
    quarantined: bool = False
    last_exit_code: int | None = None


class Supervisor:
    def __init__(self, fleet=FLEET, *, python: str | None = None,
                 log_dir: str | None = None, state_path: str | None = None,
                 max_restarts: int = 5, window_s: float = 300.0,
                 probe_timeout_s: float = 10.0,
                 readiness_interval_s: float = 60.0,
                 readiness_failures_before_restart: int = 3,
                 backoff_s: float = 2.0, health_timeout_s: float = 30.0,
                 dsn: str | None = None):
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
        slot.proc = subprocess.Popen(
            argv, cwd=cwd,
            stdout=out, stderr=subprocess.STDOUT,
            env=os.environ.copy(), start_new_session=True)
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
        for slot in self.slots:
            if slot.quarantined:
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
        if not slot.health_url or slot.proc is None:
            return
        now = time.time()
        if now - slot.last_probe_at < self.readiness_interval_s:
            return
        slot.last_probe_at = now
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
    Supervisor().run_forever()


if __name__ == "__main__":
    main()

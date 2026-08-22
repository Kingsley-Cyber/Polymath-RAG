"""P0-B — hang-death detection in the supervisor.

A process that EXITS is easy to notice. A process that stays alive while
its inference path is wedged answered `/manifest` for 16 hours and
stalled an entire corpus. Readiness must therefore be probed
periodically, must be judged on the body as well as the status code, and
must restart the slot under a bounded policy that cannot storm.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "control"))

from control.process_supervisor import Slot, Supervisor  # noqa: E402


class _Proc:
    def __init__(self):
        self.terminated = False
        self.pid = 4242

    def poll(self):
        return None            # alive throughout: this is a HANG, not a death

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.terminated = True


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {"ready": True}

    def json(self):
        return self._payload


@pytest.fixture()
def sup(monkeypatch):
    s = Supervisor.__new__(Supervisor)
    s.slots = [Slot(name="sidecar_embedder", module="", argv=["true"],
                    cwd=".", health_url="http://127.0.0.1:8742/ready")]
    s.slots[0].proc = _Proc()
    s.max_restarts = 5
    s.window_s = 300.0
    s.probe_timeout_s = 5.0
    s.readiness_interval_s = 0.0        # probe on every tick under test
    s.readiness_failures_before_restart = 3
    s.backoff_s = 0.0
    s.dsn = ""
    s.health_timeout_s = 1.0
    s.state_path = Path("/tmp/_sup_test_state.json")
    s.spawned = []
    monkeypatch.setattr(Supervisor, "_spawn",
                        lambda self, slot: self.spawned.append(slot.name))
    monkeypatch.setattr(Supervisor, "_quarantine",
                        lambda self, slot, why: setattr(slot, "quarantined", True))
    return s


def _probe(monkeypatch, resp=None, exc=None):
    import httpx

    def fake_get(url, **kw):
        if exc is not None:
            raise exc
        return resp
    monkeypatch.setattr(httpx, "get", fake_get)


def test_ready_sidecar_is_left_alone(sup, monkeypatch):
    _probe(monkeypatch, _Resp(200, {"ready": True}))
    for _ in range(5):
        sup.tick()
    assert sup.spawned == []
    assert not sup.slots[0].proc.terminated


def test_wedged_sidecar_is_restarted_after_bounded_failures(sup, monkeypatch):
    """503 from a real-inference probe: alive, but unusable."""
    _probe(monkeypatch, _Resp(503, {"ready": False, "reason": "forward pass failed"}))
    sup.tick(); sup.tick()
    assert sup.spawned == [], "restarted before the failure budget was spent"
    sup.tick()
    assert sup.spawned == ["sidecar_embedder"]
    assert sup.slots[0].proc.terminated


def test_two_hundred_ok_but_not_ready_still_counts_as_wedged(sup, monkeypatch):
    """Older sidecar builds answer 200 while reporting ready=false; the
    body is what matters."""
    _probe(monkeypatch, _Resp(200, {"ready": False}))
    for _ in range(3):
        sup.tick()
    assert sup.spawned == ["sidecar_embedder"]


def test_probe_exception_counts_as_not_ready(sup, monkeypatch):
    """A hung forward pass makes the probe time out — that IS the signal."""
    import httpx
    _probe(monkeypatch, exc=httpx.ReadTimeout("probe timed out"))
    for _ in range(3):
        sup.tick()
    assert sup.spawned == ["sidecar_embedder"]


def test_transient_failure_does_not_restart(sup, monkeypatch):
    """One slow response under load must not cause a restart storm."""
    import httpx
    _probe(monkeypatch, exc=httpx.ReadTimeout("slow"))
    sup.tick(); sup.tick()
    _probe(monkeypatch, _Resp(200, {"ready": True}))
    sup.tick()
    _probe(monkeypatch, exc=httpx.ReadTimeout("slow again"))
    sup.tick(); sup.tick()
    assert sup.spawned == [], "failure counter did not reset after recovery"


def test_readiness_restarts_are_bounded_and_then_quarantine(sup, monkeypatch):
    _probe(monkeypatch, _Resp(503, {"ready": False}))
    for _ in range(3 * 8):
        sup.tick()
        sup.slots[0].proc = _Proc()
    assert sup.slots[0].quarantined, "a permanently wedged slot must quarantine"


def test_probe_respects_its_interval(monkeypatch, sup):
    """The probe runs a real forward pass, so it must not run every tick."""
    calls = {"n": 0}

    import httpx

    def counting_get(url, **kw):
        calls["n"] += 1
        return _Resp(200, {"ready": True})
    monkeypatch.setattr(httpx, "get", counting_get)
    sup.readiness_interval_s = 3600.0
    for _ in range(10):
        sup.tick()
    assert calls["n"] == 1


def test_worker_slots_without_health_url_are_untouched(sup, monkeypatch):
    sup.slots[0].health_url = None
    import httpx
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("must not probe a worker slot")))
    for _ in range(3):
        sup.tick()
    assert sup.spawned == []

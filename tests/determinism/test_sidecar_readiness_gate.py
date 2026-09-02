"""SIDECAR-READINESS-GATE-V1: a worker that depends on a sidecar waits for
/ready (bounded) before spending an attempt; a booting sidecar is not a
stage failure. Measured 2026-09-02: project_qdrant burned 3 attempts in
8 s against an embedder the autopilot had woken in the same tick."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "workers"):
    sys.path.insert(0, str(ROOT / sub))

from polymath_shared.clients import SidecarClient


def _client() -> SidecarClient:
    return SidecarClient("http://127.0.0.1:1", timeout=1.0, require_pin=False)


def test_wait_ready_returns_once_the_sidecar_answers_and_clears_the_breaker(monkeypatch):
    c = _client()
    seq = iter([False, False, True])
    monkeypatch.setattr(c, "ready", lambda: next(seq))
    SidecarClient._refused_until[c.base_url] = 10**12          # breaker "open"
    assert c.wait_ready(timeout_s=5.0, poll_s=0.01) is True
    assert c.base_url not in SidecarClient._refused_until      # cleared on success


def test_wait_ready_gives_up_after_the_budget_without_raising(monkeypatch):
    c = _client()
    monkeypatch.setattr(c, "ready", lambda: False)
    assert c.wait_ready(timeout_s=0.05, poll_s=0.01) is False


def test_projection_worker_gates_before_the_first_embedder_call():
    src = (ROOT / "workers" / "workers" / "project_qdrant_worker.py").read_text()
    assert "client.wait_ready(" in src
    assert src.index("client.wait_ready(") < src.index("client.verify_pin()")


def test_runtime_releases_a_sidecar_unavailable_ticket_without_burning_an_attempt():
    src = (ROOT / "shared" / "polymath_shared" / "worker_runtime.py").read_text()
    assert "SidecarUnavailable" in src, "runtime must classify sidecar unavailability as transient"
    assert "_release_ticket_transient(" in src

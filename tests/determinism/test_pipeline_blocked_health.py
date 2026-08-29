"""P10 PIPELINE-BLOCKED-HEALTH — a stalled pipeline must say so.

THE DEFECT: workers that detect execution-bundle drift set
`worker_registrations.status='quarantined'` with the cause in
`last_error` and correctly refuse to claim tickets
(shared/polymath_shared/worker_runtime.py:336). Nothing read that state.
The pipeline simply stopped moving, which is indistinguishable from
"no work to do".

MEASURED cost: this stalled sentinel ingestion TWICE during the audit,
each time with zero tickets progressing and no error surfaced, and both
times it was diagnosed by hand. Measured again when this phase ran: 2 of
2 live workers quarantined under BUNDLE_STALE_CODE_DRIFT with 1 ticket
stuck — invisible until now.

THE RULE: a component that has stopped working must never look like a
component with nothing to do. BLOCKED and IDLE are different states and
must be reported differently, with the cause attached.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT):
    sys.path.insert(0, str(p))

from polymath_shared.pipeline_health import (  # noqa: E402
    BLOCKING_WORKER_STATUS,
    STATE_BLOCKED,
    STATE_HEALTHY,
    STATE_IDLE,
    pipeline_health,
)

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


class FakeConn:
    """Minimal stand-in: first execute() returns workers, second the
    queued-ticket count. Order matches pipeline_health."""

    def __init__(self, workers, queued):
        self._workers = workers
        self._queued = queued
        self._n = 0

    def execute(self, sql, params=None):
        self._n += 1
        rows = self._workers if self._n == 1 else [(self._queued,)]
        return _Result(rows)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0]


LIVE_OK = ("w1", "intake", "running", None)
LIVE_BLOCKED = ("w2", "intake", BLOCKING_WORKER_STATUS,
                "BUNDLE_STALE_CODE_DRIFT")


# ============================ THE ACCEPTANCE: DRIFT MUST READ BLOCKED
def test_bundle_drift_reports_blocked_not_idle():
    """THE MUTATION THE PHASE ASKS FOR: fingerprinted source changed
    while workers run the old bundle."""
    out = pipeline_health(FakeConn([LIVE_BLOCKED], queued=3))
    assert out["state"] == STATE_BLOCKED
    assert out["state"] != STATE_IDLE
    assert "BUNDLE_STALE_CODE_DRIFT" in out["causes"], (
        "the cause is not surfaced; an operator sees a stall with no "
        "explanation")
    assert "restarted" in out["detail"], (
        "the detail does not say what to do about it")


def test_blocked_wins_even_with_no_queued_work():
    """A quarantined worker is blocked whether or not a ticket happens
    to be queued right now. Reporting IDLE because the queue is momentarily
    empty is exactly the false negative that cost two diagnoses."""
    out = pipeline_health(FakeConn([LIVE_BLOCKED], queued=0))
    assert out["state"] == STATE_BLOCKED
    assert out["causes"] == ["BUNDLE_STALE_CODE_DRIFT"]


def test_partial_quarantine_still_reports_blocked():
    out = pipeline_health(FakeConn([LIVE_OK, LIVE_BLOCKED], queued=1))
    assert out["state"] == STATE_BLOCKED
    assert out["blocked_workers"] == 1
    assert out["live_workers"] == 2


# ================================= IDLE MUST STILL BE REPORTABLE
def test_healthy_fleet_with_work_is_healthy():
    out = pipeline_health(FakeConn([LIVE_OK], queued=5))
    assert out["state"] == STATE_HEALTHY
    assert out["causes"] == []


def test_alive_and_empty_is_idle_not_blocked():
    """The signal is only useful if IDLE stays available for the case it
    actually describes."""
    out = pipeline_health(FakeConn([LIVE_OK], queued=0))
    assert out["state"] == STATE_IDLE
    assert out["blocked_workers"] == 0


def test_no_live_workers_with_queued_work_is_blocked():
    out = pipeline_health(FakeConn([], queued=4))
    assert out["state"] == STATE_BLOCKED
    assert out["causes"] == ["NO_LIVE_WORKERS"]


def test_no_live_workers_and_no_work_is_idle():
    """An empty, quiet system is not an incident."""
    out = pipeline_health(FakeConn([], queued=0))
    assert out["state"] == STATE_IDLE


# ================================ DEAD REGISTRATIONS MUST NOT PIN IT
def test_only_live_workers_are_considered():
    """981 of 1,310 registrations in the live database are stale. If
    dead registrations counted, BLOCKED would be permanent and therefore
    meaningless."""
    src = (ROOT / "shared" / "polymath_shared"
           / "pipeline_health.py").read_text()
    assert "heartbeat_at > now() - make_interval" in src, (
        "worker liveness is no longer filtered by heartbeat; historical "
        "quarantines would pin the fleet to BLOCKED forever")


def test_endpoint_is_exposed():
    src = (ROOT / "orchestrator" / "orchestrator" / "api"
           / "health.py").read_text()
    assert '@router.get("/health/pipeline")' in src, (
        "the pipeline health endpoint is gone; the state is computable "
        "but nothing surfaces it, which was the original defect")
    assert "pipeline_health" in src


@pytest.mark.skipif(
    not os.environ.get("POLYMATH_PG_DSN") and not Path("/tmp").exists(),
    reason="postgres unavailable")
def test_live_pipeline_health_is_answerable():
    """The endpoint must return a real verdict against the real fleet,
    not raise."""
    try:
        import psycopg
        conn = psycopg.connect(DSN, connect_timeout=3)
    except Exception:
        pytest.skip("postgres unavailable")
    with conn:
        out = pipeline_health(conn)
    assert out["state"] in {STATE_BLOCKED, STATE_IDLE, STATE_HEALTHY}
    assert "detail" in out and out["detail"]
    if out["state"] == STATE_BLOCKED:
        assert out["causes"], "BLOCKED with no cause is not actionable"

"""PIPELINE-BLOCKED-HEALTH-V1 dormancy split (GAP-6) + composed CONTROL READY (GAP-1).

Provider-free, DB-free: a scripted fake connection drives `pipeline_health()` and
`control_ready()`. Asserts that a stall backlog carrying ONLY dormant diagnoses
(PENDING_ON_PREDECESSOR / PENDING_ADVANCE_BLOCKED / PENDING_OWNER_STAGE /
RUN_SETTLED_NOT_PROMOTED) can no longer pin the fleet to DEGRADED forever — the exact
live defect measured 2026-09-10 (282 open stalls, 0 queued, 0 blocked workers, state
DEGRADED) — while an ACTIVE diagnosis still degrades the fleet correctly.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import pipeline_health as PH  # noqa: E402


class _Cur:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Txn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Conn:
    """One live worker, nothing queued; `stall_rows` / `medic_rows` are scripted per test."""

    def __init__(self, stall_rows=(), medic_rows=(), workers=(("w1", "extract", "healthy", None),),
                 queued=0):
        self.stall_rows = stall_rows
        self.medic_rows = medic_rows
        self.workers = workers
        self.queued = queued

    def transaction(self):
        return _Txn()

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "FROM worker_registrations" in s:
            return _Cur(list(self.workers))
        if "WHERE status IN ('ready','leased')" in s:
            return _Cur([(self.queued,)])
        if "FROM stall_traces" in s:
            return _Cur(list(self.stall_rows))
        if "FROM medic_actions" in s:
            return _Cur(list(self.medic_rows))
        raise AssertionError(f"unscripted SQL: {s[:80]}")


def test_dormant_only_stalls_do_not_degrade_the_fleet():
    """The live GAP-6 shape: 221+32+29 dormant, 0 queued, 1 idle worker, no medic."""
    stalls = [("PENDING_ON_PREDECESSOR", 221), ("PENDING_ADVANCE_BLOCKED", 32),
              ("RUN_SETTLED_NOT_PROMOTED", 29)]
    health = PH.pipeline_health(_Conn(stall_rows=stalls, queued=0))
    assert health["stalls_open"] == 282
    assert health["stalls_active"] == 0
    assert health["stalls_dormant"] == 282
    assert health["state"] == PH.STATE_IDLE          # not DEGRADED — this is the fix


def test_one_active_diagnosis_still_degrades():
    stalls = [("PENDING_ON_PREDECESSOR", 221), ("READY_UNCLAIMED", 1)]
    health = PH.pipeline_health(_Conn(stall_rows=stalls, queued=3))
    assert health["stalls_active"] == 1
    assert health["stalls_dormant"] == 221
    assert health["state"] == PH.STATE_DEGRADED
    assert "READY_UNCLAIMED" in health["causes"][0] or any("READY_UNCLAIMED" in c for c in health["causes"])


def test_dormant_backlog_plus_live_queue_reads_healthy():
    stalls = [("RUN_SETTLED_NOT_PROMOTED", 29)]
    health = PH.pipeline_health(_Conn(stall_rows=stalls, queued=5))
    assert health["state"] == PH.STATE_HEALTHY
    assert health["stalls_dormant"] == 29                # still visible, not discarded


def test_control_ready_blocked_on_dark_sidecar():
    verdict = PH.control_ready(_Conn(queued=0), sidecars={"embedder": False, "reranker": True})
    assert verdict["state"] == "blocked"
    assert "embedder" in verdict["detail"]


def test_control_ready_ignores_optional_cloud_modal():
    verdict = PH.control_ready(_Conn(queued=0), sidecars={"cloud-modal": False, "reranker": True})
    assert verdict["state"] == "ready"


def test_control_ready_degraded_matches_pipeline_state():
    stalls = [("READY_UNCLAIMED", 2)]
    verdict = PH.control_ready(_Conn(stall_rows=stalls, queued=1), sidecars={"reranker": True})
    assert verdict["state"] == "degraded"
    assert verdict["label"] == PH.STATE_DEGRADED


def test_control_ready_blocked_on_quarantined_workers():
    workers = (("w1", "extract", "quarantined", "bundle drift"),)
    verdict = PH.control_ready(_Conn(workers=workers, queued=2), sidecars={"reranker": True})
    assert verdict["state"] == "blocked"
    assert verdict["label"] == PH.STATE_BLOCKED


def test_control_ready_ready_on_dormant_only_and_up_sidecars():
    stalls = [("PENDING_ON_PREDECESSOR", 221), ("PENDING_ADVANCE_BLOCKED", 32),
              ("RUN_SETTLED_NOT_PROMOTED", 29)]
    verdict = PH.control_ready(_Conn(stall_rows=stalls, queued=0), sidecars={"embedder": True, "reranker": True})
    assert verdict["state"] == "ready"                    # the exact live GAP-1+GAP-6 fix
    assert verdict["pipeline"]["stalls_dormant"] == 282

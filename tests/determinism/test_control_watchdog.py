"""CONTROL-HEARTBEAT-WATCHDOG-V1: the one stall the stall tracer cannot see
about itself — a control process that is alive but not completing ticks —
is caught by the supervisor from the control heartbeat, on the owner's
3-minute threshold, after a boot grace of the same length."""
import inspect
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))

from control import process_supervisor as ps
from control.process_supervisor import control_heartbeat_stale


def test_fresh_heartbeat_is_never_stale():
    assert control_heartbeat_stale(5.0, uptime_s=10_000, threshold_s=180) is False
    assert control_heartbeat_stale(179.9, uptime_s=10_000, threshold_s=180) is False


def test_stale_heartbeat_after_grace_restarts():
    assert control_heartbeat_stale(180.1, uptime_s=10_000, threshold_s=180) is True
    assert control_heartbeat_stale(3_600, uptime_s=181, threshold_s=180) is True


def test_boot_grace_masks_staleness_until_threshold_uptime():
    # a freshly spawned control has not had time to take the lease
    assert control_heartbeat_stale(3_600, uptime_s=0, threshold_s=180) is False
    assert control_heartbeat_stale(None, uptime_s=179, threshold_s=180) is False


def test_missing_heartbeat_row_counts_as_stale_after_grace():
    assert control_heartbeat_stale(None, uptime_s=181, threshold_s=180) is True


def test_decision_is_deterministic_and_pure():
    args = (200.0, 1_000.0, 180.0)
    assert all(control_heartbeat_stale(*args) is True for _ in range(50))


def test_supervisor_wiring_pins():
    """Pin the wiring, not just the helper: the readiness probe routes the
    control slot to the heartbeat check, the check reads control_owners,
    decides with the pure helper, and respawns through the budgeted path."""
    probe = inspect.getsource(ps.Supervisor._check_readiness)
    assert '_check_control_heartbeat(' in probe and 'control_probe_interval_s' in probe
    check = inspect.getsource(ps.Supervisor._check_control_heartbeat)
    assert 'control_owners' in check
    assert 'control_heartbeat_stale(' in check
    assert '_restart_allowed(' in check and '_spawn(' in check
    init = inspect.getsource(ps.Supervisor.__init__)
    assert 'stall_threshold_s' in init and 'control_probe_interval_s' in init

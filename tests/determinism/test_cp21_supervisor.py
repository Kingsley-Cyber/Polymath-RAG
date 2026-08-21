"""CP2.1 — bounded automatic restart, quarantine, observable state."""
import sys
import time

import pytest

from control.process_supervisor import Supervisor


def _script(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body)
    return str(p)


def test_dead_worker_is_detected_and_restarted(tmp_path):
    dies = _script(tmp_path, "dies.py", "import sys; sys.exit(3)\n")
    sup = Supervisor(fleet=[("w", dies)], python=sys.executable,
                     log_dir=str(tmp_path), max_restarts=50, backoff_s=0.01,
                     dsn="postgresql://nobody@127.0.0.1:1/none")
    sup.tick()                       # spawn
    time.sleep(0.4)
    sup.tick()                       # detect exit -> restart
    st = sup.state()["slots"][0]
    assert st["restarts"] >= 1 and st["last_exit_code"] == 3


def test_restart_budget_quarantines_a_crash_loop(tmp_path):
    dies = _script(tmp_path, "dies.py", "raise SystemExit(1)\n")
    sup = Supervisor(fleet=[("w", dies)], python=sys.executable,
                     log_dir=str(tmp_path), max_restarts=2, window_s=60,
                     backoff_s=0.0, dsn="postgresql://nobody@127.0.0.1:1/none")
    for _ in range(12):
        sup.tick()
        time.sleep(0.25)
        if sup.state()["slots"][0]["quarantined"]:
            break
    st = sup.state()["slots"][0]
    assert st["quarantined"] is True, "a crash loop must be surfaced, not hammered"
    # quarantine is terminal for the slot: no further spawns
    pid_before = st["pid"]
    sup.tick()
    assert sup.state()["slots"][0]["pid"] == pid_before


def test_healthy_worker_is_left_alone(tmp_path):
    lives = _script(tmp_path, "lives.py", "import time\ntime.sleep(60)\n")
    sup = Supervisor(fleet=[("w", lives)], python=sys.executable,
                     log_dir=str(tmp_path), backoff_s=0.0,
                     dsn="postgresql://nobody@127.0.0.1:1/none")
    sup.tick(); time.sleep(0.3)
    pid = sup.state()["slots"][0]["pid"]
    sup.tick(); sup.tick()
    st = sup.state()["slots"][0]
    assert st["pid"] == pid and st["restarts"] == 0 and st["alive"]
    for s in sup.slots:
        if s.proc: s.proc.terminate()


def test_state_file_is_written_for_observability(tmp_path):
    lives = _script(tmp_path, "lives.py", "import time\ntime.sleep(60)\n")
    state = tmp_path / "state.json"
    sup = Supervisor(fleet=[("w", lives)], python=sys.executable,
                     log_dir=str(tmp_path), state_path=str(state),
                     dsn="postgresql://nobody@127.0.0.1:1/none")
    sup.tick()
    assert state.exists() and '"restarts"' in state.read_text()
    for s in sup.slots:
        if s.proc: s.proc.terminate()

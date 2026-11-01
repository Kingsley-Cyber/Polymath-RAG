"""FLEET-LOG-DURABLE-V1 — fleet logs live outside /tmp, and the old path keeps working for its readers.

Measured 2026-11-01: 26 worker logs under /private/tmp/polymath_fleet were unlinked while their processes still wrote to
them (lsof link count 0) — macOS's periodic /tmp cleaner deletes files whose access time is over 3 days old, and a slot
log is opened once in append mode and never read by its writer.

Proof (every path here is under tmp_path — the real /private/tmp/polymath_fleet is never touched):
  * the default log dir is ~/PolymathRuntime/logs/fleet; POLYMATH_FLEET_LOG_DIR overrides it; POLYMATH_FLEET_DIR keeps
    its old meaning (a second instance's own dir); an explicit log_dir (tests, tools) never links anything;
  * the supervisor creates the dir, writes slot logs + state there, and the old path resolves to it:
      absent old path      -> a directory symlink (created_link);
      real old directory   -> per-entry links for the state file and each slot log; the previous log is adopted into the
                              durable dir (history kept), another component's file in it is left alone, nothing deleted;
      a symlink elsewhere  -> repointed (relinked), then idempotent (linked);
  * an unusable durable dir degrades to the old path, receipted (`log_compat.mode == "fallback"`);
  * the boot / bounce scripts share the default and no longer pre-create the old path.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

from control import process_supervisor as ps

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv(ps.FLEET_LOG_DIR_ENV, raising=False)
    monkeypatch.delenv(ps.FLEET_DIR_ENV, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def _script(tmp_path: Path, body: str) -> str:
    p = tmp_path / "w.py"
    p.write_text(body)
    return str(p)


def _sup(tmp_path, *, run_dir, **kw) -> ps.Supervisor:
    lives = _script(tmp_path, "import sys, time\nprint('new line', flush=True)\ntime.sleep(30)\n")
    return ps.Supervisor(fleet=[("w", lives)], python=sys.executable, run_dir=str(run_dir), backoff_s=0.0,
                         dsn="postgresql://nobody@127.0.0.1:1/none", **kw)


def _stop(sup: ps.Supervisor) -> None:
    for s in sup.slots:
        if s.proc:
            s.proc.terminate()
            s.proc.wait(timeout=5)


def _wait_for(path: Path, text: str, timeout: float = 5.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists() and text in path.read_text():
            return path.read_text()
        time.sleep(0.05)
    return path.read_text() if path.exists() else ""


def test_the_default_is_durable_and_outside_tmp(tmp_path):
    log_dir, run_dir = ps.resolve_fleet_dirs(env={})
    assert log_dir == tmp_path / "home" / "PolymathRuntime" / "logs" / "fleet"
    assert log_dir.is_relative_to(tmp_path / "home") and log_dir != ps.LEGACY_FLEET_DIR   # under HOME, never the cleaned /tmp path
    assert run_dir == ps.LEGACY_FLEET_DIR == Path("/private/tmp/polymath_fleet")


def test_env_overrides_and_the_old_instance_meaning(tmp_path):
    x, y = tmp_path / "x", tmp_path / "y"
    assert ps.resolve_fleet_dirs(env={ps.FLEET_LOG_DIR_ENV: str(x)}) == (x, ps.LEGACY_FLEET_DIR)
    # POLYMATH_FLEET_DIR alone = a second instance's own dir for logs + state, exactly as before: nothing to link
    assert ps.resolve_fleet_dirs(env={ps.FLEET_DIR_ENV: str(y)}) == (y, None)
    assert ps.resolve_fleet_dirs(env={ps.FLEET_LOG_DIR_ENV: str(x), ps.FLEET_DIR_ENV: str(y)}) == (x, y)
    # an explicit log_dir (tests, tools) never links an old path unless one is named
    assert ps.resolve_fleet_dirs(log_dir=str(x), env={ps.FLEET_LOG_DIR_ENV: str(y)}) == (x, None)
    assert ps.resolve_fleet_dirs(log_dir=str(x), run_dir=str(y), env={}) == (x, y)
    assert ps.resolve_fleet_dirs(log_dir=str(x), run_dir=str(x), env={}) == (x, None)


def test_the_supervisor_creates_the_dir_writes_there_and_links_an_absent_old_path(tmp_path, monkeypatch):
    durable, old = tmp_path / "rt" / "logs" / "fleet", tmp_path / "old_tmp" / "polymath_fleet"
    monkeypatch.setenv(ps.FLEET_LOG_DIR_ENV, str(durable))
    sup = _sup(tmp_path, run_dir=old)
    try:
        assert durable.is_dir() and sup.log_dir == durable and sup.state_path == durable / ps.STATE_FILE
        assert sup.log_compat["mode"] == "created_link"
        assert old.is_symlink() and os.path.realpath(old) == os.path.realpath(durable)
        sup.tick()
        assert "new line" in _wait_for(durable / "w.log", "new line")
        assert (old / "w.log").read_text() == (durable / "w.log").read_text()          # the old path reads the live log
        state = json.loads((old / ps.STATE_FILE).read_text())                          # ... and the live state
        assert [s["name"] for s in state["slots"]] == ["w"] and state["log_dir"] == str(durable)
        assert state["log_compat"]["mode"] == "created_link"
    finally:
        _stop(sup)
    again = _sup(tmp_path, run_dir=old)                                                # every boot: idempotent
    assert again.log_compat["mode"] == "linked"


def test_a_real_old_directory_gets_per_entry_links_and_keeps_the_history(tmp_path, monkeypatch):
    durable, old = tmp_path / "rt" / "fleet", tmp_path / "old_tmp" / "polymath_fleet"
    old.mkdir(parents=True)
    (old / "w.log").write_text("old line\n")                       # the previous process's log
    (old / ps.STATE_FILE).write_text('{"slots": [{"name": "stale"}]}')
    (old / "metal_lease.device").write_text("")                     # another component's file: must stay put
    monkeypatch.setenv(ps.FLEET_LOG_DIR_ENV, str(durable))
    sup = _sup(tmp_path, run_dir=old)
    try:
        assert sup.log_compat["mode"] == "per_entry" and sup.log_compat["state"] == "adopted"
        assert old.is_dir() and not old.is_symlink()                  # the directory itself is left in place
        assert (old / ps.STATE_FILE).is_symlink()
        sup.tick()
        log_text = _wait_for(durable / "w.log", "new line")
        assert log_text.startswith("old line\n") and "new line" in log_text              # adopted, then appended
        assert (old / "w.log").is_symlink() and (old / "w.log").read_text() == log_text
        assert json.loads((old / ps.STATE_FILE).read_text())["slots"][0]["name"] == "w"  # fresh state at the old path
        assert (old / "metal_lease.device").is_file() and not (old / "metal_lease.device").is_symlink()
    finally:
        _stop(sup)
    # a second boot finds the links already right; a respawn keeps appending to the same durable log
    again = _sup(tmp_path, run_dir=old)
    assert again.log_compat["mode"] == "per_entry" and again.log_compat["state"] == "linked"


def test_link_run_entry_never_deletes(tmp_path):
    old, durable = tmp_path / "old", tmp_path / "durable"
    old.mkdir()
    durable.mkdir()
    (old / "w.log").write_text("previous\n")
    (durable / "w.log").write_text("current\n")
    assert ps.link_run_entry(old, durable, "w.log") == "kept_aside"
    aside = [p for p in old.iterdir() if p.name.startswith("w.log.pre-durable-")]
    assert len(aside) == 1 and aside[0].read_text() == "previous\n"
    assert (old / "w.log").read_text() == "current\n"
    assert ps.link_run_entry(old, durable, "w.log") == "linked"
    (old / "sub").mkdir()
    assert ps.link_run_entry(old, durable, "sub") == "blocked"
    assert ps.link_run_entry(old, durable, "fresh.log") == "created"


def test_a_symlink_to_another_dir_is_repointed(tmp_path, monkeypatch):
    stale, durable, old = tmp_path / "stale", tmp_path / "durable", tmp_path / "polymath_fleet"
    stale.mkdir()
    old.symlink_to(stale, target_is_directory=True)
    monkeypatch.setenv(ps.FLEET_LOG_DIR_ENV, str(durable))
    sup = _sup(tmp_path, run_dir=old)
    assert sup.log_compat["mode"] == "relinked" and sup.log_compat["previous"] == os.path.realpath(stale)
    assert os.path.realpath(old) == os.path.realpath(durable) and stale.is_dir()


def test_an_unusable_durable_dir_falls_back_to_the_old_path_receipted(tmp_path, monkeypatch):
    blocker = tmp_path / "a_file"
    blocker.write_text("")
    old = tmp_path / "polymath_fleet"
    monkeypatch.setenv(ps.FLEET_LOG_DIR_ENV, str(blocker / "fleet"))             # mkdir fails: the parent is a file
    sup = _sup(tmp_path, run_dir=old)
    assert sup.log_dir == old and old.is_dir() and sup.run_dir is None
    assert sup.log_compat["mode"] == "fallback" and "error" in sup.log_compat
    assert sup.state()["log_compat"]["mode"] == "fallback"


def test_an_explicit_log_dir_links_nothing(tmp_path):
    sup = ps.Supervisor(fleet=[("w", "x.py")], python=sys.executable, log_dir=str(tmp_path / "logs"),
                        dsn="postgresql://nobody@127.0.0.1:1/none")
    assert sup.run_dir is None and sup.log_compat is None and (tmp_path / "logs").is_dir()
    assert sup.state_path == tmp_path / "logs" / ps.STATE_FILE


def test_the_scripts_share_the_default_and_never_pre_create_the_old_path():
    default = "$HOME/PolymathRuntime/logs/fleet"
    assert ps.default_fleet_log_dir() == Path(os.path.expanduser("~")) / "PolymathRuntime" / "logs" / "fleet"
    for name in ("boot_polymath.sh", "bounce_fleet.sh", "run_fleet_supervised.sh"):
        text = (ROOT / "scripts" / name).read_text()
        assert default in text, name
        code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        assert not re.search(r"mkdir[^\n]*(/private)?/tmp/polymath_fleet", code), name   # it would block the link
        assert "/tmp/polymath_fleet/" not in code, name                                   # lock / boot.log moved
    replay = (ROOT / "scripts" / "chat_m_replay.py").read_text()
    assert "PolymathRuntime" in replay and "POLYMATH_FLEET_LOG_DIR" in replay

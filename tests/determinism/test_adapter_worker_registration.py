"""E2 close-out — the adapter step worker is a SUPERVISED fleet slot: it registers a `worker_registrations` row with
worker_type == slot name and heartbeats (the supervisor's health gate), and the slot is declared in process_supervisor."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DSN = os.environ.get("POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def test_supervisor_declares_the_adapter_step_slot():
    src = (ROOT / "control/control/process_supervisor.py").read_text()
    assert '("adapter_step", "workers.adapter_step_worker")' in src


def test_worker_registers_and_heartbeats_as_worker_type_adapter_step():
    try:
        c = psycopg.connect(DSN, connect_timeout=3)
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"postgres unavailable: {exc}")
    if c.execute("SELECT to_regclass('public.adapter_runs')").fetchone()[0] is None:
        pytest.skip("migration 0061 not applied")
    t0 = time.time()
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'shared'}{os.pathsep}{ROOT / 'workers'}", "POLYMATH_PG_DSN": DSN}
    p = subprocess.run([sys.executable, "-m", "workers.adapter_step_worker", "--once", "--poll-s", "0.2"], cwd=ROOT / "workers", env=env,
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr[-800:]
    row = c.execute("""SELECT worker_id, status, EXTRACT(EPOCH FROM heartbeat_at), execution_bundle_hash FROM worker_registrations
                       WHERE worker_type='adapter_step' AND pid IS NOT NULL ORDER BY heartbeat_at DESC LIMIT 1""").fetchone()
    assert row and row[1] == "healthy" and float(row[2]) >= t0 - 1 and row[3], row      # fresh heartbeat after spawn (the supervisor's gate)
    c.execute("DELETE FROM worker_registrations WHERE worker_type='adapter_step' AND worker_id=%s", (row[0],)); c.commit(); c.close()

"""MEDIC-V1 regressions (owner 2026-09-05: "auto-healing when I leave or go to sleep").

Law 1  capacity re-arm: a FAILED ticket whose latest attempt error is a 429 /
       lane-refused event goes back to READY attempt 0, receipted; a ticket
       with a real error is left alone; the per-ticket daily cap refuses.
Law 2  deadlock break: a lock waiter blocked by an idle-in-transaction session
       older than the threshold is freed by terminating the blocker, receipted.
Law 3  pipeline health reports DEGRADED evidence while stall episodes are open.

Requires the dev Postgres (docker polymath-v4-postgres-1); skips otherwise.
Every mutation runs inside the test's own transaction and is rolled back,
except Law 2 which needs two real sessions and cleans up after itself.
"""
from __future__ import annotations

import os
import pathlib
import sys
import threading
import time
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("control", "shared"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from control import medic  # noqa: E402
from polymath_shared import pipeline_health as ph  # noqa: E402

DSN = os.environ.get("POLYMATH_TEST_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def _connect(autocommit=False):
    try:
        return psycopg.connect(DSN, autocommit=autocommit, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"dev postgres not reachable: {exc}")


@pytest.fixture
def conn():
    c = _connect()
    try:
        c.execute("SELECT 1 FROM medic_actions LIMIT 1")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"migration 0053 not applied: {exc}")
    yield c
    try:
        c.rollback(); c.close()
    except Exception:  # noqa: BLE001
        pass


def _seed_failed_ticket(conn, error: str) -> str:
    run_id = "run_medic_" + uuid.uuid4().hex[:12]
    tid = "tkt_medic_" + uuid.uuid4().hex[:12]
    corpus = "medic-test"
    conn.execute("INSERT INTO runs (run_id, corpus_id, status) VALUES (%s, %s, 'reconciling')", (run_id, corpus))
    conn.execute(
        """INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, event_type, attempt, status, updated_at)
           VALUES (%s, %s, %s, 'extract', 'medic_test', 3, 'failed', now() - interval '10 minutes')""",
        (tid, run_id, corpus))
    conn.execute(
        """INSERT INTO stage_attempts (run_id, stage, contract_hash, started_at, completed_at, outcome, error)
           VALUES (%s, 'extract', %s, now() - interval '9 minutes', now() - interval '8 minutes', 'failed', %s)""",
        (run_id, "h_" + uuid.uuid4().hex[:8], error))
    return tid


def test_is_capacity_error_is_a_pure_marker_match():
    assert medic.is_capacity_error("ExtractionTransportError: HTTP 429 from gemini2")
    assert medic.is_capacity_error("lane refused: LIMITER_REFUSED effective=1")
    assert not medic.is_capacity_error("ValueError: schema mismatch in extract.v2")
    assert not medic.is_capacity_error(None)


def test_capacity_failed_ticket_is_rearmed_and_receipted(conn):
    """Law 1: 429 failure → READY attempt 0 with a receipt; a real error is untouched."""
    cap = _seed_failed_ticket(conn, "ExtractionTransportError: HTTP 429 Too Many Requests (openrouter3)")
    real = _seed_failed_ticket(conn, "ValueError: extraction payload failed schema extract.v2")
    found = {t["ticket_id"] for t in medic.find_capacity_failed_tickets(conn, limit=500)}
    assert cap in found and real not in found
    out = medic.medic_pass(conn, rearm_per_tick=500, deadlock_wait_s=3600, per_ticket_daily_cap=5)
    assert out["rearmed"] >= 1
    status, attempt, owner, note = conn.execute(
        "SELECT status, attempt, lease_owner, last_error_note FROM stage_tickets WHERE ticket_id=%s", (cap,)).fetchone()
    assert (status, attempt, owner) == ("ready", 0, None)
    assert note.startswith(medic.REARM_NOTE)
    assert conn.execute("SELECT status FROM stage_tickets WHERE ticket_id=%s", (real,)).fetchone()[0] == "failed"
    kinds = [r[0] for r in conn.execute(
        "SELECT kind FROM medic_actions WHERE target=%s", (cap,)).fetchall()]
    assert kinds == ["CAPACITY_REARM"]
    # idempotent: a second pass finds nothing to do for this ticket
    assert cap not in {t["ticket_id"] for t in medic.find_capacity_failed_tickets(conn, limit=500)}


def test_daily_cap_refuses_a_ticket_that_keeps_hitting_capacity(conn):
    """Law 1b: after N re-arms in 24 h the ticket stays FAILED and the refusal is receipted."""
    tid = _seed_failed_ticket(conn, "HTTP 429")
    for _ in range(2):
        medic.record(conn, "CAPACITY_REARM", tid, {"seeded": True})
    ticket = {"ticket_id": tid, "run_id": "x", "stage": "extract", "error": "HTTP 429"}
    assert medic.rearm_ticket(conn, ticket, per_ticket_daily_cap=2) is False
    assert conn.execute("SELECT status FROM stage_tickets WHERE ticket_id=%s", (tid,)).fetchone()[0] == "failed"
    assert conn.execute("SELECT count(*) FROM medic_actions WHERE kind='CAPACITY_REARM_REFUSED' AND target=%s",
                        (tid,)).fetchone()[0] == 1


def test_idle_in_transaction_blocker_is_terminated_and_waiter_proceeds():
    """Law 2: A holds a row lock idle-in-transaction; B waits on it; the medic
    (from a third session) terminates A once both exceed the threshold; B completes."""
    a, b, m = _connect(), _connect(), _connect(autocommit=True)
    key = "medic_dl_" + uuid.uuid4().hex[:10]
    a_pid = a.info.backend_pid
    try:
        m.execute("CREATE TABLE IF NOT EXISTS medic_deadlock_probe (k text PRIMARY KEY, v int NOT NULL DEFAULT 0)")
        m.execute("INSERT INTO medic_deadlock_probe (k) VALUES (%s) ON CONFLICT DO NOTHING", (key,))
        a.execute("UPDATE medic_deadlock_probe SET v = v + 1 WHERE k = %s", (key,))   # lock held, A now idle in tx
        done: dict = {}

        def waiter():
            try:
                b.execute("UPDATE medic_deadlock_probe SET v = v + 10 WHERE k = %s", (key,))
                b.commit(); done["ok"] = True
            except Exception as exc:  # noqa: BLE001
                done["err"] = repr(exc)
        t = threading.Thread(target=waiter, daemon=True); t.start()
        time.sleep(3.5)
        assert medic.find_deadlocks(m, wait_s=3600) == [] or all(
            d["waiter_pid"] != b.info.backend_pid for d in medic.find_deadlocks(m, wait_s=3600)), "threshold not honoured"
        dls = [d for d in medic.find_deadlocks(m, wait_s=2) if d["waiter_pid"] == b.info.backend_pid]
        assert dls and dls[0]["blocker_pid"] == a.info.backend_pid, dls
        out = medic.medic_pass(m, rearm_per_tick=0, deadlock_wait_s=2)
        assert out["deadlocks_broken"] >= 1
        t.join(timeout=10)
        assert done.get("ok") is True, done
        assert m.execute("SELECT count(*) FROM medic_actions WHERE kind='DEADLOCK_BREAK' AND target=%s",
                         (str(a.info.backend_pid),)).fetchone()[0] == 1
        assert m.execute("SELECT v FROM medic_deadlock_probe WHERE k=%s", (key,)).fetchone()[0] == 10
    finally:
        for c in (a, b):
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            m.execute("DELETE FROM medic_deadlock_probe WHERE k=%s", (key,))
            m.execute("DELETE FROM medic_actions WHERE kind='DEADLOCK_BREAK' AND target=%s", (str(a_pid),))
            m.close()
        except Exception:  # noqa: BLE001
            pass


def test_open_stall_episode_surfaces_as_degradation(conn):
    """Law 3: an open, recently traced stall episode is DEGRADED evidence for /health/pipeline."""
    unit = "tkt_medic_stall_" + uuid.uuid4().hex[:10]
    conn.execute(
        """INSERT INTO stall_traces (unit_kind, unit_id, stalled_since, stage, age_s, diagnosis)
           VALUES ('ticket', %s, now() - interval '20 minutes', 'parent_enrichment', 1200, 'READY_UNCLAIMED')""", (unit,))
    d = ph._degradation(conn)
    assert d["stalls_open"] >= 1
    assert any(x.startswith("READY_UNCLAIMED") for x in d["stall_diagnoses"])
    assert ph.STATE_DEGRADED == "DEGRADED"

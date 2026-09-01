"""ENRICH-EARLY-KICK-V1 gate: the mint fires the tick intake lands
(mid-pipeline, run NOT yet promoted), exactly once — the NOT EXISTS
guard means a completed enrichment is never re-armed by the sweep —
and never fires before intake is done. DB-backed, rolled back."""
from __future__ import annotations

import pathlib
import sys
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))

from polymath_shared.settings import get_settings  # noqa: E402
from control.scheduler import auto_enrich_on_chunks  # noqa: E402


@pytest.fixture
def conn():
    c = psycopg.connect(get_settings().postgres.dsn, connect_timeout=5)
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def _mk_run(conn, tag: str, intake_status: str) -> tuple[str, str]:
    corpus = f"earlyenr-{tag}"
    run = f"run_earlyenr_{tag}"
    conn.execute(
        "INSERT INTO corpora (corpus_id, name, config_hash) "
        "VALUES (%s,%s,'t') ON CONFLICT DO NOTHING", (corpus, corpus))
    conn.execute(
        "INSERT INTO runs (run_id, corpus_id, status, metadata) "
        "VALUES (%s,%s,'intake','{}')", (run, corpus))
    conn.execute(
        "INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, "
        "event_type, status) VALUES (%s,%s,%s,'intake','intake.v1',%s)",
        (f"tkt_ee_{tag}", run, corpus, intake_status))
    return corpus, run


def _enr_ticket(conn, run):
    return conn.execute(
        "SELECT status FROM stage_tickets WHERE run_id=%s "
        "AND stage='parent_enrichment'", (run,)).fetchone()


def test_mints_once_at_intake_done_mid_pipeline(conn):
    tag = uuid.uuid4().hex[:8]
    _, run = _mk_run(conn, tag, "done")     # chain NOT complete: no
    # extract/project tickets at all — the shape moments after intake
    minted = auto_enrich_on_chunks(conn)
    assert minted >= 1
    assert _enr_ticket(conn, run) == ("ready",)
    ev = conn.execute(
        "SELECT count(*) FROM outbox_events WHERE run_id=%s "
        "AND event_type='parent_enrichment.v1'", (run,)).fetchone()[0]
    assert ev == 1

    # the sweep is FIRST-MINT-ONLY: mark the work done, sweep again —
    # it must NOT re-arm (that would re-open finished work every tick)
    conn.execute(
        "UPDATE stage_tickets SET status='done' WHERE run_id=%s "
        "AND stage='parent_enrichment'", (run,))
    auto_enrich_on_chunks(conn)
    assert _enr_ticket(conn, run) == ("done",)


def test_never_fires_before_intake_done(conn):
    tag = uuid.uuid4().hex[:8]
    _, run = _mk_run(conn, tag, "leased")   # intake still running
    auto_enrich_on_chunks(conn)
    assert _enr_ticket(conn, run) is None


def test_rescues_consumed_event_with_open_ticket(conn):
    """The 2026-09-01 stranded shape: a crash-looping handler consumed
    the delivery while the ticket stayed 'ready' — unreachable forever
    without the rescue clause."""
    tag = uuid.uuid4().hex[:8]
    corpus, run = _mk_run(conn, tag, "done")
    auto_enrich_on_chunks(conn)             # normal first mint
    # simulate the crash-burned delivery
    conn.execute(
        "UPDATE outbox_events SET delivered_at=now() WHERE run_id=%s "
        "AND event_type='parent_enrichment.v1'", (run,))
    auto_enrich_on_chunks(conn)             # rescue re-opens it
    undelivered = conn.execute(
        "SELECT count(*) FROM outbox_events WHERE run_id=%s AND "
        "event_type='parent_enrichment.v1' AND delivered_at IS NULL",
        (run,)).fetchone()[0]
    assert undelivered == 1
    assert _enr_ticket(conn, run) == ("ready",)
    # DONE tickets are never rescued back open
    conn.execute(
        "UPDATE stage_tickets SET status='done' WHERE run_id=%s "
        "AND stage='parent_enrichment'", (run,))
    conn.execute(
        "UPDATE outbox_events SET delivered_at=now() WHERE run_id=%s "
        "AND event_type='parent_enrichment.v1'", (run,))
    auto_enrich_on_chunks(conn)
    assert _enr_ticket(conn, run) == ("done",)

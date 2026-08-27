"""RECEIPT-GAP-REOPENS-TICKET-V1: a census receipt gap on a projection
stage re-opens the DONE ticket so the re-armed event is claimable.

Measured live (2026-08-26): the summary waterfall writes retrieval
summaries AFTER the first projection pass; the census flagged missing
routing receipts and re-armed project_qdrant.v1 every tick, but
claim_ticket_events requires the stage ticket to be 'ready' — the
'done' ticket made the re-drive permanently unclaimable and the run
sat in 'degraded' while every worker polled idle.

Receipts prove state; a DONE ticket whose receipts are missing is not
done.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "control", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DSN = os.environ.get(
    "POLYMATH_PG_DSN",
    "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def _pg_reachable() -> bool:
    import psycopg

    try:
        psycopg.connect(DSN, connect_timeout=3).close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_reachable(), reason="postgres unavailable (make db-up)")

RUN = "run_rgap_reopen_1"
CORPUS = "rgap_reopen_v1"


def _cleanup(conn) -> None:
    conn.execute("DELETE FROM outbox_events WHERE run_id = %s", (RUN,))
    conn.execute("DELETE FROM stage_tickets WHERE run_id = %s", (RUN,))
    conn.execute("DELETE FROM runs WHERE run_id = %s", (RUN,))
    conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (CORPUS,))


def test_receipt_gap_reopens_done_projection_ticket():
    import psycopg

    from control.census import Census, Gap
    from control.scheduler import schedule_gaps

    with psycopg.connect(DSN, autocommit=True) as conn:
        _cleanup(conn)
        conn.execute(
            "INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, 'r', 'c')",
            (CORPUS,))
        conn.execute(
            "INSERT INTO runs (run_id, corpus_id, status) VALUES (%s, %s, 'degraded')",
            (RUN, CORPUS))
        conn.execute(
            """INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage,
                   event_type, status)
               VALUES ('tick_rgap_q', %s, %s, 'project_qdrant',
                       'project_qdrant.v1', 'done'),
                      ('tick_rgap_n', %s, %s, 'project_neo4j',
                       'project_neo4j.v1', 'done')""",
            (RUN, CORPUS, RUN, CORPUS))
        try:
            census = Census()
            census.gaps.append(Gap(
                run_id=RUN, corpus_id=CORPUS, stage="project_qdrant",
                event_type="project_qdrant.v1",
                reason="5 projection receipts missing"))
            # a non-receipt gap must NOT reopen its ticket
            census.gaps.append(Gap(
                run_id=RUN, corpus_id=CORPUS, stage="project_neo4j",
                event_type="project_neo4j.v1",
                reason="stage project_neo4j missing"))

            scheduled = schedule_gaps(conn, census)
            assert scheduled >= 1

            rows = dict(conn.execute(
                "SELECT stage, status FROM stage_tickets WHERE run_id = %s",
                (RUN,)).fetchall())
            assert rows["project_qdrant"] == "ready", rows
            assert rows["project_neo4j"] == "done", rows

            # the re-armed event exists and is undelivered → claimable
            # now that the ticket is ready
            ev = conn.execute(
                """SELECT delivered_at FROM outbox_events
                   WHERE run_id = %s AND event_type = 'project_qdrant.v1'""",
                (RUN,)).fetchall()
            assert ev and all(d is None for (d,) in ev)

            # idempotent: receipts still missing next tick → stays ready,
            # no duplicate ticket, no error
            schedule_gaps(conn, census)
            rows = conn.execute(
                "SELECT COUNT(*) FROM stage_tickets WHERE run_id = %s AND stage='project_qdrant'",
                (RUN,)).fetchone()
            assert rows == (1,)
        finally:
            _cleanup(conn)

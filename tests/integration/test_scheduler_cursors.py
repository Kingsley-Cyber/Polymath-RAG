"""D7-H1: eligible-work-set keyset paging — head-of-line starvation fix.

Regression for the live 10k finding (addendum 5b): wave-2 READY tickets
beyond a full first page must be discovered via the persisted cursor,
and an empty page wraps for full-cycle coverage.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "control"))

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"
CORPUS = "d7-h1-test"


def _seed(n, status="pending"):
    with psycopg.connect(DSN) as conn:
        ids = []
        for _ in range(n):
            rid = "run_" + uuid.uuid4().hex
            conn.execute(
                """INSERT INTO runs (run_id, corpus_id, status)
                   VALUES (%s,%s,'intake')""", (rid, CORPUS))
            tid = "tkt_" + uuid.uuid4().hex
            conn.execute(
                """INSERT INTO stage_tickets (ticket_id, run_id, corpus_id,
                   stage, event_type, status)
                   VALUES (%s,%s,%s,'parent_summary',
                   'parent_summary.v1',%s)""", (tid, rid, CORPUS, status))
            ids.append(tid)
        conn.commit()
        seqs = [r[0] for r in conn.execute(
            """SELECT seq FROM stage_tickets WHERE ticket_id = ANY(%s)
               ORDER BY seq""", (ids,)).fetchall()]
    return ids, seqs


def test_head_of_line_wave2_discovered_via_cursor():
    from control.tickets import eligible_page

    _cleanup()
    old_ids, old_seqs = _seed(30)          # front of the table
    new_ids, new_seqs = _seed(5)           # wave 2 beyond the first page

    with psycopg.connect(DSN) as conn:
        # first page (limit 10 < 30 old rows): only OLD tickets visible
        page1, cursor1 = eligible_page(conn, stage="parent_summary",
                                       corpus_id=CORPUS, limit=10)
        assert all(row[1] in set(old_ids) for row in page1)

        # walk pages to exhaustion; wrap-around then discovers wave-2
        seen_new = False
        for _ in range(10):
            page, _cur = eligible_page(conn, stage="parent_summary",
                                       corpus_id=CORPUS, limit=10)
            got = {row[1] for row in page}
            if got & set(new_ids):
                seen_new = True
                break
        assert seen_new, "cursor wrap must discover wave-2 tickets"

    _cleanup()


def test_empty_page_wraps_cursor():
    from control.tickets import eligible_page
    _cleanup()
    ids, _seqs = _seed(3)
    with psycopg.connect(DSN) as conn:
        page1, cur = eligible_page(conn, stage="parent_summary",
                                   corpus_id=CORPUS, limit=10)
        assert len(page1) == 3 and cur > 0
        page2, cur2 = eligible_page(conn, stage="parent_summary",
                                    corpus_id=CORPUS, limit=10)
        assert page2 == []          # exhausted -> wrap returns empty
        assert cur2 == 0


def _cleanup():
    with psycopg.connect(DSN) as c:
        c.execute("DELETE FROM stage_tickets WHERE corpus_id=%s",
                  (CORPUS,))
        c.execute("DELETE FROM scheduler_cursors WHERE corpus_id=%s",
                  (CORPUS,))
        c.execute("DELETE FROM runs WHERE corpus_id=%s", (CORPUS,))
        c.commit()

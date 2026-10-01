"""DEAD-CHAIN-NOT-IN-FLIGHT-V1 + the VERIFY-FULL-SCAN-V1 receipt restore, against Postgres.

Measured live 2026-10-01 (cinema): a duplicate upload whose intake was refused 3/3
(NEAR_DUPLICATE_DOCUMENT, 2026-09-07) left its chain PENDING behind the failed intake. Its pending
project_qdrant ticket read as "a re-drive in flight", so RECEIPT-GAP-REOPENS-TICKET-V1 never reopened
a done ticket of the corpus again: 73 runs held at reconciling for 24 days. A pending ticket behind a
FAILED predecessor is not in flight; a pending ticket whose chain is alive still is (one re-drive per
corpus and stage, STALL-2026-08-27).
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "control", ROOT / "workers", ROOT):
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

CORPUS = "rgap_deadchain_v1"
DONE, DEAD, LIVE = "run_rgap_dc_done", "run_rgap_dc_dead", "run_rgap_dc_live"


def _cleanup(conn) -> None:
    for rid in (DONE, DEAD, LIVE):
        conn.execute("DELETE FROM outbox_events WHERE run_id = %s", (rid,))
        conn.execute("DELETE FROM stage_tickets WHERE run_id = %s", (rid,))
        conn.execute("DELETE FROM runs WHERE run_id = %s", (rid,))
    conn.execute("DELETE FROM corpora WHERE corpus_id = %s", (CORPUS,))


def _ticket(conn, run_id: str, stage: str, status: str) -> None:
    from control.tickets import _STAGE_SPEC
    conn.execute(
        """INSERT INTO stage_tickets (ticket_id, run_id, corpus_id, stage, event_type, status)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (f"tkt_{run_id}_{stage}", run_id, CORPUS, stage, _STAGE_SPEC[stage][0], status))


def _setup(conn, other_run: str, other_chain: dict[str, str]) -> None:
    _cleanup(conn)
    conn.execute("INSERT INTO corpora (corpus_id, name, config_hash) VALUES (%s, 'r', 'c')", (CORPUS,))
    conn.execute("INSERT INTO runs (run_id, corpus_id, status) VALUES (%s, %s, 'reconciling')", (DONE, CORPUS))
    conn.execute("INSERT INTO runs (run_id, corpus_id, status) VALUES (%s, %s, 'intake')", (other_run, CORPUS))
    _ticket(conn, DONE, "project_qdrant", "done")
    for stage, status in other_chain.items():
        _ticket(conn, other_run, stage, status)


def _gap_census():
    from control.census import Census, Gap
    census = Census()
    census.gaps.append(Gap(run_id=DONE, corpus_id=CORPUS, stage="project_qdrant",
                           event_type="project_qdrant.v1", reason="36075 projection receipts missing"))
    return census


def _status(conn, run_id: str) -> str:
    return conn.execute("SELECT status FROM stage_tickets WHERE run_id = %s AND stage = 'project_qdrant'",
                        (run_id,)).fetchone()[0]


def test_a_pending_ticket_behind_a_failed_intake_does_not_block_the_redrive():
    import psycopg

    from control.scheduler import schedule_gaps

    with psycopg.connect(DSN, autocommit=True) as conn:
        _setup(conn, DEAD, {"intake": "failed", "extract": "pending", "profile_document": "pending",
                            "project_qdrant": "pending"})
        try:
            schedule_gaps(conn, _gap_census())
            assert _status(conn, DONE) == "ready"          # was: done forever (the dead ticket "in flight")
            assert _status(conn, DEAD) == "pending"        # the dead chain itself is untouched
        finally:
            _cleanup(conn)


def test_a_pending_ticket_of_a_live_chain_still_holds_the_one_redrive():
    import psycopg

    from control.scheduler import schedule_gaps

    with psycopg.connect(DSN, autocommit=True) as conn:
        _setup(conn, LIVE, {"intake": "done", "extract": "ready", "profile_document": "pending",
                            "project_qdrant": "pending"})
        try:
            schedule_gaps(conn, _gap_census())
            assert _status(conn, DONE) == "done"           # STALL-2026-08-27: no duplicate corpus re-drive
        finally:
            _cleanup(conn)


def test_the_restore_switches_on_only_off_receipts_with_todays_hash():
    import psycopg

    spec = importlib.util.spec_from_file_location("restore_verified_receipts",
                                                  ROOT / "scripts" / "restore_verified_receipts.py")
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    kind = "routing_procedure"
    ids = {"ok": "proc_rvr_ok", "old": "proc_rvr_oldhash", "failed": "proc_rvr_failed", "on": "proc_rvr_on"}
    rows = [(ids["ok"], R.expected_hash(kind, ids["ok"]), False, "STALE"),
            (ids["old"], "hash-of-an-older-contract", False, "STALE"),
            (ids["failed"], R.expected_hash(kind, ids["failed"]), False, "FAILED"),
            (ids["on"], R.expected_hash(kind, ids["on"]), True, "PROJECTED")]
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (list(ids.values()),))
        try:
            for eid, h, active, state in rows:
                conn.execute(
                    """INSERT INTO projection_receipts (projection, entity_kind, entity_id, receipt_hash, active, state)
                       VALUES ('qdrant', %s, %s, %s, %s, %s)""", (kind, eid, h, active, state))
            done = R.apply(conn, {kind: sorted(ids.values())})
            got = dict((r[0], (r[1], r[2])) for r in conn.execute(
                "SELECT entity_id, active, state FROM projection_receipts WHERE entity_id = ANY(%s)",
                (list(ids.values()),)).fetchall())
            assert done == {kind: 1}
            assert got[ids["ok"]] == (True, "PROJECTED")
            assert got[ids["old"]] == (False, "STALE")     # an older contract's point: the projector's job
            assert got[ids["failed"]] == (False, "FAILED")
            assert got[ids["on"]] == (True, "PROJECTED")
        finally:
            conn.execute("DELETE FROM projection_receipts WHERE entity_id = ANY(%s)", (list(ids.values()),))


def test_the_generation_barrier_ignores_a_dead_chain_but_not_a_live_one():
    """With every receipt present, cinema's barrier still counted the refused duplicate's PENDING chain
    (7 tickets behind its failed intake) and five embedder-failed runs' (20 behind a failed projection)
    as open work, so none of its 73 settled runs could be promoted."""
    import psycopg

    from control.tickets import generation_barrier

    none_missing = {"qdrant": set(), "neo4j": set()}
    with psycopg.connect(DSN, autocommit=True) as conn:
        _setup(conn, DEAD, {"intake": "failed", "extract": "pending", "profile_document": "pending",
                            "project_qdrant": "pending", "verify_projections": "pending"})
        try:
            dead = generation_barrier(conn, CORPUS, none_missing)
            assert dead["passed"] and dead["open_tickets"] == 0, dead      # was: 4 open tickets, forever
            conn.execute("INSERT INTO runs (run_id, corpus_id, status) VALUES (%s, %s, 'intake')", (LIVE, CORPUS))
            _ticket(conn, LIVE, "intake", "done")
            _ticket(conn, LIVE, "extract", "ready")
            _ticket(conn, LIVE, "profile_document", "pending")
            live = generation_barrier(conn, CORPUS, none_missing)
            assert not live["passed"] and live["open_by_status"] == {"extract/ready": 1, "profile_document/pending": 1}, live
        finally:
            _cleanup(conn)

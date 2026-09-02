"""SUMMARY-JOB-IDEMPOTENCY-V1: a re-ingest of identical bytes mints the
SAME summary_jobs ticket ids with a NEW input_hash; _ensure_job must
supersede the stale job instead of raising on the primary key (live
2026-09-02: parent_summary failed 3/3 on the Gambling re-ingest)."""
import sys
import pathlib
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers"))
sys.path.insert(0, str(ROOT / "shared"))

import psycopg
import pytest

from workers.summary_worker_impl import _ensure_job

DSN = "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath"


@pytest.fixture()
def conn():
    with psycopg.connect(DSN, autocommit=False) as c:
        yield c
        c.rollback()


def test_same_ticket_new_input_supersedes_stale_job(conn):
    corpus = "census-probe"
    conn.execute(
        """INSERT INTO corpora (corpus_id, name, config_hash, purpose)
           VALUES (%s, %s, 'probe', 'probe') ON CONFLICT (corpus_id) DO NOTHING""",
        (corpus, corpus))
    ticket = f"tkt_probe_{uuid.uuid4().hex[:12]}:parentsuffix"
    _ensure_job(conn, ticket, "PARENT_SUMMARY", corpus, "hash-old")
    conn.execute("UPDATE summary_jobs SET state='COMPLETE' WHERE ticket_id=%s", (ticket,))
    # the collision case: identical ticket, different input -> must not raise
    _ensure_job(conn, ticket, "PARENT_SUMMARY", corpus, "hash-new")
    row = conn.execute(
        "SELECT input_hash, state FROM summary_jobs WHERE ticket_id=%s", (ticket,)
    ).fetchone()
    assert row == ("hash-new", row[1]) and row[1] != "COMPLETE"
    # the idempotent case: same ticket, same input -> attempts bump, one row
    _ensure_job(conn, ticket, "PARENT_SUMMARY", corpus, "hash-new")
    n = conn.execute("SELECT count(*) FROM summary_jobs WHERE ticket_id=%s", (ticket,)).fetchone()[0]
    assert n == 1

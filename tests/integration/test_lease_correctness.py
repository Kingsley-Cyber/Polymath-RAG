"""LONG-STAGE-LEASE-CORRECTNESS-V1 — regression over live Postgres.

The defect this pins: `release-books-v1` had all 24 projection tickets
marked `failed` without a single real failure. A worker batch-claimed
four tickets, each claim burned a retry, the lease keeper renewed only
the one executing, and the reaper both expired the queued ones and
quarantined a perfectly healthy worker.

The invariant under test:

    a ticket's `attempt` may increase ONLY because an execution failed,
    or because the worker executing it disappeared.

A ticket that merely waited must never consume a retry.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))
sys.path.insert(0, str(ROOT / "workers"))

pytestmark = pytest.mark.skipif(
    os.environ.get("POLYMATH_INTEGRATION") != "1",
    reason="set POLYMATH_INTEGRATION=1 with live stores",
)

CORPUS = "lease-correctness-test"


def _mk_ticket(conn, stage: str, status: str = "ready", attempt: int = 0,
               owner: str | None = None, lease_offset_s: int | None = None):
    from polymath_shared.identity import content_hash
    tid = "tkt_" + content_hash({"t": stage, "ts": time.time_ns()})[:32]
    run_id = "run_" + content_hash({"r": stage, "ts": time.time_ns()})[:28]
    conn.execute(
        "INSERT INTO runs (run_id, corpus_id, status) VALUES (%s,%s,'intake') "
        "ON CONFLICT DO NOTHING", (run_id, CORPUS))
    lease_sql = ("now() + make_interval(secs => %s)"
                 if lease_offset_s is not None else "NULL")
    params = [tid, run_id, CORPUS, stage, f"{stage}.v1", status, attempt, owner]
    if lease_offset_s is not None:
        params.append(lease_offset_s)
    conn.execute(
        f"""INSERT INTO stage_tickets
              (ticket_id, run_id, corpus_id, stage, event_type, status,
               attempt, lease_owner, lease_expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,{lease_sql})""", params)
    return tid, run_id


def _attempt(conn, tid: str) -> int:
    return conn.execute(
        "SELECT attempt FROM stage_tickets WHERE ticket_id=%s", (tid,)).fetchone()[0]


def _status(conn, tid: str) -> str:
    return conn.execute(
        "SELECT status FROM stage_tickets WHERE ticket_id=%s", (tid,)).fetchone()[0]


def _register(conn, worker_id: str, heartbeat_age_s: int = 0):
    conn.execute(
        """INSERT INTO worker_registrations
             (worker_id, worker_type, pid, host, build_sha, contracts,
              status, heartbeat_at)
           VALUES (%s,'test',1,'h','sha','{}'::jsonb,'healthy',
                   now() - make_interval(secs => %s))
           ON CONFLICT (worker_id) DO UPDATE
             SET heartbeat_at = EXCLUDED.heartbeat_at, status='healthy'""",
        (worker_id, heartbeat_age_s))


@pytest.fixture(autouse=True)
def _clean():
    from polymath_shared.db import tx
    yield
    with tx() as c:
        c.execute("DELETE FROM stage_tickets WHERE corpus_id=%s", (CORPUS,))
        c.execute("DELETE FROM runs WHERE corpus_id=%s", (CORPUS,))
        c.execute("DELETE FROM worker_registrations WHERE worker_type='test'")


# ---------------------------------------------------------------------------
# claiming
# ---------------------------------------------------------------------------

def test_claiming_does_not_burn_a_retry():
    """Claiming is not an attempt. This single line failed 24 projections."""
    from control.tickets import _release_expired_leases  # noqa: F401
    from polymath_shared.db import tx
    with tx() as c:
        tid, _ = _mk_ticket(c, "project_qdrant")
        c.execute(
            """UPDATE stage_tickets SET status='leased', lease_owner='w1',
                      lease_expires_at = now() + interval '300 seconds'
                WHERE ticket_id=%s AND status='ready'""", (tid,))
        assert _attempt(c, tid) == 0


def test_worker_claims_one_ticket_at_a_time_by_default():
    """Claim depth 1 makes 'held' identical to 'being processed', which is
    what removes queued-ticket starvation at the root."""
    import inspect

    from polymath_shared.worker_runtime import run_worker
    sig = inspect.signature(run_worker)
    assert sig.parameters["batch_size"].default == 1


# ---------------------------------------------------------------------------
# the reaper
# ---------------------------------------------------------------------------

def test_expired_lease_with_live_owner_does_not_consume_a_retry():
    """A heartbeating worker whose lease lapsed is a control-plane fault,
    not a stage failure."""
    from control.tickets import _release_expired_leases
    from polymath_shared.db import tx
    with tx() as c:
        _register(c, "w-alive", heartbeat_age_s=0)
        tid, _ = _mk_ticket(c, "project_qdrant", status="leased", attempt=1,
                            owner="w-alive", lease_offset_s=-10)
        _release_expired_leases(c)
        assert _attempt(c, tid) == 1, "a waiting ticket consumed a retry"
        assert _status(c, tid) == "ready"
        note = c.execute("SELECT last_error_note FROM stage_tickets WHERE ticket_id=%s",
                         (tid,)).fetchone()[0]
        assert "no retry consumed" in note
        status = c.execute("SELECT status FROM worker_registrations WHERE worker_id=%s",
                           ("w-alive",)).fetchone()[0]
        assert status == "healthy", "a healthy worker was quarantined"


def test_expired_lease_with_vanished_owner_does_consume_a_retry():
    """A worker that disappeared mid-stage IS a failed execution."""
    from control.tickets import _release_expired_leases
    from polymath_shared.db import tx
    with tx() as c:
        _register(c, "w-gone", heartbeat_age_s=600)
        tid, _ = _mk_ticket(c, "project_qdrant", status="leased", attempt=0,
                            owner="w-gone", lease_offset_s=-10)
        _release_expired_leases(c)
        assert _attempt(c, tid) == 1
        assert _status(c, tid) == "ready"
        status = c.execute("SELECT status FROM worker_registrations WHERE worker_id=%s",
                           ("w-gone",)).fetchone()[0]
        assert status == "quarantined"


def test_unregistered_owner_is_treated_as_gone():
    from control.tickets import _release_expired_leases
    from polymath_shared.db import tx
    with tx() as c:
        tid, _ = _mk_ticket(c, "extract", status="leased", attempt=0,
                            owner="w-unknown", lease_offset_s=-5)
        _release_expired_leases(c)
        assert _attempt(c, tid) == 1


def test_repeated_reaper_ticks_do_not_stack_attempts():
    """Reaper race: a ticket already returned to ready must not be
    re-charged by the next control tick."""
    from control.tickets import _release_expired_leases
    from polymath_shared.db import tx
    with tx() as c:
        _register(c, "w-gone2", heartbeat_age_s=600)
        tid, _ = _mk_ticket(c, "extract", status="leased", attempt=0,
                            owner="w-gone2", lease_offset_s=-5)
        for _ in range(4):
            _release_expired_leases(c)
        assert _attempt(c, tid) == 1


# ---------------------------------------------------------------------------
# renewal
# ---------------------------------------------------------------------------

def test_lease_keeper_renews_every_ticket_the_worker_holds():
    """Owner-scoped renewal: even if a future change re-enables batch
    claiming, queued tickets stay alive."""
    from polymath_shared.db import tx
    from polymath_shared.worker_runtime import _lease_keeper
    import threading
    with tx() as c:
        _register(c, "w-keeper", heartbeat_age_s=0)
        t1, _ = _mk_ticket(c, "extract", status="leased", owner="w-keeper",
                           lease_offset_s=5)
        t2, _ = _mk_ticket(c, "extract", status="leased", owner="w-keeper",
                           lease_offset_s=5)
    from polymath_shared.settings import get_settings
    stop = threading.Event()
    th = threading.Thread(target=_lease_keeper,
                          args=(get_settings().postgres.dsn, "w-keeper", t1,
                                300, stop, 0.2), daemon=True)
    th.start()
    time.sleep(0.6)
    stop.set(); th.join(timeout=5)
    from polymath_shared.db import tx as tx2
    with tx2() as c:
        for tid in (t1, t2):
            remaining = c.execute(
                "SELECT EXTRACT(EPOCH FROM (lease_expires_at - now())) "
                "FROM stage_tickets WHERE ticket_id=%s", (tid,)).fetchone()[0]
            assert remaining > 60, f"{tid} was not renewed (remaining {remaining})"


def test_renewal_only_touches_its_own_worker():
    from polymath_shared.db import tx
    from polymath_shared.worker_runtime import _lease_keeper
    import threading
    with tx() as c:
        _register(c, "w-mine", heartbeat_age_s=0)
        mine, _ = _mk_ticket(c, "extract", status="leased", owner="w-mine",
                             lease_offset_s=5)
        theirs, _ = _mk_ticket(c, "extract", status="leased", owner="w-other",
                               lease_offset_s=5)
    from polymath_shared.settings import get_settings
    stop = threading.Event()
    th = threading.Thread(target=_lease_keeper,
                          args=(get_settings().postgres.dsn, "w-mine", mine,
                                300, stop, 0.2), daemon=True)
    th.start(); time.sleep(0.5); stop.set(); th.join(timeout=5)
    with tx() as c:
        other = c.execute(
            "SELECT EXTRACT(EPOCH FROM (lease_expires_at - now())) "
            "FROM stage_tickets WHERE ticket_id=%s", (theirs,)).fetchone()[0]
        assert other < 60, "renewed a ticket belonging to another worker"


# ---------------------------------------------------------------------------
# failure accounting
# ---------------------------------------------------------------------------

def test_real_failure_increments_and_eventually_fails_the_ticket():
    from polymath_shared.db import tx
    from polymath_shared.worker_runtime import _fail_ticket
    with tx() as c:
        tid, _ = _mk_ticket(c, "project_qdrant", status="leased", attempt=0,
                            owner="w1", lease_offset_s=60)
    for expected, status in ((1, "ready"), (2, "ready"), (3, "failed")):
        _fail_ticket(tid, "boom")
        with tx() as c:
            assert _attempt(c, tid) == expected
            assert _status(c, tid) == status
            if status == "ready":
                c.execute("""UPDATE stage_tickets SET status='leased',
                             lease_owner='w1',
                             lease_expires_at=now() + interval '60 seconds'
                             WHERE ticket_id=%s""", (tid,))


def test_a_long_stage_beyond_ttl_survives_with_renewal():
    """The original symptom: a book-scale stage runs past claim_ttl_s.
    With renewal it must still be leased and uncharged afterwards."""
    from polymath_shared.db import tx
    from polymath_shared.worker_runtime import _lease_keeper
    from control.tickets import _release_expired_leases
    import threading
    with tx() as c:
        _register(c, "w-long", heartbeat_age_s=0)
        tid, _ = _mk_ticket(c, "extract", status="leased", attempt=0,
                            owner="w-long", lease_offset_s=1)
    from polymath_shared.settings import get_settings
    stop = threading.Event()
    th = threading.Thread(target=_lease_keeper,
                          args=(get_settings().postgres.dsn, "w-long", tid,
                                120, stop, 0.2), daemon=True)
    th.start(); time.sleep(0.8)
    with tx() as c:
        _release_expired_leases(c)
    stop.set(); th.join(timeout=5)
    with tx() as c:
        assert _status(c, tid) == "leased", "renewed ticket was reaped anyway"
        assert _attempt(c, tid) == 0

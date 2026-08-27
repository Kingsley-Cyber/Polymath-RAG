"""The control plane must run at the rate it is configured to run at.

Two defects, both silent, both found by reading rather than by any
signal the system emits:

  LEASE IDENTITY   `acquire_lease` derived the owner id from
                   `datetime.now().isoformat()` on EVERY call, so each
                   tick had a different identity. The first tick won.
                   Every later tick inside the TTL found the lease
                   unexpired (DELETE no-op), got rowcount 0 from
                   `INSERT ... ON CONFLICT DO NOTHING`, then compared the
                   STORED id against a BRAND-NEW id -- which can never
                   match. The controller could not re-acquire its own
                   lease, so with tick=10s and ttl=30s it really ran at a
                   30s period and `control_heartbeats` under-reported
                   liveness threefold.

  KEEPER LOGGER    `_lease_keeper` is module-level and its only error
                   path called `log.warning(...)`, but `log` was bound
                   only inside `run_worker`. The first transient renewal
                   failure raised NameError *inside the except handler*,
                   killing the daemon thread with no join, no supervisor
                   visibility and no log line. The lease then decayed and
                   the reaper reclaimed a healthy worker's ticket.

Both are exercised here, not asserted structurally, because both live on
error and repeat paths that no existing test entered.
"""

from __future__ import annotations

import logging
import pathlib
import sys
import threading
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "control"))


# ---------------------------------------------------------------------------
# LEASE IDENTITY
# ---------------------------------------------------------------------------

def test_owner_id_is_stable_across_calls_within_a_process():
    """A controller must recognise its own lease on the next tick."""
    from control.heartbeat import ROLE, _hostname, acquire_lease, owner_id
    from control import heartbeat as H

    a = owner_id(_hostname(), ROLE, H._PROCESS_STARTED)
    time.sleep(0.01)
    b = owner_id(_hostname(), ROLE, H._PROCESS_STARTED)
    assert a == b, (
        "owner id changes between calls; the controller cannot recognise "
        "the lease it already holds and will idle until the TTL expires")


def test_reacquire_within_ttl_succeeds_and_extends():
    """The second tick must return True, not wait out the TTL."""
    from control.heartbeat import acquire_lease

    class FakeCur:
        def __init__(self, store):
            self.store = store

    class FakeConn:
        """Minimal control_leases semantics: insert-if-absent, delete-if-expired."""

        def __init__(self):
            self.lease: tuple[str, float] | None = None
            self.updates = 0

        def execute(self, sql, args=()):
            s = " ".join(sql.split())
            outer = self

            class R:
                rowcount = 0

                def fetchone(self_inner):
                    return (outer.lease[0],) if outer.lease else None

            r = R()
            if s.startswith("INSERT INTO control_owners"):
                return r
            if s.startswith("DELETE FROM control_leases"):
                if self.lease and self.lease[1] < time.time():
                    self.lease = None
                return r
            if s.startswith("INSERT INTO control_leases"):
                if self.lease is None:
                    self.lease = (args[0], time.time() + 30)
                    r.rowcount = 1
                return r
            if s.startswith("UPDATE control_leases"):
                self.updates += 1
                if self.lease:
                    self.lease = (self.lease[0], time.time() + 30)
                return r
            if s.startswith("SELECT owner_id FROM control_leases"):
                return r
            return r

    conn = FakeConn()
    first, oid1 = acquire_lease(conn, lease_ttl_s=30)
    second, oid2 = acquire_lease(conn, lease_ttl_s=30)
    third, _ = acquire_lease(conn, lease_ttl_s=30)

    assert first is True, "first acquisition failed"
    assert second is True, (
        "the holder could not re-acquire its own unexpired lease; two of "
        "every three ticks become no-ops and the control plane runs at a "
        "third of its configured rate")
    assert third is True
    assert oid1 == oid2, "owner id changed between ticks"
    assert conn.updates >= 2, (
        "re-acquisition did not EXTEND the lease; a continuously ticking "
        "holder would still let its own lease lapse")


# ---------------------------------------------------------------------------
# KEEPER LOGGER
# ---------------------------------------------------------------------------

def test_worker_runtime_binds_a_module_level_logger():
    from polymath_shared import worker_runtime as wr

    assert isinstance(getattr(wr, "log", None), logging.Logger), (
        "worker_runtime has no module-level `log`; _lease_keeper's except "
        "branch raises NameError and kills the keeper thread")


def test_lease_keeper_survives_a_renewal_failure(monkeypatch):
    """One transient DB error must not kill the keeper.

    This is the actual regression: the thread died inside its own error
    handler, so the failure that was supposed to be logged and retried
    instead removed the mechanism that would have retried it.
    """
    import psycopg

    from polymath_shared import worker_runtime as wr

    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("transient database blip")

    # The keeper does `import psycopg as _psycopg` INSIDE the function and
    # calls `_psycopg.connect(...)` each round, so the connect symbol is
    # what has to fail. Patching a wrapper would leave the real error path
    # untested -- which is exactly how this defect survived until now.
    monkeypatch.setattr(psycopg, "connect", boom)

    stop = threading.Event()
    t = threading.Thread(
        target=wr._lease_keeper,
        args=("postgresql://unused", "worker-1", "tkt-1", 300, stop),
        kwargs={"interval_s": 0.01},
        daemon=True,
    )
    t.start()
    time.sleep(0.25)
    alive = t.is_alive()
    stop.set()
    t.join(timeout=2.0)

    assert calls["n"] >= 2, (
        f"keeper made {calls['n']} renewal attempt(s); it died on the first "
        f"error instead of retrying")
    assert alive, (
        "lease keeper thread died on a transient renewal failure; the lease "
        "then decays to expiry and the reaper reclaims a healthy worker's "
        "ticket mid-stage")

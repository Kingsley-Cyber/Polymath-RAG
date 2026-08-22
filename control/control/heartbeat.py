"""Controller heartbeat + lease (PLAN Phase E).

The lease is a Postgres row, not a wall-clock race (ISSUES_REPORT §2.2):
acquire is INSERT ON CONFLICT with an expiry predicate; renew is an
UPDATE gated on the owner. The heartbeat row is append-only evidence
for "the control plane was alive at time T".
"""
from __future__ import annotations

import datetime as dt
import socket

from psycopg import Connection

from polymath_shared.identity import owner_id

ROLE = "control"


def _hostname() -> str:
    return socket.gethostname()


#: This process's identity, fixed at import.
#:
#: It was previously recomputed on EVERY acquire_lease() call from
#: `datetime.now().isoformat()`, so each tick produced a different owner
#: id. The first tick inserted and won. Every later tick within the TTL
#: found the lease unexpired (so the DELETE was a no-op), got rowcount 0
#: from `INSERT ... ON CONFLICT DO NOTHING`, and then compared the STORED
#: id against a BRAND-NEW id -- which can never match. The controller
#: could not re-acquire its own lease.
#:
#: With tick_interval_s=10 and lease_ttl_s=30 that meant two of every
#: three ticks were no-ops and the control plane really ran at a 30s
#: period: ticket advancement, the expired-lease reaper and the stale
#: worker sweep all inherited it, and control_heartbeats under-reported
#: liveness threefold -- which is the signal the acceptance harness reads.
_PROCESS_STARTED = dt.datetime.now(dt.timezone.utc).isoformat()


def acquire_lease(conn: Connection, *, lease_ttl_s: int) -> tuple[bool, str]:
    """Claim the single-controller lease. Returns (acquired, owner_id).

    Idempotent within a process: a holder re-acquiring its own lease
    EXTENDS it rather than failing, because the owner id is stable.
    """
    host = _hostname()
    oid = owner_id(host, ROLE, _PROCESS_STARTED)
    now = dt.datetime.now(dt.timezone.utc)
    expires = now + dt.timedelta(seconds=lease_ttl_s)

    conn.execute(
        """
        INSERT INTO control_owners (owner_id, hostname, role, started_at, last_seen_at)
        VALUES (%s, %s, %s, now(), now())
        ON CONFLICT (owner_id) DO UPDATE SET last_seen_at = now()
        """,
        (oid, host, ROLE),
    )
    conn.execute(
        """
        DELETE FROM control_leases
         WHERE lease_key = 'control:primary'
           AND expires_at < now()
        """,
    )
    inserted = conn.execute(
        """
        INSERT INTO control_leases (lease_key, owner_id, acquired_at, expires_at)
        VALUES ('control:primary', %s, now(), %s)
        ON CONFLICT (lease_key) DO NOTHING
        """,
        (oid, expires),
    ).rowcount
    if inserted:
        return True, oid

    held = conn.execute(
        "SELECT owner_id FROM control_leases WHERE lease_key = 'control:primary'"
    ).fetchone()
    if held is not None and held[0] == oid:
        # We already hold it: extend rather than merely reporting success,
        # so a holder that keeps ticking never lets its own lease lapse.
        conn.execute(
            """
            UPDATE control_leases SET expires_at = %s
             WHERE lease_key = 'control:primary' AND owner_id = %s
            """,
            (expires, oid),
        )
        return True, oid
    return False, oid


def renew_lease(conn: Connection, owner: str, *, lease_ttl_s: int) -> bool:
    conn.execute(
        "UPDATE control_owners SET last_seen_at = now() WHERE owner_id = %s", (owner,)
    )
    updated = conn.execute(
        """
        UPDATE control_leases
           SET expires_at = now() + (%s || ' seconds')::interval
         WHERE lease_key = 'control:primary' AND owner_id = %s
        """,
        (lease_ttl_s, owner),
    ).rowcount
    return updated > 0


def record_heartbeat(conn: Connection, owner: str, *, tick_ok: bool, census_size: int) -> None:
    conn.execute(
        """
        INSERT INTO control_heartbeats (control_id, occurred_at, last_tick_ok, last_census_size)
        VALUES (%s, now(), %s, %s)
        """,
        (owner, tick_ok, census_size),
    )

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


def acquire_lease(conn: Connection, *, lease_ttl_s: int) -> tuple[bool, str]:
    """Claim the single-controller lease. Returns (acquired, owner_id)."""
    host = _hostname()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    oid = owner_id(host, ROLE, started)
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
    return held is not None and held[0] == oid, oid


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

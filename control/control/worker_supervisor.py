"""CONTROL-PLANE-V2 worker supervisor (ADR-0014).

Worker lifecycle visibility: stale detection, fleet status,
lease-timeout quarantine. The supervisor MARKS; automatic restart
stays a V2.1 item. (The sidecar supervisor stub lives in
supervisor.py — different concern.)
"""
from __future__ import annotations

from psycopg import Connection

from polymath_shared.execution import STALE_AFTER_S


def mark_stale_workers(conn: Connection) -> list[str]:
    rows = conn.execute(
        """
        UPDATE worker_registrations SET status='stale'
         WHERE status='healthy'
           AND heartbeat_at < now() - make_interval(secs => %s)
         RETURNING worker_id
        """,
        (STALE_AFTER_S,),
    ).fetchall()
    return [r[0] for r in rows]


def revoke_leases_for(conn: Connection, worker_id: str) -> int:
    rows = conn.execute(
        """
        UPDATE stage_tickets SET status='ready', lease_owner=NULL,
               lease_expires_at=NULL, updated_at=now()
         WHERE lease_owner=%s AND status='leased'
        """,
        (worker_id,),
    )
    return rows.rowcount or 0


def fleet_status(conn: Connection) -> dict:
    rows = conn.execute(
        "SELECT worker_type, status, COUNT(*) FROM worker_registrations "
        "GROUP BY 1,2 ORDER BY 1,2"
    ).fetchall()
    return {
        "fleet": {f"{t}/{s}": c for t, s, c in rows},
        "summary": {
            "healthy": sum(c for t, s, c in rows if s == "healthy"),
            "stale": sum(c for t, s, c in rows if s == "stale"),
            "quarantined": sum(c for t, s, c in rows if s == "quarantined"),
        },
    }


#: REGISTRATION-RETENTION-V1 (2026-09-03): every spawn registers a new
#: worker_id and nothing ever deleted the row — 3,145 dead registrations
#: (pids long gone) sat beside 1 live one and the build fence listed them
#: as stale workers. A registration whose heartbeat is older than this is
#: a dead process; keep 24 h for forensics, then drop it.
REGISTRATION_RETENTION_S = 24 * 3600


def prune_dead_registrations(conn: Connection, retention_s: int = REGISTRATION_RETENTION_S) -> int:
    cur = conn.execute(
        """DELETE FROM worker_registrations
            WHERE heartbeat_at < now() - make_interval(secs => %s)""",
        (retention_s,))
    return cur.rowcount or 0


def sweep(conn: Connection) -> dict:
    """One supervision pass: mark stale, revoke their leases, prune the dead."""
    stale = mark_stale_workers(conn)
    revoked = sum(revoke_leases_for(conn, w) for w in stale)
    pruned = prune_dead_registrations(conn)
    return {"stale": stale, "revoked_leases": revoked, "pruned_registrations": pruned}

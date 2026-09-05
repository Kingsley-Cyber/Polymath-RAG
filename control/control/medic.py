"""MEDIC-V1 (owner 2026-09-05: "I need this auto-healing and correcting itself
when I leave or go to sleep").

The stall tracer diagnoses; the medic ACTS on the failure classes measured on
the 63-document `cinema` ingest, each action bounded, idempotent and receipted
in `medic_actions` (migration 0053):

  1. CAPACITY_REARM   — a ticket FAILED whose latest attempt error is a provider
                        capacity event (HTTP 429 / lane refused / LIMITER_REFUSED)
                        goes back to READY with attempt 0. Pacing is never a
                        document failure. Per-ticket cap per day, per-tick cap.
  2. DEADLOCK_BREAK   — a session waiting on a row lock for longer than the wait
                        threshold whose blocker is `idle in transaction` for at
                        least as long: the blocker is terminated (its transaction
                        rolls back; the waiter proceeds). Postgres cannot see
                        these cycles when one edge is a Python wait.

Everything here is a FACT computed from state; thresholds come from
ControlSettings (POLYMATH_CONTROL_MEDIC_*). Evidence-only failures of the
medic never abort the control tick (it runs in its own savepoint).
"""
from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger("polymath-control")

CAPACITY_MARKERS = ("HTTP 429", "429 Too Many Requests", "lane refused", "LIMITER_REFUSED")
REARM_NOTE = "MEDIC re-armed: provider capacity event (HTTP 429 / lane refused) is not a document failure"


def is_capacity_error(text: str | None) -> bool:
    t = text or ""
    return any(m in t for m in CAPACITY_MARKERS)


def record(conn, kind: str, target: str, detail: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO medic_actions (kind, target, detail) VALUES (%s, %s, %s)",
        (kind, target, json.dumps(detail or {}, default=str)))


def rearms_today(conn, ticket_id: str) -> int:
    return conn.execute(
        """SELECT count(*) FROM medic_actions
            WHERE kind = 'CAPACITY_REARM' AND target = %s
              AND at > now() - interval '24 hours'""", (ticket_id,)).fetchone()[0]


def find_capacity_failed_tickets(conn, limit: int = 20) -> list[dict]:
    """FAILED tickets whose most recent attempt error is a capacity event."""
    rows = conn.execute(
        """
        SELECT t.ticket_id, t.run_id, t.stage, t.attempt, t.last_error_note,
               (SELECT a.error FROM stage_attempts a
                 WHERE a.run_id = t.run_id AND a.stage = t.stage
                 ORDER BY a.started_at DESC LIMIT 1) AS last_attempt_error
          FROM stage_tickets t
         WHERE t.status = 'failed' AND t.archived_at IS NULL
         ORDER BY t.updated_at ASC
         LIMIT %s
        """, (limit * 4,)).fetchall()
    out = []
    for tid, run_id, stage, attempt, note, err in rows:
        if is_capacity_error(err) or is_capacity_error(note):
            out.append({"ticket_id": tid, "run_id": run_id, "stage": stage, "attempt": attempt,
                        "error": (err or note or "")[:200]})
        if len(out) >= limit:
            break
    return out


def rearm_ticket(conn, ticket: dict, per_ticket_daily_cap: int = 5) -> bool:
    tid = ticket["ticket_id"]
    prior = rearms_today(conn, tid)
    if prior >= per_ticket_daily_cap:
        record(conn, "CAPACITY_REARM_REFUSED", tid,
               {"reason": f"{prior} re-arms in 24h reached the cap", "stage": ticket.get("stage")})
        return False
    n = conn.execute(
        """UPDATE stage_tickets
              SET status = 'ready', attempt = 0, lease_owner = NULL, lease_expires_at = NULL,
                  last_error_note = %s, updated_at = now()
            WHERE ticket_id = %s AND status = 'failed'""",
        (f"{REARM_NOTE} (#{prior + 1} today)", tid)).rowcount
    if n:
        record(conn, "CAPACITY_REARM", tid, {"run_id": ticket.get("run_id"), "stage": ticket.get("stage"),
                                             "error": ticket.get("error"), "rearm_no": prior + 1})
        log.warning("medic: re-armed %s (%s) after capacity event", tid[:20], ticket.get("stage"),
                    extra={"error_code": "MEDIC_CAPACITY_REARM"})
    return bool(n)


def find_deadlocks(conn, wait_s: int = 120) -> list[dict]:
    """Waiter on a lock ≥ wait_s whose blocker is idle in transaction ≥ wait_s."""
    rows = conn.execute(
        """
        SELECT w.pid, b.pid, w.wait_event,
               extract(epoch FROM now() - w.query_start)::int,
               extract(epoch FROM now() - b.state_change)::int,
               left(regexp_replace(w.query, '\\s+', ' ', 'g'), 160),
               left(regexp_replace(b.query, '\\s+', ' ', 'g'), 160),
               b.application_name
          FROM pg_stat_activity w
          JOIN LATERAL unnest(pg_blocking_pids(w.pid)) AS bp(pid) ON true
          JOIN pg_stat_activity b ON b.pid = bp.pid
         WHERE w.datname = current_database()
           AND w.wait_event_type = 'Lock'
           AND now() - w.query_start > make_interval(secs => %s)
           AND b.state LIKE 'idle in transaction%%'
           AND now() - b.state_change > make_interval(secs => %s)
           AND w.pid <> pg_backend_pid() AND b.pid <> pg_backend_pid()
        """, (wait_s, wait_s)).fetchall()
    return [{"waiter_pid": r[0], "blocker_pid": r[1], "wait_event": r[2], "waiter_wait_s": r[3],
             "blocker_idle_s": r[4], "waiter_query": r[5], "blocker_query": r[6], "blocker_app": r[7]}
            for r in rows]


def break_deadlock(conn, dl: dict) -> bool:
    ok = conn.execute("SELECT pg_terminate_backend(%s)", (dl["blocker_pid"],)).fetchone()[0]
    record(conn, "DEADLOCK_BREAK", str(dl["blocker_pid"]), dict(dl, terminated=bool(ok)))
    log.error("medic: terminated idle-in-transaction blocker pid %s (waiter %s waited %ss on %s)",
              dl["blocker_pid"], dl["waiter_pid"], dl["waiter_wait_s"], dl["wait_event"],
              extra={"error_code": "MEDIC_DEADLOCK_BREAK"})
    return bool(ok)


def medic_pass(conn, *, rearm_per_tick: int = 20, deadlock_wait_s: int = 120,
               per_ticket_daily_cap: int = 5, enabled: bool = True) -> dict[str, Any]:
    if not enabled:
        return {"enabled": False}
    out: dict[str, Any] = {"enabled": True, "rearmed": 0, "rearm_refused": 0, "deadlocks_broken": 0}
    for t in find_capacity_failed_tickets(conn, limit=rearm_per_tick):
        if rearm_ticket(conn, t, per_ticket_daily_cap):
            out["rearmed"] += 1
        else:
            out["rearm_refused"] += 1
    for dl in find_deadlocks(conn, wait_s=deadlock_wait_s):
        if break_deadlock(conn, dl):
            out["deadlocks_broken"] += 1
    return out


def recent_actions(conn, minutes: int = 15) -> list[dict]:
    rows = conn.execute(
        """SELECT kind, target, at, detail FROM medic_actions
            WHERE at > now() - make_interval(mins => %s) ORDER BY at DESC LIMIT 20""", (minutes,)).fetchall()
    return [{"kind": k, "target": t, "at": str(a), "detail": d} for k, t, a, d in rows]

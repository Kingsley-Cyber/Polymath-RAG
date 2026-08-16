"""The control plane — a separate process (ADR-0004, ISSUES_REPORT §4.2).

Owns: census, scheduling, recovery, heartbeat. Never: inference, user
requests, workflow authority writes other than scheduling and status
transitions. The orchestrator can crash and this keeps ticking; this
can crash and the orchestrator keeps serving.

Tick cycle (all in one Postgres transaction):
  1. acquire/renew the primary lease
  2. census: desired vs observed stage attempts
  3. schedule: gaps -> outbox events (idempotent)
  4. promotions / failures
  5. heartbeat
"""
from __future__ import annotations

import logging
import time

import psycopg

from polymath_shared.db import tx
from polymath_shared.logging import configure_logging
from polymath_shared.settings import get_settings
from control.census import compute_census
from control.heartbeat import acquire_lease, record_heartbeat, renew_lease
from control.scheduler import apply_failures, apply_promotions, schedule_gaps

log = logging.getLogger("control")


def tick() -> dict:
    settings = get_settings()
    acquired, owner = None, None
    with tx() as conn:
        acquired, owner = acquire_lease(conn, lease_ttl_s=settings.control.lease_ttl_s)
        if not acquired:
            return {"tick": "skipped", "reason": "lease not held"}

        # CONTROL-PLANE-V2 (ADR-0014): ticket DAG creation (backpressure-
        # gated), explicit-handoff advancement, worker supervision, and
        # generation-barrier-gated promotion — in the same transaction as
        # the legacy census path (which still drives failure retries).
        from control import tickets as cp2_tickets
        from control.worker_supervisor import sweep as supervise

        ensured = _ensure_tickets_backpressure_gated(conn)
        advanced = cp2_tickets.advance_tickets(conn)
        supervised = supervise(conn)
        census = compute_census(conn, max_attempts=settings.control.max_attempts)
        # The legacy scheduler still drives FAILED-stage retries (its
        # events are idempotent against ticket events by content hash).
        scheduled = schedule_gaps(conn, census)
        barrier = _barrier_or_none(conn, census)
        if barrier is None:
            apply_promotions(conn, census)
        apply_failures(conn, census)
        record_heartbeat(conn, owner, tick_ok=True, census_size=len(census.gaps))
        return {
            "tick": "ok",
            "owner": owner[:12],
            "gaps": len(census.gaps),
            "scheduled": scheduled,
            "promoted": len(census.promote),
            "failed": len(census.fail),
        }


def _ensure_tickets_backpressure_gated(conn) -> int:
    """Create ticket chains for active runs that lack them; pause NEW
    chains while a downstream stage's queue is at the high watermark
    (backpressure — existing chains always complete)."""
    from control.tickets import (
        backpressure_paused,
        ensure_run_tickets,
    )
    from polymath_shared.execution import default_execution_contract

    if backpressure_paused(conn):
        return 0
    rows = conn.execute(
        """
        SELECT r.run_id, r.corpus_id FROM runs r
        WHERE r.status IN ('intake', 'reconciling', 'degraded')
          AND NOT EXISTS (SELECT 1 FROM stage_tickets t WHERE t.run_id = r.run_id)
        ORDER BY r.created_at LIMIT 32
        """
    ).fetchall()
    ensured = 0
    for run_id, corpus_id in rows:
        ensured += len(ensure_run_tickets(
            conn, run_id, corpus_id, default_execution_contract()))
    return ensured


def _barrier_or_none(conn, census) -> dict | None:
    """Generation barrier (ADR-0014): block promotion of any corpus whose
    ticket chains are not fully DONE with desired==actual projections.
    Returns the blocking verdict, or None when promotion may proceed."""
    from control.tickets import generation_barrier

    corpora = {gap.corpus_id for gap in census.gaps} | set(census.promote)
    for corpus_id in sorted(corpora):
        verdict = generation_barrier(conn, corpus_id)
        if not verdict["passed"]:
            return verdict
    return None


def run_forever() -> None:
    configure_logging("polymath-control")
    settings = get_settings()
    while True:
        started = time.monotonic()
        try:
            result = tick()
            if result.get("tick") == "ok":
                log.info("control tick", extra={
                    "stage": "control",
                    "duration_ms": int((time.monotonic() - started) * 1000),
                })
        except psycopg.errors.OperationalError as exc:
            log.warning("postgres unavailable; backing off", extra={"error_code": "pg_unavailable"})
        except Exception as exc:
            log.exception("control tick failed", extra={"error_code": type(exc).__name__})
        time.sleep(settings.control.tick_interval_s)


if __name__ == "__main__":
    run_forever()

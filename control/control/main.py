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

        census = compute_census(conn, max_attempts=settings.control.max_attempts)
        scheduled = schedule_gaps(conn, census)
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

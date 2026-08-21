"""CONTROL-PLANE-V2 worker runtime (ADR-0014).

One worker loop for the whole fleet: register identity, heartbeat,
claim ONLY ticket-gated work that is READY and compatible with this
worker's build/contracts, execute, mark the ticket done. Workers
become dumb executors of exactly-scoped legal work units; the control
plane owns what happens next.

Compatibility: events without a ticket row pass through (legacy
in-process harnesses); events with a ticket require status='ready'
and contract compatibility with the run's pinned execution contract.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

import psycopg

from polymath_shared.db import tx
from polymath_shared.execution import (
    compatible,
    heartbeat,
    register_worker,
    worker_identity,
)
from polymath_shared.logging import configure_logging
from polymath_shared.receipts import StageFailed

LEASE_SECONDS = 300


def claim_ticket_events(conn, identity: dict, event_types: list[str], limit: int) -> list[dict]:
    """Claim undelivered events gated by ticket readiness + worker
    compatibility. Leases the ticket for LEASE_SECONDS."""
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """
            SELECT e.event_id, e.run_id, e.event_type, e.payload, e.idempotency_key,
                   t.ticket_id, t.status AS ticket_status,
                   r.execution_contract::text AS execution_contract
              FROM outbox_events e
              LEFT JOIN stage_tickets t
                ON t.run_id = e.run_id AND t.event_type = e.event_type
              LEFT JOIN runs r ON r.run_id = e.run_id
             WHERE e.delivered_at IS NULL
               AND e.event_type = ANY(%s)
               AND (t.ticket_id IS NULL OR t.status = 'ready')
             ORDER BY e.event_id
             LIMIT %s
             FOR UPDATE OF e SKIP LOCKED
            """,
            (event_types, limit),
        )
        events = cur.fetchall()
        claimed = []
        for e in events:
            if e["ticket_id"] is not None:
                if e["ticket_status"] != "ready":
                    continue
                contract = json.loads(e["execution_contract"] or "{}")
                if contract and not compatible(identity["contracts"], contract):
                    logging.getLogger("worker-runtime").warning(
                        "lease refused: worker %s incompatible with run %s contract",
                        identity["worker_id"], e["run_id"],
                    )
                    continue
                cur.execute(
                    """
                    UPDATE stage_tickets SET status='leased', lease_owner=%s,
                           lease_expires_at = now() + make_interval(secs => %s),
                           attempt = attempt + 1, updated_at=now()
                     WHERE ticket_id=%s AND status='ready'
                    """,
                    (identity["worker_id"], LEASE_SECONDS, e["ticket_id"]),
                )
                if cur.rowcount == 0:
                    continue  # lost the ticket race
            claimed.append(dict(e))
        if claimed:
            cur.execute(
                "UPDATE outbox_events SET delivered_at=now() WHERE event_id = ANY(%s)",
                ([e["event_id"] for e in claimed],),
            )
    return claimed


def complete_ticket(conn, ticket_id: str | None) -> None:
    if not ticket_id:
        return
    conn.execute(
        "UPDATE stage_tickets SET status='done', lease_owner=NULL, "
        "lease_expires_at=NULL, updated_at=now() WHERE ticket_id=%s",
        (ticket_id,),
    )


def _lease_keeper(dsn: str, worker_id: str, ticket_id: str,
                  ttl_s: int, stop, interval_s: float = 60.0):
    """CP2.1 lease handling for LONG stages.

    A book-scale extract runs far past claim_ttl_s (300s). Without renewal
    the control plane revokes a HEALTHY worker's lease mid-stage: the ticket
    returns to ready (double-processing risk with >1 worker of a type), the
    owner is falsely quarantined, and heartbeats pause because the worker
    loop only beats BETWEEN events. This thread renews the lease and beats
    the heart WHILE processing; it stops the moment the stage finishes, so
    genuine death still expires the lease within one TTL.
    """
    import psycopg as _psycopg
    while not stop.wait(interval_s):
        try:
            with _psycopg.connect(dsn, connect_timeout=5) as conn:
                conn.execute(
                    """UPDATE stage_tickets
                          SET lease_expires_at = now() + make_interval(secs => %s)
                        WHERE ticket_id = %s AND lease_owner = %s
                          AND status = 'leased'""",
                    (ttl_s, ticket_id, worker_id))
                heartbeat(conn, worker_id, current_ticket=ticket_id)
                conn.commit()
        except Exception:
            log.warning("lease renewal failed; will retry",
                        extra={"error_code": "lease_renew_failed"})


def run_worker(worker_type: str, event_types: list[str],
               process_event: Callable[..., None],
               poll_interval_s: float = 2.0, batch_size: int = 4,
               extra_env_check: Callable[[], None] | None = None) -> None:
    """The fleet's single loop: register → heartbeat → claim gated work
    → execute → complete ticket. `process_event(conn, event)` keeps its
    existing signature and stage logic."""
    configure_logging(f"worker-{worker_type.replace('_', '-')}")
    identity = worker_identity(worker_type)
    contracts = identity["contracts"]
    log = logging.getLogger(f"worker-{worker_type}")
    registered = False
    while True:
        try:
            with tx() as conn:
                if not registered:
                    register_worker(conn, identity)
                    registered = True
                    log.info("registered", extra={
                        "worker_id": identity["worker_id"],
                        "build_sha": identity["build_sha"],
                    })
                heartbeat(conn, identity["worker_id"])
                events = claim_ticket_events(conn, identity, event_types, batch_size)
            for event in events:
                ticket_id = event.get("ticket_id")
                import threading as _threading

                from polymath_shared.settings import get_settings as _gs
                _stop = _threading.Event()
                _keeper = _threading.Thread(
                    target=_lease_keeper,
                    args=(_gs().postgres.dsn, identity["worker_id"], ticket_id,
                          _gs().worker.claim_ttl_s, _stop),
                    daemon=True)
                _keeper.start()
                try:
                    with tx() as conn:
                        heartbeat(conn, identity["worker_id"], current_ticket=ticket_id)
                        process_event(conn, event)
                        complete_ticket(conn, ticket_id)
                    with tx() as conn:
                        heartbeat(conn, identity["worker_id"],
                                  current_ticket=None, processed_count=1)
                    log.info("ticket processed", extra={
                        "run_id": event.get("run_id"), "stage": worker_type,
                        "attempt_id": (event.get("idempotency_key") or "")[:16],
                    })
                except StageFailed as exc:
                    log.error(str(exc), extra={
                        "run_id": event.get("run_id"), "stage": worker_type,
                        "error_code": "stage_failed",
                    })
                    _fail_ticket(ticket_id, str(exc))
                except Exception as exc:
                    log.exception("processing failed", extra={
                        "run_id": event.get("run_id"),
                        "error_code": type(exc).__name__,
                    })
                    _fail_ticket(ticket_id, f"{type(exc).__name__}: {exc}")
                    with tx() as conn:
                        heartbeat(conn, identity["worker_id"],
                                  last_error=f"{type(exc).__name__}: {exc}")
                finally:
                    _stop.set()
        except psycopg.errors.OperationalError:
            log.warning("postgres unavailable; backing off",
                        extra={"error_code": "pg_unavailable"})
        except Exception as exc:
            log.exception("worker loop failed", extra={"error_code": type(exc).__name__})
        time.sleep(poll_interval_s)


def _fail_ticket(ticket_id: str | None, reason: str) -> None:
    if not ticket_id:
        return
    try:
        with tx() as conn:
            conn.execute(
                """
                UPDATE stage_tickets SET
                    status = CASE WHEN attempt >= 3 THEN 'failed' ELSE 'ready' END,
                    lease_owner=NULL, lease_expires_at=NULL,
                    last_error_note = %s, updated_at=now()
                 WHERE ticket_id=%s AND status='leased'
                """,
                (reason[:500], ticket_id),
            )
    except Exception:
        pass

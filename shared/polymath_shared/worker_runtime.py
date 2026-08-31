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
import os
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

#: Module-level logger.
#:
#: `_lease_keeper` is a module-level function whose only error path called
#: `log.warning(...)`, but `log` was bound ONLY inside `run_worker`. The
#: first transient renewal failure therefore raised NameError *inside the
#: except handler*, which propagated out of the daemon thread target and
#: killed the keeper with no join, no supervisor visibility and no log
#: line. The lease then decayed to expiry and the reaper reclaimed a
#: healthy worker's ticket -- re-introducing, through the error path, the
#: exact failure LONG-STAGE-LEASE-CORRECTNESS-V1 was written to prevent.
log = logging.getLogger("worker-runtime")

#: CLAIM-STARVATION-V1. Events this process has already refused on
#: contract grounds, excluded from the next fetch so the scan advances
#: past them instead of re-reading the same head forever.
#:
#: An old `vocab-probe-v2` run pinned `semantic-query-policy-v2` and the
#: `semantic_v2` chunker -- semantics this fleet does not run, so no
#: worker could ever claim it. Because the claim query ordered by
#: event_id and took the first `limit` rows, that single permanently
#: incompatible event sat at the head of the intake queue and starved 48
#: compatible events behind it, including an entire freshly ingested
#: corpus. The fleet looked healthy: workers heartbeated, leases were
#: sound, nothing errored. It simply never claimed anything.
_REFUSED: dict[str, set[int]] = {}

#: Refusals are forgotten periodically so a deliberate semantic cutover
#: re-admits work that a previous configuration could not run.
_REFUSED_TTL_S = 900.0
_REFUSED_AT: dict[str, float] = {}


def _refused_set(worker_type: str) -> set[int]:
    now = time.time()
    if now - _REFUSED_AT.get(worker_type, 0.0) > _REFUSED_TTL_S:
        _REFUSED[worker_type] = set()
        _REFUSED_AT[worker_type] = now
    return _REFUSED.setdefault(worker_type, set())


#: Stages exempt from the run-era compatibility pin. The semantic-bundle
#: fence makes an INGEST run's processing atomic across one code era —
#: right for extraction, wrong for ADDITIVE owner-triggered stages that
#: must run over mixed-era corpora (§0b): parent enrichment's artifact
#: identity hashes its OWN inputs (children + prompt + model contract),
#: so a code-era mismatch cannot silently blur provenance.
CONTRACT_EXEMPT_EVENTS = frozenset({"parent_enrichment.v1"})


def _era_exempt(event: dict) -> bool:
    """True when this event may claim across the run-era pin: the
    enrichment stage itself, and a project_qdrant event MINTED BY the
    enrichment hand-off (payload-tagged) — latent points carry their
    own receipts + the corpus-pinned embedding contract, and receipt
    incrementality means nothing else re-projects."""
    if event.get("event_type") in CONTRACT_EXEMPT_EVENTS:
        return True
    if event.get("event_type") == "project_qdrant.v1":
        payload = event.get("payload") or {}
        return isinstance(payload, dict) and             payload.get("reason") == "latent_projection"
    return False


def claim_ticket_events(conn, identity: dict, event_types: list[str], limit: int,
                        lane_affinity: str | None = None) -> list[dict]:
    """Claim undelivered events gated by ticket readiness + worker
    compatibility. Leases the ticket for LEASE_SECONDS.

    LANE-AFFINITY-STEAL-V1 (owner 2026-08-30): when `lane_affinity` is
    "local" or "cloud", the FIRST pass claims only events whose run
    belongs to that extraction lane (a run is cloud-lane iff it contains
    at least one cloud-eligible document by the owner's byte boundary);
    when the home lane has nothing claimable, a SECOND pass claims from
    any lane — the steal — and logs it (silent-fallback accounting).
    Affinity never blocks work: an affine worker always drains the
    global queue once its own lane is dry.
    """
    lane_sql, lane_params = "", []
    if lane_affinity in ("local", "cloud"):
        from polymath_shared.llm_extraction.policy import effective_threshold
        from polymath_shared.settings import get_settings as _gs
        threshold = effective_threshold(_gs().worker.cloud_min_bytes)
        exists = ("EXISTS (SELECT 1 FROM documents d "
                  "WHERE d.corpus_id = r.corpus_id AND d.byte_length > %s)")
        lane_sql = ("AND " + exists if lane_affinity == "cloud"
                    else "AND NOT " + exists)
        lane_params = [threshold]
    refused = _refused_set(identity.get("worker_type", "?"))
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
                -- TICKET-GATE-FAIL-CLOSED-V1 (measured 2026-08-30): an
                -- event with NO ticket row used to pass through (legacy
                -- harness compatibility). The legacy census emits events
                -- for every missing stage one tick after intake, and a
                -- run whose chain is minted one tick late had nothing to
                -- hold them: SC-200 ran profile/canonicalize/neo4j/verify
                -- BEFORE extract. No ticket => not claimable (a LEFT-JOIN
                -- miss leaves t.status NULL, which fails the equality).
                -- The ONE exception is the entry stage: the orchestrator
                -- emits intake.v1 at upload, the intake stage creates the
                -- corpus row, and the ticket chain is minted only for runs
                -- whose corpus exists — intake has no predecessor, so it
                -- carries no ordering risk (measured 2026-08-30 13:32:
                -- two uploads sat in `intake` forever under the strict gate).
                AND ((t.status = 'ready' AND t.archived_at IS NULL)
                     OR (t.ticket_id IS NULL AND e.event_type = 'intake.v1'))
                AND NOT (e.event_id = ANY(%s))
                {lane_sql}
             ORDER BY CASE WHEN r.created_at > now() - interval '15 minutes'
                           THEN 0 ELSE 1 END,
                      CASE WHEN t.ticket_id IS NOT NULL
                           THEN 0 ELSE 1 END,
                      e.event_id
             LIMIT %s
             FOR UPDATE OF e SKIP LOCKED
            """.format(lane_sql=lane_sql),
            (event_types, list(refused), *lane_params, limit),
        )
        events = cur.fetchall()
        claimed = []
        for e in events:
            if e["ticket_id"] is None and e["event_type"] != "intake.v1":
                continue                    # fail closed (see the query)
            if e["ticket_id"] is not None:
                if e["ticket_status"] != "ready":
                    continue
                contract = json.loads(e["execution_contract"] or "{}")
                if (not _era_exempt(e)
                        and contract
                        and not compatible(identity["contracts"], contract)):
                    # Remember it, so the NEXT fetch scans past it rather
                    # than returning the same unclaimable head forever.
                    first_time = e["event_id"] not in refused
                    refused.add(e["event_id"])
                    if first_time:
                        logging.getLogger("worker-runtime").warning(
                            "lease refused: worker %s incompatible with run %s "
                            "contract; skipping event %s (%d refused this "
                            "window)",
                            identity["worker_id"], e["run_id"],
                            e["event_id"], len(refused),
                        )
                    continue
                # LONG-STAGE-LEASE-CORRECTNESS-V1: claiming is not an
                # attempt. `attempt` counts EXECUTIONS THAT FAILED, and is
                # incremented by _fail_ticket or by the reaper when the
                # executing worker disappears. Incrementing here burned the
                # retry budget of every ticket a worker merely queued, which
                # failed all 24 projections of release-books-v1 without a
                # single real failure.
                cur.execute(
                    """
                    UPDATE stage_tickets SET status='leased', lease_owner=%s,
                           lease_expires_at = now() + make_interval(secs => %s),
                           updated_at=now()
                     WHERE ticket_id=%s AND status='ready'
                    """,
                    (identity["worker_id"], LEASE_SECONDS, e["ticket_id"]),
                )
                if cur.rowcount == 0:
                    continue  # lost the ticket race
            # EVENT-ADAPTER-V1: normalize BEFORE handing to the stage.
            # A legacy payload that cannot be recovered fails its ticket
            # ONCE here (typed reason, attempt burned deterministically)
            # instead of crash-looping a worker on a missing key.
            from polymath_shared.event_adapter import (
                LegacyEventUnrecoverable,
                normalize_event,
            )
            try:
                e = dict(e)
                e["payload"] = normalize_event(
                    cur, e["event_type"], e["payload"], e["run_id"])
            except LegacyEventUnrecoverable as exc:
                if e.get("ticket_id") is not None:
                    cur.execute(
                        """
                        UPDATE stage_tickets
                           SET status='failed', attempt = attempt + 1,
                               lease_owner=NULL, lease_expires_at=NULL,
                               last_error_note=%s, updated_at=now()
                         WHERE ticket_id=%s AND status='leased'
                        """,
                        (exc.reason[:500], e["ticket_id"]),
                    )
                logging.getLogger("worker-runtime").error(
                    "legacy event unrecoverable; ticket failed once",
                    extra={"error_code": "LEGACY_EVENT_UNRECOVERABLE",
                           "run_id": e["run_id"],
                           "event_type": e["event_type"],
                           "detail": str(exc)[:200]})
                continue
            claimed.append(dict(e))
        if claimed:
            cur.execute(
                "UPDATE outbox_events SET delivered_at=now() WHERE event_id = ANY(%s)",
                ([e["event_id"] for e in claimed],),
            )
    if not claimed and lane_affinity in ("local", "cloud"):
        # LANE-AFFINITY-STEAL-V1: home lane dry — steal from the global
        # queue. Counted + surfaced, never silent.
        stolen = claim_ticket_events(conn, identity, event_types, limit)
        if stolen:
            logging.getLogger("worker-runtime").info(
                "lane steal: %s-affinity worker %s claimed %d event(s) "
                "from the other lane",
                lane_affinity, identity.get("worker_id", "?"), len(stolen),
                extra={"error_code": "LANE_STEAL_CLAIM"})
        return stolen
    return claimed


def complete_ticket(conn, ticket_id: str | None) -> None:
    if not ticket_id:
        return
    conn.execute(
        "UPDATE stage_tickets SET status='done', lease_owner=NULL, "
        "lease_expires_at=NULL, updated_at=now() WHERE ticket_id=%s",
        (ticket_id,),
    )


#: STAGE-DEADLINE-WATCHDOG-V1 (STALL-2026-08-27). Hard ceiling on one
#: stage execution. The keeper below renews the lease and heartbeats
#: WHILE the stage runs — which means a stage frozen inside a hung call
#: is indistinguishable from a healthy busy worker: lease never
#: expires, reaper never fires, autopilot sees the lane served.
#: MEASURED LIVE: nine workers of eight types sat wedged on one ticket
#: each for up to 4 h (tkt_1418981e wedged two successive
#: project_qdrant workers back-to-back) while the fleet froze around
#: them. The deadline must clear the longest LEGITIMATE stage — the
#: documented corpus routing pass is ~2.3 h — so the default is 4 h.
_STAGE_DEADLINE_S = float(os.environ.get("POLYMATH_STAGE_DEADLINE_S", "14400"))


def _lease_keeper(dsn: str, worker_id: str, ticket_id: str,
                  ttl_s: int, stop, interval_s: float = 60.0,
                  deadline_s: float | None = None):
    # Renews EVERY ticket this worker holds, not just the one executing.
    # With claim depth 1 that is the same set; keeping it owner-scoped is
    # defence in depth so a future batching change cannot resurrect the
    # queued-ticket starvation bug.
    """CP2.1 lease handling for LONG stages.

    A book-scale extract runs far past claim_ttl_s (300s). Without renewal
    the control plane revokes a HEALTHY worker's lease mid-stage: the ticket
    returns to ready (double-processing risk with >1 worker of a type), the
    owner is falsely quarantined, and heartbeats pause because the worker
    loop only beats BETWEEN events. This thread renews the lease and beats
    the heart WHILE processing; it stops the moment the stage finishes, so
    genuine death still expires the lease within one TTL.

    STAGE-DEADLINE-WATCHDOG-V1: renewal is NOT unconditional. Past
    `deadline_s` the stage is declared wedged: the ticket is failed with
    a typed note (burning one attempt, returning it to ready below the
    retry cap), the registration records the reason, and the PROCESS
    exits — a thread frozen in a hung C call cannot be interrupted from
    Python, so process death is the only real release. The supervisor
    respawns a clean worker; CP2.1 SIGKILL-recovery semantics make the
    abort safe (attempts roll back, receipt checkpoints survive).
    """
    import psycopg as _psycopg
    if deadline_s is None:
        deadline_s = _STAGE_DEADLINE_S
    deadline_at = time.monotonic() + deadline_s
    while not stop.wait(interval_s):
        if time.monotonic() >= deadline_at:
            reason = (f"STAGE_DEADLINE_EXCEEDED: ticket {ticket_id} ran "
                      f"past {deadline_s:.0f}s; worker exiting")
            log.critical(reason, extra={
                "error_code": "STAGE_DEADLINE_EXCEEDED",
                "worker_id": worker_id})
            try:
                with _psycopg.connect(dsn, connect_timeout=5) as conn:
                    if ticket_id:
                        conn.execute(
                            """
                            UPDATE stage_tickets SET
                                attempt = attempt + 1,
                                status = CASE WHEN attempt + 1 >= 3
                                              THEN 'failed' ELSE 'ready' END,
                                lease_owner=NULL, lease_expires_at=NULL,
                                last_error_note = %s, updated_at=now()
                             WHERE ticket_id=%s AND status='leased'
                            """,
                            (reason[:500], ticket_id))
                    heartbeat(conn, worker_id, last_error=reason[:500])
                    conn.commit()
            except Exception:
                pass  # the exit itself frees the wedge either way
            os._exit(70)
        try:
            with _psycopg.connect(dsn, connect_timeout=5) as conn:
                conn.execute(
                    """UPDATE stage_tickets
                          SET lease_expires_at = now() + make_interval(secs => %s)
                        WHERE lease_owner = %s AND status = 'leased'""",
                    (ttl_s, worker_id))
                heartbeat(conn, worker_id, current_ticket=ticket_id)
                conn.commit()
        except Exception:
            log.warning("lease renewal failed; will retry",
                        extra={"error_code": "lease_renew_failed"})


def run_worker(worker_type: str, event_types: list[str],
               process_event: Callable[..., None],
               poll_interval_s: float = 2.0, batch_size: int = 1,
               extra_env_check: Callable[[], None] | None = None) -> None:
    """The fleet's single loop: register → heartbeat → claim gated work
    → execute → complete ticket. `process_event(conn, event)` keeps its
    existing signature and stage logic.

    batch_size defaults to 1 (LONG-STAGE-LEASE-CORRECTNESS-V1): a worker
    executes tickets serially, so claiming ahead bought nothing but made
    "held" differ from "being processed" — and a book-scale stage running
    past claim_ttl_s let the reaper expire the queued ones. Parallelism
    comes from running several workers of a type, which is unaffected.
    """
    configure_logging(f"worker-{worker_type.replace('_', '-')}")
    identity = worker_identity(worker_type)
    contracts = identity["contracts"]
    log = logging.getLogger(f"worker-{worker_type}")
    # EXECUTION-BUNDLE-FENCE-V1: pin the boot fingerprint. If the pinned
    # surfaces change on disk while this process lives, its boot-time
    # self-description no longer describes the code it would execute —
    # refuse claims loudly instead of producing provenance-orphaned
    # knowledge (measured failure class during P0.7 parity).
    from polymath_shared.execution_bundle import (
        bundle_id,
        fast_code_fingerprint,
        semantic_file_hashes,
    )
    boot_fingerprint = fast_code_fingerprint()
    boot_semantic_files = semantic_file_hashes()
    bundle_stale_reason: str | None = None
    # LANE-AFFINITY-STEAL-V1: only the extract stage has lanes; other
    # worker types ignore the env entirely.
    lane_affinity = (os.environ.get("POLYMATH_EXTRACT_AFFINITY", "").strip()
                     or None) if worker_type == "extract" else None
    if lane_affinity and lane_affinity not in ("local", "cloud"):
        raise ValueError(
            f"POLYMATH_EXTRACT_AFFINITY must be local|cloud, got {lane_affinity!r}")
    if lane_affinity:
        log.info("extract lane affinity: %s (steals when home lane is dry)",
                 lane_affinity)
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
                        "execution_bundle": identity["execution_bundle_id"],
                    })
                heartbeat(conn, identity["worker_id"])
                if bundle_stale_reason is None:
                    drift = None
                    if fast_code_fingerprint() != boot_fingerprint:
                        drift = "BUNDLE_STALE_CODE_DRIFT"
                    else:
                        now_files = semantic_file_hashes()
                        if now_files != boot_semantic_files:
                            drift = "BUNDLE_STALE_SEMANTIC_FILE_DRIFT"
                    if drift:
                        bundle_stale_reason = drift
                        log.critical(
                            "execution bundle stale; refusing claims",
                            extra={"error_code": drift,
                                   "worker_id": identity["worker_id"],
                                   "bundle": identity["execution_bundle_id"]})
                events = []
                if bundle_stale_reason is not None:
                    conn.execute(
                        """
                        UPDATE worker_registrations
                           SET last_error = %s, status = 'quarantined'
                         WHERE worker_id = %s
                        """,
                        (bundle_stale_reason, identity["worker_id"]),
                    )
                    log.error("claims refused while bundle is stale",
                              extra={"error_code": bundle_stale_reason})
                else:
                    events = claim_ticket_events(
                        conn, identity, event_types, batch_size,
                        lane_affinity=lane_affinity)
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
                # SELF-DEADLOCK (measured): heartbeating INSIDE the stage
                # transaction locks this worker's own worker_registrations
                # row for the whole stage. A 46-minute projection therefore
                # blocked its own lease keeper (which heartbeats on a second
                # connection) AND the control plane's staleness sweep — so
                # the heartbeat froze, the lease expired, control stopped
                # ticking, and the worker looked wedged while it was in fact
                # working. The heartbeat belongs in its own short
                # transaction, before the long one opens.
                try:
                    with tx() as conn:
                        heartbeat(conn, identity["worker_id"], current_ticket=ticket_id)
                except Exception:
                    log.warning("pre-stage heartbeat failed; continuing",
                                extra={"error_code": "heartbeat_failed"})
                try:
                    with tx() as conn:
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
                    attempt = attempt + 1,
                    status = CASE WHEN attempt + 1 >= 3 THEN 'failed' ELSE 'ready' END,
                    lease_owner=NULL, lease_expires_at=NULL,
                    last_error_note = %s, updated_at=now()
                 WHERE ticket_id=%s AND status='leased'
                """,
                (reason[:500], ticket_id),
            )
    except Exception:
        pass

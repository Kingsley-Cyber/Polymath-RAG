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
from control.census import compute_census, pop_census_timing
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

        # TICK-PHASE-TIMING-V1: every phase is measured, not guessed.
        import time as _t
        phase_ms: dict[str, float] = {}

        def _phase(name, fn, *a, **k):
            _s = _t.perf_counter()
            out = fn(*a, **k)
            phase_ms[name] = round((_t.perf_counter() - _s) * 1000, 1)
            return out

        # STEP 1c (addendum 5e): reconcile contract drift BEFORE ticket
        # creation, so stranded pre-upgrade runs mint successors under
        # the CURRENT contract instead of freezing forever. Zero
        # deletion; lineage columns record the supersession.
        from control.reconciliation import reconcile_contract_drift
        reconciled = _phase("reconcile", reconcile_contract_drift, conn)

        ensured = _phase("ensure_tickets", _ensure_tickets_backpressure_gated,
                         conn)
        advanced = _phase("advance_tickets", cp2_tickets.advance_tickets, conn)
        supervised = _phase("supervise", supervise, conn)
        census = compute_census(conn, max_attempts=settings.control.max_attempts)
        _ct = pop_census_timing() or {}
        phase_ms["census_total"] = _ct.get("census_total_ms", 0.0)
        phase_ms["census_runs_query"] = _ct.get("runs_query_ms")
        phase_ms["census_dirty_select"] = _ct.get("dirty_select_ms")
        phase_ms["census_attempts_fetch"] = _ct.get("attempts_fetch_ms")
        phase_ms["census_python_loop"] = _ct.get("python_loop_ms")
        phase_ms["census_receipt_checks"] = _ct.get("receipt_checks_ms")
        # The legacy scheduler still drives FAILED-stage retries (its
        # events are idempotent against ticket events by content hash).
        scheduled = _phase("schedule_gaps", schedule_gaps, conn, census)
        barrier = _barrier_or_none(conn, census)
        if barrier is None:
            _phase("apply_promotions", apply_promotions, conn, census)
        else:
            # Per-corpus barrier: a blocked corpus must not freeze
            # promotion for healthy corpora — promote everything whose
            # own corpus passes the generation barrier.
            _s = _t.perf_counter()
            blocked = _corpora_with_open_barriers(conn, census)
            promoted = [r for r in census.promote
                        if _corpus_of_run(conn, r) not in blocked]
            if len(promoted) != len(census.promote):
                census = census.__class__(gaps=census.gaps, promote=promoted, fail=census.fail)
            apply_promotions(conn, census)
            phase_ms["barrier_promotions"] = round(
                (_t.perf_counter() - _s) * 1000, 1)
        _phase("apply_failures", apply_failures, conn, census)
        record_heartbeat(conn, owner, tick_ok=True, census_size=len(census.gaps))
        return {
            "tick": "ok",
            "owner": owner[:12],
            "gaps": len(census.gaps),
            "scheduled": scheduled,
            "promoted": len(census.promote),
            "failed": len(census.fail),
            "reconciled": len(reconciled.get("reconciled", {})),
            "phase_ms": {k: v for k, v in phase_ms.items() if v is not None},
        }


def _ensure_tickets_backpressure_gated(conn) -> int:
    """D7-5d: creation fairness + sticky hysteresis.

    Per-corpus runtime state gates NEW ticket chains: pause enters at
    >= watermark and resumes only at <= watermark/2. The creation
    window is distributed round-robin across ELIGIBLE corpora
    (last_creation_tick NULLS FIRST), so a saturated corpus can never
    fill the window."""
    from control.tickets import fair_ensure_tickets_backpressure_gated

    return fair_ensure_tickets_backpressure_gated(conn, window=32)

def _barrier_or_none(conn, census) -> dict | None:
    """Generation barrier (ADR-0014): block promotion of any corpus whose
    ticket chains are not fully DONE with desired==actual projections.
    Returns the blocking verdict, or None when promotion may proceed."""
    blocked = _corpora_with_open_barriers(conn, census)
    return next(iter(blocked.values()), None) if blocked else None


def _corpora_with_open_barriers(conn, census) -> dict:
    from control.tickets import generation_barrier

    corpora = {gap.corpus_id for gap in census.gaps} | {
        _corpus_of_run(conn, r) for r in census.promote
    }
    blocked = {}
    for corpus_id in sorted(corpora):
        verdict = generation_barrier(conn, corpus_id)
        if not verdict["passed"]:
            blocked[corpus_id] = verdict
    return blocked


def _corpus_of_run(conn, run_id: str) -> str:
    row = conn.execute("SELECT corpus_id FROM runs WHERE run_id=%s", (run_id,)).fetchone()
    return row[0] if row else ""


def run_forever() -> None:
    configure_logging("polymath-control")
    settings = get_settings()
    while True:
        started = time.monotonic()
        try:
            import time as _perf, json as _json
            _t0 = _perf.perf_counter()
            result = tick()
            log.info('tick completed', extra={
                'error_code': 'TICK-PHASE-TIMING-V1',
                'duration_ms': round((_perf.perf_counter()-_t0)*1000, 1),
                'detail': _json.dumps({
                    'tick_result': str(result.get('tick')),
                    'reason': str(result.get('reason'))[:40],
                    'gaps': result.get('gaps'),
                    'phase_ms': result.get('phase_ms')})})
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

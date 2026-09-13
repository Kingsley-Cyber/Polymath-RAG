"""PIPELINE-BLOCKED-HEALTH-V1 (P10, 2026-08-28).

A quarantined fleet produced NO signal. Workers that detect execution
bundle drift set `worker_registrations.status='quarantined'` with the
cause in `last_error` and then correctly refuse to claim tickets
(shared/polymath_shared/worker_runtime.py:336) — but nothing read that
state, so the pipeline simply stopped moving. To an operator that is
indistinguishable from "no work to do".

MEASURED cost: this stalled the sentinel ingestion TWICE during the
audit, each time with zero tickets progressing and no error surfaced.
Both times it was diagnosed by hand.

The rule this encodes: a component that has stopped working must never
look the same as a component with nothing to do. BLOCKED and IDLE are
different states and must be reported differently, with the cause
attached.
"""
from __future__ import annotations

from typing import Any

STATE_HEALTHY = "HEALTHY"
STATE_IDLE = "IDLE"
STATE_BLOCKED = "BLOCKED"

#: A worker in this state cannot claim work. It is not idle.
BLOCKING_WORKER_STATUS = "quarantined"


#: A registration whose heartbeat is older than this is a dead process,
#: not a blocked one. Without this window every historical quarantine
#: would pin the fleet to BLOCKED forever — 981 of 1,310 registrations
#: in the live database are already stale.
LIVE_HEARTBEAT_SECONDS = 120

#: GAP-4 (FRONTEND-V2-CONTRACT-INVENTORY-V1): the owner's standing stall rule
#: (2026-09-02) is 3 minutes — the same threshold stall_tracer.py uses
#: (STALL_THRESHOLD_S) to decide a unit stopped advancing. Reused here so a run
#: whose `updated_at` predates this window is judged "not moving" by the same
#: definition the tracer already applies, not a second invented number.
DORMANT_RUN_AGE_SECONDS = 180


STATE_DEGRADED = "DEGRADED"

#: STALL-DORMANCY-SPLIT-V1 (GAP-6, FRONTEND-V2-CONTRACT-INVENTORY-V1). A stall_traces
#: row with one of these diagnoses only exists, BY CONSTRUCTION, when nothing live is
#: backing it: diagnose_pending() (control/control/stall_tracer.py) returns None — no
#: row at all — for PENDING_ON_PREDECESSOR/PENDING_ADVANCE_BLOCKED whenever a live
#: predecessor or sibling is running; PENDING_OWNER_STAGE waits on an owner action the
#: DAG never drives; RUN_SETTLED_NOT_PROMOTED means no open ticket remains for the run.
#: Measured 2026-09-10: exactly these three diagnoses (221+32+29=282) accounted for the
#: entire open-stall count on a fleet with 0 queued tickets and 0 blocked workers — a
#: migration backlog the owner classified, not a live pipeline defect. Everything else
#: (READY_*, LEASED_*, RUN_NO_TICKET_CHAIN, RUN_DEGRADED_AWAITING_DECISION,
#: SUMMARY_JOB_*, PENDING_ADVANCE_NOT_REACHED) names either live work or a scheduler
#: defect and stays ACTIVE.
DORMANT_STALL_DIAGNOSES = frozenset({
    "PENDING_ON_PREDECESSOR", "PENDING_ADVANCE_BLOCKED",
    "PENDING_OWNER_STAGE", "RUN_SETTLED_NOT_PROMOTED",
})


def _degradation(conn) -> dict[str, Any]:
    """Open stall episodes older than the trace threshold and recent medic actions.
    Both tables are created by migrations 0046+/0053; absence degrades to zeros.

    `stalls_open` is kept as the raw total (existing readers); `stalls_active` /
    `stalls_dormant` split it by DORMANT_STALL_DIAGNOSES so a backlog of records
    nothing is currently running behind cannot pin the pipeline state to DEGRADED
    forever (GAP-6)."""
    out: dict[str, Any] = {"stalls_open": 0, "stalls_active": 0, "stalls_dormant": 0,
                            "stall_diagnoses": [], "medic_actions_15m": []}
    try:
        with conn.transaction():
            rows = conn.execute(
                """SELECT diagnosis, count(*) FROM stall_traces
                    WHERE resolved_at IS NULL AND last_traced_at > now() - interval '10 minutes'
                    GROUP BY diagnosis ORDER BY 2 DESC""").fetchall()
        out["stalls_open"] = int(sum(r[1] for r in rows))
        out["stalls_dormant"] = int(sum(n for d, n in rows if d in DORMANT_STALL_DIAGNOSES))
        out["stalls_active"] = out["stalls_open"] - out["stalls_dormant"]
        out["stall_diagnoses"] = [f"{d}×{n}" for d, n in rows][:6]
    except Exception:  # noqa: BLE001
        pass
    try:
        with conn.transaction():
            rows = conn.execute(
                """SELECT kind, target, at FROM medic_actions
                    WHERE at > now() - interval '15 minutes' ORDER BY at DESC LIMIT 10""").fetchall()
        out["medic_actions_15m"] = [{"kind": k, "target": t, "at": str(a)} for k, t, a in rows]
    except Exception:  # noqa: BLE001
        pass
    return out


def pipeline_health(conn, live_seconds: int = LIVE_HEARTBEAT_SECONDS) -> dict[str, Any]:
    """Report BLOCKED (with cause) / IDLE / HEALTHY for the LIVE fleet.

    IDLE means "alive and nothing queued". BLOCKED means "work exists or
    could exist, and the workers that should do it cannot". The
    distinction is the whole point — never collapse them.

    Only workers heartbeating within `live_seconds` count. A stale
    registration is a dead process; reporting it as blocked would make
    BLOCKED permanent and therefore meaningless.
    """
    workers = conn.execute(
        """
        SELECT worker_id, worker_type, status, last_error
          FROM worker_registrations
         WHERE heartbeat_at > now() - make_interval(secs => %s)
        """,
        (live_seconds,),
    ).fetchall()

    blocked = [
        {"worker_id": w[0], "worker_type": w[1], "cause": w[3] or "unknown"}
        for w in workers
        if (w[2] or "") == BLOCKING_WORKER_STATUS
    ]

    queued = conn.execute(
        "SELECT count(*) FROM stage_tickets "
        "WHERE status IN ('ready','leased') AND archived_at IS NULL"
    ).fetchone()[0]

    if blocked:
        causes = sorted({b["cause"] for b in blocked})
        return {
            "state": STATE_BLOCKED,
            "blocked_workers": len(blocked),
            "live_workers": len(workers),
            "causes": causes,
            "detail": (
                f"{len(blocked)} of {len(workers)} live workers are "
                f"quarantined and refusing claims ({', '.join(causes)}). "
                f"{queued} ticket(s) will not progress until the fleet is "
                f"restarted on the current code."),
            "queued_tickets": queued,
            "workers": blocked[:20],
        }

    if not workers:
        return {
            "state": STATE_BLOCKED if queued else STATE_IDLE,
            "blocked_workers": 0, "live_workers": 0,
            "causes": ["NO_LIVE_WORKERS"] if queued else [],
            "detail": (f"no live workers and {queued} ticket(s) queued; "
                       "nothing can claim them") if queued else
                      "no live workers and no queued work",
            "queued_tickets": queued, "workers": [],
        }

    # MEDIC-V1 / STALL-TRACER: a fleet whose units are traced as stalled, or that
    # the medic had to repair in the last 15 minutes, is DEGRADED — HEALTHY while
    # tickets sat READY_UNCLAIMED for hours (measured 2026-09-05) was a lie.
    degraded = _degradation(conn)
    if queued and degraded["stalls_active"] == 0 and not degraded["medic_actions_15m"]:
        return {"state": STATE_HEALTHY, "blocked_workers": 0,
                "live_workers": len(workers), "causes": [],
                "detail": f"{queued} ticket(s) in flight",
                "queued_tickets": queued, "workers": [], **degraded}
    if degraded["stalls_active"] or degraded["medic_actions_15m"]:
        return {"state": STATE_DEGRADED, "blocked_workers": 0,
                "live_workers": len(workers), "causes": degraded["stall_diagnoses"],
                "detail": (f"{degraded['stalls_active']} unit(s) traced as stalled "
                           f"({', '.join(degraded['stall_diagnoses'][:3]) or 'see stall_traces'}); "
                           f"medic acted {len(degraded['medic_actions_15m'])} time(s) in 15 min; "
                           f"{queued} ticket(s) in flight"),
                "queued_tickets": queued, "workers": [], **degraded}

    # GAP-6: dormant backlog alone (0 active stalls) is IDLE/HEALTHY-adjacent, not
    # DEGRADED — but the dormant count still travels so the UI can show it exists.
    return {"state": STATE_IDLE, "blocked_workers": 0,
            "live_workers": len(workers), "causes": [],
            "detail": "workers alive, no tickets queued",
            "queued_tickets": queued, "workers": [], **degraded}


#: CONTROL-READY-V1 (GAP-1, FRONTEND-V2-CONTRACT-INVENTORY-V1). Before this, "is the
#: machinery healthy?" required composing two separate calls (`/ready` for sidecars,
#: `/health/pipeline` for the fleet) IN THE UI — recomputation of a verdict this module
#: already owns, and exactly the class of drift the design law forbids (11.187: two
#: screens composing it differently will disagree). This is the one authority; callers
#: render the result, they do not derive it.
CONTROL_READY_STATES = frozenset({"ready", "blocked", "degraded"})


def control_ready(conn, *, sidecars: dict[str, bool] | None = None,
                   live_seconds: int = LIVE_HEARTBEAT_SECONDS) -> dict[str, Any]:
    """Single CONTROL READY verdict: sidecars up AND the fleet not BLOCKED/DEGRADED.

    `sidecars` is the in-process readiness map `/ready` already computes
    (name -> is_ready()); it cannot be read from Postgres, so the caller passes it
    through rather than this module reaching into app state. `cloud-modal` is
    optional and never blocks (matches the existing `/ready` + frontend behavior).
    """
    sidecars = sidecars or {}
    dark = sorted(name for name, up in sidecars.items() if not up and name != "cloud-modal")
    pipeline = pipeline_health(conn, live_seconds=live_seconds)
    state = pipeline.get("state")

    if dark:
        return {"state": "blocked", "label": state or "NOT READY",
                "detail": f"sidecars down: {', '.join(dark)}", "pipeline": pipeline}
    if state == STATE_BLOCKED:
        return {"state": "blocked", "label": state, "detail": pipeline.get("detail"),
                "pipeline": pipeline}
    if state == STATE_DEGRADED:
        return {"state": "degraded", "label": state, "detail": pipeline.get("detail"),
                "pipeline": pipeline}
    # HEALTHY or IDLE: both mean the fleet can do the work it has (none, for IDLE).
    return {"state": "ready", "label": state or "READY", "pipeline": pipeline}

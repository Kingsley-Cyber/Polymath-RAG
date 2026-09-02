"""STALL-TRACER-V1 — the control plane's own "why is this stuck" pass.

Owner rule (2026-09-02): any unit of work that has not advanced for
three minutes is a defect to trace, never to wait out. Every tick this
module walks the units that can stall — stage tickets, runs, summary
jobs — and for each one older than the threshold writes ONE diagnosis
row (stall_traces) naming what it waits on, using the same predicates
the scheduler uses to advance work. It never mutates the unit:
detection and evidence only; the fix is a code change in the writer the
diagnosis names.

Diagnoses (deterministic, one per unit per tick):
  ticket/ready    READY_NO_CLAIM_EVENT, READY_NO_LIVE_SLOT, READY_UNCLAIMED
  ticket/leased   LEASED_EXPIRED_NOT_RELEASED, LEASED_OWNER_GONE,
                  LEASED_LONG_RUNNING
  ticket/pending  PENDING_OWNER_STAGE, PENDING_ON_PREDECESSOR,
                  PENDING_ADVANCE_BLOCKED, PENDING_ADVANCE_NOT_REACHED
  run             RUN_NO_TICKET_CHAIN, RUN_DEGRADED_AWAITING_DECISION,
                  RUN_SETTLED_NOT_PROMOTED
  summary_job     SUMMARY_JOB_INFLIGHT_STALLED, SUMMARY_JOB_FAILED_TICKET_OPEN
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("control.stall_tracer")

STALL_THRESHOLD_S = 180
# Mirrors _release_expired_leases: a heartbeat older than this means the
# executing worker is gone.
OWNER_STALE_S = 90
TERMINAL_RUN_STATUSES = ("query_ready", "failed", "superseded")
OPEN_TICKET_STATUSES = ("pending", "ready", "leased")
SUPERVISOR_STATE = Path("/tmp/polymath_fleet/supervisor_state.json")
_LIMIT = 500


@dataclass
class Stall:
    unit_kind: str
    unit_id: str
    stalled_since: datetime
    age_s: int
    diagnosis: str
    detail: dict = field(default_factory=dict)
    run_id: str | None = None
    stage: str | None = None
    corpus_id: str | None = None

    @property
    def key(self) -> str:
        return f"{self.unit_kind}:{self.unit_id}"


# ---------------------------------------------------------------- fleet view

def fleet_slots_alive(path: Path = SUPERVISOR_STATE) -> dict[str, bool] | None:
    """Best-effort read of the supervisor's state file. None when absent."""
    try:
        data = json.loads(Path(path).read_text())
        return {s["name"]: bool(s.get("alive")) for s in data.get("slots", [])}
    except Exception:
        return None


def lane_slots(stage: str) -> tuple[str | None, set[str]]:
    from control.fleet_autopilot import LANES
    for lane, stages, slots in LANES:
        if stage in stages:
            return lane, set(slots)
    return None, set()


# ------------------------------------------------------------ pure diagnoses

def _age(ts: datetime | None, now: datetime) -> int | None:
    return None if ts is None else int((now - ts).total_seconds())


def diagnose_ready(row: dict, slots_alive: dict[str, bool] | None) -> tuple[str, dict]:
    lane, slots = lane_slots(row["stage"])
    base = {"lane": lane, "slots": sorted(slots), "attempt": row.get("attempt"),
            "live_workers": row.get("live_workers")}
    if not row.get("claim_event_pending"):
        base["note"] = ("no undelivered claim event for this ticket: the "
                        "advance phase's READY backfill has not re-emitted it")
        return "READY_NO_CLAIM_EVENT", base
    if slots_alive is not None and slots and not any(slots_alive.get(s) for s in slots):
        base["slots_alive"] = {s: bool(slots_alive.get(s)) for s in sorted(slots)}
        base["note"] = "claim event pending but no slot of its lane is alive (autopilot demand or budget)"
        return "READY_NO_LIVE_SLOT", base
    if slots_alive is not None:
        base["slots_alive"] = {s: bool(slots_alive.get(s)) for s in sorted(slots)}
    base["note"] = ("claim event pending and a lane slot is alive: the worker's "
                    "claim gate (capability/contract/readiness) refuses it")
    return "READY_UNCLAIMED", base


def diagnose_leased(row: dict, now: datetime) -> tuple[str, dict]:
    hb_age = _age(row.get("heartbeat_at"), now)
    expires_in = None
    if row.get("lease_expires_at") is not None:
        expires_in = int((row["lease_expires_at"] - now).total_seconds())
    detail = {"lease_owner": row.get("lease_owner"), "worker_pid": row.get("pid"),
              "worker_status": row.get("worker_status"),
              "heartbeat_age_s": hb_age, "lease_expires_in_s": expires_in}
    if expires_in is not None and expires_in < 0:
        detail["note"] = ("lease expired but not released: the advance phase's "
                          "expiry sweep is not running")
        return "LEASED_EXPIRED_NOT_RELEASED", detail
    if hb_age is None or hb_age > OWNER_STALE_S:
        detail["note"] = "executing worker gone; the lease is released at expiry (attempt charged)"
        return "LEASED_OWNER_GONE", detail
    detail["note"] = "holder alive and heartbeating: a long call, watch the lane's provider latency"
    return "LEASED_LONG_RUNNING", detail


def diagnose_pending(conn, row: dict, chain: dict[str, str]) -> tuple[str, dict]:
    from control.tickets import (DAG_ORDER, _STAGE_SPEC, _artifacts_present,
                                 _receipts_present, _stage_attempt_ok)
    stage = row["stage"]
    if stage not in DAG_ORDER:
        return "PENDING_OWNER_STAGE", {
            "note": "owner-triggered stage: pending is never advanced by the DAG"}
    preds = DAG_ORDER[:DAG_ORDER.index(stage)]
    for pr in preds:
        if not _stage_attempt_ok(conn, row["run_id"], pr):
            return "PENDING_ON_PREDECESSOR", {
                "predecessor": pr,
                "predecessor_ticket_status": chain.get(pr, "no ticket")}
    for pr in preds:
        _evt, art, rec = _STAGE_SPEC[pr]
        if not _artifacts_present(conn, row["run_id"], pr, art):
            return "PENDING_ADVANCE_BLOCKED", {
                "predecessor": pr, "missing": "artifacts", "keys": list(art)}
        for projection in rec:
            if not _receipts_present(conn, row["run_id"], row["corpus_id"], projection):
                return "PENDING_ADVANCE_BLOCKED", {
                    "predecessor": pr, "missing": "receipts", "projection": projection}
    return "PENDING_ADVANCE_NOT_REACHED", {
        "note": ("predecessors complete and evidenced; the advance phase has not "
                 "visited this ticket (phase failing, or cursor wrapped)")}


def diagnose_run(row: dict, census_gaps: list[str]) -> tuple[str, dict]:
    detail = {"status": row["status"], "source_name": row.get("source_name"),
              "corpus_exists": row.get("corpus_exists"),
              "tickets_not_done": row.get("not_done"),
              "census_gaps": census_gaps,
              "degraded_reasons": row.get("degraded_reasons")}
    if not row.get("n_tickets"):
        detail["note"] = "no ticket chain was ever minted for this run"
        return "RUN_NO_TICKET_CHAIN", detail
    if row["status"] == "degraded":
        detail["note"] = "census verdict stands; needs a retry or an owner decision"
        return "RUN_DEGRADED_AWAITING_DECISION", detail
    detail["note"] = "no open ticket, not promoted: the census barrier or failed tickets hold it"
    return "RUN_SETTLED_NOT_PROMOTED", detail


# ----------------------------------------------------------------- collectors

def _rows(cur) -> list[dict]:
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def collect_stalls(conn, *, census=None, threshold_s: int = STALL_THRESHOLD_S,
                   slots_alive: dict[str, bool] | None = None) -> list[Stall]:
    now = conn.execute("SELECT now()").fetchone()[0]
    out: list[Stall] = []

    tickets = _rows(conn.execute(
        """
        SELECT t.ticket_id, t.run_id, t.corpus_id, t.stage, t.status, t.attempt,
               t.lease_owner, t.lease_expires_at, t.updated_at, t.last_error_note,
               w.heartbeat_at, w.pid, w.status AS worker_status,
               EXISTS (SELECT 1 FROM outbox_events e
                        WHERE e.run_id = t.run_id AND e.event_type = t.event_type
                          AND e.delivered_at IS NULL
                          AND e.payload->>'ticket_id' = t.ticket_id) AS claim_event_pending,
               (SELECT count(*) FROM worker_registrations wr
                 WHERE wr.heartbeat_at > now() - make_interval(secs => %s)) AS live_workers
          FROM stage_tickets t
          LEFT JOIN worker_registrations w ON w.worker_id = t.lease_owner
         WHERE t.status IN ('pending', 'ready', 'leased')
           AND t.updated_at < now() - make_interval(secs => %s)
         ORDER BY t.updated_at
         LIMIT %s
        """, (OWNER_STALE_S, threshold_s, _LIMIT)))
    chains: dict[str, dict[str, str]] = {}
    for row in tickets:
        if row["status"] == "ready":
            code, detail = diagnose_ready(row, slots_alive)
        elif row["status"] == "leased":
            code, detail = diagnose_leased(row, now)
        else:
            if row["run_id"] not in chains:
                chains[row["run_id"]] = dict(conn.execute(
                    "SELECT stage, status FROM stage_tickets WHERE run_id = %s "
                    "ORDER BY seq", (row["run_id"],)).fetchall())
            code, detail = diagnose_pending(conn, row, chains[row["run_id"]])
        detail["ticket_status"] = row["status"]
        if row.get("last_error_note"):
            detail["last_error_note"] = row["last_error_note"]
        out.append(Stall("ticket", row["ticket_id"], row["updated_at"],
                         _age(row["updated_at"], now) or 0, code, detail,
                         run_id=row["run_id"], stage=row["stage"],
                         corpus_id=row["corpus_id"]))

    gaps_by_run: dict[str, list[str]] = {}
    for g in (getattr(census, "gaps", None) or []):
        gaps_by_run.setdefault(g.run_id, []).append(f"{g.stage}: {g.reason}")
    runs = _rows(conn.execute(
        """
        SELECT r.run_id, r.corpus_id, r.status, r.updated_at,
               r.metadata->>'source_name' AS source_name,
               r.metadata->'degraded_reasons' AS degraded_reasons,
               (SELECT count(*) FROM stage_tickets t WHERE t.run_id = r.run_id) AS n_tickets,
               (SELECT count(*) FROM stage_tickets t WHERE t.run_id = r.run_id
                 AND t.status IN ('pending', 'ready', 'leased')) AS n_open,
               (SELECT string_agg(t.stage || '=' || t.status, ',' ORDER BY t.seq)
                  FROM stage_tickets t WHERE t.run_id = r.run_id
                   AND t.status NOT IN ('done', 'skipped')) AS not_done,
               EXISTS (SELECT 1 FROM corpora c WHERE c.corpus_id = r.corpus_id) AS corpus_exists
          FROM runs r
         WHERE r.superseded_by_run_id IS NULL
           AND r.status NOT IN ('query_ready', 'failed', 'superseded')
           AND r.updated_at < now() - make_interval(secs => %s)
         ORDER BY r.updated_at
         LIMIT %s
        """, (threshold_s, _LIMIT)))
    for row in runs:
        if row["n_open"]:
            continue    # explained by its own ticket traces above
        code, detail = diagnose_run(row, gaps_by_run.get(row["run_id"], []))
        out.append(Stall("run", row["run_id"], row["updated_at"],
                         _age(row["updated_at"], now) or 0, code, detail,
                         run_id=row["run_id"], corpus_id=row["corpus_id"]))

    jobs = _rows(conn.execute(
        """
        SELECT j.ticket_id, j.stage, j.corpus_id, j.state, j.attempts, j.worker_id,
               j.created_at, t.status AS ticket_status, t.run_id
          FROM summary_jobs j
          LEFT JOIN stage_tickets t ON t.ticket_id = split_part(j.ticket_id, ':', 1)
         WHERE j.created_at < now() - make_interval(secs => %s)
           AND (j.state NOT IN ('COMPLETE', 'FAILED')
                OR (j.state = 'FAILED' AND t.status IN ('pending', 'ready', 'leased')))
         ORDER BY j.created_at
         LIMIT %s
        """, (threshold_s, _LIMIT)))
    for row in jobs:
        code = ("SUMMARY_JOB_FAILED_TICKET_OPEN" if row["state"] == "FAILED"
                else "SUMMARY_JOB_INFLIGHT_STALLED")
        out.append(Stall("summary_job", row["ticket_id"], row["created_at"],
                         _age(row["created_at"], now) or 0, code,
                         {"state": row["state"], "attempts": row["attempts"],
                          "worker_id": row["worker_id"],
                          "ticket_status": row["ticket_status"]},
                         run_id=row["run_id"], stage=row["stage"],
                         corpus_id=row["corpus_id"]))
    return out


# ---------------------------------------------------------------- persistence

def persist_traces(conn, stalls: list[Stall]) -> list[Stall]:
    """Upsert one row per stall episode; resolve episodes that cleared.
    Returns the stalls traced for the FIRST time this tick."""
    new: list[Stall] = []
    for s in stalls:
        inserted = conn.execute(
            """
            INSERT INTO stall_traces (unit_kind, unit_id, stalled_since, run_id, stage,
                                      corpus_id, age_s, diagnosis, detail)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (unit_kind, unit_id, stalled_since) DO UPDATE SET
                last_traced_at = now(), age_s = EXCLUDED.age_s,
                diagnosis = EXCLUDED.diagnosis, detail = EXCLUDED.detail,
                resolved_at = NULL
            RETURNING (xmax = 0) AS inserted
            """,
            (s.unit_kind, s.unit_id, s.stalled_since, s.run_id, s.stage, s.corpus_id,
             s.age_s, s.diagnosis, json.dumps(s.detail, default=str))).fetchone()[0]
        if inserted:
            new.append(s)
    conn.execute(
        """
        UPDATE stall_traces SET resolved_at = now()
         WHERE resolved_at IS NULL
           AND (unit_kind || ':' || unit_id) <> ALL(%s::text[])
        """, ([s.key for s in stalls],))
    return new


def trace_stalls(conn, census=None, *, threshold_s: int = STALL_THRESHOLD_S,
                 fleet_state_path: Path = SUPERVISOR_STATE) -> dict:
    stalls = collect_stalls(conn, census=census, threshold_s=threshold_s,
                            slots_alive=fleet_slots_alive(fleet_state_path))
    new = persist_traces(conn, stalls)
    for s in new:
        # The JSON logger emits a fixed field set: the diagnosis rides the
        # message and error_code so the line is self-explanatory.
        log.warning(
            f"stall traced: {s.unit_kind} {s.unit_id} {s.age_s}s {s.diagnosis} "
            f"{json.dumps(s.detail, default=str)[:400]}",
            extra={"stage": s.stage, "run_id": s.run_id, "error_code": s.diagnosis})
    return {"stalls": len(stalls), "new": len(new)}

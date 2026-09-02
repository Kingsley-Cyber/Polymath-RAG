"""Intake API. POST /intake — the transactional intake boundary.

Validates input, writes one run row and one intake.v1 outbox event in a
SINGLE Postgres transaction, returns run_id immediately (PLAN Phase B
exit proof). Replaying identical canonical input returns the existing
run_id and creates no second run.

The write itself lives in shared/polymath_shared/intake_submission.py —
the ONE execution path shared with the I1 manifest producer.

The orchestrator decides nothing about what happens next — the control
plane and workers own that.
"""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from polymath_shared.contracts import IntakeRequest
from polymath_shared.db import tx
from polymath_shared.intake_submission import canonical_intake_payload, submit_intake

router = APIRouter()


class IntakeResponse(BaseModel):
    run_id: str
    accepted: bool
    already_exists: bool = False


@router.post("/intake", response_model=IntakeResponse)
async def intake(req: IntakeRequest) -> IntakeResponse:
    canonical_payload = canonical_intake_payload(
        req.corpus_id, req.source_name, req.media_type, req.content_b64, req.config
    )
    try:
        with tx() as conn:
            result = submit_intake(conn, canonical_payload)
            return IntakeResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except psycopg.errors.UniqueViolation:
        return IntakeResponse(
            run_id=result.get("run_id", ""), accepted=True, already_exists=True,
        )


@router.get("/runs/{run_id}")
async def run_status(run_id: str) -> dict:
    with tx() as conn:
        run = conn.execute(
            "SELECT run_id, corpus_id, status, created_at, updated_at FROM runs WHERE run_id = %s",
            (run_id,),
        ).fetchone()
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        attempts = conn.execute(
            """
            SELECT stage, contract_hash, outcome, completed_at, error
              FROM stage_attempts WHERE run_id = %s ORDER BY stage
            """,
            (run_id,),
        ).fetchall()
    return {
        "run_id": run[0],
        "corpus_id": run[1],
        "status": run[2],
        "created_at": run[3].isoformat(),
        "updated_at": run[4].isoformat(),
        "stages": [
            {"stage": a[0], "contract_hash": a[1], "outcome": a[2],
             "completed_at": a[3].isoformat() if a[3] else None, "error": a[4]}
            for a in attempts
        ],
    }


@router.get("/status")
async def pipeline_status(corpus_id: str, source_name: str | None = None,
                          run_id: str | None = None) -> dict:
    """DOCUMENT-STATUS-V1 (POLYMATH-MCP-V2): what an agent needs after an
    upload, in one read — the run's status and whether it is queryable,
    every stage ticket, enrichment progress, the last error, and any OPEN
    stall trace the control plane holds for the run. Read-only. Look up
    by run_id, or by (corpus_id, source_name) → the current (non-
    superseded) run for that document."""
    if not run_id and not source_name:
        raise HTTPException(422, "pass run_id or source_name")
    with tx() as conn:
        if run_id:
            run = conn.execute(
                """SELECT run_id, status, created_at, updated_at,
                          metadata->>'source_name', metadata->'degraded_reasons'
                     FROM runs WHERE run_id = %s AND corpus_id = %s""",
                (run_id, corpus_id)).fetchone()
        else:
            run = conn.execute(
                """SELECT run_id, status, created_at, updated_at,
                          metadata->>'source_name', metadata->'degraded_reasons'
                     FROM runs
                    WHERE corpus_id = %s AND metadata->>'source_name' = %s
                      AND superseded_by_run_id IS NULL
                    ORDER BY created_at DESC LIMIT 1""",
                (corpus_id, source_name)).fetchone()
        if run is None:
            raise HTTPException(404, {"error_code": "RUN_NOT_FOUND",
                                      "message": "no run for that document in that corpus"})
        rid, status, created, updated, sname, degraded = run
        tickets = conn.execute(
            """SELECT stage, status, attempt, updated_at, last_error_note
                 FROM stage_tickets WHERE run_id = %s ORDER BY seq""",
            (rid,)).fetchall()
        doc = conn.execute(
            """SELECT doc_id, byte_length FROM documents
                WHERE corpus_id = %s AND source_name = %s
                ORDER BY created_at DESC LIMIT 1""",
            (corpus_id, sname)).fetchone()
        enrichment = chunks = None
        if doc:
            e = conn.execute(
                """SELECT COUNT(DISTINCT parent_id) FILTER (WHERE status = 'READY'),
                          COUNT(DISTINCT parent_id)
                     FROM parent_enrichments WHERE doc_id = %s""", (doc[0],)).fetchone()
            c = conn.execute(
                """SELECT COUNT(*) FILTER (WHERE tier = 'child'),
                          COUNT(DISTINCT parent_id) FILTER (WHERE tier = 'child')
                     FROM chunks WHERE doc_id = %s""", (doc[0],)).fetchone()
            enrichment = {"parents_ready": e[0], "parents_seen": e[1],
                          "parents_total": c[1]}
            chunks = {"children": c[0], "parents": c[1]}
        try:
            stalls = conn.execute(
                """SELECT unit_kind, unit_id, stage, age_s, diagnosis, detail
                     FROM stall_traces
                    WHERE run_id = %s AND resolved_at IS NULL
                    ORDER BY first_traced_at""", (rid,)).fetchall()
        except Exception:  # noqa: BLE001 — table absent on an older store
            stalls = []
        last_error = conn.execute(
            """SELECT last_error_note FROM stage_tickets
                WHERE run_id = %s AND last_error_note IS NOT NULL
                ORDER BY updated_at DESC LIMIT 1""", (rid,)).fetchone()
    open_stages = [t[0] for t in tickets if t[1] in ("pending", "ready", "leased")]
    return {
        "run_id": rid, "corpus_id": corpus_id, "source_name": sname,
        "status": status, "query_ready": status == "query_ready",
        "created_at": created, "updated_at": updated,
        "doc_id": doc[0] if doc else None, "bytes": doc[1] if doc else None,
        "chunks": chunks, "enrichment": enrichment,
        "stages": [{"stage": t[0], "status": t[1], "attempt": t[2],
                    "updated_at": t[3], "error": t[4]} for t in tickets],
        "open_stages": open_stages,
        "degraded_reasons": degraded,
        "last_error": last_error[0] if last_error else None,
        "stalls": [{"unit_kind": s[0], "unit_id": s[1], "stage": s[2],
                    "age_s": s[3], "diagnosis": s[4], "detail": s[5]} for s in stalls],
        "hint": ("queryable — call ask()" if status == "query_ready" else
                 f"in progress: {open_stages}" if open_stages else
                 f"settled with status {status!r} — see degraded_reasons/last_error"),
    }

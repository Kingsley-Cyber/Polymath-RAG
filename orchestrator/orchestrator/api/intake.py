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

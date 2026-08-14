"""Intake API. POST /intake — the transactional intake boundary.

Validates input, writes one run row and one intake.v1 outbox event in a
SINGLE Postgres transaction, returns run_id immediately (PLAN Phase B
exit proof). Replaying identical canonical input returns the existing
run_id and creates no second run.

The orchestrator decides nothing about what happens next — the control
plane and workers own that.
"""
from __future__ import annotations

import base64
import json

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from polymath_shared.contracts import IntakeRequest
from polymath_shared.db import tx
from polymath_shared.identity import content_hash, run_id

router = APIRouter()


class IntakeResponse(BaseModel):
    run_id: str
    accepted: bool
    already_exists: bool = False


@router.post("/intake", response_model=IntakeResponse)
async def intake(req: IntakeRequest) -> IntakeResponse:
    try:
        base64.b64decode(req.content_b64, validate=True)
    except Exception:
        raise HTTPException(status_code=422, detail="content_b64 is not valid base64")

    canonical_payload = {
        "corpus_id": req.corpus_id,
        "source_name": req.source_name,
        "media_type": req.media_type,
        "content_b64": req.content_b64,
        "config": req.config,
    }
    rid = run_id(req.corpus_id, canonical_payload)
    outbox_key = content_hash({"run": rid, "type": "intake.v1", "payload": canonical_payload})

    try:
        with tx() as conn:
            existing = conn.execute("SELECT 1 FROM runs WHERE run_id = %s", (rid,)).fetchone()
            if existing:
                return IntakeResponse(run_id=rid, accepted=True, already_exists=True)

            conn.execute(
                """
                INSERT INTO runs (run_id, corpus_id, status, metadata)
                VALUES (%s, %s, 'intake', %s)
                """,
                (rid, req.corpus_id, json.dumps({
                    "source_name": req.source_name,
                    "intake_payload": canonical_payload,
                })),
            )
            conn.execute(
                """
                INSERT INTO outbox_events (run_id, event_type, payload, idempotency_key)
                VALUES (%s, 'intake.v1', %s, %s)
                """,
                (rid, json.dumps(canonical_payload), outbox_key),
            )
    except psycopg.errors.UniqueViolation:
        return IntakeResponse(run_id=rid, accepted=True, already_exists=True)

    return IntakeResponse(run_id=rid, accepted=True)


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

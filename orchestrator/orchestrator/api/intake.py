"""Intake API. POST /ingest.

Validates input, writes a runs row, enqueues an intake.v1 job.
Returns run_id immediately. The control plane picks up the job.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


class IngestRequest(BaseModel):
    corpus_id: str
    source: str  # path or URL
    profile: str = "default"


class IngestResponse(BaseModel):
    run_id: str
    accepted: bool


@router.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest) -> IngestResponse:
    # TODO: write runs row + outbox + enqueue (atomically).
    raise NotImplementedError

"""Cross-process Pydantic models. Used everywhere."""
from __future__ import annotations

from pydantic import BaseModel


class RunRecord(BaseModel):
    run_id: str
    corpus_id: str
    status: str  # intake | reconciling | query_ready | degraded
    created_at: str
    updated_at: str


class StageAttempt(BaseModel):
    run_id: str
    stage: str
    contract_hash: str
    started_at: str
    completed_at: str | None
    outcome: str  # ok | failed | skipped
    error: str | None = None

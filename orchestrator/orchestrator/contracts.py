"""Orchestrator Pydantic models. Validation only."""
from __future__ import annotations

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    corpus_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    profile: str = "default"


class IngestResponse(BaseModel):
    run_id: str
    accepted: bool


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    corpus_id: str | None = None

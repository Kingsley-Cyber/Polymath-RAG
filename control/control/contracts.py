"""Control-plane Pydantic models. Validation only; no logic."""
from __future__ import annotations

from pydantic import BaseModel


class Heartbeat(BaseModel):
    control_id: str
    occurred_at: str  # ISO 8601 UTC
    last_tick_ok: bool
    last_census_size: int


class CorpusCensus(BaseModel):
    corpus_id: str
    desired: int
    observed: int
    missing: list[str]


class CensusReport(BaseModel):
    corpora: list[CorpusCensus]
    generated_at: str  # ISO 8601 UTC

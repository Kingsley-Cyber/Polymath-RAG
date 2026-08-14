"""GLiNER two-pass runtime. See AGENTS.md and ADR-0001.

Role: sidecar-gpu. One resident model serves entity and evidence proposal
tasks. Predicate selection remains outside this process.
"""
from __future__ import annotations

import os
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


MANIFEST_PATH = Path(__file__).with_name("manifest.toml")
EVIDENCE_LABELS: list[str] = [
    "creation: created, founded, established, or started",
    "causation: caused, led to, or produced",
    "usage: uses, applies, or operates with",
    "ownership: owns, possesses, or holds",
    "location: located, based, or headquartered",
    "temporal: happens at, during, before, or after",
    "part_of: part, component, or member of",
    "is_a: kind, type, or instance of",
    "employment: works for or has a role at",
    "communication: says, announces, reports, or tells",
    "comparison: compared, contrasted, or differs",
    "similarity: resembles, parallels, or is analogous",
    "opposition: opposes, conflicts, or contradicts",
    "improvement: improves or upgrades",
    "degradation: harms, degrades, or reduces",
    "dependency: depends on, requires, or relies on",
    "measurement: measured, quantified, or evaluated",
    "intention: intends, plans, or aims",
]


class InferRequest(BaseModel):
    task: Literal["entity", "evidence"]
    text: str
    threshold: float
    labels: list[str] = Field(default_factory=list)


class ProposalSpan(BaseModel):
    text: str
    start: int
    end: int
    label: str
    score: float


class InferResponse(BaseModel):
    task: Literal["entity", "evidence"]
    spans: list[ProposalSpan]
    model_release: str


def load_manifest() -> dict:
    with MANIFEST_PATH.open("rb") as handle:
        return tomllib.load(handle)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from gliner import GLiNER

    manifest = load_manifest()
    model_cfg = manifest["identity"]["model"]
    device = os.environ["POLYMATH_GLINER_DEVICE"]
    model = GLiNER.from_pretrained(
        model_cfg["id"],
        revision=model_cfg["revision"],
    )
    app.state.model = model.to(device)
    app.state.manifest = manifest
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/manifest")
async def manifest() -> dict:
    return app.state.manifest


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    model = app.state.model
    if model is None:
        return {"ready": False, "reason": "model not loaded"}
    model.predict_entities("readiness probe", ["readiness probe"])
    return {"ready": True}


@app.post("/infer", response_model=InferResponse)
async def infer(request: InferRequest) -> InferResponse:
    if request.task == "entity" and not request.labels:
        raise HTTPException(status_code=422, detail="entity task requires labels")
    labels = request.labels if request.task == "entity" else EVIDENCE_LABELS
    raw = app.state.model.predict_entities(
        request.text,
        labels,
        threshold=request.threshold,
    )
    return InferResponse(
        task=request.task,
        spans=[
            ProposalSpan(
                text=item["text"],
                start=int(item["start"]),
                end=int(item["end"]),
                label=item["label"].split(":", 1)[0].strip(),
                score=float(item["score"]),
            )
            for item in raw
        ],
        model_release=app.state.manifest["identity"]["version"],
    )

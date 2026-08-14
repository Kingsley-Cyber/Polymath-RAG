"""Reranker sidecar. ADR-0005.

Role: sidecar-gpu. Owns: one reranker model. Cosine scores, not logits.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class RerankRequest(BaseModel):
    query: str
    documents: list[str]
    top_k: int | None = None


class RerankResponse(BaseModel):
    scores: list[float]
    indices: list[int]


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sentence_transformers import CrossEncoder
    app.state.model = CrossEncoder("Qwen/Qwen3-Reranker-0.6B")
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    model = app.state.model
    if model is None:
        return {"ready": False, "reason": "model not loaded"}
    return {"ready": True}


@app.post("/rerank", response_model=RerankResponse)
async def rerank(req: RerankRequest) -> RerankResponse:
    model = app.state.model
    pairs = [[req.query, d] for d in req.documents]
    scores = model.predict(pairs).tolist()
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    if req.top_k is not None:
        order = order[: req.top_k]
    return RerankResponse(
        scores=scores,
        indices=order,
    )

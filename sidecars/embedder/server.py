"""Embedder sidecar. ADR-0005.

Role: sidecar-gpu. Owns: one embedding model. /ready does a real
1-token forward pass (ADR-0003 + ADR-0005).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class EmbedRequest(BaseModel):
    input: list[str]


class EmbedResponse(BaseModel):
    model: str
    data: list[dict]


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sentence_transformers import SentenceTransformer
    app.state.model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")
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
    # Real readiness: 1-token forward pass.
    _ = model.encode(["ready"], normalize_embeddings=True)
    return {"ready": True}


@app.post("/embeddings", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    model = app.state.model
    vectors = model.encode(req.input, normalize_embeddings=True)
    return EmbedResponse(
        model="qwen3-embedding-0.6b",
        data=[{"index": i, "embedding": v.tolist()} for i, v in enumerate(vectors)],
    )

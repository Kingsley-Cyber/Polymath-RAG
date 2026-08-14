"""Chat API. POST /chat.

Validates input, reads from the ledger, calls the synthesis path.
No long-running work. No scheduling. No model loading.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    corpus_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[int]


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    raise NotImplementedError

"""QUERY-RECEIPTS-V1 read surface: `GET /queries` — the last N served queries
(latency, scope, mode, status ok/abstained/error, citations, error text) plus
per-mode p50/p95 and abstention/error counts over the window. Backed by the
`query_receipts` table every /chat, /ask and /retrieve writes to."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from polymath_shared.db import tx
from polymath_shared.query_receipts import query_summary, recent_queries

router = APIRouter()


@router.get("/queries")
def queries(corpus_id: Optional[str] = None, kind: Optional[str] = None,
            limit: int = Query(20, ge=1, le=200),
            since_h: float = Query(24.0, gt=0, le=24 * 30)) -> dict:
    with tx() as conn:
        rows = recent_queries(conn, corpus_id=corpus_id, kind=kind, limit=limit, since_h=since_h)
        summary = query_summary(conn, corpus_id=corpus_id, kind=kind, since_h=since_h)
    return {"corpus_id": corpus_id, "kind": kind, "since_h": since_h,
            "count": len(rows), "summary": summary, "queries": rows}

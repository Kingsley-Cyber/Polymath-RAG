"""Health endpoints. /health (liveness), /ready (traffic), /sidecars.

The liveness/readiness split is the ISSUES_REPORT §3.3 fix: autoheal
acts only on /live failures; /ready reports "can I serve traffic now"
including sidecar readiness, without punishing startup.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict:
    try:
        sidecars = request.app.state.sidecars
    except AttributeError:
        sidecars = {}
    statuses = {name: s.is_ready() for name, s in sidecars.items()}
    return {"ready": True, "sidecars": statuses}


@router.get("/semantic_readiness")
async def semantic_readiness(corpus_id: str) -> dict:
    """SEMANTIC-READINESS-V1: the explicit semantic-completion verdict.

    `query_ready` (control contract, untouched) says the blocking
    pipeline converged; THIS says whether every semantic lane —
    FACT/PROCEDURE/CONCEPT execution, summaries, corpus map, artifact
    projections — completed. Zero yield is completion; failure is not.
    """
    from polymath_shared.db import tx
    from polymath_shared.semantic_readiness import semantic_completion

    with tx() as conn:
        row = conn.execute(
            "SELECT 1 FROM corpora WHERE corpus_id = %s", (corpus_id,),
        ).fetchone()
        if not row:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail={
                "error_code": "QUERY_SCOPE_UNKNOWN",
                "message": f"corpus {corpus_id!r} not found",
            })
        return semantic_completion(conn, corpus_id)


@router.get("/sidecars")
async def sidecars(request: Request) -> dict:
    try:
        registry = request.app.state.sidecars
    except AttributeError:
        registry = {}
    return {
        name: {
            "release": s.manifest.get("identity", {}).get("version"),
            "model": s.manifest.get("identity", {}).get("model"),
            "base_url": s.base_url,
            "ready": s.is_ready(),
        }
        for name, s in registry.items()
    }

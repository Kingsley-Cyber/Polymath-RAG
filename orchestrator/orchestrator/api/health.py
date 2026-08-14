"""Health endpoints. /health, /ready, /manifest."""
from __future__ import annotations

from fastapi import APIRouter, Request


router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict:
    # /ready means "I can serve traffic right now." Different from /health.
    sidecars = request.app.state.sidecars
    statuses = {name: s.is_ready() for name, s in sidecars.items()}
    return {"ready": all(statuses.values()), "sidecars": statuses}


@router.get("/manifest")
async def manifest(request: Request) -> dict:
    sidecars = request.app.state.sidecars
    return {"sidecars": {name: s.manifest for name, s in sidecars.items()}}

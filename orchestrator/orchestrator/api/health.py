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

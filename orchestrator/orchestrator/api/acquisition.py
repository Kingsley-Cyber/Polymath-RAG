"""RESEARCH ACQUISITION API (AUTORESEARCH-SOURCES-AND-HARNESS-V1 slice R8): the public entrypoint behind the MCP tool `research_acquire`.
A connected harness without its own browser asks Polymath to read a permitted page for the run's OPEN research step. All policy lives
in polymath_shared.acquisition.service; this module finds the run's open HARNESS_ACTION (read-only), applies run ownership exactly as
the adapter routes do, runs the read off the event loop (no database transaction is held while the browser reads) and maps refusals
to status codes.

Only the MCP servers on this host may call it. They call this listener directly; a request that came through a reverse proxy (it
carries X-Forwarded-For / X-Forwarded-Host: the public web UI proxy forwards every path here) is refused, because the proxy's own
login is not the MCP gate that keeps the host browser, which holds the owner's sign-ins, owner-only."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from polymath_shared import principal_context
from polymath_shared.acquisition import service as acquisition
from polymath_shared.adapter import service, store
from polymath_shared.db import tx

router = APIRouter()
log = logging.getLogger("orchestrator.acquisition")


class AcquireRequest(BaseModel):
    operation: str
    target: str = ""
    site: Optional[str] = None
    search_intent_id: Optional[str] = None
    limit: Optional[int] = None


def open_harness_action(conn, run_id: str) -> dict[str, Any] | None:
    """The run's open research step (the issued HARNESS_ACTION it awaits), or None. Read-only."""
    st = service.status(conn, run_id)
    if st.get("status") != "awaiting_harness":
        return None
    row = store.current_step(conn, run_id)
    step = (row or {}).get("step") or {}
    if (row or {}).get("status") != "issued" or not isinstance(step.get("harness_action"), dict):
        return None
    return step["harness_action"]


PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "forwarded")


@router.post("/adapter/{run_id}/acquire")
async def acquire(run_id: str, req: AcquireRequest, request: Request) -> dict:
    if any(request.headers.get(h) for h in PROXY_HEADERS):
        raise HTTPException(status_code=403, detail={"code": "PROXIED_CALLER", "message": "research acquisition answers only the MCP servers "
                                                     "on this host (their tool research_acquire), never a request relayed by a proxy"})
    principal = principal_context.current()
    try:
        with tx() as conn:
            service.assert_owner(conn, run_id, principal)
            action = open_harness_action(conn, run_id)
    except service.NotRunOwner:
        raise HTTPException(status_code=403, detail="no such run for this principal")
    except service.UnknownRun:
        raise HTTPException(status_code=404, detail=f"unknown adapter run {run_id!r}")
    try:
        out = await asyncio.to_thread(acquisition.acquire, principal_id=principal, action=action, operation=req.operation,
                                      target=req.target, site=req.site, search_intent_id=req.search_intent_id, limit=req.limit)
    except acquisition.AcquisitionRefused as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message})
    log.info("acquisition %s run=%s action=%s operation=%s site=%s target=%s status=%s items=%s sources=%s", out.get("acquisition_id"), run_id,
             (action or {}).get("action_id"), req.operation, out.get("site"), str(out.get("target") or "")[:300], out.get("status"),
             len(out.get("items") or []), ",".join(s_["source_id"] for s_ in out.get("sources") or [])[:600])
    return out

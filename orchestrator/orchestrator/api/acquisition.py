"""RESEARCH ACQUISITION API (AUTORESEARCH-SOURCES-AND-HARNESS-V1 slice R8): the public entrypoint behind the MCP tool `research_acquire`.
A connected harness without its own browser asks Polymath to read a permitted page for the run's OPEN research step. All policy lives
in polymath_shared.acquisition.service; this module finds the run's open HARNESS_ACTION (read-only), applies run ownership exactly as
the adapter routes do, runs the read off the event loop (no database transaction is held while the browser reads) and maps refusals
to status codes.

Only the MCP servers on this host may call it. They call this listener directly; a request that came through a reverse proxy (it
carries X-Forwarded-For / X-Forwarded-Host: the public web UI proxy forwards every path here) is refused, because the proxy's own
login is not the MCP gate that keeps the host browser, which holds the owner's sign-ins, owner-only. They call it by a loopback name
(127.0.0.1:7200 by default), so a request whose Host names anything else is refused too: a web page that re-bound its own name to
this machine (DNS rebinding) arrives direct and without proxy headers, but it still sends ITS name (TRAIL-EXT-BUGHUNT-V1 B-28).

SUPPLIER-APIS (owner-approved 2026-09-27): the READ-ONLY supplier routes behind the MCP tools supplier_search / supplier_product /
supplier_freight / supplier_warehouses live here too, under the same rules: the MCP servers on this host only (no proxy, a
loopback Host), the owner only (they spend the owner's CJ account and quota: a principal gets 403). The policy is
polymath_shared.acquisition.supplier; nothing here orders, pays, lists or disputes."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from polymath_shared import principal_context
from polymath_shared.acquisition import service as acquisition
from polymath_shared.acquisition import supplier
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
#: the names the MCP servers call this listener by (POLYMATH_ORCH_URL / POLYMATH_API default to http://127.0.0.1:7200)
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def loopback_host(host: str | None) -> bool:
    """True when a Host header names this machine's loopback (any port)."""
    try:
        return urlsplit("//" + (host or "")).hostname in LOOPBACK_HOSTS
    except ValueError:
        return False


def refuse_unless_direct(request: Request, what: str = "research acquisition", tools: str = "tool research_acquire") -> None:
    """403 unless the MCP servers on this host called directly: no proxy header, a loopback Host (B-28)."""
    if any(request.headers.get(h) for h in PROXY_HEADERS):
        raise HTTPException(status_code=403, detail={"code": "PROXIED_CALLER", "message": f"{what} answers only the MCP servers "
                                                     f"on this host (their {tools}), never a request relayed by a proxy"})
    if not loopback_host(request.headers.get("host")):
        raise HTTPException(status_code=403, detail={"code": "NON_LOOPBACK_HOST", "message": f"{what} answers only the MCP "
                                                     "servers on this host, which call it at 127.0.0.1 or localhost; a request naming another "
                                                     "host (such as a web page that re-bound its own name to this machine) is refused"})


@router.post("/adapter/{run_id}/acquire")
async def acquire(run_id: str, req: AcquireRequest, request: Request) -> dict:
    refuse_unless_direct(request)
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


# ------------------------------------------------------------------------------------------ SUPPLIER-APIS: the supplier tools --
class SupplierSearchRequest(BaseModel):
    query: str
    source: str = "cj"
    limit: int | None = supplier.SEARCH_LIMIT_DEFAULT


class SupplierProductRequest(BaseModel):
    product_id: str


class SupplierFreightRequest(BaseModel):
    variant_id: str
    country: str
    quantity: int = 1
    from_country: str = "CN"


_SUPPLIER_WHAT, _SUPPLIER_TOOLS = "supplier lookup", "tools " + ", ".join(supplier.TOOLS)


async def _supplier(request: Request, tool: str, fn, **kw: Any) -> dict:
    refuse_unless_direct(request, _SUPPLIER_WHAT, _SUPPLIER_TOOLS)
    try:
        out = await asyncio.to_thread(fn, principal_id=principal_context.current(), **kw)
    except acquisition.AcquisitionRefused as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message})
    log.info("supplier %s source=%s status=%s rows=%s", tool, out.get("source"), out.get("status"),
             len(out.get("items") or out.get("variants") or out.get("options") or out.get("warehouses") or []))
    return out


@router.post("/supplier/search")
async def supplier_search(req: SupplierSearchRequest, request: Request) -> dict:
    return await _supplier(request, "supplier_search", supplier.search, query=req.query, source=req.source, limit=req.limit)


@router.post("/supplier/product")
async def supplier_product(req: SupplierProductRequest, request: Request) -> dict:
    return await _supplier(request, "supplier_product", supplier.product, product_id=req.product_id)


@router.post("/supplier/freight")
async def supplier_freight(req: SupplierFreightRequest, request: Request) -> dict:
    return await _supplier(request, "supplier_freight", supplier.freight, variant_id=req.variant_id, country=req.country,
                           quantity=req.quantity, from_country=req.from_country)


@router.get("/supplier/warehouses")
async def supplier_warehouses(request: Request) -> dict:
    return await _supplier(request, "supplier_warehouses", supplier.warehouses)

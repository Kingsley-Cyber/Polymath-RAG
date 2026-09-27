"""ADAPTER RUN API (COGNITIVE-ADAPTER-V1, ADR-0018, plan §3): the thin public entrypoints behind the seven MCP tools.
All authority lives in polymath_shared.adapter.service; this module only maps HTTP ↔ service and errors ↔ status codes."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from polymath_shared import principal_context
from polymath_shared.adapter import dossier, run_view, service
from polymath_shared.adapter.contracts import ContractViolation
from polymath_shared.adapter.transitions import SubmissionRejected
from polymath_shared.db import tx

router = APIRouter()
log = logging.getLogger("orchestrator.adapter")

#: the dossier page: inline styles only — no script, no fetch, no form, no base, no framing by another site
REPORT_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'",
    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"}


class StartRequest(BaseModel):
    adapter_id: str
    input: dict[str, Any]
    request_options: Optional[dict[str, Any]] = None


class SubmitRequest(BaseModel):
    step_id: str
    payload: dict[str, Any]
    agent_identity: str = "connected-agent"
    model: Optional[str] = None
    kind: Optional[str] = None          # reasoning | receipt (derived from the awaiting step when omitted)


def _404(run_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"unknown adapter run {run_id!r}")


def _own(conn, run_id: str) -> None:
    """RUN OWNERSHIP (migration 0066): a request made for a principal reaches only that principal's runs. One answer for
    "not yours" and "no such run". No principal context = the legacy / trusted-local caller, unchanged."""
    try:
        service.assert_owner(conn, run_id, principal_context.current())
    except service.NotRunOwner:
        raise HTTPException(status_code=403, detail="no such run for this principal")


@router.get("/adapter/list")
async def adapter_list() -> dict:
    return {"adapters": service.list_adapters(), "contract": "adapter-v1"}


@router.get("/adapter/runs")
async def adapter_runs(status: str | None = None, adapter_id: str | None = None, limit: int = 50,
                       before: str | None = None) -> dict:
    """TRAIL-INTERFACE-V1 T1: newest first. A principal sees only its own runs (the web boundary forwards a signed-in friend
    as one); no principal = the owner / trusted-local caller, every run."""
    with tx() as conn:
        return {"runs": run_view.list_runs(conn, principal_context.current(), status=status, adapter_id=adapter_id,
                                           limit=limit, before=before)}


@router.post("/adapter/start")
async def adapter_start(req: StartRequest) -> dict:
    from orchestrator.web_scope import require_adapter_start
    require_adapter_start(req.adapter_id, req.input, req.request_options)  # FRIENDS-ACCESS-V1 D5
    try:
        with tx() as conn:
            return service.start(conn, adapter_id=req.adapter_id, input_payload=req.input, request_options=req.request_options,
                                 owner_principal_id=principal_context.current())
    except service.UnknownAdapter as exc:
        raise HTTPException(status_code=404, detail=f"unknown adapter {exc.args[0]!r}")
    except (ContractViolation, SubmissionRejected) as exc:
        raise HTTPException(status_code=422, detail=getattr(exc, "errors", [str(exc)]))


@router.get("/adapter/{run_id}/next")
async def adapter_next(run_id: str) -> dict:
    try:
        with tx() as conn:
            _own(conn, run_id)
            return service.next_step(conn, run_id)
    except service.UnknownRun:
        raise _404(run_id)


@router.post("/adapter/{run_id}/submit")
async def adapter_submit(run_id: str, req: SubmitRequest) -> dict:
    submission = {"run_id": run_id, "step_id": req.step_id, "payload": req.payload,
                  "submitted_by": {"agent_identity": req.agent_identity, **({"model": req.model} if req.model else {})},
                  **({"kind": req.kind} if req.kind else {})}
    try:
        with tx() as conn:
            _own(conn, run_id)
            return service.submit(conn, run_id, submission)
    except service.UnknownRun:
        raise _404(run_id)
    except SubmissionRejected as exc:
        raise HTTPException(status_code=422, detail={"rejected": exc.errors})
    except ContractViolation as exc:
        raise HTTPException(status_code=422, detail={"rejected": exc.errors})


@router.get("/adapter/{run_id}/status")
async def adapter_status(run_id: str) -> dict:
    try:
        with tx() as conn:
            _own(conn, run_id)
            return service.status(conn, run_id)
    except service.UnknownRun:
        raise _404(run_id)


@router.get("/adapter/{run_id}/view")
async def adapter_view(run_id: str) -> dict:
    """TRAIL-INTERFACE-V1 T1: one run for the Research screens — progress, the recompiled output sections, contradictions and
    unknowns, whether it has a dossier; the owner (no principal) also gets the registry block (T5). Read-only; the run owner's
    check as for every run route."""
    try:
        with tx() as conn:
            _own(conn, run_id)
            return run_view.build_view(conn, run_id, owner=principal_context.current() is None)
    except service.UnknownRun:
        raise _404(run_id)


def _report_html(run_id: str, layout: str, principal: str | None) -> str:
    """In a worker thread, under the request's own principal: the run's rows are read in one short transaction, then the engine
    renders them in a subprocess after the transaction has closed."""
    with principal_context.acting_as(principal):
        try:
            with tx() as conn:
                _own(conn, run_id)
                journal = run_view.dossier_journal(conn, run_id)
        except service.UnknownRun:
            raise _404(run_id)
        except dossier.NoDossier as exc:
            raise HTTPException(status_code=404, detail={"error_code": "NO_DOSSIER", "message": f"adapter {exc.args[0]!r} has no dossier"})
    try:
        return dossier.render_dossier(journal, layout, title=f"Dossier · {run_view.title_of(journal.get('input'))}")
    except dossier.DossierError as exc:
        log.warning("dossier run=%s layout=%s %s: %s", run_id, layout, exc.code, exc)
        raise HTTPException(status_code=504 if exc.code == "DOSSIER_TIMEOUT" else 500,
                            detail={"error_code": exc.code, "message": "the dossier could not be rendered"})


@router.get("/adapter/{run_id}/report")
async def adapter_report(run_id: str, layout: str = "FULL_RESEARCH", download: bool = False) -> HTMLResponse:
    """TRAIL-INTERFACE-V1 T5: the run's research dossier — the engine's own renderer, run out of process on the journal rebuilt from the
    stored run, sanitized, and sent under a CSP that allows no script. The run owner's check as for every run route; `download=1`
    sends it as a file."""
    if layout not in dossier.LAYOUTS:
        raise HTTPException(status_code=422, detail={"error_code": "UNKNOWN_LAYOUT", "message": f"layout is one of {', '.join(dossier.LAYOUTS)}"})
    page = await run_in_threadpool(_report_html, run_id, layout, principal_context.current())
    headers = dict(REPORT_HEADERS)
    if download:
        headers["Content-Disposition"] = f'attachment; filename="dossier-{re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)}.html"'
    return HTMLResponse(page, headers=headers)


@router.get("/adapter/{run_id}/result")
async def adapter_result(run_id: str) -> dict:
    try:
        with tx() as conn:
            _own(conn, run_id)
            return service.result(conn, run_id)
    except service.UnknownRun:
        raise _404(run_id)
    except service.NotTerminal as exc:
        raise HTTPException(status_code=409, detail=f"run is not terminal (status {exc.args[0]})")


def _external_cancel(ext: dict) -> dict | None:
    """Best-effort CANCEL of a pending TrailSignal operation through Trail's public boundary (E4)."""
    from polymath_shared.adapter import trail_client as TC
    client = TC.TrailMCPClient.from_env()
    if not client.configured:
        return None
    ref = {"operation_id": ext["operation_id"], "operation_kind": ext["operation_kind"], "temporal_workflow_id": ext.get("temporal_workflow_id"),
           "temporal_run_id": ext.get("temporal_run_id"), "submitted_at": ext["submitted_at"]}
    status = client.status(ref)
    if status.get("phase") == "TERMINAL":
        return TC.receipt_after_poll(ext, status)
    cmd = TC.cancel_command(ext["operation_id"], expected_revision=int(status.get("revision") or 0),
                            key=TC.identifier(ext["run_id"], ext["step_id"], "cancel"))
    return TC.receipt_after_poll(ext, client.cancel(cmd))


@router.post("/adapter/{run_id}/cancel")
async def adapter_cancel(run_id: str) -> dict:
    try:
        with tx() as conn:
            _own(conn, run_id)
            return service.cancel(conn, run_id, external_cancel=_external_cancel)
    except service.UnknownRun:
        raise _404(run_id)

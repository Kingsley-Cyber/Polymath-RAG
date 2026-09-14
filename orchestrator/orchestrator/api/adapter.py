"""ADAPTER RUN API (COGNITIVE-ADAPTER-V1, ADR-0018, plan §3): the thin public entrypoints behind the seven MCP tools.
All authority lives in polymath_shared.adapter.service; this module only maps HTTP ↔ service and errors ↔ status codes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from polymath_shared.adapter import service
from polymath_shared.adapter.contracts import ContractViolation
from polymath_shared.adapter.transitions import SubmissionRejected
from polymath_shared.db import tx

router = APIRouter()


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


@router.get("/adapter/list")
async def adapter_list() -> dict:
    return {"adapters": service.list_adapters(), "contract": "adapter-v1"}


@router.post("/adapter/start")
async def adapter_start(req: StartRequest) -> dict:
    try:
        with tx() as conn:
            return service.start(conn, adapter_id=req.adapter_id, input_payload=req.input, request_options=req.request_options)
    except service.UnknownAdapter as exc:
        raise HTTPException(status_code=404, detail=f"unknown adapter {exc.args[0]!r}")
    except (ContractViolation, SubmissionRejected) as exc:
        raise HTTPException(status_code=422, detail=getattr(exc, "errors", [str(exc)]))


@router.get("/adapter/{run_id}/next")
async def adapter_next(run_id: str) -> dict:
    try:
        with tx() as conn:
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
            return service.status(conn, run_id)
    except service.UnknownRun:
        raise _404(run_id)


@router.get("/adapter/{run_id}/result")
async def adapter_result(run_id: str) -> dict:
    try:
        with tx() as conn:
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
            return service.cancel(conn, run_id, external_cancel=_external_cancel)
    except service.UnknownRun:
        raise _404(run_id)

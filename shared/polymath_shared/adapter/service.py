"""The adapter-run service: what the orchestrator routes (adapter_*) and the step worker call. Composes the pure core
(transitions/manifest/contracts) with the store; each public function runs inside the caller's transaction."""
from __future__ import annotations

import datetime as _dt
import hashlib
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from .contracts import AUTOMATIC_STEP_TYPES, assert_valid, stable_hash
from .manifest import ADAPTER_DIR, Manifest, list_manifests
from . import store, transitions as T
from .transitions import BudgetExhausted, RunState, SubmissionRejected

#: an executor for one automatic step: (step, state, manifest) -> ExecOutcome
ExecOutcome = dict[str, Any]   # keys: output (dict), evidence_refs (list), external (dict|None), gap (dict|None)
Executor = Callable[[dict[str, Any], RunState, Manifest], ExecOutcome]

KNOWLEDGE_KINDS = ("chunk", "document", "graph_fact", "graph_hop", "parent_map")
MAX_CONTEXT_REFS = 200


class UnknownAdapter(KeyError):
    pass


class UnknownRun(KeyError):
    pass


class NotTerminal(RuntimeError):
    pass


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@lru_cache(maxsize=4)
def _registry(directory: str) -> dict[str, Manifest]:
    return {m.adapter_id: m for m in list_manifests(Path(directory))}


def registry(directory: Path | None = None) -> dict[str, Manifest]:
    return _registry(str(directory or ADAPTER_DIR))


def reset_registry() -> None:
    _registry.cache_clear()


def manifest_for(adapter_id: str, directory: Path | None = None) -> Manifest:
    try:
        return registry(directory)[adapter_id]
    except KeyError:
        raise UnknownAdapter(adapter_id) from None


def list_adapters(directory: Path | None = None) -> list[dict[str, Any]]:
    out = []
    for m in registry(directory).values():
        ext = [s for s in m.steps.values() if s["type"] == "EXTERNAL_OPERATION"]
        out.append({**m.identity, "description": m.raw.get("description", ""), "steps": len(m.steps),
                    "agent_reason_steps": sum(1 for s in m.steps.values() if s["type"] == "AGENT_REASON"),
                    "external_operations": {"working": sum(1 for s in ext if (s.get("external") or {}).get("availability") == "working"),
                                            "planned": sum(1 for s in ext if (s.get("external") or {}).get("availability") == "planned")},
                    "input_schema": m.raw.get("input_schema"), "entry_step_id": m.entry_step_id, "terminal_step_id": m.terminal_step_id})
    return out


# ─────────────────────────────────────────────────────────── lifecycle (routes)
def start(conn, *, adapter_id: str, input_payload: dict[str, Any], request_options: dict[str, Any] | None = None,
          directory: Path | None = None) -> dict[str, Any]:
    """Create a durable run (status running — the worker picks it up). Idempotent on request_options.idempotency_key."""
    m = manifest_for(adapter_id, directory)
    opts = dict(request_options or {})
    assert_valid("adapter_run_request", {"adapter_id": adapter_id, "input": input_payload, "request_options": opts})
    key = opts.get("idempotency_key")
    if key:
        existing = store.find_run_by_idempotency(conn, f"{adapter_id}:{key}")
        if existing:
            return run_ref(conn, existing)
    seed = f"{adapter_id}:{key}" if key else f"{adapter_id}:{uuid.uuid4()}"
    run_id = "adr_" + hashlib.sha256(seed.encode()).hexdigest()[:32]
    state = T.start_run(m, run_id, input_payload, opts)
    state = T.replace(state, status="running")
    store.insert_run(conn, state, m, idempotency_key=(f"{adapter_id}:{key}" if key else None),
                     agent_identity=opts.get("agent_identity"))
    return run_ref(conn, run_id)


def run_ref(conn, run_id: str) -> dict[str, Any]:
    loaded = store.load_run(conn, run_id)
    if not loaded:
        raise UnknownRun(run_id)
    state, meta = loaded
    ref = {"run_id": run_id, "adapter_id": state.adapter_id, "adapter_version": meta["adapter_version"],
           "workflow_version": meta["workflow_version"], "created_at": _ts(meta["created_at"]), "status": state.status}
    assert_valid("adapter_run_ref", ref)
    return ref


def _ts(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return v.astimezone(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def status(conn, run_id: str, directory: Path | None = None) -> dict[str, Any]:
    loaded = store.load_run(conn, run_id)
    if not loaded:
        raise UnknownRun(run_id)
    state, meta = loaded
    m = manifest_for(state.adapter_id, directory)
    return T.run_status_view(m, state, started_at=_ts(meta["created_at"]), updated_at=_ts(meta["updated_at"]),
                             terminal_at=_ts(meta["terminal_at"]), agent_identity=meta.get("agent_identity"))


def next_step(conn, run_id: str, directory: Path | None = None) -> dict[str, Any]:
    """The step the connected agent must answer, or the run status when nothing is awaiting it."""
    st = status(conn, run_id, directory)
    if st["status"] == "awaiting_agent":
        row = store.current_step(conn, run_id)
        if row and row["status"] == "issued":
            return {"kind": "step", "step": row["step"], "status": st}
    return {"kind": "status", "status": st}


def submit(conn, run_id: str, submission: dict[str, Any], directory: Path | None = None) -> dict[str, Any]:
    """Validate and accept an AGENT_REASON submission; the run returns to `running` for the worker. Raises SubmissionRejected."""
    loaded = store.load_run(conn, run_id, for_update=True)
    if not loaded:
        raise UnknownRun(run_id)
    state, meta = loaded
    m = manifest_for(state.adapter_id, directory)
    row = store.current_step(conn, run_id)
    if not row:
        raise SubmissionRejected(["no step has been issued"])
    step = row["step"]
    sub = {**submission, "run_id": run_id}
    sub.setdefault("submitted_at", now_iso())
    sub.setdefault("submission_hash", stable_hash(submission.get("payload")))
    started = now_iso()
    try:
        new_state = T.accept_submission(m, state, step, sub)
    except SubmissionRejected as exc:
        receipt = _receipt(step, "rejected", started, evidence_ids=[], model=sub.get("submitted_by", {}).get("model"),
                           validation={"ok": False, "errors": exc.errors})
        # the step stays ISSUED (the agent may retry); the rejection is receipted on the row
        store.finish_step(conn, run_id, row["sequence"], status="issued", receipt=receipt)
        raise
    receipt = _receipt(step, "accepted", started, evidence_ids=sorted(_cited(sub["payload"])),
                       model=sub.get("submitted_by", {}).get("model") or sub.get("submitted_by", {}).get("agent_identity"),
                       validation={"ok": True, "errors": []})
    store.finish_step(conn, run_id, row["sequence"], status="accepted", receipt=receipt, output=sub["payload"], submission=sub)
    store.save_state(conn, new_state)
    return status(conn, run_id, directory)


def cancel(conn, run_id: str, directory: Path | None = None) -> dict[str, Any]:
    loaded = store.load_run(conn, run_id, for_update=True)
    if not loaded:
        raise UnknownRun(run_id)
    state, _ = loaded
    store.save_state(conn, T.cancel_run(state))
    return status(conn, run_id, directory)


def result(conn, run_id: str) -> dict[str, Any]:
    loaded = store.load_run(conn, run_id)
    if not loaded:
        raise UnknownRun(run_id)
    state, _ = loaded
    if not state.terminal:
        raise NotTerminal(state.status)
    res = store.load_result(conn, run_id)
    if res is None:                       # cancelled / failed / gap before COMPILE_RESULT: synthesise the terminal result
        res = _compile_result(conn, run_id, state, manifest_for(state.adapter_id), output={}, persist=True)
    return res


# ─────────────────────────────────────────────────────────── the step engine (worker)
def advance(conn, run_id: str, executors: dict[str, Executor], *, max_steps: int | None = None,
            directory: Path | None = None) -> RunState:
    """Drive a RUNNING run forward: issue the next step; execute automatic steps through `executors`; stop at an
    AGENT_REASON step (awaiting_agent), at COMPILE_RESULT (completed + result), at a typed gap, or after `max_steps`.
    Each step commits as one unit through the caller's transaction discipline (the worker wraps each call in tx())."""
    loaded = store.load_run(conn, run_id, for_update=True)
    if not loaded:
        raise UnknownRun(run_id)
    state, _ = loaded
    m = manifest_for(state.adapter_id, directory)
    done = 0
    while state.status == "running" and (max_steps is None or done < max_steps):
        row = store.current_step(conn, run_id)
        if row and row["status"] == "issued":
            # an automatic step issued by a crashed worker, or a PENDING external operation: re-execute it
            # (idempotent) — a prior ExternalOperationReceiptV1 travels with the step so the executor polls, not resubmits
            step = dict(row["step"])
            if row.get("external_operation"):
                step["_external_receipt"] = row["external_operation"]
        else:
            try:
                state, step = T.issue_step(m, state, issued_at=now_iso(), evidence_refs=_context_refs(state),
                                           inputs=state.input)
            except BudgetExhausted as exc:
                state = T.terminal_gap(state, "BUDGET_EXHAUSTED", str(exc), step_id=state.current_step_id)
                store.save_state(conn, state)
                break
            store.insert_step(conn, step)
            store.save_state(conn, state)
            if step["step_type"] == "AGENT_REASON":
                break                                        # the agent answers through adapter_submit
        started = now_iso()
        if step["step_type"] == "COMPILE_RESULT":
            out = _compile_result(conn, run_id, state, m, output=None, persist=True, step=step)
            receipt = _receipt(step, "executed", started, evidence_ids=out["lineage"]["polymath_evidence_ids"], model=None,
                               validation={"ok": True, "errors": []})
            store.finish_step(conn, run_id, step["sequence"], status="executed", receipt=receipt, output={"result_hash": stable_hash(out)})
            state = T.record_automatic_output(state, step["step_id"], {"result_hash": stable_hash(out)})
            state = T.complete_run(state)
            store.save_state(conn, state)
            done += 1
            break
        executor = executors.get(step["step_type"])
        if executor is None:
            state = T.terminal_gap(state, "STEP_TYPE_UNSUPPORTED", f"no executor for {step['step_type']}", step_id=step["step_id"])
            store.finish_step(conn, run_id, step["sequence"], status="skipped",
                              receipt=_receipt(step, "skipped", started, evidence_ids=[], model=None, validation={"ok": False, "errors": ["unsupported"]}))
            store.save_state(conn, state)
            break
        try:
            outcome = executor(step, state, m)
        except Exception as exc:  # noqa: BLE001 — a step failure is a typed run failure, never a silent skip
            failure = {"code": "STEP_EXECUTOR_ERROR", "message": f"{type(exc).__name__}: {exc}"[:2000], "step_id": step["step_id"]}
            store.finish_step(conn, run_id, step["sequence"], status="failed",
                              receipt=_receipt(step, "failed", started, evidence_ids=[], model=None, validation={"ok": False, "errors": [failure["message"]]}, failure=failure))
            state = T.replace(state, status="failed", failure=failure)
            store.save_state(conn, state)
            break
        if outcome.get("pending"):
            # EXTERNAL_OPERATION two-phase: the operation is submitted/polled but not terminal. Record its
            # ExternalOperationReceiptV1 on the ISSUED step and stop; the next claim re-executes this step, which
            # finds the receipt and polls again (idempotent by operation_id — never a second submit).
            ext = outcome.get("external")
            if ext:
                assert_valid("external_operation_receipt", ext)
            store.finish_step(conn, run_id, step["sequence"], status="issued", receipt=None, external=ext)
            state = T.replace(state, status="running")
            store.save_state(conn, state)
            break
        gap = outcome.get("gap")
        if gap:
            store.finish_step(conn, run_id, step["sequence"], status="skipped",
                              receipt=_receipt(step, "skipped", started, evidence_ids=[], model=None, validation={"ok": False, "errors": [gap["message"]]}, failure=None),
                              external=outcome.get("external"))
            state = T.terminal_gap(state, gap["code"], gap["message"], step_id=step["step_id"])
            store.save_state(conn, state)
            break
        output = dict(outcome.get("output") or {})
        refs = list(outcome.get("evidence_refs") or [])
        if refs:
            output["_evidence_refs"] = refs
        receipt = _receipt(step, "executed", started, evidence_ids=[r["id"] for r in refs], model=None,
                           validation={"ok": True, "errors": []},
                           external_ids=[outcome["external"]["operation_id"]] if outcome.get("external") else [])
        store.finish_step(conn, run_id, step["sequence"], status="executed", receipt=receipt, output=output, external=outcome.get("external"))
        state = T.record_automatic_output(state, step["step_id"], output)
        store.save_state(conn, state)
        done += 1
    return state


# ─────────────────────────────────────────────────────────── helpers
def _cited(payload: Any) -> set[str]:
    return T._cited_ids(payload)


def _context_refs(state: RunState) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for sid, out in state.outputs.items():
        for r in (out or {}).get("_evidence_refs") or []:
            seen.setdefault(r["id"], r)
    return list(seen.values())[:MAX_CONTEXT_REFS]


def _receipt(step: dict[str, Any], status_: str, started: str, *, evidence_ids: list[str], model: str | None,
             validation: dict[str, Any], failure: dict[str, Any] | None = None, external_ids: list[str] | None = None) -> dict[str, Any]:
    ended = now_iso()
    r = {"run_id": step["run_id"], "step_id": step["step_id"], "step_type": step["step_type"], "sequence": step["sequence"],
         "status": status_, "started_at": started, "ended_at": ended,
         "wall_ms": max(0, int((_dt.datetime.fromisoformat(ended.replace("Z", "+00:00")) - _dt.datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds() * 1000)),
         "evidence_ids": list(evidence_ids), "external_operation_ids": list(external_ids or []), "model_or_agent": model,
         "validation": validation, "failure": failure}
    r["receipt_hash"] = stable_hash(r)
    assert_valid("adapter_step_receipt", r)
    return r


def _gather(outputs: dict[str, Any], key: str) -> Any:
    """First value named `key` found in step outputs, newest step first (top level, then one level down)."""
    for sid in reversed(list(outputs)):
        out = outputs[sid] or {}
        if isinstance(out, dict):
            if key in out:
                return out[key]
            for v in out.values():
                if isinstance(v, dict) and key in v:
                    return v[key]
    return None


def _collect_lists(outputs: dict[str, Any], key: str) -> list[Any]:
    found: list[Any] = []
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == key and isinstance(v, list):
                    found.extend(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    for out in outputs.values():
        walk(out)
    return found


def _compile_result(conn, run_id: str, state: RunState, m: Manifest, *, output: dict[str, Any] | None, persist: bool,
                    step: dict[str, Any] | None = None) -> dict[str, Any]:
    _, meta = store.load_run(conn, run_id)
    steps = store.list_steps(conn, run_id)
    include = list((step or {}).get("config", {}).get("include") or (m.step(m.terminal_step_id).get("config") or {}).get("include") or [])
    if output is None:
        output = {}
        for key in include:
            if key == "lineage":
                continue
            v = _gather(state.outputs, key)
            if v is not None:
                output[key] = v
    evidence_ids, query_ids, ext_ops = [], [], []
    for r in _context_refs(state):
        (query_ids if r["kind"] == "query_receipt" else evidence_ids if r["kind"] in KNOWLEDGE_KINDS else []).append(r["id"])
    for s in steps:
        e = s.get("external_operation")
        if e:
            ext_ops.append({"external_system": e["external_system"], "operation_kind": e.get("operation_kind"), "operation_id": e["operation_id"],
                            "record_ids": list(e.get("record_ids") or [])})
    terminal_status = {"completed": "completed", "terminal_gap": "terminal_gap", "cancelled": "cancelled", "failed": "failed"}.get(state.status, "completed")
    res = {"run_id": run_id, **m.identity, "status": terminal_status, "started_at": _ts(meta["created_at"]),
           "terminal_at": _ts(meta["terminal_at"]) or now_iso(), "output": output,
           "lineage": {"polymath_evidence_ids": sorted(set(evidence_ids)), "query_receipt_ids": sorted(set(query_ids)),
                       "step_receipt_hashes": [s["receipt"]["receipt_hash"] for s in steps if s.get("receipt")],
                       "external_operations": ext_ops},
           "contradictions": [c for c in _collect_lists(state.outputs, "contradictions") if isinstance(c, dict)],
           "unknowns": [({"about": u} if isinstance(u, str) else u) for u in _collect_lists(state.outputs, "unknowns")],
           "gap": state.gap, "agent_identity": meta.get("agent_identity")}
    assert_valid("adapter_result", res)
    if persist:
        store.insert_result(conn, run_id, res, stable_hash(res))
    return res

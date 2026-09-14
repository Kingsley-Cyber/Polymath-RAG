"""The adapter-run service: what the orchestrator routes (adapter_*) and the step worker call. Composes the pure core
(transitions/manifest/contracts) with the store; each public function runs inside the caller's transaction."""
from __future__ import annotations

import datetime as _dt
import hashlib
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from .contracts import AGENT_ANSWERED_STEP_TYPES, AUTOMATIC_STEP_TYPES, PRIOR_EVIDENCE_KINDS, assert_valid, stable_hash, validate
from .manifest import ADAPTER_DIR, Manifest, list_manifests
from . import hypotheses as H, store, transitions as T
from .hypotheses import HypothesisRejected
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
    if st["status"] in ("awaiting_agent", "awaiting_harness"):
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
    who = sub.get("submitted_by", {}).get("model") or sub.get("submitted_by", {}).get("agent_identity")
    if step["step_type"] == "HARNESS_ACTION":
        # a HarnessResearchReceiptV1: provenance recorded, nothing admitted yet (TrailSignal admission is the next automatic step)
        rec = dict(sub["payload"])
        rhash = stable_hash(rec)
        store.record_receipt(conn, step["harness_action"]["action_id"], rec, rhash)
        output = {**rec, "_harness_action_id": step["harness_action"]["action_id"], "_receipt_hash": rhash}
        new_state = T.replace(new_state, outputs={**new_state.outputs, step["step_id"]: output})   # later steps see the bound receipt
        receipt = _receipt(step, "accepted", started, evidence_ids=[], model=rec.get("harness_id") or who, validation={"ok": True, "errors": []})
        receipt["harness_receipt_hash"] = rhash
        receipt["receipt_hash"] = stable_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
        store.finish_step(conn, run_id, row["sequence"], status="accepted", receipt=receipt, output=output, submission=sub)
        store.save_state(conn, new_state)
        return status(conn, run_id, directory)
    # θ ledger: generated hypotheses and/or proposed transitions inside a reasoning payload become durable state in the SAME unit
    output = dict(sub["payload"])
    transition_ids: list[str] = []
    try:
        output, transition_ids = _apply_theta(conn, run_id, step, m, state, output, started)
    except HypothesisRejected as exc:
        errors = ["hypotheses: " + e for e in exc.errors]
        receipt = _receipt(step, "rejected", started, evidence_ids=[], model=who, validation={"ok": False, "errors": errors})
        store.finish_step(conn, run_id, row["sequence"], status="issued", receipt=receipt)
        raise SubmissionRejected(errors) from None
    new_state = T.replace(new_state, outputs={**new_state.outputs, step["step_id"]: output})       # payload + ledger ids
    receipt = _receipt(step, "accepted", started, evidence_ids=sorted(_cited(sub["payload"])), model=who, validation={"ok": True, "errors": []})
    if transition_ids:
        receipt["hypothesis_transition_ids"] = transition_ids
        receipt["receipt_hash"] = stable_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
    store.finish_step(conn, run_id, row["sequence"], status="accepted", receipt=receipt, output=output, submission=sub)
    store.save_state(conn, new_state)
    return status(conn, run_id, directory)


def _apply_theta(conn, run_id: str, step: dict[str, Any], m: Manifest, state: RunState, payload: dict[str, Any], now: str) -> tuple[dict[str, Any], list[str]]:
    """A reasoning payload may carry `hypotheses` (θ GENERATE) and/or `transitions` (θ REVISE/SPLIT proposals). They are validated by
    the pure ledger against the step's context and persisted as immutable revisions + transitions; the payload gains the ids."""
    out = dict(payload)
    tids: list[str] = []
    max_h = int(m.budgets.get("max_hypotheses", 8))
    snapshot = _registry_snapshot(state)
    current = store.current_hypotheses(conn, run_id)
    if isinstance(payload.get("hypotheses"), list) and step.get("theta_op") in (None, "generate_hypotheses", "split_hypotheses", "derive_mechanisms",
                                                                                "cross_map_frictions", "derive_physical_jobs", "derive_analogies", "generate_product_mechanisms") \
            and (step.get("cognitive_op") == "theta" or step.get("theta_op")):
        states, trs = H.generate(run_id, step, payload["hypotheses"], registry_snapshot_id=(snapshot or {}).get("snapshot_id"), recorded_at=now,
                                 max_hypotheses=max(0, max_h - len([h for h in current.values() if h["status"] not in H.ABSORBED_STATUSES])) or 1,
                                 ordinal_base=len(current))
        store.insert_hypothesis_revisions(conn, states)
        store.insert_transitions(conn, trs)
        out["hypothesis_ids"] = [s_["hypothesis_id"] for s_ in states]
        tids += [t["transition_id"] for t in trs]
        current.update({s_["hypothesis_id"]: s_ for s_ in states})
    if isinstance(payload.get("transitions"), list) and payload["transitions"]:
        allowed = _allowed_causes(conn, run_id, step, current)
        states, trs = H.apply(run_id, step, current, payload["transitions"], actor="theta", allowed_causes=allowed, recorded_at=now,
                              registry_snapshot_id=(snapshot or {}).get("snapshot_id"), max_hypotheses=max_h)
        store.insert_hypothesis_revisions(conn, states)
        store.insert_transitions(conn, trs)
        out["hypothesis_transition_ids"] = [t["transition_id"] for t in trs]
        tids += out["hypothesis_transition_ids"]
    return out, tids


def _allowed_causes(conn, run_id: str, step: dict[str, Any], current: dict[str, dict[str, Any]]) -> dict[str, str]:
    allowed = {r["id"]: r["kind"] for r in step.get("context", {}).get("evidence_refs") or []}
    allowed.update({h: "hypothesis" for h in current})
    allowed.update({a: "evidence_admission" for a in store.admission_ids(conn, run_id)})
    allowed.update({r["id"]: "field_evidence" for r in store.admitted_evidence_refs(conn, run_id)})
    allowed.update({sid: "step_output" for sid in store.load_run(conn, run_id)[0].outputs})
    return allowed


def _registry_snapshot(state: RunState) -> dict[str, Any] | None:
    snap = _gather(state.outputs, "registry_snapshot", state.output_order)
    if isinstance(snap, dict) and snap.get("snapshot_id") and snap.get("content_hash"):
        return {"snapshot_id": str(snap["snapshot_id"]), "content_hash": str(snap["content_hash"])}
    return None


def _compile_harness_action(state: RunState, spec: dict[str, Any], step_id: str, sequence: int, hyps: dict[str, dict[str, Any]],
                            snapshot: dict[str, Any] | None, issued_at: str) -> dict[str, Any] | None:
    """HarnessActionV1 = the manifest's `harness` block (kind, roles, budget, independence, freshness) + the latest compiled research
    directive found in prior step outputs (`research_directive`: gaps, search intents, conditions, geography, language) + the live
    hypotheses + the registry snapshot. Without a directive there is nothing lawful to hand to the harness → None (typed gap)."""
    directive = _gather(state.outputs, "research_directive", state.output_order)
    if not isinstance(directive, dict) or not directive.get("search_intents") or not snapshot:
        return None
    hb = spec.get("harness") or {}
    live = [h for h, s_ in sorted(hyps.items()) if s_["status"] not in H.ABSORBED_STATUSES] or list(directive.get("hypothesis_ids") or [])
    if not live:
        return None
    budget = {**{"max_queries": 20, "max_sources": 15, "max_observations": 60}, **(directive.get("budget") or {}), **(hb.get("budget") or {})}
    action = {"action_id": "hact_" + hashlib.sha256(f"{state.run_id}:{step_id}:{sequence}".encode()).hexdigest()[:24], "run_id": state.run_id, "step_id": step_id,
              "action_kind": hb["action_kind"], "hypothesis_ids": live[:64], "objective": str(directive.get("objective") or spec.get("objective") or spec.get("title") or step_id)[:4000],
              "evidence_gaps": list(directive.get("evidence_gaps") or [])[:200], "search_intents": list(directive["search_intents"])[:100],
              "preferred_source_roles": list(hb.get("preferred_source_roles") or directive.get("preferred_source_roles") or [])[:50],
              "disallowed_source_roles": list(hb.get("disallowed_source_roles") or directive.get("disallowed_source_roles") or [])[:50],
              "freshness_requirement": {"max_age_days": hb.get("freshness_max_age_days", (directive.get("freshness_requirement") or {}).get("max_age_days")),
                                        "policy_ref": (directive.get("freshness_requirement") or {}).get("policy_ref")},
              "geography": directive.get("geography"), "language": directive.get("language"),
              "minimum_independent_sources": int(hb.get("minimum_independent_sources") or directive.get("minimum_independent_sources") or 1),
              "success_condition": str(directive.get("success_condition") or "the evidence gaps are answered by independent sources")[:2000],
              "falsification_condition": str(directive.get("falsification_condition") or "independent sources contradict the hypotheses")[:2000],
              "budget": budget, "registry_snapshot": snapshot, "issued_at": issued_at}
    return action


def cancel(conn, run_id: str, directory: Path | None = None,
           external_cancel: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None) -> dict[str, Any]:
    """Cancel the run (terminal, idempotent). If the current step holds a NON-terminal external operation and a cancel
    callable is supplied, it is invoked best-effort (its outcome or error is recorded on the receipt; cancel never blocks)."""
    loaded = store.load_run(conn, run_id, for_update=True)
    if not loaded:
        raise UnknownRun(run_id)
    state, _ = loaded
    if state.terminal:
        return status(conn, run_id, directory)
    row = store.current_step(conn, run_id)
    ext = (row or {}).get("external_operation")
    if ext and ext.get("phase") != "TERMINAL" and external_cancel is not None:
        try:
            updated = external_cancel(ext)
            if updated:
                assert_valid("external_operation_receipt", updated)
                store.finish_step(conn, run_id, row["sequence"], status=row["status"], receipt=None, external=updated)
        except Exception as exc:  # noqa: BLE001 — best effort; the run still cancels
            ext2 = {**ext, "failure": {"code": "EXTERNAL_CANCEL_FAILED", "message": f"{type(exc).__name__}: {exc}"[:2000]}}
            store.finish_step(conn, run_id, row["sequence"], status=row["status"], receipt=None, external=ext2)
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
            if row.get("output"):
                step["_partial_output"] = row["output"]
        else:
            hyps = store.current_hypotheses(conn, run_id)
            snapshot = _registry_snapshot(state)
            sid = T.next_step_id(m, state)
            harness_action = None
            if sid and m.step(sid)["type"] == "HARNESS_ACTION":
                harness_action = _compile_harness_action(state, m.step(sid), sid, state.sequence + 1, hyps, snapshot, now_iso())
                if harness_action is None:
                    state = T.terminal_gap(state, "HARNESS_DIRECTIVE_MISSING",
                                           f"{sid}: no compiled research directive, registry snapshot or live hypothesis to hand to the harness", step_id=sid)
                    store.save_state(conn, state)
                    break
            try:
                state, step = T.issue_step(m, state, issued_at=now_iso(), evidence_refs=_context_refs(conn, state), inputs=state.input,
                                           hypotheses=H.context_view(hyps), registry_snapshot=snapshot, harness_action=harness_action)
            except BudgetExhausted as exc:
                state = T.terminal_gap(state, "BUDGET_EXHAUSTED", str(exc), step_id=state.current_step_id)
                store.save_state(conn, state)
                break
            store.insert_step(conn, step)
            if harness_action:
                store.insert_harness_action(conn, harness_action, step["sequence"])
            store.save_state(conn, state)
            if step["step_type"] in AGENT_ANSWERED_STEP_TYPES:
                break                                        # the agent / harness answers through adapter_submit
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
            store.finish_step(conn, run_id, step["sequence"], status="issued", receipt=None, external=ext,
                              output=outcome.get("output"))          # composite progress survives the pause
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
        # ADR-0019: an automatic step may carry TrailSignal's admission projection and/or φ verdicts; both become durable state
        # in this same unit, or the run ends with a typed gap — a verdict is never silently dropped
        gap = _apply_phi_outputs(conn, run_id, step, m, state, output, started)
        if gap:
            store.finish_step(conn, run_id, step["sequence"], status="skipped",
                              receipt=_receipt(step, "skipped", started, evidence_ids=[], model=None, validation={"ok": False, "errors": [gap["message"]]}),
                              external=outcome.get("external"), output=output)
            state = T.terminal_gap(state, gap["code"], gap["message"], step_id=step["step_id"])
            store.save_state(conn, state)
            break
        receipt = _receipt(step, "executed", started, evidence_ids=[r["id"] for r in refs], model=None,
                           validation={"ok": True, "errors": []},
                           external_ids=[outcome["external"]["operation_id"]] if outcome.get("external") else [])
        if output.get("hypothesis_transition_ids"):
            receipt["hypothesis_transition_ids"] = list(output["hypothesis_transition_ids"])
            receipt["receipt_hash"] = stable_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
        if output.get("evidence_admission"):
            receipt["admission_id"] = output["evidence_admission"]["admission_id"]
            receipt["receipt_hash"] = stable_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
        store.finish_step(conn, run_id, step["sequence"], status="executed", receipt=receipt, output=output, external=outcome.get("external"))
        state = T.record_automatic_output(state, step["step_id"], output)
        store.save_state(conn, state)
        done += 1
    return state


# ─────────────────────────────────────────────────────────── helpers
def _cited(payload: Any) -> set[str]:
    return T._cited_ids(payload)


def _context_refs(conn, state: RunState) -> list[dict[str, Any]]:
    """What an issued step may carry: knowledge refs and registry priors produced by executed steps, plus TrailSignal-ADMITTED field
    evidence from the store. Raw harness observations never appear here (ADR-0019 §5)."""
    seen: dict[str, dict[str, Any]] = {}
    for sid, out in state.outputs.items():
        for r in (out or {}).get("_evidence_refs") or []:
            seen.setdefault(r["id"], r)
    for r in store.admitted_evidence_refs(conn, state.run_id):
        seen.setdefault(r["id"], r)
    return list(seen.values())[:MAX_CONTEXT_REFS]


def _apply_phi_outputs(conn, run_id: str, step: dict[str, Any], m: Manifest, state: RunState, output: dict[str, Any], now: str) -> dict[str, Any] | None:
    """Admission projections (`evidence_admission`) and φ verdicts (`hypothesis_verdicts`) on an automatic step's output."""
    adm = output.get("evidence_admission")
    if adm is not None:
        errs = validate("evidence_admission", adm)
        if errs or adm.get("run_id") != run_id:
            return {"code": "ADMISSION_INVALID", "message": "; ".join(errs[:5]) or "admission run_id mismatch"}
        if store.harness_action_row(conn, adm["action_id"]) is None:
            return {"code": "ADMISSION_INVALID", "message": f"admission for unknown harness action {adm['action_id']}"}
        store.record_admission(conn, adm)
        output["_admitted_evidence_ids"] = [a["admitted_evidence_id"] for a in adm.get("admitted") or []]
    verdicts = output.get("hypothesis_verdicts")
    if verdicts:
        current = store.current_hypotheses(conn, run_id)
        allowed = _allowed_causes(conn, run_id, step, current)
        allowed.update({r["id"]: r["kind"] for r in output.get("_evidence_refs") or []})
        try:
            states, trs = H.apply(run_id, step, current, list(verdicts), actor="phi", allowed_causes=allowed, recorded_at=now,
                                  registry_snapshot_id=(_registry_snapshot(state) or {}).get("snapshot_id"), max_hypotheses=int(m.budgets.get("max_hypotheses", 8)))
        except HypothesisRejected as exc:
            return {"code": "PHI_VERDICT_INVALID", "message": "; ".join(exc.errors[:5])}
        store.insert_hypothesis_revisions(conn, states)
        store.insert_transitions(conn, trs)
        output["hypothesis_transition_ids"] = [t["transition_id"] for t in trs]
    return None


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


def _gather(outputs: dict[str, Any], key: str, order: tuple[str, ...] = ()) -> Any:
    """First value named `key` found in step outputs, NEWEST accepted step first (top level, then one level down). `order` is the
    run's acceptance order — JSONB does not keep dict order, so callers pass `state.output_order`."""
    for sid in reversed(order or tuple(outputs)):
        out = outputs.get(sid) or {}
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
            v = _gather(state.outputs, key, state.output_order)
            if v is not None:
                output[key] = v
    evidence_ids, query_ids, ext_ops = [], [], []
    for r in _context_refs(conn, state):
        (query_ids if r["kind"] == "query_receipt" else evidence_ids if r["kind"] in KNOWLEDGE_KINDS else []).append(r["id"])
    actions = store.list_harness_actions(conn, run_id)
    hyps = store.current_hypotheses(conn, run_id)
    snapshots = sorted({str((_gather({sid: o}, "registry_snapshot") or {}).get("snapshot_id")) for sid, o in state.outputs.items()
                        if isinstance(_gather({sid: o}, "registry_snapshot"), dict)} - {"None"})
    score_ids = [str(x) for x in _collect_lists(state.outputs, "trail_score_record_ids") if isinstance(x, str)]
    ts = _gather(state.outputs, "trail_score", state.output_order)
    if isinstance(ts, dict) and ts.get("record_id"):
        score_ids.append(str(ts["record_id"]))
    for s in steps:
        e = s.get("external_operation")
        if e:
            ext_ops.append({"external_system": e["external_system"], "operation_kind": e.get("operation_kind"), "operation_id": e["operation_id"],
                            "record_ids": list(e.get("record_ids") or [])})
    # composite steps (e.g. batch acquire + per-artifact extraction) report their sub-operations on the step output
    for out in state.outputs.values():
        for e in (out or {}).get("_external_operations") or []:
            if e.get("operation_id") and e["operation_id"] not in {x["operation_id"] for x in ext_ops}:
                ext_ops.append({"external_system": e.get("external_system", "trailsignal"), "operation_kind": e.get("operation_kind"),
                                "operation_id": e["operation_id"], "record_ids": list(e.get("record_ids") or [])})
    terminal_status = {"completed": "completed", "terminal_gap": "terminal_gap", "cancelled": "cancelled", "failed": "failed"}.get(state.status, "completed")
    res = {"run_id": run_id, **m.identity, "status": terminal_status, "started_at": _ts(meta["created_at"]),
           "terminal_at": _ts(meta["terminal_at"]) or now_iso(), "output": output,
           "lineage": {"polymath_evidence_ids": sorted(set(evidence_ids)), "query_receipt_ids": sorted(set(query_ids)),
                       "step_receipt_hashes": [s["receipt"]["receipt_hash"] for s in steps if s.get("receipt")],
                       "external_operations": ext_ops,
                       "hypothesis_ids": sorted(hyps), "admitted_evidence_ids": sorted(r["id"] for r in store.admitted_evidence_refs(conn, run_id)),
                       "harness_action_ids": [a["action_id"] for a in actions],
                       "harness_ids": sorted({(a["receipt"] or {}).get("harness_id") for a in actions if a.get("receipt")} - {None}),
                       "registry_snapshot_ids": snapshots, "trail_score_record_ids": sorted(set(score_ids))},
           "contradictions": [c for c in _collect_lists(state.outputs, "contradictions") if isinstance(c, dict)],
           "unknowns": [({"about": u} if isinstance(u, str) else u) for u in _collect_lists(state.outputs, "unknowns")],
           "gap": state.gap, "agent_identity": meta.get("agent_identity")}
    assert_valid("adapter_result", res)
    if persist:
        store.insert_result(conn, run_id, res, stable_hash(res))
    return res

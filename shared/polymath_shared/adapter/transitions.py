"""Run/step state transitions for the cognitive-adapter runtime. Pure and deterministic: same (manifest, state, inputs)
=> same next step, same issued step dict, same acceptance verdict. Persistence is the caller's job (receipts/outbox)."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import jsonschema

from .contracts import AGENT_ANSWERED_STEP_TYPES, AUTOMATIC_STEP_TYPES, PRIOR_EVIDENCE_KINDS, TERMINAL_RUN_STATUSES, assert_valid, stable_hash, validate
from .manifest import Manifest


class SubmissionRejected(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors[:5]))
        self.errors = errors


class BudgetExhausted(RuntimeError):
    pass


@dataclass(frozen=True)
class RunState:
    """The durable-in-Postgres part of a run, as the pure core sees it. Immutable; transitions return new states."""
    run_id: str
    adapter_id: str
    status: str = "created"
    current_step_id: str | None = None
    sequence: int = 0                       # steps issued so far (1-based sequence of the last issued step)
    steps_accepted: int = 0
    branch_loops: int = 0
    agent_reason_count: int = 0
    external_operation_count: int = 0
    harness_action_count: int = 0
    input: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)      # request_options (corpus scope, retrieval mode, …)
    outputs: dict[str, Any] = field(default_factory=dict)       # step_id -> accepted/executed output payload
    output_order: tuple[str, ...] = ()                         # step ids in acceptance order (JSONB drops dict order); newest last
    failure: dict[str, Any] | None = None
    gap: dict[str, Any] | None = None

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_RUN_STATUSES


# ─────────────────────────────────────────────────────────── predicates (closed)
def _lookup(path: str, ctx: dict[str, Any]) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def evaluate_predicate(pred: dict[str, Any], ctx: dict[str, Any]) -> bool:
    """Closed predicate vocabulary over a dotted path into ``ctx``:
    exists · count_gte(n) · count_lt(n) · equals(value) · all_of(of) · any_of(of). Unknown op → False (never raises)."""
    op = pred.get("op")
    if op == "all_of":
        return all(evaluate_predicate(p, ctx) for p in pred.get("of") or [])
    if op == "any_of":
        return any(evaluate_predicate(p, ctx) for p in pred.get("of") or [])
    val = _lookup(str(pred.get("path", "")), ctx)
    if op == "exists":
        return val is not None
    if op == "equals":
        return val == pred.get("value")
    if op in ("count_gte", "count_lt"):
        n = int(pred.get("n", 0))
        count = len(val) if isinstance(val, (list, dict, str)) else (int(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else 0)
        return count >= n if op == "count_gte" else count < n
    return False


def _ctx(state: RunState) -> dict[str, Any]:
    return {"steps": {sid: {"output": out} for sid, out in state.outputs.items()},
            "run": {"branch_loops": state.branch_loops, "sequence": state.sequence, "steps_accepted": state.steps_accepted,
                    "agent_reason_count": state.agent_reason_count, "external_operation_count": state.external_operation_count},
            "input": state.input, "options": state.options}


# ─────────────────────────────────────────────────────────── navigation
def next_step_id(manifest: Manifest, state: RunState) -> str | None:
    """The step that follows ``state.current_step_id`` (or the entry step for a fresh run). A BRANCH step is resolved
    HERE: the first branch whose predicate holds wins, else its default ``next``; taking a branch counts a loop."""
    if state.current_step_id is None:
        return manifest.entry_step_id
    cur = manifest.step(state.current_step_id)
    if cur["type"] == "BRANCH":
        for b in cur.get("branches") or []:
            if evaluate_predicate(b["when"], _ctx(state)):
                return b["next"]
    return cur.get("next")


def _check_budgets(manifest: Manifest, state: RunState, step_type: str, took_branch: bool) -> None:
    b = manifest.budgets
    if state.sequence + 1 > b["max_steps"]:
        raise BudgetExhausted(f"max_steps {b['max_steps']} reached")
    if step_type == "AGENT_REASON" and state.agent_reason_count + 1 > b["max_agent_reason"]:
        raise BudgetExhausted(f"max_agent_reason {b['max_agent_reason']} reached")
    if step_type == "EXTERNAL_OPERATION" and state.external_operation_count + 1 > b.get("max_external_operations", 10**9):
        raise BudgetExhausted(f"max_external_operations reached")
    if step_type == "HARNESS_ACTION" and state.harness_action_count + 1 > b.get("max_harness_actions", 10**9):
        raise BudgetExhausted("max_harness_actions reached")
    if took_branch and state.branch_loops + 1 > b["max_branch_loops"]:
        raise BudgetExhausted(f"max_branch_loops {b['max_branch_loops']} reached")


def start_run(manifest: Manifest, run_id: str, input_payload: dict[str, Any], options: dict[str, Any] | None = None) -> RunState:
    """Validate the domain input against the manifest's input_schema and open the run (status=created)."""
    errors = [e.message for e in jsonschema.Draft202012Validator(manifest.raw.get("input_schema") or {"type": "object"}).iter_errors(input_payload)]
    if errors:
        raise SubmissionRejected(["input: " + m for m in sorted(errors)])
    return RunState(run_id=run_id, adapter_id=manifest.adapter_id, input=dict(input_payload), options=dict(options or {}))


def issue_step(manifest: Manifest, state: RunState, *, issued_at: str, evidence_refs: list[dict[str, Any]] | None = None,
               inputs: dict[str, Any] | None = None, hypotheses: list[dict[str, Any]] | None = None,
               registry_snapshot: dict[str, Any] | None = None, harness_action: dict[str, Any] | None = None,
               admitted_evidence_ids: list[str] | None = None) -> tuple[RunState, dict[str, Any]]:
    """Advance to the next step and build its AdapterStepV1 dict (validated). Returns (new_state, step).
    Terminal runs never issue; budget exhaustion raises BudgetExhausted for the caller to record as a typed gap."""
    if state.terminal:
        raise RuntimeError(f"run {state.run_id} is terminal ({state.status})")
    sid = next_step_id(manifest, state)
    if sid is None:
        raise RuntimeError("no successor step — the manifest graph should have reached COMPILE_RESULT")
    took_branch = state.current_step_id is not None and manifest.step(state.current_step_id)["type"] == "BRANCH" \
        and sid != manifest.step(state.current_step_id).get("next")
    spec = manifest.step(sid)
    _check_budgets(manifest, state, spec["type"], took_branch)
    seq = state.sequence + 1
    if spec["type"] == "HARNESS_ACTION":
        if not harness_action:
            raise RuntimeError(f"{sid}: HARNESS_ACTION needs a compiled harness action (no research directive available)")
        assert_valid("harness_action", harness_action)
    context = {"evidence_refs": list(evidence_refs or []), "inputs": dict(inputs or {}), "prior_step_ids": list(state.outputs.keys()),
               "admitted_evidence_ids": list(admitted_evidence_ids or [])}
    if hypotheses:
        context["hypotheses"] = list(hypotheses)
    if registry_snapshot:
        context["registry_snapshot"] = dict(registry_snapshot)
    step = {
        "run_id": state.run_id, "step_id": sid, "step_type": spec["type"], "sequence": seq, "issued_at": issued_at,
        "objective": spec.get("objective") or spec.get("title") or sid,
        "context": context,
        "constraints": list(spec.get("constraints") or []),
        "output_schema": dict(spec.get("output_schema") or {"type": "object"}),
        "acceptance_rules": list(spec.get("acceptance_rules") or []),
        "external": ({"system": spec["external"]["system"], "operation_kind": spec["external"]["operation_kind"]}
                     if spec["type"] == "EXTERNAL_OPERATION" else None),
        "cognitive_op": spec.get("cognitive_op") or ("theta" if spec["type"] == "AGENT_REASON" and spec.get("theta_op") else None),
        "theta_op": spec.get("theta_op"),
        "harness_action": dict(harness_action) if spec["type"] == "HARNESS_ACTION" else None,
        "expires_at": None,
    }
    assert_valid("adapter_step", step)
    status = {"AGENT_REASON": "awaiting_agent", "HARNESS_ACTION": "awaiting_harness"}.get(spec["type"], "running")
    new = replace(state, status=status, current_step_id=sid, sequence=seq,
                  branch_loops=state.branch_loops + (1 if took_branch else 0),
                  agent_reason_count=state.agent_reason_count + (1 if spec["type"] == "AGENT_REASON" else 0),
                  external_operation_count=state.external_operation_count + (1 if spec["type"] == "EXTERNAL_OPERATION" else 0),
                  harness_action_count=state.harness_action_count + (1 if spec["type"] == "HARNESS_ACTION" else 0))
    return new, step


def _bump_order(order: tuple[str, ...], step_id: str) -> tuple[str, ...]:
    """Acceptance order of step outputs; a step re-entered through a loop moves to the end (newest last)."""
    return tuple(x for x in order if x != step_id) + (step_id,)


def newest_output(state: RunState, key: str) -> Any:
    """The value under `key` on the most recently accepted/executed step output that carries it (top level, or one level down)."""
    for sid in reversed(state.output_order or tuple(state.outputs)):
        out = state.outputs.get(sid)
        if isinstance(out, dict):
            if key in out:
                return out[key]
            for v in out.values():
                if isinstance(v, dict) and key in v:
                    return v[key]
    return None


# ─────────────────────────────────────────────────────────── submissions
def _cited_ids(payload: Any) -> set[str]:
    """Every string under a key that ends with `_ids` (the citation convention of AGENT_REASON output schemas)."""
    out: set[str] = set()
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k.endswith("_ids") and isinstance(v, list):
                out |= {x for x in v if isinstance(x, str)}
            else:
                out |= _cited_ids(v)
    elif isinstance(payload, list):
        for v in payload:
            out |= _cited_ids(v)
    return out


def validate_submission(step: dict[str, Any], payload: Any) -> list[str]:
    """The step's output_schema + the machine-checkable acceptance invariant: every cited `*_ids` value must be an
    id from context.evidence_refs (an agent may never cite evidence it was not given)."""
    errors = [("payload/" + "/".join(map(str, e.path)) if e.path else "payload") + ": " + e.message
              for e in sorted(jsonschema.Draft202012Validator(step["output_schema"]).iter_errors(payload),
                              key=lambda e: (list(map(str, e.path)), e.message))]
    refs = step.get("context", {}).get("evidence_refs", [])
    allowed = {r["id"] for r in refs if r.get("kind") not in PRIOR_EVIDENCE_KINDS}
    priors = {r["id"] for r in refs if r.get("kind") in PRIOR_EVIDENCE_KINDS}
    cited = _cited_ids(payload)
    cited_priors = sorted(cited & priors)
    if cited_priors:
        errors.append("registry priors may never be cited as evidence: " + ", ".join(cited_priors[:10]))
    uncited = sorted(cited - allowed - priors) if allowed or cited else []
    if uncited:
        errors.append("cited ids not in context.evidence_refs: " + ", ".join(uncited[:10]))
    return errors


def validate_receipt(step: dict[str, Any], payload: Any) -> list[str]:
    """A HARNESS_ACTION answer is a HarnessResearchReceiptV1 for THIS action: provenance shape only (the harness never decides
    what counts as evidence — TrailSignal admission does)."""
    errors = ["payload: " + e for e in validate("harness_receipt", payload)]
    action = step.get("harness_action") or {}
    if isinstance(payload, dict):
        if payload.get("action_id") != action.get("action_id"):
            errors.append(f"receipt action_id {payload.get('action_id')!r} does not match the issued action {action.get('action_id')!r}")
        if payload.get("run_id") != step["run_id"]:
            errors.append("receipt run_id does not match the run")
        # TRAIL PARITY, cross-field (a JSON schema cannot say these; TrailSignal's HarnessResearchReceiptV1 enforces both, and a receipt
        # that broke one ended a real run as TRAIL_REFUSED instead of being handed back to the harness):
        listed = {s.get("source_id") for s in payload.get("sources") or [] if isinstance(s, dict)}
        orphan = sorted({str(o.get("source_id")) for o in payload.get("observations") or [] if isinstance(o, dict) and o.get("source_id") not in listed})
        if orphan:
            errors.append("observations name sources that are not listed: " + ", ".join(orphan[:10]))
        started, completed = _instant(payload.get("started_at")), _instant(payload.get("completed_at"))
        if started and completed and completed < started:
            errors.append("completed_at precedes started_at")
    return errors


def _instant(value: Any):
    from datetime import datetime, timezone
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def accept_submission(manifest: Manifest, state: RunState, step: dict[str, Any], submission: dict[str, Any]) -> RunState:
    """Validate an AdapterSubmissionV1 (reasoning or receipt) for the CURRENT awaiting step and record its payload. Anything
    out of order — a duplicate submit, a wrong step, a wrong kind — is rejected with the reason."""
    assert_valid("adapter_submission", submission)
    if state.terminal:
        raise SubmissionRejected([f"run is terminal ({state.status})"])
    expected = {"AGENT_REASON": ("awaiting_agent", "reasoning"), "HARNESS_ACTION": ("awaiting_harness", "receipt")}.get(step["step_type"])
    if expected is None or state.status != expected[0] or step["step_id"] != state.current_step_id or submission["step_id"] != state.current_step_id:
        raise SubmissionRejected([f"step {submission['step_id']!r} is not the awaiting step {state.current_step_id!r}"])
    if submission.get("kind") and submission["kind"] != expected[1]:
        raise SubmissionRejected([f"submission kind {submission['kind']!r} does not fit a {step['step_type']} step (expected {expected[1]!r})"])
    errors = validate_receipt(step, submission["payload"]) if step["step_type"] == "HARNESS_ACTION" else validate_submission(step, submission["payload"])
    if errors:
        raise SubmissionRejected(errors)
    # A step id re-entered through a bounded loop is a NEW issuance: its payload may legitimately differ from the earlier pass
    # (the earlier output stays on its own step row + receipt). A duplicate submit of the same issuance is refused above because
    # the run is no longer awaiting once the first one is accepted.
    return replace(state, status="running", steps_accepted=state.steps_accepted + 1,
                   outputs={**state.outputs, step["step_id"]: submission["payload"]}, output_order=_bump_order(state.output_order, step["step_id"]))


def record_automatic_output(state: RunState, step_id: str, output: dict[str, Any]) -> RunState:
    """An automatic step (retrieve/plan/graph/external/validate/branch/compile) executed by the runtime."""
    if state.current_step_id != step_id or state.status != "running":
        raise RuntimeError(f"step {step_id!r} is not the running step {state.current_step_id!r}")
    return replace(state, steps_accepted=state.steps_accepted + 1, outputs={**state.outputs, step_id: output}, output_order=_bump_order(state.output_order, step_id))


def cancel_run(state: RunState) -> RunState:
    """Cancellation is terminal and idempotent; accepted work is never rolled back."""
    if state.terminal:
        return state
    return replace(state, status="cancelled")


def terminal_gap(state: RunState, code: str, message: str, step_id: str | None = None) -> RunState:
    if state.terminal:
        return state
    return replace(state, status="terminal_gap", gap={"code": code, "message": message, **({"step_id": step_id} if step_id else {})})


def complete_run(state: RunState) -> RunState:
    if state.status != "running":
        raise RuntimeError(f"cannot complete a run in status {state.status}")
    return replace(state, status="completed")


def run_status_view(manifest: Manifest, state: RunState, *, started_at: str, updated_at: str,
                    terminal_at: str | None = None, agent_identity: str | None = None) -> dict[str, Any]:
    """The AdapterRunStatusV1 projection of a state (validated)."""
    spec = manifest.step(state.current_step_id) if state.current_step_id else None
    view = {"run_id": state.run_id, **manifest.identity, "status": state.status, "current_step_id": state.current_step_id,
            "current_step_type": spec["type"] if spec else None, "steps_issued": state.sequence,
            "steps_accepted": state.steps_accepted, "branch_loops": state.branch_loops, "harness_actions": state.harness_action_count,
            "started_at": started_at,
            "updated_at": updated_at, "terminal_at": terminal_at, "failure": state.failure, "gap": state.gap,
            "agent_identity": agent_identity}
    assert_valid("adapter_run_status", view)
    return view

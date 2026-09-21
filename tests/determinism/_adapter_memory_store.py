"""In-memory double of `polymath_shared.adapter.store` for runtime tests that must NOT touch the shared Postgres.

NOT a test module. The adapter determinism tests that use the `conn` fixture share the live fleet's database; a test that needs
`service.start / advance / submit / result` end to end installs this double with `monkeypatch.setattr(service, "store", MemoryStore())`
and passes `conn=None`. Semantics mirror store.py where a test can observe them: values round-trip through JSON exactly like JSONB
(tuples become lists, key order is not preserved), the newest step is the highest sequence, `finish_step` keeps an existing
receipt / output / submission when handed None (COALESCE), results and hypothesis revisions are insert-once.
Leases (`claim_run` …) are deliberately absent: a test drives `service.advance` itself.
"""
from __future__ import annotations

import json
from typing import Any

from polymath_shared.adapter.transitions import RunState

_NOW = "2026-09-20T00:00:00Z"


def _rt(v: Any) -> Any:
    return json.loads(json.dumps(v, sort_keys=True, ensure_ascii=False)) if v is not None else None


class MemoryStore:
    def __init__(self) -> None:
        self.runs: dict[str, dict[str, Any]] = {}
        self.steps: dict[str, list[dict[str, Any]]] = {}
        self.results: dict[str, dict[str, Any]] = {}
        self.hypotheses: dict[str, list[dict[str, Any]]] = {}
        self.transitions: dict[str, dict[str, Any]] = {}
        self.actions: dict[str, dict[str, Any]] = {}
        self.admitted: list[dict[str, Any]] = []

    # ── runs
    def insert_run(self, conn, state: RunState, manifest, *, idempotency_key, agent_identity) -> None:
        self.runs[state.run_id] = {"state": self._dump(state), "idempotency_key": idempotency_key,
                                   "meta": {"adapter_id": manifest.adapter_id, "adapter_version": manifest.adapter_version,
                                            "workflow_version": manifest.workflow_version, "retrieval_policy_version": manifest.retrieval_policy_version,
                                            "input_schema_version": manifest.input_schema_version, "output_schema_version": manifest.output_schema_version,
                                            "agent_identity": agent_identity, "created_at": _NOW, "updated_at": _NOW, "terminal_at": None,
                                            "lease_owner": None, "lease_expires_at": None}}
        self.steps[state.run_id] = []

    @staticmethod
    def _dump(state: RunState) -> dict[str, Any]:
        return _rt({"run_id": state.run_id, "adapter_id": state.adapter_id, "status": state.status, "current_step_id": state.current_step_id,
                    "sequence": state.sequence, "steps_accepted": state.steps_accepted, "branch_loops": state.branch_loops,
                    "agent_reason_count": state.agent_reason_count, "external_operation_count": state.external_operation_count,
                    "harness_action_count": state.harness_action_count, "input": state.input, "options": state.options,
                    "outputs": state.outputs, "output_order": list(state.output_order), "failure": state.failure, "gap": state.gap})

    def set_run_owner(self, conn, run_id: str, owner_principal_id: str) -> None:
        self.runs[run_id]["owner_principal_id"] = owner_principal_id

    def run_owner(self, conn, run_id: str):
        return (True, self.runs[run_id].get("owner_principal_id")) if run_id in self.runs else (False, None)

    def find_run_by_idempotency(self, conn, key: str) -> str | None:
        return next((rid for rid, r in self.runs.items() if r["idempotency_key"] == key), None)

    def load_run(self, conn, run_id: str, *, for_update: bool = False):
        row = self.runs.get(run_id)
        if not row:
            return None
        d = _rt(row["state"])
        d["output_order"] = tuple(d["output_order"] or [])
        return RunState(**d), dict(row["meta"])

    def save_state(self, conn, state: RunState) -> None:
        row = self.runs[state.run_id]
        row["state"] = self._dump(state)
        row["meta"]["updated_at"] = _NOW
        if state.terminal and not row["meta"]["terminal_at"]:
            row["meta"]["terminal_at"] = _NOW

    # ── steps
    def insert_step(self, conn, step: dict[str, Any]) -> None:
        self.steps[step["run_id"]].append({"sequence": step["sequence"], "step_id": step["step_id"], "step_type": step["step_type"], "status": "issued",
                                           "step": _rt(step), "submission": None, "output": None, "receipt": None, "external_operation": None,
                                           "started_at": _NOW, "ended_at": None})

    def current_step(self, conn, run_id: str):
        rows = self.steps.get(run_id) or []
        return _rt(max(rows, key=lambda r: r["sequence"])) if rows else None

    def list_steps(self, conn, run_id: str) -> list[dict[str, Any]]:
        return [_rt({k: v for k, v in r.items() if k not in ("started_at", "ended_at")}) for r in sorted(self.steps.get(run_id) or [], key=lambda r: r["sequence"])]

    def finish_step(self, conn, run_id: str, sequence: int, *, status: str, receipt, output=None, submission=None, external=None) -> None:
        row = next(r for r in self.steps[run_id] if r["sequence"] == sequence)
        row["status"] = status
        for key, val in (("receipt", receipt), ("output", output), ("submission", submission or None), ("external_operation", external or None)):
            if val is not None:
                row[key] = _rt(val)
        if status in ("accepted", "executed", "failed", "skipped"):
            row["ended_at"] = _NOW

    # ── results
    def insert_result(self, conn, run_id: str, result: dict[str, Any], result_hash: str) -> None:
        self.results.setdefault(run_id, _rt(result))

    def load_result(self, conn, run_id: str):
        return _rt(self.results.get(run_id))

    # ── hypotheses
    def insert_hypothesis_revisions(self, conn, states: list[dict[str, Any]]) -> None:
        for st in states:
            rows = self.hypotheses.setdefault(st["run_id"], [])
            if not any(r["hypothesis_id"] == st["hypothesis_id"] and r["revision"] == st["revision"] for r in rows):
                rows.append(_rt(st))

    def insert_transitions(self, conn, transitions: list[dict[str, Any]]) -> None:
        for t in transitions:
            self.transitions.setdefault(t["transition_id"], _rt(t))

    def current_hypotheses(self, conn, run_id: str) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for st in self.hypotheses.get(run_id) or []:                # generation order, newest revision per hypothesis
            if st["hypothesis_id"] not in out or st["revision"] > out[st["hypothesis_id"]]["revision"]:
                out[st["hypothesis_id"]] = _rt(st)
        return out

    def list_transitions(self, conn, run_id: str) -> list[dict[str, Any]]:
        return sorted((_rt(t) for t in self.transitions.values() if t["run_id"] == run_id), key=lambda t: (t["sequence"], t["transition_id"]))

    # ── harness actions + admitted evidence
    def insert_harness_action(self, conn, action: dict[str, Any], sequence: int) -> None:
        self.actions.setdefault(action["action_id"], {"action_id": action["action_id"], "run_id": action["run_id"], "step_id": action["step_id"],
                                                      "sequence": int(sequence), "status": "issued", "action": _rt(action), "receipt": None,
                                                      "receipt_hash": None, "admission": None})

    def record_receipt(self, conn, action_id: str, receipt: dict[str, Any], receipt_hash: str) -> None:
        self.actions[action_id].update(status="received", receipt=_rt(receipt), receipt_hash=receipt_hash)

    def record_admission(self, conn, admission: dict[str, Any]) -> None:
        self.actions[admission["action_id"]].update(status="admitted" if admission.get("admitted") else "rejected", admission=_rt(admission))
        for a in admission.get("admitted") or []:
            if not any(r["evidence_id"] == a["admitted_evidence_id"] for r in self.admitted):
                self.admitted.append({"evidence_id": a["admitted_evidence_id"], "run_id": admission["run_id"], "admission_id": admission["admission_id"],
                                      "evidence_role": a["evidence_role"], "polarity": a["polarity"]})

    def harness_action_row(self, conn, action_id: str):
        return _rt(self.actions.get(action_id))

    def list_harness_actions(self, conn, run_id: str) -> list[dict[str, Any]]:
        rows = sorted((r for r in self.actions.values() if r["run_id"] == run_id), key=lambda r: r["sequence"])
        return [{"action_id": r["action_id"], "status": r["status"], "receipt": _rt(r["receipt"]), "admission": _rt(r["admission"])} for r in rows]

    def admitted_evidence_refs(self, conn, run_id: str) -> list[dict[str, Any]]:
        return [{"kind": "field_evidence", "id": r["evidence_id"], "note": f"{r['evidence_role']}/{r['polarity']}"} for r in self.admitted if r["run_id"] == run_id]

    def admission_ids(self, conn, run_id: str) -> list[str]:
        return sorted({r["admission_id"] for r in self.admitted if r["run_id"] == run_id})

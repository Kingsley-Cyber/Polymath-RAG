"""TRAIL-INTERFACE-V1 T1 — the read model behind the web UI's Research section: the runs list and one run's view.

It only OBSERVES: nothing here writes, scores or decides (TrailSignal's score is its own, LAW 1). A run's output is recompiled
from its step outputs through the fixed readers (gap A-15), so a run stored before that fix shows its real qualifications; the
stored result stays the untouched record. Field text passes through as data — the UI renders it as text, never HTML."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import service, store
from .transitions import RunState

_TITLE_KEYS = ("seed", "seed_idea", "question", "topic", "brief")
#: the sections the Research screens render; any other output key is listed by name only
SECTION_KEYS = ("qualifications", "trail_scores", "score_refusals", "evidence_admissions", "lived_clusters", "product_concepts",
                "concept_reality", "product_opportunity", "unresolved_research_gaps", "hypothesis_semantics")
_DONE = {"accepted", "executed"}
_FAILED = {"failed", "rejected"}


def title_of(inp: Any) -> str:
    if isinstance(inp, dict):
        for k in _TITLE_KEYS:
            v = inp.get(k)
            if isinstance(v, str) and v.strip():
                text = " ".join(v.split())
                return text if len(text) <= 140 else text[:139] + "…"
    return "Untitled run"


def outcome_of(status: str, scores: int | None, refusals: int | None, gap: Any) -> str:
    """One line a person can read. Counts only: the score VALUES are TrailSignal's and never read here."""
    if status == "awaiting_agent":
        return "Waiting for your agent"
    if status == "awaiting_harness":
        return "Waiting for web research"
    if status in ("created", "running"):
        return "Running"
    if status == "cancelled":
        return "Cancelled"
    if status == "failed":
        return "Failed"
    if status == "terminal_gap":
        code = gap.get("code") if isinstance(gap, dict) else None
        return f"Stopped: {code}" if code else "Stopped early"
    if scores:
        return f"{scores} scored" + (f", {refusals} refused" if refusals else "")
    if refusals:
        return "TrailSignal refused the score" if refusals == 1 else f"TrailSignal refused all {refusals} scores"
    if scores == 0 and refusals == 0:
        return "Completed, nothing scored"
    return "Completed"


def _summary(row: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": row["run_id"], "adapter_id": row["adapter_id"], "adapter_version": row["adapter_version"],
            "title": title_of(row["input"]), "status": row["status"], "current_step_id": row["current_step_id"],
            "steps_accepted": row["steps_accepted"], "harness_actions": row["harness_action_count"],
            "started_at": service._ts(row["created_at"]), "updated_at": service._ts(row["updated_at"]),
            "finished_at": service._ts(row["terminal_at"]), "agent_identity": row["agent_identity"], "owner": row["owner_principal_id"],
            "outcome": outcome_of(row["status"], row["scores"], row["refusals"], row["gap"])}


def list_runs(conn, principal_id: str | None, *, status: str | None = None, adapter_id: str | None = None,
              limit: int = 50, before: str | None = None) -> list[dict[str, Any]]:
    """A principal (a friend) sees only their own runs; no principal (the owner / trusted-local caller) sees every run."""
    return [_summary(r) for r in store.list_runs(conn, owner_principal_id=principal_id, status=status, adapter_id=adapter_id,
                                                  limit=limit, before=before)]


def progress_of(manifest_steps: dict[str, dict[str, Any]], stored_steps: list[dict[str, Any]], state: RunState) -> list[dict[str, Any]]:
    """Every manifest step in manifest order: done · current · waiting_agent · waiting_harness · failed · skipped · pending, with
    how many times a bounded loop visited it."""
    by_step: dict[str, list[dict[str, Any]]] = {}
    for s in stored_steps:
        by_step.setdefault(s["step_id"], []).append(s)
    rows = []
    for step_id, spec in manifest_steps.items():
        visits = by_step.get(step_id, [])
        last = visits[-1]["status"] if visits else None
        if step_id == state.current_step_id and not state.terminal:
            st = {"awaiting_agent": "waiting_agent", "awaiting_harness": "waiting_harness"}.get(state.status, "current")
        elif last in _DONE:
            st = "done"
        elif last in _FAILED:
            st = "failed"
        elif last == "skipped":
            st = "skipped"
        elif last == "issued":
            st = "current"
        else:
            st = "pending"
        rows.append({"step_id": step_id, "type": spec.get("type"), "title": spec.get("title") or step_id, "state": st,
                     "visits": len(visits)})
    return rows


def build_view(conn, run_id: str, directory: Path | None = None) -> dict[str, Any]:
    loaded = store.load_run(conn, run_id)
    if not loaded:
        raise service.UnknownRun(run_id)
    state, meta = loaded
    m = service.manifest_for(state.adapter_id, directory)
    steps = store.list_steps(conn, run_id)
    recompiled = service._compile_result(conn, run_id, state, m, output=None, persist=False)
    output = recompiled.get("output") or {}
    stored = store.load_result(conn, run_id)
    stored_quals = ((stored or {}).get("output") or {}).get("qualifications")
    return {
        "run": {"run_id": run_id, "adapter_id": state.adapter_id, "adapter_version": meta.get("adapter_version"),
                "title": title_of(state.input), "status": state.status, "terminal": state.terminal,
                "current_step_id": state.current_step_id, "started_at": service._ts(meta.get("created_at")),
                "updated_at": service._ts(meta.get("updated_at")), "finished_at": service._ts(meta.get("terminal_at")),
                "agent_identity": meta.get("agent_identity"), "gap": state.gap, "failure": state.failure,
                "input": state.input, "steps_accepted": state.steps_accepted, "harness_actions": state.harness_action_count},
        "progress": progress_of(m.steps, steps, state),
        "sections": {k: output[k] for k in SECTION_KEYS if k in output},
        "other_output_keys": sorted(k for k in output if k not in SECTION_KEYS),
        "contradictions": recompiled.get("contradictions") or [],
        "unknowns": recompiled.get("unknowns") or [],
        # true when the stored result lost qualifications the steps hold (runs stored before the A-15 fix)
        "stored_result_shadowed": bool(stored) and not stored_quals and bool(output.get("qualifications")),
    }

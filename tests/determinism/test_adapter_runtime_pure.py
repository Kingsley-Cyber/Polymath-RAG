"""COGNITIVE-ADAPTER-V1 (ADR-0018) — the pure core: manifests, predicates, transitions, submissions. No I/O."""
from __future__ import annotations

import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.adapter import (  # noqa: E402
    ADAPTER_DIR, BudgetExhausted, ManifestError, SubmissionRejected, accept_submission, cancel_run, complete_run,
    evaluate_predicate, graph_integrity_errors, issue_step, list_manifests, load_manifest, record_automatic_output,
    run_status_view, stable_hash, start_run, terminal_gap, validate,
)

T0 = "2026-09-13T18:50:00Z"
RUN = "adr_" + "ab" * 16
INPUT = {"seed": "outdoor cold-plunge recovery routines for amateur athletes", "corpus_ids": ["cinema"]}
EVIDENCE = [{"kind": "chunk", "id": "chunk_1", "corpus_id": "cinema"}, {"kind": "graph_fact", "id": "fact_9"},
            {"kind": "trail_record", "id": "urlc_1"}, {"kind": "trail_record", "id": "score_1"}]


def _m():
    ms = list_manifests(ADAPTER_DIR)
    return next(m for m in ms if m.adapter_id == "trail.product_discovery")


def test_admitted_manifest_loads_and_matches_the_contract_example():
    m = _m()
    ex = json.loads((ROOT / "contracts/adapter/v1/adapter_manifest.example.json").read_text())
    assert m.identity == {k: ex[k] for k in m.identity}
    assert m.entry_step_id == "A_understand" and m.terminal_step_id == "K_compile" and len(m.steps) == 13


@pytest.mark.parametrize("mutate, expect", [
    (lambda r: r["steps"][1].__setitem__("next", "nope"), "is not a step"),
    (lambda r: r["steps"].append(dict(r["steps"][0])), "duplicate step_id"),
    (lambda r: r.__setitem__("terminal_step_id", "A_understand"), "must be COMPILE_RESULT"),
    (lambda r: r["steps"][8]["external"].pop("planned_node"), "names its graph node"),
    (lambda r: r["steps"][4].pop("output_schema"), "AGENT_REASON needs objective"),
])
def test_graph_integrity_catches_broken_manifests(mutate, expect):
    raw = copy.deepcopy(_m().raw)
    mutate(raw)
    assert any(expect in e for e in graph_integrity_errors(raw)), graph_integrity_errors(raw)


def test_load_manifest_fails_loudly_on_a_malformed_file(tmp_path):
    bad = tmp_path / "x.json"
    raw = copy.deepcopy(_m().raw); raw["budgets"]["max_steps"] = 0
    bad.write_text(json.dumps(raw))
    with pytest.raises(ManifestError):
        load_manifest(bad)


def test_predicates_are_closed_and_deterministic():
    ctx = {"steps": {"G": {"output": {"gaps": [1, 2]}}}, "run": {"branch_loops": 1}}
    assert evaluate_predicate({"op": "exists", "path": "steps.G.output.gaps"}, ctx)
    assert not evaluate_predicate({"op": "exists", "path": "steps.X.output"}, ctx)
    assert evaluate_predicate({"op": "count_gte", "path": "steps.G.output.gaps", "n": 2}, ctx)
    assert not evaluate_predicate({"op": "count_gte", "path": "steps.G.output.gaps", "n": 3}, ctx)
    assert evaluate_predicate({"op": "count_lt", "path": "run.branch_loops", "n": 3}, ctx)
    assert evaluate_predicate({"op": "equals", "path": "run.branch_loops", "value": 1}, ctx)
    assert evaluate_predicate({"op": "all_of", "of": [{"op": "exists", "path": "run"}, {"op": "count_lt", "path": "run.branch_loops", "n": 2}]}, ctx)
    assert evaluate_predicate({"op": "any_of", "of": [{"op": "exists", "path": "nope"}, {"op": "exists", "path": "run"}]}, ctx)
    assert not evaluate_predicate({"op": "python", "path": "run"}, ctx)      # unknown op never raises, never passes


def _walk_to(m, state, target, outputs):
    """Issue automatic steps (recording canned outputs) until `target` is the current step."""
    while True:
        state, step = issue_step(m, state, issued_at=T0, evidence_refs=EVIDENCE)
        if step["step_id"] == target:
            return state, step
        assert step["step_type"] != "AGENT_REASON", f"unexpected agent step {step['step_id']} before {target}"
        state = record_automatic_output(state, step["step_id"], outputs.get(step["step_id"], {"ok": True}))


def test_full_walk_of_the_reference_manifest_with_bounded_gap_loop():
    m = _m()
    st = start_run(m, RUN, INPUT)
    assert st.status == "created" and validate("adapter_run_ref", {"run_id": RUN, **{k: m.identity[k] for k in ("adapter_id", "adapter_version", "workflow_version")}, "created_at": T0, "status": "created"}) == []
    st, step = _walk_to(m, st, "C_hypotheses", {})
    assert st.status == "awaiting_agent" and step["step_type"] == "AGENT_REASON" and step["sequence"] == 5
    assert validate("adapter_step", step) == [] and step["context"]["prior_step_ids"] == ["A_understand", "B_plan", "B_retrieve", "B_graph"]
    good = {"hypotheses": [{"activity": "a", "friction": "f", "direction": "d", "supporting_evidence_ids": ["chunk_1"], "confidence": "low"}]}
    sub = lambda p: {"run_id": RUN, "step_id": "C_hypotheses", "payload": p, "submitted_by": {"agent_identity": "hermes-local"}}
    with pytest.raises(SubmissionRejected) as e1:                       # schema violation
        accept_submission(m, st, step, sub({"hypotheses": []}))
    assert "payload" in e1.value.errors[0]
    with pytest.raises(SubmissionRejected) as e2:                       # cites evidence it was never given
        accept_submission(m, st, step, sub({"hypotheses": [{**good["hypotheses"][0], "supporting_evidence_ids": ["chunk_invented"]}]}))
    assert "not in context.evidence_refs" in e2.value.errors[0]
    st = accept_submission(m, st, step, sub(good))
    assert st.status == "running" and st.outputs["C_hypotheses"] == good and st.steps_accepted == 5
    # a wrong step id / a different payload / an identical replay
    with pytest.raises(SubmissionRejected):
        accept_submission(m, st, step, sub(good))                       # no longer awaiting -> rejected
    # continue: D, E, F (agent), G, H (branch) — first pass has gaps => loop back to D
    st, f_step = _walk_to(m, st, "F_normalize", {})
    st = accept_submission(m, st, f_step, {"run_id": RUN, "step_id": "F_normalize", "submitted_by": {"agent_identity": "hermes-local"},
        "payload": {"candidates": [{"activity": "a", "task": "t", "context": "c", "friction": "f", "workaround": "w", "product_territory": "p", "candidate": "x", "trail_record_ids": ["urlc_1"]}]}})
    loops = 0
    while True:
        st, step = issue_step(m, st, issued_at=T0, evidence_refs=EVIDENCE)
        if step["step_id"] == "G_gates":
            st = record_automatic_output(st, "G_gates", {"gaps": ["seasonality"] if loops < 3 else []})
        elif step["step_id"] == "H_gap_loop":
            st = record_automatic_output(st, "H_gap_loop", {})
        elif step["step_id"] == "D_discover":
            loops += 1; st = record_automatic_output(st, "D_discover", {"leads": ["urlc_1"]})
        elif step["step_id"] in ("E_acquire",):
            st = record_automatic_output(st, step["step_id"], {"records": ["urlc_1"]})
        elif step["step_type"] == "AGENT_REASON" and step["step_id"] == "F_normalize":
            st = accept_submission(m, st, step, {"run_id": RUN, "step_id": "F_normalize", "submitted_by": {"agent_identity": "hermes-local"},
                "payload": {"candidates": [{"activity": "a", "task": "t", "context": "c", "friction": "f", "workaround": "w", "product_territory": "p", "candidate": "x", "trail_record_ids": ["urlc_1"]}]}})
        elif step["step_id"] == "I_score":
            break
    assert loops == 3 and st.branch_loops == 3                          # bounded by budgets.max_branch_loops = 3 (count_lt 3 exits)
    st = record_automatic_output(st, "I_score", {"scores": [{"record_id": "score_1"}]})
    st, j = issue_step(m, st, issued_at=T0, evidence_refs=EVIDENCE)
    st = accept_submission(m, st, j, {"run_id": RUN, "step_id": "J_interpret", "submitted_by": {"agent_identity": "hermes-local"},
        "payload": {"interpretations": [{"candidate": "x", "trail_score_record_id": "score_1", "explanation": "e", "cheapest_falsification_experiment": "x"}]}})
    st, k = issue_step(m, st, issued_at=T0)
    assert k["step_type"] == "COMPILE_RESULT" and k["step_id"] == m.terminal_step_id
    st = record_automatic_output(st, "K_compile", {"product_hypotheses": []})
    st = complete_run(st)
    assert st.terminal and st.status == "completed"
    with pytest.raises(RuntimeError):
        issue_step(m, st, issued_at=T0)                                 # a terminal run never issues
    view = run_status_view(m, st, started_at=T0, updated_at=T0, terminal_at=T0)
    assert view["status"] == "completed" and view["steps_issued"] == st.sequence
    assert cancel_run(st) is st                                         # cancel is idempotent on a terminal run


def test_budget_exhaustion_is_a_typed_gap_not_a_crash():
    m = _m()
    raw = copy.deepcopy(m.raw); raw["budgets"]["max_steps"] = 3
    import tempfile
    p = pathlib.Path(tempfile.mkdtemp()) / "tight.json"; p.write_text(json.dumps(raw))
    tight = load_manifest(p)
    st = start_run(tight, RUN, INPUT)
    for _ in range(3):
        st, step = issue_step(tight, st, issued_at=T0)
        st = record_automatic_output(st, step["step_id"], {})
    with pytest.raises(BudgetExhausted):
        issue_step(tight, st, issued_at=T0)
    st = terminal_gap(st, "BUDGET_EXHAUSTED", "max_steps 3 reached", step_id=st.current_step_id)
    assert st.status == "terminal_gap" and st.gap["code"] == "BUDGET_EXHAUSTED"
    assert run_status_view(tight, st, started_at=T0, updated_at=T0, terminal_at=T0)["gap"]["step_id"] == "B_retrieve"


def test_start_run_validates_the_domain_input():
    with pytest.raises(SubmissionRejected):
        start_run(_m(), RUN, {"constraints": ["no seed"]})


def test_issue_and_hashes_are_deterministic():
    m = _m()
    a = _walk_to(m, start_run(m, RUN, INPUT), "C_hypotheses", {})[1]
    b = _walk_to(m, start_run(m, RUN, INPUT), "C_hypotheses", {})[1]
    assert a == b and stable_hash(a) == stable_hash(b)
    assert stable_hash({"x": 1, "y": [1, 2]}) == stable_hash({"y": [1, 2], "x": 1})


# ─────────────────────────────────────────────────────────── ADR-0019 graph rules (R1)
from polymath_shared.adapter import manifest as _M  # noqa: E402
def _mini(steps):
    return {"adapter_id": "probe.harness", "adapter_version": "1.0.0", "workflow_version": "1.0.0", "retrieval_policy_version": "1.0.0",
            "input_schema_version": "1.0.0", "output_schema_version": "1.0.0", "budgets": {"max_steps": 20, "max_agent_reason": 4, "max_branch_loops": 2, "max_harness_actions": 2},
            "entry_step_id": steps[0]["step_id"], "terminal_step_id": steps[-1]["step_id"], "steps": steps}


def _harness_manifest(*, branch_to_action=False, missing_kind=False, theta_on_validate=False):
    steps = [
        {"step_id": "a", "type": "AGENT_REASON", "title": "t", "objective": "o", "theta_op": "generate_hypotheses", "output_schema": {"type": "object"}, "next": "h"},
        {"step_id": "h", "type": "HARNESS_ACTION", "title": "research", "objective": "find field evidence",
         **({} if missing_kind else {"harness": {"action_kind": "AGENT_RESEARCH", "minimum_independent_sources": 3}}), "next": "v"},
        {"step_id": "v", "type": "VALIDATE", "title": "v", **({"theta_op": "derive_mechanisms"} if theta_on_validate else {}), "next": "b"},
        {"step_id": "b", "type": "BRANCH", "title": "b", "branches": [{"when": {"op": "exists", "path": "steps.v.output.ok"}, "next": "h" if branch_to_action else "a"}], "next": "k"},
        {"step_id": "k", "type": "COMPILE_RESULT", "title": "k", "next": None},
    ]
    return _mini(steps)


def test_harness_action_is_in_the_closed_vocabulary_and_answered_not_executed():
    from polymath_shared.adapter import contracts as C
    assert "HARNESS_ACTION" in C.STEP_TYPES and "HARNESS_ACTION" in C.AGENT_ANSWERED_STEP_TYPES
    assert "HARNESS_ACTION" not in C.AUTOMATIC_STEP_TYPES and "AGENT_REASON" not in C.AUTOMATIC_STEP_TYPES
    assert "awaiting_harness" in C.RUN_STATUSES
    assert _M.graph_integrity_errors(_harness_manifest()) == []


@pytest.mark.parametrize("kw, needle", [
    ({"branch_to_action": True}, "may not target HARNESS_ACTION"),
    ({"missing_kind": True}, "HARNESS_ACTION needs harness.action_kind"),
    ({"theta_on_validate": True}, "theta_op is only valid on AGENT_REASON"),
])
def test_graph_integrity_enforces_the_adr_0019_rules(kw, needle):
    errs = _M.graph_integrity_errors(_harness_manifest(**kw))
    assert any(needle in e for e in errs), errs

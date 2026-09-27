"""Gap A-15: TrailSignal's result envelope carries EVERY field; the ones an operation does not fill arrive as null or an EMPTY
tuple. Polymath must keep only what each operation fills, so a later operation's unfilled `qualifications` / `open_gaps` /
`redundancy_groups` / verdicts never shadow an earlier operation's real value, and runs stored before the fix must read back the
real value too. The envelopes here are built from the PINNED Trail model itself (its true wire defaults), not hand-written."""
from __future__ import annotations

import ast
import json
import pathlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[2]
TRAIL_SRC = ROOT / "governance" / "trail" / "src"
sys.path.insert(0, str(TRAIL_SRC))

import workers.adapter_step_worker as W
from polymath_shared.adapter import service
from polymath_shared.adapter import trail_client as TC
from polymath_shared.adapter.transitions import RunState
from trail_signal.contexts.workflow.public.operations import (
    ResearchResultV1,
)

SNAP = {"snapshot_id": "trs_a15", "content_hash": "sha256:" + "e" * 64}
OPERATIONS_SRC = TRAIL_SRC / "trail_signal" / "contexts" / "workflow" / "application" / "research_operations.py"


def _filled_by_source() -> dict[str, set[str]]:
    """Re-derive the map from the pinned Trail source: for each `if kind == "…"` branch, the keywords of its ResearchResultV1(…)."""
    found: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(OPERATIONS_SRC.read_text())):
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "kind" and isinstance(node.test.comparators[0], ast.Constant)):
            fields: set[str] = set()
            for sub in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(sub, ast.Call) and getattr(sub.func, "id", None) == "ResearchResultV1":
                    fields |= {kw.arg for kw in sub.keywords}
            found[node.test.comparators[0].value] = fields
    return found


def test_the_map_matches_the_pinned_trail_source():
    assert {k: set(v) for k, v in TC.FIELDS_BY_OPERATION.items()} == _filled_by_source()
    assert set(TC.FIELDS_BY_OPERATION) == set(TC.BOUNDED_OPERATIONS)
    assert set(TC.RESULT_FIELDS) == set(ResearchResultV1.model_fields)


def _wire_result(**filled) -> dict:
    """Trail's real wire shape: every field at its default (null or []), then the fields this operation fills."""
    return {**ResearchResultV1().model_dump(mode="json"), **filled}


def _exec(monkeypatch, kind: str, result: dict, prior: dict | None = None) -> dict:
    def handler(req):
        body = json.loads(req.content)
        value = {"operation_id": f"op-{kind}", "operation_kind": kind, "status_revision": 1, "registry_snapshot": SNAP, "result": result}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {
            "content": [{"type": "text", "text": json.dumps(value)}], "structuredContent": value, "isError": False}})
    monkeypatch.setattr(W, "_TRAIL", TC.TrailMCPClient("http://trail.a15/mcp", "a15-token", transport=httpx.MockTransport(handler)))
    spec = {"external": {"system": "trailsignal", "operation_kind": kind, "availability": "working"}, "config": {"stage": "market_delta"}, "harness": {}}
    m = type("M", (), {"step": staticmethod(lambda sid: spec)})()
    ctx = {"hypotheses": [{"hypothesis_id": "hyp_a", "revision": 0, "status": "proposed", "statement": "s"}], "registry_snapshot": SNAP}
    st = RunState(run_id="adr_" + "f" * 32, adapter_id="ecommerce.product_research", outputs=dict(prior or {}), output_order=tuple(prior or {}))
    out = W.exec_external({"step_id": "X", "sequence": 7, "context": ctx}, st, m)
    assert "output" in out, out
    return out["output"]


def test_the_wire_default_really_is_an_empty_list():
    # the premise of A-15: an unfilled tuple field is [] on the wire, not null, so "skip nulls" alone let it through
    wire = _wire_result()
    assert wire["qualifications"] == [] and wire["open_gaps"] == [] and wire["redundancy_groups"] == []


def test_a_score_step_stores_no_unfilled_fields(monkeypatch):
    out = _exec(monkeypatch, "opportunity.score", _wire_result(score_refusals=[{"record_id": "ref_1", "reason_code": "HARD_GATE_UNMET"}]))
    assert out["score_refusals"] == [{"record_id": "ref_1", "reason_code": "HARD_GATE_UNMET"}]
    assert out["trail_scores"] == []                                        # filled by score: an empty list is a real answer
    for unfilled in ("qualifications", "open_gaps", "redundancy_groups", "unsupported_hypothesis_ids", "territories", "hypothesis_verdicts"):
        assert unfilled not in out, unfilled


def test_a_qualify_step_keeps_an_empty_qualification_list(monkeypatch):
    out = _exec(monkeypatch, "opportunity.qualify", _wire_result(qualifications=[], open_gaps=[]))
    assert out["qualifications"] == [] and out["open_gaps"] == []
    assert "score_refusals" not in out and "trail_scores" not in out


def test_an_admit_step_stores_no_unfilled_fields(monkeypatch):
    receipt = {"H_field": {"_harness_action_id": "ha_1", "sources": [], "observations": []}}
    out = _exec(monkeypatch, "evidence.admit", _wire_result(evidence_admission={"admission_id": "adm_1", "admitted": [], "rejected": []}), receipt)
    assert out["evidence_admission"]["admission_id"] == "adm_1"
    assert "open_gaps" not in out and "redundancy_groups" not in out and "hypothesis_verdicts" not in out


# ── runs stored BEFORE the fix: every Trail step output carries every unfilled field as []
def _stored_before_fix() -> tuple[dict, tuple]:
    outputs = {
        "A_registry": {"operation_kind": "registry.project", "redundancy_groups": [["hyp_a", "hyp_b"]], "open_gaps": [], "qualifications": []},
        "B_judge": {"operation_kind": "hypotheses.judge", "open_gaps": [{"gap_id": "g1"}], "hypothesis_verdicts": [{"kind": "CONTRADICT"}],
                    "redundancy_groups": [], "qualifications": []},
        "C_admit": {"operation_kind": "evidence.admit", "evidence_admission": {"admission_id": "adm_2"}, "open_gaps": [],
                    "redundancy_groups": [], "hypothesis_verdicts": [], "qualifications": []},
        "R_qualify": {"operation_kind": "opportunity.qualify", "qualifications": [{"record_id": "q1", "stage": "market_delta"}],
                      "open_gaps": [{"gap_id": "g2"}], "redundancy_groups": [], "hypothesis_verdicts": []},
        "V_score": {"operation_kind": "opportunity.score", "trail_scores": [], "score_refusals": [{"record_id": "ref_1"}],
                    "qualifications": [], "open_gaps": [], "redundancy_groups": [], "hypothesis_verdicts": []},
        "W_interpret": {"interpretation": {"summary": "agent text"}},
    }
    return outputs, tuple(outputs)


def test_the_compiled_result_reads_the_real_qualifications_of_an_old_run():
    outputs, order = _stored_before_fix()
    assert service._gather(outputs, "qualifications", order) == [{"record_id": "q1", "stage": "market_delta"}]
    assert service._gather(outputs, "score_refusals", order) == [{"record_id": "ref_1"}]
    assert service._gather(outputs, "trail_scores", order) == []            # the score step filled it (empty = no score)
    assert service._gather(outputs, "hypothesis_verdicts", order) == [{"kind": "CONTRADICT"}]
    assert service._gather(outputs, "open_gaps", order) == [{"gap_id": "g2"}]
    assert service._gather(outputs, "interpretation", order) == {"summary": "agent text"}   # Polymath's own keys unchanged


def test_later_steps_see_the_real_groups_and_gaps_of_an_old_run():
    outputs, order = _stored_before_fix()
    st = RunState(run_id="adr_" + "f" * 32, adapter_id="ecommerce.product_research", outputs=outputs, output_order=order)
    assert W._newest_output_with(st, "redundancy_groups")["redundancy_groups"] == [["hyp_a", "hyp_b"]]
    assert W._newest_output_with(st, "open_gaps")["open_gaps"] == [{"gap_id": "g2"}]


def test_a_judge_step_receives_the_registry_redundancy_groups(monkeypatch):
    outputs, _ = _stored_before_fix()
    prior = {k: outputs[k] for k in ("A_registry", "C_admit")}
    sent = {}

    def handler(req):
        body = json.loads(req.content)
        sent.update(body)
        value = {"operation_id": "op-judge", "operation_kind": "hypotheses.judge", "status_revision": 1, "registry_snapshot": SNAP,
                 "result": _wire_result(verdicts=[], open_gaps=[])}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {
            "content": [{"type": "text", "text": json.dumps(value)}], "structuredContent": value, "isError": False}})
    monkeypatch.setattr(W, "_TRAIL", TC.TrailMCPClient("http://trail.a15/mcp", "a15-token", transport=httpx.MockTransport(handler)))
    spec = {"external": {"system": "trailsignal", "operation_kind": "hypotheses.judge", "availability": "working"}, "config": {}, "harness": {}}
    m = type("M", (), {"step": staticmethod(lambda sid: spec)})()
    ctx = {"hypotheses": [{"hypothesis_id": "hyp_a", "revision": 0, "status": "proposed", "statement": "s"}], "registry_snapshot": SNAP}
    st = RunState(run_id="adr_" + "f" * 32, adapter_id="ecommerce.product_research", outputs=prior, output_order=tuple(prior))
    W.exec_external({"step_id": "D_judge", "sequence": 9, "context": ctx}, st, m)
    assert '"redundancy_groups": [["hyp_a", "hyp_b"]]' in json.dumps(sent), "the judge must receive the registry's groups"


def test_a_newer_filled_empty_list_still_wins():
    outputs = {"R1": {"operation_kind": "opportunity.qualify", "qualifications": [{"record_id": "old"}]},
               "R2": {"operation_kind": "opportunity.qualify", "qualifications": []}}
    assert service._gather(outputs, "qualifications", ("R1", "R2")) == []


def test_fills_leaves_polymath_keys_and_non_trail_steps_alone():
    assert TC.fills(None, "qualifications") and TC.fills("opportunity.score", "physical_jobs")
    assert not TC.fills("opportunity.score", "qualifications") and not TC.fills("evidence.admit", "hypothesis_verdicts")
    assert TC.fills("hypotheses.judge", "hypothesis_verdicts") and TC.fills("unknown.kind", "qualifications")

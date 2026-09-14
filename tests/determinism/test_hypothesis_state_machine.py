"""ADR-0019 §3/§4 — the generic hypothesis ledger is pure and lineage-preserving (plan §9 tests A, E, G-pure, I).
θ may generate/revise/split; φ applies selective pressure; every transition names a cause; priors are never evidence;
no payload field can carry a score."""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.adapter import hypotheses as H  # noqa: E402
from polymath_shared.adapter import transitions as T  # noqa: E402
from polymath_shared.adapter.contracts import assert_valid  # noqa: E402

RUN = "adr_" + "1" * 32
NOW = "2026-09-13T20:00:00Z"
REFS = [{"kind": "chunk", "id": "chunk_a", "corpus_id": "c"}, {"kind": "graph_fact", "id": "fact_b"},
        {"kind": "trail_prior", "id": "fr-03", "note": "friction_primitive"}, {"kind": "field_evidence", "id": "fev_0000000000aa"}]


def _step(step_id="C_hypotheses", seq=5, refs=REFS):
    return {"run_id": RUN, "step_id": step_id, "sequence": seq, "context": {"evidence_refs": refs}, "harness_action": None}


def _proposals():
    return [{"statement": "runners lose access to small items mid-stride", "mechanism": "pocket bounce", "supporting_evidence_ids": ["chunk_a", "fact_b"],
             "trail_priors": [{"registry_record_id": "fr-03", "prior_role": "friction_primitive"}], "knowledge_gaps": [{"question": "how often?", "evidence_role": "behavior"}]},
            {"statement": "runners lose access to small items mid-stride (duplicate)", "supporting_evidence_ids": ["chunk_a"]}]


def test_generate_keeps_knowledge_lineage_and_attaches_priors_without_citing_them():
    states, trs = H.generate(RUN, _step(), _proposals(), registry_snapshot_id="trs_x", recorded_at=NOW)
    assert len(states) == 2 and len(trs) == 2
    s = states[0]
    assert s["revision"] == 0 and s["status"] == "proposed" and s["parent_hypothesis_ids"] == []
    assert {k["chunk_id"] for k in s["knowledge_support"] if k["chunk_id"]} == {"chunk_a"}
    assert {k["graph_fact_id"] for k in s["knowledge_support"] if k["graph_fact_id"]} == {"fact_b"}
    assert s["trail_priors"] == [{"registry_snapshot_id": "trs_x", "registry_record_id": "fr-03", "prior_role": "friction_primitive"}]
    assert trs[0]["kind"] == "GENERATE" and trs[0]["actor"] == "theta" and {c["id"] for c in trs[0]["cause_refs"]} == {"chunk_a", "fact_b", "fr-03"}
    assert H.lineage_intact(states, trs) == []
    for st in states:
        assert_valid("hypothesis_state", st)


@pytest.mark.parametrize("bad, needle", [
    ([{"statement": "x", "supporting_evidence_ids": ["fr-03"]}], "registry prior and may never be cited"),
    ([{"statement": "x", "supporting_evidence_ids": ["chunk_zzz"]}], "not in context.evidence_refs"),
    ([{"statement": "x", "supporting_evidence_ids": []}], "cite at least one evidence id"),
    ([{"statement": "x", "supporting_evidence_ids": ["chunk_a"]}] * 9, "between 1 and 8"),
])
def test_generate_refuses_priors_as_evidence_and_unknown_or_missing_citations(bad, needle):
    with pytest.raises(H.HypothesisRejected) as exc:
        H.generate(RUN, _step(), bad, registry_snapshot_id="trs_x", recorded_at=NOW)
    assert any(needle in e for e in exc.value.errors), exc.value.errors


def test_phi_verdicts_strengthen_split_merge_and_kill_with_lineage_and_theta_cannot_kill():
    states, trs = H.generate(RUN, _step(), _proposals(), registry_snapshot_id="trs_x", recorded_at=NOW)
    cur = {s["hypothesis_id"]: s for s in states}
    a, b = sorted(cur)
    causes = {"fev_0000000000aa": "field_evidence", "hadm_00000000aa": "evidence_admission", a: "hypothesis", b: "hypothesis", "chunk_a": "chunk"}
    step2 = _step("J_revise", 9)
    # θ may not apply selective pressure
    with pytest.raises(H.HypothesisRejected) as exc:
        H.apply(RUN, step2, cur, [{"hypothesis_id": b, "kind": "KILL", "cause_refs": [{"kind": "hypothesis", "id": a}]}], actor="theta", allowed_causes=causes, recorded_at=NOW)
    assert any("requires phi" in e for e in exc.value.errors)
    # φ: merge the duplicate into a, strengthen a with admitted evidence, split a into two children
    new, trs2 = H.apply(RUN, step2, cur, [
        {"hypothesis_id": b, "kind": "MERGE", "into_hypothesis_id": a, "cause_refs": [{"kind": "hypothesis", "id": a}], "reason_code": "DUPLICATE_STATEMENT"},
        {"hypothesis_id": a, "kind": "STRENGTHEN", "cause_refs": [{"kind": "field_evidence", "id": "fev_0000000000aa"}, {"kind": "evidence_admission", "id": "hadm_00000000aa"}],
         "field_evidence_ids": ["fev_0000000000aa"], "reason_code": "INDEPENDENT_SUPPORT_THRESHOLD_MET"},
        {"hypothesis_id": a, "kind": "SPLIT", "cause_refs": [{"kind": "chunk", "id": "chunk_a"}], "children": [
            {"statement": "runners: phone access", "supporting_evidence_ids": ["chunk_a"]}, {"statement": "runners: key access", "supporting_evidence_ids": ["chunk_a"]}]},
    ], actor="phi", allowed_causes=causes, recorded_at=NOW)
    by = {s["hypothesis_id"]: s for s in new}
    assert by[b]["status"] == "merged" and by[a]["status"] == "split" and a in by[b]["parent_hypothesis_ids"] or b in by[a]["parent_hypothesis_ids"]
    assert "fev_0000000000aa" in by[a]["field_evidence_ids"]
    children = [s for s in new if s["parent_hypothesis_ids"] == [a]]
    assert len(children) == 2 and all(c["knowledge_support"] and c["revision"] == 0 for c in children)
    kinds = [t["kind"] for t in trs2]
    assert kinds.count("MERGE") == 1 and kinds.count("STRENGTHEN") == 1 and kinds.count("SPLIT") == 1 and kinds.count("GENERATE") == 2
    assert all(t["cause_refs"] for t in trs2)
    assert H.lineage_intact(states + new, trs + trs2) == []
    # absorbed hypotheses cannot transition again; a transition without a cause is refused
    cur2 = {**cur, **by}
    with pytest.raises(H.HypothesisRejected):
        H.apply(RUN, _step("K", 10), cur2, [{"hypothesis_id": b, "kind": "WEAKEN", "cause_refs": [{"kind": "hypothesis", "id": a}]}], actor="phi", allowed_causes=causes, recorded_at=NOW)
    with pytest.raises(H.HypothesisRejected) as exc:
        H.apply(RUN, _step("K", 10), cur2, [{"hypothesis_id": children[0]["hypothesis_id"], "kind": "KILL", "cause_refs": []}], actor="phi", allowed_causes=causes, recorded_at=NOW)
    assert any("at least one cause" in e for e in exc.value.errors)
    view = H.context_view(cur2)
    assert b not in {v["hypothesis_id"] for v in view} and any(v["hypothesis_id"] == a for v in view)


def test_submission_validation_refuses_a_cited_prior_and_receipt_validation_binds_the_action():
    step = {**_step(), "step_type": "AGENT_REASON", "output_schema": {"type": "object"}}
    errs = T.validate_submission(step, {"hypotheses": [{"supporting_evidence_ids": ["chunk_a", "fr-03"]}]})
    assert any("registry priors may never be cited" in e for e in errs), errs
    assert T.validate_submission(step, {"hypotheses": [{"supporting_evidence_ids": ["chunk_a", "fev_0000000000aa"]}]}) == []
    import json
    action = json.loads((ROOT / "contracts/adapter/v1/harness_action.example.json").read_text())
    receipt = json.loads((ROOT / "contracts/adapter/v1/harness_receipt.example.json").read_text())
    hstep = {"run_id": action["run_id"], "step_id": action["step_id"], "sequence": 12, "step_type": "HARNESS_ACTION", "harness_action": action, "context": {"evidence_refs": []}}
    assert T.validate_receipt(hstep, receipt) == []
    assert any("does not match the issued action" in e for e in T.validate_receipt(hstep, {**receipt, "action_id": "hact_ffffffffffff"}))
    assert any("payload" in e for e in T.validate_receipt(hstep, {**receipt, "score": 0.5}))          # LAW 1 at the wire
    assert any("payload" in e for e in T.validate_receipt(hstep, {**receipt, "observations": [{**receipt["observations"][0], "score": 0.9}]}))

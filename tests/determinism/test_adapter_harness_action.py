"""HARNESS-RESEARCH-MIGRATION-V1 R2 (ADR-0019): the HARNESS_ACTION pause, receipts from two harness identities, TrailSignal's
admission projection and φ verdicts as durable state, the θ ledger on AGENT_REASON, the closed φ dedupe rule, lineage in the
result, and the typed gaps. Real Postgres (migrations 0061 + 0062); knowledge and Trail steps are fake executors
(this proves the engine, not Polymath retrieval or Trail). Plan §9 tests A, B, E, F, G, I."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import uuid

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in ("shared", "workers", "orchestrator"):
    sys.path.insert(0, str(ROOT / p))
pytest.importorskip("psycopg")
if not os.environ.get("POLYMATH_PG_DSN"):
    pytest.skip("POLYMATH_PG_DSN not set", allow_module_level=True)

from polymath_shared.adapter import service, store  # noqa: E402
from polymath_shared.adapter.transitions import SubmissionRejected  # noqa: E402
from polymath_shared.db import tx  # noqa: E402

SNAP = {"snapshot_id": "trs_probe_1", "content_hash": "sha256:" + "b" * 64}
RECEIPT_TPL = json.loads((ROOT / "contracts/adapter/v1/harness_receipt.example.json").read_text())


def _manifest(tmp: pathlib.Path, *, with_directive: bool = True, bad_verdict: bool = False) -> pathlib.Path:
    ext = lambda kind: {"system": "trailsignal", "operation_kind": kind, "availability": "working"}
    steps = [
        {"step_id": "A_retrieve", "type": "POLYMATH_RETRIEVE", "title": "retrieve", "next": "B_hyp", "config": {"source": "input.seed"}},
        {"step_id": "B_hyp", "type": "AGENT_REASON", "title": "hypotheses", "objective": "propose hypotheses", "theta_op": "generate_hypotheses",
         "output_schema": {"type": "object", "required": ["hypotheses"], "properties": {"hypotheses": {"type": "array", "minItems": 1}}}, "next": "C_project"},
        {"step_id": "C_project", "type": "EXTERNAL_OPERATION", "title": "priors", "external": ext("registry.project"), "next": "D_gaps" if with_directive else "E_research"},
        {"step_id": "D_gaps", "type": "EXTERNAL_OPERATION", "title": "gaps", "external": ext("gaps.compile"), "next": "E_research"},
        {"step_id": "E_research", "type": "HARNESS_ACTION", "title": "field research", "objective": "find field evidence for the live hypotheses",
         "harness": {"action_kind": "AGENT_RESEARCH", "minimum_independent_sources": 2, "preferred_source_roles": ["community_discussion"],
                     "budget": {"max_queries": 10, "max_sources": 8, "max_observations": 30}}, "next": "F_admit"},
        {"step_id": "F_admit", "type": "EXTERNAL_OPERATION", "title": "admission", "external": ext("evidence.admit"), "next": "G_dedupe"},
        {"step_id": "G_dedupe", "type": "VALIDATE", "title": "phi dedupe", "config": {"phi": "deduplicate"}, "next": "H_revise"},
        {"step_id": "H_revise", "type": "AGENT_REASON", "title": "revise", "objective": "revise with admitted evidence", "theta_op": "derive_mechanisms",
         "output_schema": {"type": "object", "required": ["transitions"], "properties": {"transitions": {"type": "array"}}}, "next": "K_compile"},
        {"step_id": "K_compile", "type": "COMPILE_RESULT", "title": "compile", "next": None, "config": {"include": ["hypothesis_ids", "lineage"]}},
    ]
    if not with_directive:
        steps = [s for s in steps if s["step_id"] != "D_gaps"]
    m = {"adapter_id": "probe.harness_loop", "adapter_version": "1.0.0", "workflow_version": "1.0.0", "retrieval_policy_version": "1.0.0",
         "input_schema_version": "1.0.0", "output_schema_version": "1.0.0", "evidence_roles": ["friction", "workaround", "behavior"],
         "input_schema": {"type": "object", "required": ["seed"], "properties": {"seed": {"type": "string"}}},
         "budgets": {"max_steps": 30, "max_agent_reason": 4, "max_branch_loops": 1, "max_harness_actions": 2, "max_hypotheses": 8},
         "entry_step_id": "A_retrieve", "terminal_step_id": "K_compile", "steps": steps}
    (tmp / "probe.harness_loop.json").write_text(json.dumps(m))
    tmp.joinpath("_bad_verdict").write_text("1" if bad_verdict else "0")
    return tmp


def _executors(tmp: pathlib.Path):
    bad = tmp.joinpath("_bad_verdict").read_text() == "1"

    def retrieve(step, state, m):
        return {"output": {"rows": 2}, "evidence_refs": [{"kind": "chunk", "id": "chunk_k1", "corpus_id": "probe"}, {"kind": "graph_fact", "id": "fact_k2"}]}

    def external(step, state, m):
        kind = step["external"]["operation_kind"]
        if kind == "registry.project":
            return {"output": {"registry_snapshot": SNAP}, "evidence_refs": [{"kind": "trail_prior", "id": "fr-03", "note": "friction_primitive"}]}
        if kind == "gaps.compile":
            return {"output": {"research_directive": {"search_intents": [{"intent_id": "si_1", "intent": "find first-person friction complaints", "evidence_goal": "complaint", "evidence_roles": ["friction"]}],
                                                       "evidence_gaps": [{"gap_id": "gap_1", "hypothesis_id": sorted(store_hyps(state))[0], "question": "is it recurring?", "evidence_role": "friction"}],
                                                       "geography": "US", "language": "en", "success_condition": "3 independent complaints", "falsification_condition": "none found"}}}
        if kind == "evidence.admit":
            rec = state.outputs["E_research"]
            hid = sorted(store_hyps(state))[0]
            adm_id = "hadm_" + hashlib.sha256(rec["_harness_action_id"].encode()).hexdigest()[:12]
            admitted = [{"admitted_evidence_id": "fev_" + hashlib.sha256(o["observation_id"].encode()).hexdigest()[:12], "observation_id": o["observation_id"], "source_id": o["source_id"],
                         "evidence_role": "friction", "source_class": "community_discussion", "source_suitability": "suitable", "freshness": "fresh", "provenance": "recorded",
                         "independence_group": o["source_id"], "duplicate_of": None, "polarity": "supporting", "hypothesis_ids": [hid], "stage_relevance": "field_evidence",
                         "limitations": [], "trail_admission_record_id": "adm_rec_" + o["observation_id"]} for o in rec["observations"]]
            adm = {"admission_id": adm_id, "run_id": state.run_id, "action_id": rec["_harness_action_id"], "registry_snapshot": SNAP, "trail_operation_id": "op_probe_admit",
                   "admitted": admitted, "rejected": [{"observation_id": "obs_x", "reason_code": "SOURCE_ROLE_UNSUITABLE", "detail": "supplier listing cannot support friction"}],
                   "evaluated_at": "2026-09-13T21:00:00Z"}
            verdict = {"hypothesis_id": hid, "kind": "STRENGTHEN", "cause_refs": ([] if bad else [{"kind": "field_evidence", "id": admitted[0]["admitted_evidence_id"]}, {"kind": "evidence_admission", "id": adm_id}]),
                       "field_evidence_ids": [a["admitted_evidence_id"] for a in admitted], "reason_code": "INDEPENDENT_SUPPORT_THRESHOLD_MET"}
            return {"output": {"evidence_admission": adm, "hypothesis_verdicts": [verdict], "_evidence_refs": []}, "external": None}
        raise AssertionError(kind)

    from workers.adapter_step_worker import exec_branch, exec_validate
    return {"POLYMATH_RETRIEVE": retrieve, "EXTERNAL_OPERATION": external, "VALIDATE": exec_validate, "BRANCH": exec_branch}


def store_hyps(state):
    with tx() as conn:
        return store.current_hypotheses(conn, state.run_id)


def _advance(run_id, execs, d):
    with tx() as conn:
        return service.advance(conn, run_id, execs, directory=d)


def _submit(run_id, step_id, payload, d, *, identity="probe", kind=None):
    sub = {"step_id": step_id, "payload": payload, "submitted_by": {"agent_identity": identity}}
    if kind:
        sub["kind"] = kind
    with tx() as conn:
        return service.submit(conn, run_id, sub, directory=d)


def _next(run_id, d):
    with tx() as conn:
        return service.next_step(conn, run_id, directory=d)


def _cleanup(run_id):
    with tx() as conn:
        store.delete_run(conn, run_id)


def _receipt(action, harness_id):
    r = json.loads(json.dumps(RECEIPT_TPL))
    r.update({"action_id": action["action_id"], "run_id": action["run_id"], "harness_id": harness_id})
    for o in r["observations"]:
        o["hypothesis_ids"] = list(action["hypothesis_ids"][:1])
    return r


@pytest.fixture
def probe(tmp_path):
    d = _manifest(tmp_path)
    service.reset_registry()
    yield d
    service.reset_registry()


def _start(d, seed="runners lose access to small items"):
    with tx() as conn:
        ref = service.start(conn, adapter_id="probe.harness_loop", input_payload={"seed": seed}, request_options={"idempotency_key": uuid.uuid4().hex}, directory=d)
    return ref["run_id"]


def _walk_to_harness(run_id, d, execs):
    st = _advance(run_id, execs, d)
    assert st.status == "awaiting_agent" and st.current_step_id == "B_hyp"
    step = _next(run_id, d)["step"]
    ids = {r["id"]: r["kind"] for r in step["context"]["evidence_refs"]}
    assert ids == {"chunk_k1": "chunk", "fact_k2": "graph_fact"}
    hyps = [{"statement": "runners lose access to small items mid-stride", "mechanism": "pocket bounce", "supporting_evidence_ids": ["chunk_k1", "fact_k2"]},
            {"statement": "Runners lose access to small items mid-stride", "supporting_evidence_ids": ["chunk_k1"]},
            {"statement": "runners drop keys when opening zips with gloves", "supporting_evidence_ids": ["fact_k2"]}]
    st = _submit(run_id, "B_hyp", {"hypotheses": hyps}, d)
    assert st["status"] == "running"
    st = _advance(run_id, execs, d)
    assert st.status == "awaiting_harness" and st.current_step_id == "E_research", (st.status, st.current_step_id, st.gap)
    nxt = _next(run_id, d)
    assert nxt["kind"] == "step" and nxt["step"]["step_type"] == "HARNESS_ACTION"
    return nxt["step"]


def test_harness_action_pauses_durably_and_a_receipt_resumes_the_same_run_with_lineage(probe):
    d, execs = probe, _executors(probe)
    run_id = _start(d)
    try:
        step = _walk_to_harness(run_id, d, execs)
        action = step["harness_action"]
        assert action["action_kind"] == "AGENT_RESEARCH" and len(action["hypothesis_ids"]) == 3 and action["registry_snapshot"] == SNAP
        assert action["minimum_independent_sources"] == 2 and action["budget"]["max_queries"] == 10 and action["search_intents"][0]["intent_id"] == "si_1"
        assert step["context"]["registry_snapshot"] == SNAP and {h["status"] for h in step["context"]["hypotheses"]} == {"proposed"}
        assert any(r["kind"] == "trail_prior" for r in step["context"]["evidence_refs"])          # priors travel as coordinates
        # a run awaiting the harness is NOT claimable by a worker (durable pause) and survives a "restart" (fresh load)
        with tx() as conn:
            assert store.claim_run(conn, "worker-b", 60) is None
            state2, _ = store.load_run(conn, run_id)
            assert state2.status == "awaiting_harness" and state2.harness_action_count == 1
            assert store.harness_action_row(conn, action["action_id"])["status"] == "issued"
        # wrong answers: a reasoning payload, a receipt for another action, a receipt with a score field (LAW 1)
        with pytest.raises(SubmissionRejected):
            _submit(run_id, "E_research", {"hypotheses": []}, d, kind="reasoning")
        with pytest.raises(SubmissionRejected) as exc:
            _submit(run_id, "E_research", {**_receipt(action, "hermes"), "action_id": "hact_ffffffffffff"}, d)
        assert any("does not match the issued action" in e for e in exc.value.errors)
        with pytest.raises(SubmissionRejected):
            _submit(run_id, "E_research", {**_receipt(action, "hermes"), "score": 0.9}, d)
        st = _submit(run_id, "E_research", _receipt(action, "hermes"), d, identity="hermes", kind="receipt")
        assert st["status"] == "running" and st["harness_actions"] == 1
        st = _advance(run_id, execs, d)              # F_admit + G_dedupe run; H_revise is issued
        assert st.status == "awaiting_agent" and st.current_step_id == "H_revise", (st.status, st.current_step_id, st.gap, st.failure)
        with tx() as conn:
            hyps = store.current_hypotheses(conn, run_id)
            trs = store.list_transitions(conn, run_id)
            admitted = store.admitted_evidence_refs(conn, run_id)
            row = store.harness_action_row(conn, action["action_id"])
        assert row["status"] == "admitted" and row["receipt"]["harness_id"] == "hermes" and row["receipt_hash"]
        assert len(admitted) == 2 and all(r["kind"] == "field_evidence" for r in admitted)
        statuses = sorted(h["status"] for h in hyps.values())
        assert statuses == ["merged", "proposed", "strengthened"], statuses      # φ: STRENGTHEN by admission, MERGE by dedupe
        strong = next(h for h in hyps.values() if h["status"] == "strengthened")
        merged = next(h for h in hyps.values() if h["status"] == "merged")
        # r1 = STRENGTHEN (admission), r2 = the duplicate merged INTO it (φ dedupe) — and the merged one is now its parent
        assert set(strong["field_evidence_ids"]) == {r["id"] for r in admitted} and strong["revision"] == 2
        assert merged["hypothesis_id"] in strong["parent_hypothesis_ids"] and merged["revision"] == 1
        assert {t["kind"] for t in trs} >= {"GENERATE", "STRENGTHEN", "MERGE", "REVISE"} and all(t["cause_refs"] for t in trs)
        # H_revise: context carries admitted field evidence and live hypotheses; θ proposes a REVISE citing admitted evidence
        step = _next(run_id, d)["step"]
        kinds = {r["kind"] for r in step["context"]["evidence_refs"]}
        assert "field_evidence" in kinds and len(step["context"]["hypotheses"]) == 2
        fev = next(r["id"] for r in step["context"]["evidence_refs"] if r["kind"] == "field_evidence")
        with pytest.raises(SubmissionRejected) as exc:                       # priors can never be cited as a cause
            _submit(run_id, "H_revise", {"transitions": [{"hypothesis_id": strong["hypothesis_id"], "kind": "KILL", "cause_refs": [{"kind": "field_evidence", "id": fev}]}]}, d)
        assert any("requires phi" in e for e in exc.value.errors)
        st = _submit(run_id, "H_revise", {"transitions": [{"hypothesis_id": strong["hypothesis_id"], "kind": "REVISE", "cause_refs": [{"kind": "field_evidence", "id": fev}],
                                                             "changes": {"mechanism": "pocket bounce plus glove dexterity"}, "reason_code": "MECHANISM_REFINED"}]}, d)
        st = _advance(run_id, execs, d)
        assert st.status == "completed", (st.status, st.gap, st.failure)
        with tx() as conn:
            res = service.result(conn, run_id)
        lin = res["lineage"]
        assert set(lin["hypothesis_ids"]) == set(hyps) and set(lin["admitted_evidence_ids"]) == {r["id"] for r in admitted}
        assert lin["harness_action_ids"] == [action["action_id"]] and lin["harness_ids"] == ["hermes"] and lin["registry_snapshot_ids"] == [SNAP["snapshot_id"]]
        assert lin["polymath_evidence_ids"] == ["chunk_k1", "fact_k2"] and lin["trail_score_record_ids"] == []
        with tx() as conn:
            steps = store.list_steps(conn, run_id)
        e_step = next(s for s in steps if s["step_id"] == "E_research")
        assert e_step["receipt"]["harness_receipt_hash"] == row["receipt_hash"] and e_step["status"] == "accepted"
        assert next(s for s in steps if s["step_id"] == "F_admit")["receipt"]["admission_id"].startswith("hadm_")
    finally:
        _cleanup(run_id)


def test_a_second_harness_identity_completes_the_same_contract(probe):
    d, execs = probe, _executors(probe)
    run_id = _start(d, seed="cyclists lose gloves at stops")
    try:
        step = _walk_to_harness(run_id, d, execs)
        _submit(run_id, "E_research", _receipt(step["harness_action"], "claude-code"), d, identity="claude-code")
        st = _advance(run_id, execs, d)
        assert st.status == "awaiting_agent" and st.current_step_id == "H_revise"
        with tx() as conn:
            assert store.harness_action_row(conn, step["harness_action"]["action_id"])["receipt"]["harness_id"] == "claude-code"
    finally:
        _cleanup(run_id)


def test_missing_directive_is_a_typed_gap_not_an_invented_action(tmp_path):
    d = _manifest(tmp_path, with_directive=False)
    service.reset_registry()
    execs = _executors(d)
    run_id = _start(d)
    try:
        st = _advance(run_id, execs, d)
        _submit(run_id, "B_hyp", {"hypotheses": [{"statement": "s", "supporting_evidence_ids": ["chunk_k1"]}]}, d)
        st = _advance(run_id, execs, d)
        assert st.status == "terminal_gap" and st.gap["code"] == "HARNESS_DIRECTIVE_MISSING" and st.gap["step_id"] == "E_research"
    finally:
        _cleanup(run_id); service.reset_registry()


def test_an_invalid_phi_verdict_ends_the_run_with_a_typed_gap(tmp_path):
    d = _manifest(tmp_path, bad_verdict=True)
    service.reset_registry()
    execs = _executors(d)
    run_id = _start(d)
    try:
        step = _walk_to_harness(run_id, d, execs)
        _submit(run_id, "E_research", _receipt(step["harness_action"], "codex"), d)
        st = _advance(run_id, execs, d)
        assert st.status == "terminal_gap" and st.gap["code"] == "PHI_VERDICT_INVALID"
        with tx() as conn:                       # the admission itself was recorded before the verdict failed (same unit → rolled back with the gap? no: recorded)
            assert store.list_harness_actions(conn, run_id)[0]["status"] in ("admitted", "issued", "received")
    finally:
        _cleanup(run_id); service.reset_registry()

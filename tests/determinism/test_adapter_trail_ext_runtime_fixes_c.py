"""TRAIL-EXT-BUGHUNT-V1, group `runtime`, batch C — adapter behaviour through the REAL runtime (`service.start / advance / next_step /
submit / status / cancel`, the orchestrator's adapter routes) over the in-memory store. No database, no network, no daemon.

Each test names the finding it reproduces (docs/wiki/experiments/trail-ext-bughunt-2026-09-26). The pure half is in
tests/contracts/test_trail_ext_runtime_fixes_c.py; the store doubles come from the batch A/B file beside this one.
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import sys

import pytest
from fastapi import HTTPException

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (ROOT / "workers", ROOT / "shared", ROOT / "orchestrator", pathlib.Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import test_adapter_trail_ext_runtime_fixes as AB  # the batch A/B rigs: TxStore (a store whose tx rolls back), the fixture manifests
import workers.adapter_step_worker as W
from _adapter_memory_store import MemoryStore
from orchestrator.api import adapter as A
from polymath_shared.adapter import contracts as C
from polymath_shared.adapter import hypotheses as H
from polymath_shared.adapter import service
from polymath_shared.adapter.transitions import SubmissionRejected

ROWS = [{"kind": "chunk", "id": "chunk_fake_1", "doc_id": "doc_fake", "corpus_id": "probe", "text": "a load away from the body bounces"}]


class RollbackStore(MemoryStore):
    """MemoryStore + a tx() that restores a snapshot on exception, like db.tx's rollback (AB.TxStore also rolls back, but its lease clock
    stores integer timestamps that the status view cannot render)."""
    tx = AB.TxStore.tx

    def __init__(self):
        super().__init__()
        self.clock = 0


def _retrieve(step, state, m):
    return {"output": {"rows": ROWS}, "evidence_refs": [{"kind": "chunk", "id": "chunk_fake_1", "corpus_id": "probe"}]}


def test_the_code_under_test_is_this_checkout():
    for mod in (A, C, service, W, AB):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


def _manifest(d: pathlib.Path, adapter_id: str, version: str, steps: list[dict], entry: str) -> None:
    raw = {"adapter_id": adapter_id, "adapter_version": version, "workflow_version": version, "retrieval_policy_version": "1.0.0",
           "input_schema_version": "1.0.0", "output_schema_version": "1.0.0", "description": "bug-hunt fixture",
           "input_schema": {"type": "object"}, "output_schema": {"type": "object"},
           "budgets": {"max_steps": 12, "max_agent_reason": 3, "max_branch_loops": 0, "max_external_operations": 0},
           "entry_step_id": entry, "terminal_step_id": "X_compile",
           "steps": steps + [{"step_id": "X_compile", "type": "COMPILE_RESULT", "title": "compile", "next": None, "config": {"include": ["lineage"]}}]}
    (d / f"{adapter_id}.json").write_text(json.dumps(raw))
    service.reset_registry()


@pytest.fixture
def rig(tmp_path, monkeypatch):
    d = tmp_path / "adapters"
    d.mkdir()
    store = RollbackStore()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setattr(A, "tx", store.tx)
    service.reset_registry()
    monkeypatch.setattr(service, "manifest_for", lambda adapter_id, directory=None: service.registry(d)[adapter_id])
    yield d, store
    service.reset_registry()


def _brief(step_id: str = "brief", *, theta: bool = False) -> dict:
    return {"step_id": step_id, "type": "AGENT_REASON", "title": "brief", "next": "X_compile", "objective": "write",
            **({"theta_op": "generate_hypotheses"} if theta else {}),
            "output_schema": {"type": "object", "properties": {"statement": {"type": "string", "maxLength": 20}}}}


def _parked(d, store, adapter_id="fixture.brief", *, theta=False) -> str:
    _manifest(d, adapter_id, "1.0.0", [{"step_id": "A_retrieve", "type": "POLYMATH_RETRIEVE", "title": "retrieve", "next": "brief"}, _brief(theta=theta)], "A_retrieve")
    rid = service.start(None, adapter_id=adapter_id, input_payload={"q": "x"})["run_id"]
    with store.tx():
        st = service.advance(None, rid, {"POLYMATH_RETRIEVE": _retrieve})
    assert st.status == "awaiting_agent" and st.current_step_id == "brief"
    return rid


# ─────────────────────────────────────────────────────────── B-48: a rejection is receipted durably, not rolled back with the route
def _submit_route(rid: str, payload: dict) -> dict:
    return asyncio.run(A.adapter_submit(rid, A.SubmitRequest(step_id="brief", payload=payload)))


def test_b48_a_rejected_submission_keeps_its_receipt_through_the_route(rig):
    d, store = rig
    rid = _parked(d, store)
    with pytest.raises(HTTPException) as exc:
        _submit_route(rid, {"statement": "far too long for this step's own schema"})
    assert exc.value.status_code == 422 and any("too long" in e for e in exc.value.detail["rejected"])
    row = store.current_step(None, rid)
    assert row["status"] == "issued" and (row["receipt"] or {}).get("status") == "rejected", row["receipt"]   # the defect: rolled back
    assert C.validate("adapter_step_receipt", row["receipt"]) == []
    assert _submit_route(rid, {"statement": "short"})["status"] == "running"                           # the step stayed open for the fix


def test_b48_a_rejected_theta_submission_writes_nothing_to_the_ledger(rig):
    """A committed rejection must carry nothing but its receipt. `service.submit` is called on the store WITHOUT a rollback (what now
    commits): a payload whose hypotheses are lawful but whose transition is not wrote the generated hypotheses BEFORE the transition was
    refused — harmless only while every rejection was rolled back."""
    d, store = rig
    rid = _parked(d, store, "fixture.theta", theta=True)
    payload = {"hypotheses": [{"statement": "runners lose small items mid stride", "supporting_evidence_ids": ["chunk_fake_1"]}],
               "transitions": [{"hypothesis_id": "hyp_" + "0" * 24, "kind": "REVISE", "cause_refs": [{"kind": "chunk", "id": "chunk_fake_1"}]}]}
    with pytest.raises(SubmissionRejected, match="unknown hypothesis"):
        service.submit(None, rid, {"step_id": "brief", "payload": payload, "submitted_by": {"agent_identity": "t"}}, d)
    assert store.current_hypotheses(None, rid) == {} and store.transitions == {}                    # the defect: the generated one stayed
    assert store.current_step(None, rid)["receipt"]["status"] == "rejected"


# ─────────────────────────────────────────────────────────── B-57: a redeploy that renames the step a run stands at
def test_b57_a_parked_run_whose_step_a_redeploy_renamed_stays_readable_refusable_and_cancellable(rig):
    d, store = rig
    rid = _parked(d, store, "fixture.drift")
    _manifest(d, "fixture.drift", "1.1.0", [{"step_id": "A_retrieve", "type": "POLYMATH_RETRIEVE", "title": "retrieve", "next": "brief_v2"},
                                            _brief("brief_v2")], "A_retrieve")
    st = service.status(None, rid, d)                                                               # the defect: ManifestError (HTTP 500)
    assert (st["status"], st["current_step_id"], st["current_step_type"]) == ("awaiting_agent", "brief", None)
    assert st["adapter_version"] == "1.0.0" == service.run_ref(None, rid)["adapter_version"]        # the run's own version, as run_ref says
    nxt = service.next_step(None, rid, d)
    assert nxt["kind"] == "step" and nxt["step"]["step_id"] == "brief"
    with pytest.raises(SubmissionRejected, match="MANIFEST_VERSION_UNAVAILABLE"):
        service.submit(None, rid, {"step_id": "brief", "payload": {"statement": "short"}, "submitted_by": {"agent_identity": "t"}}, d)
    assert service.status(None, rid, d)["status"] == "awaiting_agent"                               # refused, still parked (a rollback of the deploy resumes it)
    with store.tx():
        assert service.cancel(None, rid, d)["status"] == "cancelled"                                 # the defect: cancel raised and rolled back
    assert store.load_run(None, rid)[0].status == "cancelled"


def test_b57_a_running_run_whose_step_a_redeploy_removed_ends_with_a_typed_gap(rig):
    d, _store = rig
    _manifest(d, "fixture.drift", "1.0.0", [{"step_id": "prep", "type": "VALIDATE", "title": "prep", "next": "brief"}, _brief()], "prep")
    rid = service.start(None, adapter_id="fixture.drift", input_payload={"q": "x"})["run_id"]
    service.advance(None, rid, W.EXECUTORS, max_steps=1)                                            # `prep` executed; the run is running at it
    _manifest(d, "fixture.drift", "1.1.0", [{"step_id": "prep2", "type": "VALIDATE", "title": "prep", "next": "brief"}, _brief()], "prep2")
    st = service.advance(None, rid, W.EXECUTORS, max_steps=1)                                       # the defect: ManifestError out of advance
    assert st.status == "terminal_gap" and st.gap["code"] == "MANIFEST_VERSION_UNAVAILABLE"
    assert "'prep'" in st.gap["message"] and "1.0.0" in st.gap["message"] and "1.1.0" in st.gap["message"]
    assert service.status(None, rid, d)["gap"]["code"] == "MANIFEST_VERSION_UNAVAILABLE"


# ─────────────────────────────────────────────────────────── B-69: the runtime applies nothing a domain wrote in Trail's name
def test_b69_a_domain_verdict_fails_the_step_and_applies_no_transition(tmp_path, monkeypatch):
    d = tmp_path / "adapters"
    d.mkdir()
    dom = tmp_path / "domains" / "fakedomain"
    dom.mkdir(parents=True)
    store = MemoryStore()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setattr(W, "_DOMAINS_DIR", tmp_path / "domains")
    (dom / "binding.py").write_text("import sys\nsys.stdin.read()\nprint(open('out.json').read())\n")
    _manifest(d, "fixture.domain", "1.0.0", [{"step_id": "S_dom", "type": "DOMAIN_OPERATION", "title": "domain", "next": "X_compile",
                                              "config": {"domain": "fakedomain", "operation": "probe.run"}}], "S_dom")
    rid = service.start(None, adapter_id="fixture.domain", input_payload={"q": "x"}, directory=d)["run_id"]
    states, trs = H.generate(rid, {"run_id": rid, "step_id": "gen", "sequence": 1, "context": {"evidence_refs": [{"kind": "chunk", "id": "chunk_fake_1"}]}},
                             [{"statement": "runners lose small items mid stride", "supporting_evidence_ids": ["chunk_fake_1"]}],
                             registry_snapshot_id=None, recorded_at="2026-09-26T00:00:00Z")
    store.insert_hypothesis_revisions(None, states)
    store.insert_transitions(None, trs)
    hid = states[0]["hypothesis_id"]
    (dom / "out.json").write_text(json.dumps({"ok": True, "output": {"hypothesis_verdicts": [
        {"hypothesis_id": hid, "kind": "KILL", "cause_refs": [{"kind": "hypothesis", "id": hid}], "reason_code": "DOMAIN_SAYS_SO"}]}}))
    st = service.advance(None, rid, W.EXECUTORS, max_steps=1, directory=d)
    assert store.current_hypotheses(None, rid)[hid]["status"] == "proposed"                         # the defect: KILLED by domain code, as φ
    assert st.status == "failed" and st.failure["code"] == "STEP_EXECUTOR_ERROR" and "hypothesis_verdicts" in st.failure["message"]
    service.reset_registry()


def test_b57_a_manifest_set_that_does_not_load_never_ends_a_run_the_worker_claims(tmp_path, monkeypatch):
    """The other side of B-57 (and of B-06's net): a deploy that ships a MALFORMED manifest breaks every adapter at once. The worker
    backs off and the run waits for the fixed deploy — it is never ended for an error that says nothing about it."""
    d = tmp_path / "adapters"
    d.mkdir()
    store = AB.TxStore()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setattr(W, "tx", store.tx)
    monkeypatch.setattr(service, "manifest_for", lambda adapter_id, directory=None: service.registry(d)[adapter_id])
    _manifest(d, "fixture.healthy", "1.0.0", [_brief()], "brief")
    rid = service.start(None, adapter_id="fixture.healthy", input_payload={"q": "x"})["run_id"]
    store.save_state(None, store.load_run(None, rid)[0])
    (d / "fixture.broken.json").write_text('{"adapter_id": "fixture.broken", "steps": [')       # a half-written file ships
    service.reset_registry()
    with pytest.raises(ValueError):                                                              # the loop backs off (B-06: an iteration error)
        W.process_one("worker-1", 120)
    assert store.load_run(None, rid)[0].status == "running" and store.runs[rid]["meta"]["lease_owner"] is None   # the defect: ended `failed`
    (d / "fixture.broken.json").unlink()                                                          # the deploy is fixed
    service.reset_registry()
    assert W.process_one("worker-1", 120) == rid and store.load_run(None, rid)[0].status == "awaiting_agent"
    service.reset_registry()

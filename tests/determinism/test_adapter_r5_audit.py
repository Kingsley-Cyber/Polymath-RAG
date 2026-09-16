"""R5-AUDIT-FIX adversarial tests (independent of the builder's happy-path loop).

These encode the invariants the independent audit required, at production-realistic scale and against the real composition-root
functions — the context budget must not evict a required evidence class, Trail response identity is validated before any
normalization/persistence, and payload construction depends on authoritative acceptance order, not dict/JSONB iteration order.
No database is required: the pure selection/validation functions are exercised directly with constructed state.
"""
from __future__ import annotations

import json
import pathlib
import sys

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "workers", "orchestrator", "control"):
    sys.path.insert(0, str(ROOT / sub))

from polymath_shared.adapter import service  # noqa: E402
from polymath_shared.adapter import trail_client as TC  # noqa: E402
from polymath_shared.adapter.transitions import RunState  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402

SNAP = {"snapshot_id": "trs_audit_1", "content_hash": "sha256:" + "d" * 64}


def _state(run_id="adr_" + "a" * 32, outputs=None, order=None):
    outs = outputs or {}
    return RunState(run_id=run_id, adapter_id="trail.product_discovery", outputs=outs,
                    output_order=tuple(order if order is not None else outs.keys()))


# ─────────────────────────────────────────── FIX 1: mixed deterministic context budget
def _run_context(monkeypatch, admitted, knowledge_refs):
    monkeypatch.setattr(service.store, "admitted_evidence_refs", lambda conn, rid: list(admitted))
    st = _state(outputs={"S": {"_evidence_refs": list(knowledge_refs)}}, order=("S",))
    return service._context_refs(None, st)


def _fev(n):
    return [{"kind": "field_evidence", "id": f"fev_{i:04d}", "note": "friction/supporting"} for i in range(n)]


def _knowledge(chunks=0, graph_facts=0, other=0):
    refs = [{"kind": "chunk", "id": f"chunk_{i:04d}"} for i in range(chunks)]
    refs += [{"kind": "graph_fact", "id": f"fact_{i:04d}"} for i in range(graph_facts)]
    refs += [{"kind": "document", "id": f"doc_{i:04d}"} for i in range(other)]
    return refs


def test_display_context_is_capped_and_balanced(monkeypatch):
    # _context_refs is the CITATION display list, capped at MAX_CONTEXT_REFS with per-class floors so no class starves another.
    out = _run_context(monkeypatch, _fev(200), _knowledge(chunks=150, graph_facts=60))
    kinds = [r["kind"] for r in out]
    assert len(out) == service.MAX_CONTEXT_REFS, "display context never exceeds the cap (so it can never breach the adapter_step maxItems)"
    assert kinds.count("field_evidence") >= 80 and kinds.count("chunk") >= 50 and kinds.count("graph_fact") >= 40


def test_display_context_stays_capped_under_huge_admitted(monkeypatch):
    # even 600 admitted observations produce a display list <= the cap, so issue-time adapter_step validation (evidence_refs maxItems:500) never breaks.
    out = _run_context(monkeypatch, _fev(600), _knowledge(chunks=150))
    assert len(out) == service.MAX_CONTEXT_REFS <= 500
    assert [r["kind"] for r in out].count("field_evidence") >= 80


def test_display_context_spillover_and_determinism(monkeypatch):
    a = _run_context(monkeypatch, _fev(5), _knowledge(chunks=400))       # scarce admitted -> its unused slots spill to knowledge
    b = _run_context(monkeypatch, _fev(5), _knowledge(chunks=400))
    assert a == b, "display selection must be deterministic"
    ka = [r["kind"] for r in a]
    assert ka.count("field_evidence") == 5 and ka.count("chunk") == service.MAX_CONTEXT_REFS - 5
    small = _run_context(monkeypatch, _fev(3), _knowledge(chunks=4, graph_facts=2, other=1))
    assert len(small) == 10 and {r["kind"] for r in small} == {"field_evidence", "chunk", "graph_fact", "document"}


def test_gate_facing_admitted_set_is_complete_and_schema_legal():
    # the COMPLETE admitted set travels as context.admitted_evidence_ids (gate-facing), decoupled from and unbounded by the display
    # evidence_refs. The adapter_step contract must accept a large admitted set alongside a capped display, and reject an over-cap display.
    from polymath_shared.adapter.contracts import validate
    step = {"run_id": "adr_" + "a" * 32, "step_id": "R_qualify", "step_type": "EXTERNAL_OPERATION", "sequence": 9, "issued_at": "2026-09-15T00:00:00Z",
            "objective": "qualify the opportunity", "output_schema": {"type": "object"},
            "context": {"evidence_refs": [{"kind": "field_evidence", "id": f"fev_{i:04d}"} for i in range(service.MAX_CONTEXT_REFS)],
                        "inputs": {}, "prior_step_ids": [], "admitted_evidence_ids": [f"fev_{i:04d}" for i in range(1000)]}}
    assert validate("adapter_step", step) == [], "a capped display + a complete 1000-id admitted set must be a valid adapter_step"
    over = {**step, "context": {**step["context"], "evidence_refs": [{"kind": "field_evidence", "id": f"x_{i:04d}"} for i in range(501)]}}
    assert validate("adapter_step", over) != [], "an over-cap display (>500) must be rejected — the cap is what keeps _context_refs legal"


def _score_payload(outputs, order):
    st = _state(outputs=outputs, order=order)
    return W._payload_for("opportunity.score", {"context": {"hypotheses": [], "admitted_evidence_ids": []}, "config": {"stage": "score"}}, st, {"stage": "score"})


def test_score_qualifications_follow_acceptance_order_not_dict_order():
    q_market = {"qualification": {"record_id": "qm", "stage": "market_delta", "state": "PROMOTED"}}
    q_supply = {"qualification": {"record_id": "qs", "stage": "supply", "state": "PROMOTED"}}
    order = ("R_qualify", "U_qualify")
    forward = _score_payload({"R_qualify": q_market, "U_qualify": q_supply}, order)
    # same outputs, REVERSED dict insertion order, SAME authoritative acceptance order → identical payload
    reversed_insertion = _score_payload({"U_qualify": q_supply, "R_qualify": q_market}, order)
    assert forward == reversed_insertion, "qualification order must not depend on dict/JSONB iteration order"
    assert [q["stage"] for q in forward["qualifications"]] == ["market_delta", "supply"]


# ─────────────────────────────────────────── FIX 2 + 4: Trail response identity + wire-faithful verdict translation
def _client(handler):
    return TC.TrailMCPClient("http://trail.audit/mcp", "audit-token", transport=httpx.MockTransport(handler))


def _envelope(body, name, result, **extra):
    value = {"operation_id": f"op-{name}", "operation_kind": name, "status_revision": 1, "registry_snapshot": SNAP, **extra, "result": result}
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": json.dumps(value)}], "structuredContent": value, "isError": False}})


def _exec(monkeypatch, kind, handler, *, context=None):
    monkeypatch.setattr(W, "_TRAIL", _client(handler))
    spec = {"external": {"system": "trailsignal", "operation_kind": kind, "availability": "working"}, "config": {"stage": "market_delta"}, "harness": {}}
    m = type("M", (), {"step": staticmethod(lambda sid: spec)})()
    ctx = {"hypotheses": [{"hypothesis_id": "hyp_x", "revision": 0, "status": "proposed", "statement": "s"}], "registry_snapshot": SNAP}
    ctx.update(context or {})
    step = {"step_id": "D_x", "sequence": 5, "context": ctx}
    return W.exec_external(step, _state(), m)


def test_wrong_operation_kind_is_refused_before_persistence(monkeypatch):
    def h(req):
        body = json.loads(req.content)
        return _envelope(body, "opportunity.qualify", {"qualification": {"record_id": "q", "stage": "market_delta", "state": "PROMOTED"}}, operation_kind="opportunity.score")
    out = _exec(monkeypatch, "opportunity.qualify", h)
    assert out.get("gap", {}).get("code") == "TRAIL_RESPONSE_MISMATCH" and "output" not in out and "external" not in out


def test_wrong_snapshot_is_refused_before_persistence(monkeypatch):
    def h(req):
        body = json.loads(req.content)
        bad = {**SNAP, "snapshot_id": "trs_OTHER"}
        return _envelope(body, "opportunity.qualify", {"qualification": {"record_id": "q", "stage": "market_delta", "state": "PROMOTED"}}, registry_snapshot=bad)
    out = _exec(monkeypatch, "opportunity.qualify", h)
    assert out.get("gap", {}).get("code") == "TRAIL_RESPONSE_MISMATCH" and "output" not in out


def test_admission_from_another_run_is_refused_before_persistence(monkeypatch):
    def h(req):
        body = json.loads(req.content)
        adm = {"admission_id": "hadm_1", "run_id": "run:adr-DIFFERENT", "action_id": "hact_1", "registry_snapshot": SNAP,
               "trail_operation_id": "op-evidence.admit", "admitted": [], "rejected": [], "evaluated_at": "2026-09-15T00:00:00Z"}
        return _envelope(body, "evidence.admit", {"evidence_admission": adm})
    receipt_out = {"_harness_action_id": "hact_1", "run_id": "run:adr-" + "a" * 32, "harness_id": "h", "started_at": "2026-09-15T00:00:00Z",
                   "completed_at": "2026-09-15T00:10:00Z", "sources": [], "observations": [], "tool_trace": [], "limitations": []}
    monkeypatch.setattr(W, "_TRAIL", _client(h))
    spec = {"external": {"system": "trailsignal", "operation_kind": "evidence.admit", "availability": "working"}, "config": {"stage": "field_evidence"}, "harness": {}}
    m = type("M", (), {"step": staticmethod(lambda sid: spec)})()
    ctx = {"hypotheses": [{"hypothesis_id": "hyp_x", "revision": 0, "status": "proposed", "statement": "s"}], "registry_snapshot": SNAP}
    st = _state(outputs={"E_research": receipt_out}, order=("E_research",))
    out = W.exec_external({"step_id": "J_admit", "sequence": 6, "context": ctx}, st, m)
    assert out.get("gap", {}).get("code") == "TRAIL_RESPONSE_MISMATCH" and "output" not in out and "external" not in out


def test_verdict_translation_maps_and_drops(monkeypatch):
    def h(req):
        body = json.loads(req.content)
        verdicts = [{"hypothesis_id": "hyp_x", "kind": "CHALLENGE", "polymath_transition": "CONTRADICT", "cause_refs": [], "reason_code": "R"},
                    {"hypothesis_id": "hyp_x", "kind": "REQUIRE_EVIDENCE", "polymath_transition": None, "cause_refs": [], "reason_code": "R"}]
        return _envelope(body, "hypotheses.judge", {"verdicts": verdicts, "open_gaps": []})
    out = _exec(monkeypatch, "hypotheses.judge", h)
    hv = out["output"]["hypothesis_verdicts"]
    assert [v["kind"] for v in hv] == ["CONTRADICT"], hv                  # CHALLENGE→CONTRADICT translated; REQUIRE_EVIDENCE (null) dropped
    assert all("polymath_transition" not in v for v in hv)


def test_bare_kind_verdict_is_still_accepted_for_compatibility(monkeypatch):
    def h(req):
        body = json.loads(req.content)
        return _envelope(body, "hypotheses.judge", {"verdicts": [{"hypothesis_id": "hyp_x", "kind": "WEAKEN", "cause_refs": [], "reason_code": "R"}], "open_gaps": []})
    out = _exec(monkeypatch, "hypotheses.judge", h)
    assert [v["kind"] for v in out["output"]["hypothesis_verdicts"]] == ["WEAKEN"]


# ─────────────────────────────────────────── BLOCKER regression: admitted ids reach the gate regardless of the display budget
def _admit_output(stage, ids):
    return {"evidence_admission": {"admission_id": f"hadm_{stage}", "admitted": [{"admitted_evidence_id": i} for i in ids]}}


def _payload(kind, admitted_ids=()):
    ctx = {"hypotheses": [{"hypothesis_id": "hyp_x", "revision": 0, "status": "proposed", "statement": "s"}],
           "evidence_refs": [], "admitted_evidence_ids": list(admitted_ids)}
    return W._payload_for(kind, {"context": ctx, "config": {"stage": "market_delta"}}, _state(), {"stage": "market_delta"})


def test_qualify_receives_every_admitted_id_from_the_context():
    # >80 (and >200) admitted ids all reach the gate via context.admitted_evidence_ids — never touched by the display budget.
    ids = [f"fev_{i:03d}" for i in range(130)]
    for kind in ("opportunity.qualify", "opportunity.score"):
        got = _payload(kind, admitted_ids=ids)
        assert got["admitted_evidence_ids"] == ids and len(got["admitted_evidence_ids"]) == 130, (kind, len(got["admitted_evidence_ids"]))


def test_admitted_ids_preserve_context_order():
    ids = ["x1", "x2", "x3", "x4"]
    assert _payload("opportunity.score", admitted_ids=ids)["admitted_evidence_ids"] == ids



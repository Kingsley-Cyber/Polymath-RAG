"""HARNESS-RESEARCH-MIGRATION-V1 R4 — `trail.product_discovery` 2.0.0 end to end on the real substrate against a STUB Trail daemon
that implements the seven bounded operations (httpx MockTransport, Trail's JSON-RPC envelope). Real Postgres, real worker executors
(exec_external → bounded ops, VALIDATE φ dedupe), real transitions and ledger; only Polymath knowledge steps are faked. Proves the
owner's loop: θ hypotheses → priors → φ filter → mechanisms → gaps → HARNESS_ACTION (paused, answered by TWO harness identities across
the run) → admission → re-reason → judge → bounded loop back through reasoning → physical jobs → territory → product reality → market
delta → supplier research → supply → score → final product with cross-system lineage; and that the ACTIVE config (Trail HR3 still
working after the R5 cutover) reaches Trail at the first operation."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import uuid

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for p in (ROOT / "shared", ROOT / "workers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
pytest.importorskip("psycopg")
if not os.environ.get("POLYMATH_PG_DSN"):
    pytest.skip("POLYMATH_PG_DSN not set", allow_module_level=True)
from polymath_shared.adapter import service, store  # noqa: E402
from polymath_shared.adapter import trail_client as TC  # noqa: E402
from polymath_shared.db import tx  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402

SNAP = {"snapshot_id": "trs_stub_2026_09_13", "content_hash": "sha256:" + "c" * 64}
RECEIPT_TPL = json.loads((ROOT / "contracts/adapter/v1/harness_receipt.example.json").read_text())
FAKE_REFS = [{"kind": "chunk", "id": "chunk_k1", "doc_id": "doc_k", "corpus_id": "probe"}, {"kind": "graph_fact", "id": "fact_k2"}]


def _fake_knowledge(step, state, m):
    return {"output": {"rows": 2}, "evidence_refs": FAKE_REFS}


class StubTrail:
    """Deterministic in-memory implementation of the seven bounded operations (the wire HR3 must honour)."""
    def __init__(self):
        self.calls: list[str] = []; self.n = 0; self.judged = 0

    def handle(self, req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content); name = body["params"]["name"]; args = body["params"]["arguments"]
        self.calls.append(name)
        assert req.headers["authorization"].startswith("Bearer ") and "mcp-session-id" not in req.headers
        r = args.get("request") or {}; payload = r.get("payload") or {}; self.n += 1
        env = {"operation_id": f"op-{name.replace('.', '-')}-{self.n}", "operation_kind": name, "status_revision": 1, "registry_snapshot": SNAP}
        hyps = payload.get("hypotheses") or []
        ids = [h["hypothesis_id"] for h in hyps]
        def ok(result, **extra):
            value = {**env, **extra, "result": result}
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": json.dumps(value)}], "structuredContent": value, "isError": False}})
        if name == "registry.project":
            assert r["registry_snapshot_id"] is None
            return ok({"priors": [{"registry_record_id": "fr-03", "prior_role": "friction_primitive", "hypothesis_ids": ids},
                                  {"registry_record_id": "pt-02", "prior_role": "product_territory", "hypothesis_ids": ids[:1]}], "redundancy_groups": []}, registry_snapshot=SNAP)
        assert r["registry_snapshot_id"] == SNAP["snapshot_id"], name
        if name == "hypotheses.judge":
            if payload["stage"] == "filter":
                verdicts = ([{"hypothesis_id": ids[1], "kind": "WEAKEN", "polymath_transition": "WEAKEN", "cause_refs": [{"kind": "trail_prior", "id": "fr-03"}], "reason_code": "WEAK_PRIOR_SUPPORT"}] if len(ids) > 1 else []) + \
                           [{"hypothesis_id": ids[0], "kind": "REQUIRE_EVIDENCE", "polymath_transition": None, "cause_refs": [], "reason_code": "INSUFFICIENT_EVIDENCE"}]  # null transition: keep gathering, dropped by the worker
                return ok({"verdicts": verdicts, "open_gaps": []})
            self.judged += 1
            adm = payload.get("latest_admission_id")
            verdicts = [{"hypothesis_id": ids[0], "kind": "STRENGTHEN", "polymath_transition": "STRENGTHEN", "cause_refs": [{"kind": "evidence_admission", "id": adm}], "reason_code": "INDEPENDENT_SUPPORT"}] if adm else []
            return ok({"verdicts": verdicts, "open_gaps": [{"gap_id": "g-demand", "evidence_role": "demand"}] if self.judged == 1 else []})
        if name == "gaps.compile":
            gaps = [{"gap_id": f"gap_{i}", "hypothesis_id": g.get("hypothesis_id") or ids[0], "question": g["question"], "evidence_role": g.get("evidence_role", "friction")}
                    for i, g in enumerate(payload.get("knowledge_gaps") or [])][:20] or [{"gap_id": "gap_0", "hypothesis_id": ids[0], "question": "is the friction recurring?", "evidence_role": "friction"}]
            return ok({"research_directive": {"objective": "find first-person field evidence", "evidence_gaps": gaps, "geography": "US", "language": "en",
                                              "search_intents": [{"intent_id": "si_complaint", "intent": "find first-person friction complaints", "evidence_goal": "complaint", "evidence_roles": ["friction", "behavior"]},
                                                                 {"intent_id": "si_workaround", "intent": "find workaround discussions", "evidence_goal": "workaround", "evidence_roles": ["workaround"]}],
                                              "success_condition": "10 independent complaints", "falsification_condition": "no recurring complaints"}})
        if name == "evidence.admit":
            rec = payload["receipt"]; stage = payload["stage"]
            role = {"field_evidence": "friction", "product_reality": "competition", "supply": "supply"}[stage]
            adm_id = "hadm_" + hashlib.sha256(payload["action_id"].encode()).hexdigest()[:12]
            admitted = [{"admitted_evidence_id": "fev_" + hashlib.sha256((payload["action_id"] + o["observation_id"]).encode()).hexdigest()[:12], "observation_id": o["observation_id"],
                         "source_id": o["source_id"], "evidence_role": role, "source_class": "community_discussion" if stage == "field_evidence" else ("product_review" if stage == "product_reality" else "supplier_listing"),
                         "source_suitability": "suitable", "freshness": "fresh", "provenance": "recorded", "independence_group": o["source_id"], "duplicate_of": None,
                         "polarity": "supporting", "hypothesis_ids": ids[:1], "stage_relevance": stage, "limitations": [], "trail_admission_record_id": f"adm-{self.n}-{o['observation_id']}"} for o in rec["observations"]]
            return ok({"evidence_admission": {"admission_id": adm_id, "run_id": r["run_ref"], "action_id": payload["action_id"], "registry_snapshot": SNAP, "trail_operation_id": env["operation_id"],
                                              "admitted": admitted, "rejected": [], "evaluated_at": "2026-09-13T21:00:00Z"}, "verdicts": []})
        if name == "territory.project":
            return ok({"territories": [{"territory_id": "pt-02", "territory": "body_mounted_access", "hypothesis_ids": ids[:1]}],
                       "research_directive": {"objective": "map current competing products", "evidence_gaps": [], "geography": "US", "language": "en",
                                              "search_intents": [{"intent_id": "si_skus", "intent": "find current competing SKUs", "evidence_goal": "competition", "evidence_roles": ["competition", "price"]}],
                                              "success_condition": "3 comparable products with prices", "falsification_condition": "a dominant incumbent already solves it"}})
        if name == "opportunity.qualify":
            # HR4 (ADR-064) portfolio wire: one qualification record per live hypothesis, in the caller's hypothesis order
            if payload["stage"] == "market_delta":
                return ok({"qualifications": [{"record_id": f"qual-market-{i + 1}", "stage": "market_delta", "state": "PROVISIONAL" if i == 0 else "UNPROVEN", "hypothesis_ids": [hid]} for i, hid in enumerate(ids)], "open_gaps": [],
                           "research_directive": {"objective": "find supply feasibility", "evidence_gaps": [], "geography": None, "language": "en",
                                                  "search_intents": [{"intent_id": "si_supply", "intent": "find supplier MOQ and unit economics", "evidence_goal": "supply", "evidence_roles": ["supply", "price"]}],
                                                  "success_condition": "2 suppliers with price and MOQ", "falsification_condition": "no supplier under the target landed cost"}})
            return ok({"qualifications": [{"record_id": f"qual-supply-{i + 1}", "stage": "supply", "state": "PROMOTED" if i == 0 else "UNPROVEN", "hypothesis_ids": [hid]} for i, hid in enumerate(ids)]})
        if name == "opportunity.score":
            # the caller forwards EVERY qualification record of every stage in acceptance order (market_delta before supply) and never selects a winner
            assert [q["stage"] for q in payload["qualifications"]] == ["market_delta"] * len(ids) + ["supply"] * len(ids), payload["qualifications"]
            assert [q["hypothesis_ids"] for q in payload["qualifications"]] == [[h] for h in ids] * 2
            return ok({"trail_scores": [{"record_id": "score-1", "hypothesis_id": ids[0], "score": 0.61, "subscores": {"demand": 0.6, "pain": 0.7}, "confidence": 0.58, "provenance": {"scoring_version": "score-1.0.0", "registry_snapshot_id": SNAP["snapshot_id"]}}],
                       "score_refusals": [{"record_id": f"score-{i + 2}", "hypothesis_id": hid, "reason_code": "HARD_GATE_UNMET", "detail": "HARD_GATE_UNMET: no admitted evidence for this hypothesis", "authority_class": "SCORE_REFUSAL"} for i, hid in enumerate(ids[1:])]})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": f"unknown tool {name}"}], "isError": True}})


def _working_copy(tmp: pathlib.Path) -> pathlib.Path:
    m = json.loads((ROOT / "config/adapters/trail.product_discovery.json").read_text())
    for s in m["steps"]:
        if s["type"] == "EXTERNAL_OPERATION":
            s["external"] = {"system": "trailsignal", "operation_kind": s["external"]["operation_kind"], "availability": "working"}
    (tmp / "trail.product_discovery.json").write_text(json.dumps(m))
    return tmp


@pytest.fixture
def rig(tmp_path, monkeypatch):
    stub = StubTrail()
    monkeypatch.setattr(W, "_TRAIL", TC.TrailMCPClient("http://trail.stub/mcp", "stub-token", transport=httpx.MockTransport(stub.handle)))
    execs = {**W.EXECUTORS, "POLYMATH_RETRIEVE": _fake_knowledge, "POLYMATH_COMPILE_PLAN": _fake_knowledge, "POLYMATH_GRAPH_EXPAND": _fake_knowledge}
    service.reset_registry()
    yield stub, execs
    service.reset_registry()


def _theta(step):
    ctx = step["context"]; sid = step["step_id"]
    live = [h["hypothesis_id"] for h in ctx.get("hypotheses") or []]
    fev = [r["id"] for r in ctx["evidence_refs"] if r["kind"] == "field_evidence"]
    if sid == "C_hypotheses":
        return {"hypotheses": [{"statement": "runners lose access to small items mid-stride because pockets bounce", "mechanism": "pocket bounce", "population": "runners", "activity": "running", "task": "access a small item", "context": "mid-stride", "suspected_friction": "access latency",
                                "supporting_evidence_ids": ["chunk_k1", "fact_k2"], "knowledge_gaps": [{"question": "is the friction recurring?", "evidence_role": "friction"}], "trail_priors": []},
                               {"statement": "runners drop keys when opening zips with gloves", "supporting_evidence_ids": ["fact_k2"]}]}
    if sid == "G_mechanisms":
        return {"transitions": [{"hypothesis_id": live[0], "kind": "REVISE", "cause_refs": [{"kind": "chunk", "id": "chunk_k1"}], "changes": {"mechanism": "bounce plus glove dexterity"}, "reason_code": "MECHANISM_REFINED"}],
                "knowledge_gaps": [{"hypothesis_id": live[0], "question": "how often does it happen per run?", "evidence_role": "behavior"}]}
    if sid == "K_revise":
        return {"transitions": [{"hypothesis_id": live[0], "kind": "REVISE", "cause_refs": [{"kind": "field_evidence", "id": fev[0]}], "changes": {"context": "mid-stride, cold, gloved"}, "reason_code": "FIELD_EVIDENCE"}], "open_gaps": []}
    if sid == "N_jobs":
        return {"transitions": [], "physical_jobs": [{"hypothesis_id": live[0], "job": "quick access", "mechanism": "glove-operable clip"}]}
    if sid == "W_interpret":
        return {"product_opportunity": {"product_concept": {"title": "glove-operable stride pouch", "mechanism_explanation": "…", "population": "runners", "activity": "running", "context": "cold, gloved", "problem": "access latency"},
                                        "evidence_chain": [{"hypothesis_id": live[0]}], "field_evidence_ids": fev[:2], "contradictions": [], "competing_products": [], "product_delta": "one-hand access",
                                        "supply": {"supplier_url": "https://supplier.example/x", "unit_price": 4.2, "moq": 200}, "trail_score_refs": ["score-1"],
                                        "remaining_uncertainty": ["warm-season demand"], "cheapest_falsification_experiment": "concept interviews"}}
    raise AssertionError(sid)


def _run_loop(d, execs, harness_ids):
    with tx() as conn:
        rid = service.start(conn, adapter_id="trail.product_discovery", input_payload={"seed": "runners lose access to small items", "corpus_ids": ["probe"]},
                            request_options={"corpus_ids": ["probe"], "idempotency_key": uuid.uuid4().hex}, directory=d)["run_id"]
    harness_used = []
    for _ in range(120):
        with tx() as conn:
            st = service.advance(conn, rid, execs, max_steps=1, directory=d)
        if st.terminal:
            break
        if st.status == "awaiting_agent":
            with tx() as conn:
                step = service.next_step(conn, rid, directory=d)["step"]
                service.submit(conn, rid, {"step_id": step["step_id"], "payload": _theta(step), "submitted_by": {"agent_identity": "test-agent"}}, directory=d)
        elif st.status == "awaiting_harness":
            with tx() as conn:
                step = service.next_step(conn, rid, directory=d)["step"]
                hid = harness_ids[len(harness_used) % len(harness_ids)]; harness_used.append(hid)
                rec = json.loads(json.dumps(RECEIPT_TPL)); rec.update({"action_id": step["harness_action"]["action_id"], "run_id": rid, "harness_id": hid})
                for o in rec["observations"]:
                    o["hypothesis_ids"] = step["harness_action"]["hypothesis_ids"][:1]
                service.submit(conn, rid, {"step_id": step["step_id"], "payload": rec, "submitted_by": {"agent_identity": hid}, "kind": "receipt"}, directory=d)
    return rid, st, harness_used


def test_product_discovery_2_0_0_runs_the_owner_loop_end_to_end_with_two_harnesses(rig, tmp_path):
    stub, execs = rig
    d = _working_copy(tmp_path)
    rid, st, used = _run_loop(d, execs, ["hermes", "claude-code"])
    try:
        assert st.status == "completed", (st.status, st.gap, st.failure, st.current_step_id)
        with tx() as conn:
            res = service.result(conn, rid); hyps = store.current_hypotheses(conn, rid); trs = store.list_transitions(conn, rid); actions = store.list_harness_actions(conn, rid)
        # the harness executed research: 2 field passes (bounded gap loop) + product reality + supplier, alternating identities
        assert [a["status"] for a in actions] == ["admitted"] * 4 and used == ["hermes", "claude-code", "hermes", "claude-code"]
        assert sorted(res["lineage"]["harness_ids"]) == ["claude-code", "hermes"] and len(res["lineage"]["harness_action_ids"]) == 4
        # Trail: no acquisition, only the bounded operations; the score originates in Trail only
        assert not {"discover.submit", "scrape.submit", "extract.submit", "crawl.submit"} & set(stub.calls)
        assert stub.calls.count("evidence.admit") == 4 and stub.calls.count("opportunity.score") == 1 and stub.calls.count("hypotheses.judge") == 3
        assert res["lineage"]["trail_score_record_ids"] == ["score-1"] and res["output"]["product_opportunity"]["trail_score_refs"] == ["score-1"]
        # HR4 portfolio: per-hypothesis records reach the terminal output; the refusal's record id joins the external-operation lineage, never the score ids
        assert [s["record_id"] for s in res["output"]["trail_scores"]] == ["score-1"] and [r["reason_code"] for r in res["output"]["score_refusals"]] == ["HARD_GATE_UNMET"]
        assert len(res["output"]["qualifications"]) == 2 and {q["stage"] for q in res["output"]["qualifications"]} == {"supply"}
        assert any("score-2" in e["record_ids"] and "score-1" in e["record_ids"] for e in res["lineage"]["external_operations"] if e["operation_kind"] == "opportunity.score")
        assert res["lineage"]["registry_snapshot_ids"] == [SNAP["snapshot_id"]] and len(res["lineage"]["admitted_evidence_ids"]) == 8
        ext = res["lineage"]["external_operations"]
        assert len(ext) == 14 and {e["operation_kind"] for e in ext} == set(TC.BOUNDED_OPERATIONS) and all(e["operation_id"].startswith("op-") for e in ext)
        # hypotheses evolved with lineage: weakened by φ filter, revised by θ (twice), strengthened by φ after admission
        statuses = sorted(h["status"] for h in hyps.values())
        assert statuses == ["strengthened", "weakened"], statuses          # last φ verdict wins; θ revisions in between
        strong = next(h for h in hyps.values() if h["status"] == "strengthened")
        kinds = [t["kind"] for t in trs if t["hypothesis_id"] == strong["hypothesis_id"]]
        assert kinds.count("GENERATE") == 1 and kinds.count("STRENGTHEN") == 2 and kinds.count("REVISE") >= 3 and strong["revision"] >= 5
        assert all(t["cause_refs"] for t in trs) and strong["knowledge_support"] and strong["context"] == "mid-stride, cold, gloved"
        assert st.branch_loops == 1 and st.harness_action_count == 4 and res["lineage"]["polymath_evidence_ids"] == ["chunk_k1", "fact_k2"]
    finally:
        with tx() as conn:
            store.delete_run(conn, rid)


def test_active_config_reaches_trail_at_the_first_operation(rig):
    """R5 cutover: the admitted manifest no longer plans the Trail operations; the first Trail call is registry.project."""
    stub, execs = rig
    with tx() as conn:
        rid = service.start(conn, adapter_id="trail.product_discovery", input_payload={"seed": "runners lose access to small items", "corpus_ids": ["probe"]},
                            request_options={"corpus_ids": ["probe"], "idempotency_key": uuid.uuid4().hex})["run_id"]
    try:
        with tx() as conn:
            st = service.advance(conn, rid, execs)
        assert st.status == "awaiting_agent" and st.current_step_id == "C_hypotheses"
        with tx() as conn:
            step = service.next_step(conn, rid)["step"]
            service.submit(conn, rid, {"step_id": "C_hypotheses", "payload": _theta(step), "submitted_by": {"agent_identity": "t"}})
            st = service.advance(conn, rid, execs)
        assert st.status != "terminal_gap" and st.failure is None, (st.status, st.gap, st.failure)
        assert stub.calls[:1] == ["registry.project"], stub.calls        # the active config calls Trail: no planned gap left
        m = json.loads((ROOT / "config/adapters/trail.product_discovery.json").read_text())
        assert all(s["external"]["availability"] == "working" and "planned_node" not in s["external"] for s in m["steps"] if s["type"] == "EXTERNAL_OPERATION")
        with tx() as conn:
            assert len(store.current_hypotheses(conn, rid)) == 2   # θ state is durable across the Trail projection
    finally:
        with tx() as conn:
            store.delete_run(conn, rid)


def _scale_knowledge(step, state, m):
    # a production-scale knowledge return: 120 chunks + 60 graph facts + 10 documents (190 refs) on every retrieval step, so every
    # issued step's context is dominated by knowledge — the exact condition under which the pre-fix builder starved admitted evidence.
    refs = (FAKE_REFS                                                # the ids the scripted θ cites, kept first so they survive the chunk/graph-fact budget floors
            + [{"kind": "chunk", "id": f"c_{i:03d}", "doc_id": "d", "corpus_id": "probe"} for i in range(120)]
            + [{"kind": "graph_fact", "id": f"g_{i:03d}"} for i in range(60)]
            + [{"kind": "document", "id": f"doc_{i:03d}"} for i in range(10)])
    return {"output": {"rows": len(refs)}, "evidence_refs": refs}


def test_full_loop_survives_a_large_knowledge_corpus(rig, tmp_path):
    stub, _ = rig
    execs = {**W.EXECUTORS, "POLYMATH_RETRIEVE": _scale_knowledge, "POLYMATH_COMPILE_PLAN": _scale_knowledge, "POLYMATH_GRAPH_EXPAND": _scale_knowledge}
    d = _working_copy(tmp_path)
    rid, st, used = _run_loop(d, execs, ["hermes", "claude-code"])
    try:
        # the whole pipeline (admit → judge → territory → qualify → score) completes with 190 knowledge refs per step; the pre-fix
        # context builder truncated admitted field evidence out and Trail refused the score with NO_ADMITTED_EVIDENCE / HARD_GATE_UNMET.
        assert st.status == "completed", (st.status, st.gap, st.failure, st.current_step_id)
        with tx() as conn:
            res = service.result(conn, rid)
        assert res["lineage"]["trail_score_record_ids"] == ["score-1"]
        assert len(res["lineage"]["admitted_evidence_ids"]) >= 4, "admitted field evidence must survive a large-knowledge context and reach qualify/score"
    finally:
        with tx() as conn:
            store.delete_run(conn, rid)

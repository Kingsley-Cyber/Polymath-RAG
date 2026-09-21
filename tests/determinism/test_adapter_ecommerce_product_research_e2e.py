"""Consolidation migration — acceptance-ladder rung E in test form: ONE complete `ecommerce.product_research` run through the EXISTING
runtime (`service.start / advance / next_step / submit / result`, the real `EXECUTORS` incl. the real out-of-process ecommerce domain
operations) with a scripted agent, a scripted harness and a stub TrailSignal answering the seven bounded operations through the
production `TrailMCPClient`. No database (in-memory store), no network, no live web.

What it proves: seed -> knowledge -> interpretation (lineage law) -> population -> hypotheses (ledger) -> bridge + portfolio law ->
Trail judgement -> research planned by the domain -> admission -> evidence cards -> lived situations (law) -> revision -> several product
concepts with variations (law) -> product reality -> supply planned per concept -> admission -> price / MOQ + lead join -> qualification
-> TrailSignal's score / refusal -> result. What it does NOT prove: anything about a live TrailSignal, a live host or real evidence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from polymath_shared.adapter import contracts as C  # noqa: E402
from polymath_shared.adapter import service  # noqa: E402
from polymath_shared.adapter import trail_client as TC  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402
from _adapter_memory_store import MemoryStore  # noqa: E402

ADAPTER_ID = "ecommerce.product_research"
SNAP = {"snapshot_id": "trs_stub_e2e", "content_hash": "sha256:" + "e" * 64}
SEED = "runners lose access to small items while moving"
RECEIPT_TPL = json.loads((ROOT / "contracts/adapter/v1/harness_receipt.example.json").read_text())
ROW = {"id": "chunk_k1", "kind": "chunk", "doc_id": "doc_k", "corpus_id": "probe", "source": "Example Source — chapter 3", "utility_role": "DIRECT", "ca4_grade": "DIRECT",
       "c4_valid": True, "origin": "USER", "text": "A load carried away from the body's centre of mass oscillates with every stride, so small items bounce and work loose."}


def _directive(intent_id, goal, roles, objective):
    return {"objective": objective, "evidence_gaps": [], "geography": "US", "language": "en", "budget": {"max_queries": 8},
            "search_intents": [{"intent_id": intent_id, "intent": f"find {goal} evidence", "evidence_goal": goal, "evidence_roles": roles}],
            "success_condition": "independent sources answer the gaps", "falsification_condition": "independent sources contradict the hypotheses"}


class StubTrail:
    """The seven bounded operations, deterministic, in the wire shape the production client expects."""
    def __init__(self):
        self.calls: list[str] = []

    def handle(self, req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content); name = body["params"]["name"]; r = body["params"]["arguments"].get("request") or {}; payload = r.get("payload") or {}
        self.calls.append(name if name not in ("hypotheses.judge", "opportunity.qualify", "evidence.admit") and payload.get("stage") != "supply" else f"{name}:{payload['stage']}")
        ids = [h["hypothesis_id"] for h in payload.get("hypotheses") or []]
        env = {"operation_id": f"op-{len(self.calls)}", "operation_kind": name, "status_revision": 1, "registry_snapshot": SNAP}
        if name == "registry.project":
            result = {"priors": [{"registry_record_id": "fr-03", "prior_role": "friction_primitive", "hypothesis_ids": ids}], "redundancy_groups": []}
        elif name == "hypotheses.judge" and payload["stage"] == "filter":
            result = {"verdicts": [{"hypothesis_id": ids[1], "kind": "WEAKEN", "polymath_transition": "WEAKEN", "cause_refs": [{"kind": "trail_prior", "id": "fr-03"}], "reason_code": "WEAK_PRIOR_SUPPORT"}], "open_gaps": []}
        elif name == "hypotheses.judge":
            adm = payload.get("latest_admission_id")
            result = {"verdicts": [{"hypothesis_id": ids[0], "kind": "STRENGTHEN", "polymath_transition": "STRENGTHEN", "cause_refs": [{"kind": "evidence_admission", "id": adm}],
                                    "reason_code": "INDEPENDENT_SUPPORT"}], "open_gaps": []}
        elif name == "gaps.compile" and payload["stage"] == "supply":                    # TrailSignal compiles the supply directive here, from the qualification's open gaps
            result = {"research_directive": _directive("si_supply", "supply", ["supply", "price"], "find supply feasibility")}
        elif name == "gaps.compile":
            d = _directive("q-complaint", "complaint", ["friction", "behavior", "workaround"], "find first-person field evidence")
            d["evidence_gaps"] = [{"gap_id": "gap_0", "hypothesis_id": ids[0], "question": "do runners complain that keys bounce out of pockets mid stride", "evidence_role": "friction"}]
            result = {"research_directive": d}
        elif name == "evidence.admit":
            rec, stage = payload["receipt"], payload["stage"]
            role = {"field_evidence": "friction", "product_reality": "competition", "supply": "supply"}[stage]
            adm_id = "hadm_" + hashlib.sha256(payload["action_id"].encode()).hexdigest()[:12]
            admitted = [{"admitted_evidence_id": "fev_" + hashlib.sha256((payload["action_id"] + o["observation_id"]).encode()).hexdigest()[:12], "observation_id": o["observation_id"], "source_id": o["source_id"],
                         "evidence_role": role, "source_class": "community_discussion" if stage == "field_evidence" else ("product_review" if stage == "product_reality" else "supplier_listing"),
                         "source_suitability": "suitable", "freshness": "fresh", "provenance": "recorded", "independence_group": o["source_id"], "duplicate_of": None, "polarity": "supporting",
                         "hypothesis_ids": ids[:1], "stage_relevance": stage, "limitations": [], "trail_admission_record_id": f"adm-{len(self.calls)}-{o['observation_id']}"} for o in rec["observations"]]
            result = {"evidence_admission": {"admission_id": adm_id, "run_id": r["run_ref"], "action_id": payload["action_id"], "registry_snapshot": SNAP, "trail_operation_id": env["operation_id"],
                                             "admitted": admitted, "rejected": [], "evaluated_at": "2026-09-20T21:00:00Z"}, "verdicts": []}
        elif name == "territory.project":
            result = {"territories": [{"territory_id": "pt-02", "territory": "body_mounted_access", "hypothesis_ids": ids[:1]}],
                      "research_directive": _directive("si_skus", "competition", ["competition", "price"], "map current competing products")}
        elif name == "opportunity.qualify" and payload["stage"] == "market_delta":
            result = {"qualifications": [{"record_id": f"qual-market-{i + 1}", "stage": "market_delta", "state": "PROVISIONAL" if i == 0 else "UNPROVEN", "hypothesis_ids": [h]} for i, h in enumerate(ids)],
                      "open_gaps": [{"gap_id": "g-supply", "hypothesis_id": ids[0], "question": "is there a supplier under the target landed cost?", "evidence_role": "supply"}]}
        elif name == "opportunity.qualify":
            result = {"qualifications": [{"record_id": f"qual-supply-{i + 1}", "stage": "supply", "state": "PROMOTED" if i == 0 else "UNPROVEN", "hypothesis_ids": [h]} for i, h in enumerate(ids)]}
        elif name == "opportunity.score":
            result = {"trail_scores": [{"record_id": "score-1", "hypothesis_id": ids[0], "score": 0.61, "subscores": {"demand": 0.6, "pain": 0.7}, "confidence": 0.58,
                                        "provenance": {"scoring_version": "score-1.0.0", "registry_snapshot_id": SNAP["snapshot_id"]}, "authority_class": "TRAIL_SCORE"}],
                      "score_refusals": [{"record_id": f"score-{i + 2}", "hypothesis_id": h, "reason_code": "HARD_GATE_UNMET", "detail": "HARD_GATE_UNMET: no admitted evidence for this hypothesis",
                                          "authority_class": "SCORE_REFUSAL"} for i, h in enumerate(ids[1:])]}
        else:
            raise AssertionError(name)
        value = {**env, "result": result}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": json.dumps(value)}], "structuredContent": value, "isError": False}})


NEEDS: dict[str, str] = {}


def _knowledge(step, state, m):
    """A knowledge step's output in the shape the real evidence boundary stores it (surface, need, contract, per-call grades)."""
    need = NEEDS[step["step_id"]] = W._query_text(step, state, m)
    call = {"need_index": 0, "corpus_id": "probe", "contract": {"schema_version": "evidence-packet-v1", "synthesis_performed": False, "valid": True}, "retrieval_mode": "WILDCARD",
            "n_evidence": 1, "grades": {"DIRECT": 1}, "compiled_queries": 3, "corpus_explorer_requested": True, "corpus_explorer_used": True}
    return {"output": {"surface": "evidence_boundary", "mode": "WILDCARD", "corpus_explorer": True, "needs": [need], "corpus_ids": ["probe"], "rows": [dict(ROW)], "calls": [call],
                       "retrieval_completed": True, "evidence_contract": "evidence-packet-v1", "queries": []},
            "evidence_refs": [{"kind": "chunk", "id": "chunk_k1", "doc_id": "doc_k", "corpus_id": "probe"}]}


def _bridge(hid, mech):
    return {"hypothesis_id": hid, "source": "load oscillation", "path": ["items carried off the centre of mass oscillate", "pockets amplify the bounce", f"a {mech} keeps the item still"],
            "target_mechanism": mech, "evidence_boundary": {"first_inference_at": "pockets amplify the bounce"}, "hop_refs": {"0": ["chunk_k1"]}, "gaps": ["do runners report items bouncing out?"],
            "alternatives": ["the items are simply too many"], "falsifiers": ["runners report pockets hold items fine"], "status": "WORKING_HYPOTHESIS", "grounding": "CORPUS_ONLY"}


def _concept(i, form, fev):
    return {"id": f"pc_{i}", "mechanism_id": "m_clip", "name": f"stride {form}", "form_factor": form, "target_moment": "DURING", "buyer": "trail runners", "differentiator": "generic pockets bounce",
            "variations": [{"name": "standard", "twist": "single item"}, {"name": "reflective", "twist": "night running"}], "evidence_refs": [fev]}


class Agent:
    """θ, scripted. It answers from what the runtime SHOWS it: the step context and the `materials` sibling."""
    def __init__(self):
        self.seen: dict[str, list[dict]] = {}

    def answer(self, nxt: dict) -> dict:
        step, mats = nxt["step"], (nxt.get("materials") or {}).get("values") or {}
        sid, ctx = step["step_id"], step["context"]
        self.keys = getattr(self, "keys", {})
        self.keys[sid] = set(nxt)
        n = len(self.seen.setdefault(sid, [])); self.seen[sid].append(mats)
        live = [h["hypothesis_id"] for h in ctx.get("hypotheses") or []]
        fev = [r["id"] for r in ctx["evidence_refs"] if r["kind"] == "field_evidence"]
        if sid == "C_primitives":
            prim = {"generative_signal": True, "frictions": ["access_interruption"], "shared_predicates": ["carry"], "physical_jobs": ["carry keys while running"],
                    "evidence_refs": {"frictions": ["chunk_k1"]}, "population_leads": [{"name": "trail runners", "frictions": ["keys bounce in pocket"], "activities": ["trail running"]}],
                    "latent_structures": [{"id": "ls1", "kind": "FRICTION", "text": "small items bounce and work loose during repetitive motion", "evidence_refs": ["chunk_k1"],
                                           "authority": "LATENT_HYPOTHESIS", "possible_populations": ["dog walkers"]}]}
            return {"primitives": {**prim, "row_relevance": {} if n == 0 else {"chunk_k1": "SEMANTIC_MATCH"}}}              # first draft cites an UNCLASSIFIED row
        if sid == "C_hypotheses":
            return {"hypotheses": [{"statement": s, "suspected_friction": "access_interruption", "population": "runners", "activity": "running", "supporting_evidence_ids": ["chunk_k1"]}
                                   for s in ("runners lose small items mid stride because pockets bounce", "runners drop keys opening zips with gloves", "runners leave items behind because carrying is awkward")]}
        if sid == "C_bridge":
            mechs = ["magnetic clip"] * 3 if n == 0 else ["magnetic clip", "oversized zip pull", "body-hugging pouch"]                # first draft: one mechanism three times
            return {"bridges": [_bridge(h, m) for h, m in zip(live, mechs)]}
        if sid == "G_mechanisms":
            return {"transitions": [{"hypothesis_id": live[0], "kind": "REVISE", "cause_refs": [{"kind": "chunk", "id": "chunk_k1"}], "changes": {"mechanism": "pocket bounce"}, "reason_code": "MECHANISM_REFINED"}],
                    "knowledge_gaps": [{"hypothesis_id": live[0], "question": "how often does it happen per run?", "evidence_role": "behavior"}]}
        if sid == "K_situations":
            cluster = mats["lived_clusters"][0]
            return {"lived_situations": [{"id": "ls_run_1", "cluster_id": cluster["id"], "authority": "FIELD_ANCHORED" if cluster["authority"] == "ANCHOR" else "RECONSTRUCTED", "activity": "running",
                                          "moment": "DURING", "participants": "trail runners", "unknowns": ["how often per run"],
                                          "frictions": [{"text": "keys bounce out of the pocket", "authority": "FIELD_OBSERVATION", "refs": cluster["record_ids"][:2]}]}]}
        if sid == "K_revise":
            return {"transitions": [{"hypothesis_id": live[0], "kind": "REVISE", "cause_refs": [{"kind": "field_evidence", "id": fev[0]}], "changes": {"context": "mid-stride, trail"}, "reason_code": "FIELD_EVIDENCE"}], "open_gaps": []}
        if sid == "N_jobs":
            return {"transitions": [], "physical_jobs": [{"hypothesis_id": live[0], "job": "quick access", "mechanism": "glove-operable clip"}]}
        if sid == "N_concepts":
            mechanisms = [{"id": "m_clip", "name": "glove-operable magnetic clip", "hypothesis_id": live[0], "evidence_refs": fev[:2], "product_terms": ["clip", "holder", "pouch"]}]
            forms = ["magnetic belt clip"] if n == 0 else ["magnetic belt clip", "wrist pouch", "shoe-lace key holder"]             # first draft: one idea
            return {"mechanisms": mechanisms, "product_concepts": [_concept(i, f, fev[0]) for i, f in enumerate(forms, 1)]}
        if sid == "W_interpret":
            return {"product_opportunity": {"product_concept": {"title": "stride-stable key carry", "mechanism_explanation": "holds a small item against the body", "population": "runners", "activity": "running",
                                                                "context": "mid stride", "problem": "items bounce loose"},
                                            "evidence_chain": [{"hypothesis_id": live[0]}], "field_evidence_ids": fev[:2], "contradictions": [], "competing_products": [], "product_delta": "one-hand access",
                                            "supply": ({"supplier_url": mats["leads"][0]["url"], "unit_price": mats["leads"][0]["price_usd_low"], "moq": mats["leads"][0]["moq_units"]}
                                                       if mats.get("leads") else None),                  # no lead -> no supply claim; never invent one
                                            "trail_score_refs": [s["record_id"] for s in (mats.get("trail_scores") or []) + (mats.get("score_refusals") or [])], "remaining_uncertainty": ["warm-season demand"], "cheapest_falsification_experiment": "concept interviews"}}
        raise AssertionError(sid)


def _receipt(action, rid, rows):
    """`rows` = [(url, source_class, context, claim)] — one source and one observation per row, in the contract example's shape."""
    rec = copy.deepcopy(RECEIPT_TPL)
    src, obs = rec["sources"][0], rec["observations"][0]
    rec.update({"action_id": action["action_id"], "run_id": rid, "harness_id": "test-harness",
                "sources": [{**src, "source_id": f"src_{i}", "url": url, "source_class": cls} for i, (url, cls, _, _) in enumerate(rows)],
                "observations": [{**obs, "observation_id": f"obs_{i}", "source_id": f"src_{i}", "claim": claim, "paraphrase_or_excerpt": claim, "metric_if_present": None, "context": ctx,
                                  "hypothesis_ids": action["hypothesis_ids"][:1]} for i, (_, _, ctx, claim) in enumerate(rows)]})
    rec["tool_trace"] = [dict(rec["tool_trace"][0], search_intent_id=action["search_intents"][0]["intent_id"])] if rec.get("tool_trace") else []
    return rec


def _harness(step, rid):
    action, kind = step["harness_action"], step["harness_action"]["action_kind"]
    if kind == "AGENT_RESEARCH":
        ctx = "community: r/running · activity: running · moment: during"
        rows = [(f"https://forum{i}.example/thread/{i}", "community_discussion", ctx, f"my keys bounced out of my pocket again on the trail ({i})") for i in range(5)]
    elif kind == "PRODUCT_REALITY_CHECK":
        rows = [("https://shop.example/p/1", "product_review", "product: running belt", "the belt rides up and the keys still jingle")]
    else:
        rows = [("https://www.supplier-a.example/item/a1", "supplier_listing", "listing: magnetic belt clip key holder · supplier: Example Hardware Co · price as listed: US$1.20-1.80 / piece · MOQ as listed: 500 pieces · concept: pc_1", "listing"),
                ("https://www.supplier-b.example/item/b2", "supplier_listing", "listing: running wrist pouch wallet · supplier: unresolved · price as listed: $4.35 · MOQ as listed: 50 pcs · concept: pc_2", "listing")]
    return _receipt(action, rid, rows)


@pytest.fixture
def runtime(monkeypatch):
    store, trail = MemoryStore(), StubTrail()
    monkeypatch.setattr(service, "store", store)
    monkeypatch.setattr(W, "_TRAIL", TC.TrailMCPClient("http://trail.stub/mcp", "stub-token", transport=httpx.MockTransport(trail.handle)))
    service.reset_registry()
    NEEDS.clear()
    yield store, trail
    service.reset_registry()


def test_the_code_under_test_is_this_checkout():
    for mod in (C, service, TC, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


def _run(agent):
    execs = {**W.EXECUTORS, "POLYMATH_RETRIEVE": _knowledge, "POLYMATH_COMPILE_PLAN": _knowledge, "POLYMATH_GRAPH_EXPAND": _knowledge}
    rid = service.start(None, adapter_id=ADAPTER_ID, input_payload={"seed": SEED, "corpus_ids": ["probe"]}, request_options={"corpus_ids": ["probe"]})["run_id"]
    actions = {}
    for _ in range(200):
        st = service.advance(None, rid, execs, max_steps=1)
        if st.terminal:
            break
        if st.status in ("awaiting_agent", "awaiting_harness"):
            nxt = service.next_step(None, rid)
            step = nxt["step"]
            if st.status == "awaiting_agent":
                service.submit(None, rid, {"step_id": step["step_id"], "payload": agent.answer(nxt), "submitted_by": {"agent_identity": "test-agent"}})
            else:
                assert C.validate("harness_action", step["harness_action"]) == []
                actions[step["step_id"]] = (step["harness_action"], (nxt.get("materials") or {}).get("values") or {})
                service.submit(None, rid, {"step_id": step["step_id"], "payload": _harness(step, rid), "submitted_by": {"agent_identity": "test-harness"}, "kind": "receipt"})
    return rid, st, actions


def test_one_complete_ecommerce_product_research_run(runtime):
    store, trail = runtime
    agent = Agent()
    rid, st, actions = _run(agent)
    assert st.status == "completed", (st.status, st.gap, st.failure)

    rows = store.list_steps(None, rid)
    order = [r["step_id"] for r in rows]
    domain = [r for r in rows if r["step_type"] == "DOMAIN_OPERATION"]
    assert all(r["status"] == "executed" for r in domain) and not [s for s in order if s.startswith("Z_refuse")]
    assert [r["step_id"] for r in domain] == ["B_intake", "B_lenses", "C_lineage", "C_lineage", "C_population", "C_bridge_law", "C_bridge_law", "H_plan", "J_cards", "K_situations_law", "K_questions",
                                              "N_concepts_law", "N_concepts_law", "S_plan", "T_leads"]
    assert st.branch_loops == 3                                                                            # three domain laws each sent one draft back through reasoning, then passed
    assert trail.calls == ["registry.project", "hypotheses.judge:filter", "gaps.compile", "evidence.admit:field_evidence", "hypotheses.judge:revision", "territory.project",
                           "evidence.admit:product_reality", "opportunity.qualify:market_delta", "gaps.compile:supply", "evidence.admit:supply", "opportunity.qualify:supply", "opportunity.score"]

    # `materials` is strictly opt-in: a step whose manifest declares no `config.show` answers with exactly the pre-existing keys
    assert agent.keys["G_mechanisms"] == {"kind", "step", "status", "evidence"} and agent.keys["C_primitives"] == {"kind", "step", "status", "evidence", "materials"}
    # the agent was SHOWN what it needed — the previous law's errors, the lived clusters, TrailSignal's own records (external-review finding M1-08)
    assert any("UNCLASSIFIED" in e for e in agent.seen["C_primitives"][1]["previous_lineage_errors"])
    assert any("duplicate mechanism families" in e for e in agent.seen["C_bridge"][1]["previous_portfolio_errors"])
    assert agent.seen["K_situations"][0]["lived_clusters"][0]["authority"] == "ANCHOR"                       # 5 admitted records, 5 sources, 5 of TrailSignal's independence groups
    assert any("3–6 distinct product concepts" in e for e in agent.seen["N_concepts"][1]["previous_concept_errors"])
    assert agent.seen["W_interpret"][0]["trail_scores"][0]["record_id"] == "score-1" and agent.seen["W_interpret"][0]["score_refusals"]

    # TrailSignal said WHAT, the domain said HOW — for field research and, per concept, for supply
    research, supply = actions["I_research"][0], actions["S_supply"][0]
    assert research["search_intents"][0]["intent_id"] == "q-complaint" and any(":" in i["intent_id"] and "bounce" in i["template"] for i in research["search_intents"][1:])
    assert supply["search_intents"][0]["intent_id"] == "si_supply" and {i["intent_id"].rsplit(":", 1)[-1] for i in supply["search_intents"][1:]} >= {"pc_1", "pc_2", "pc_3"}
    assert [j["concept_id"] for j in actions["S_supply"][1]["sourcing_plan"]][:2] == ["pc_1", "pc_1"]
    # the knowledge need after admission is the field-grounded question, never a hypothesis statement (defect D2)
    assert "access interruption" in NEEDS["K_retrieve"] and "runners lose small items mid stride" not in NEEDS["K_retrieve"]

    result = service.result(None, rid)
    assert result["status"] == "completed"
    out = result["output"]
    assert len(out["product_concepts"]) == 3 and all(len(c["variations"]) >= 2 for c in out["product_concepts"])          # several distinct concepts, each with variations
    assert [l["concept_id"] for l in out["leads"]] == ["pc_1", "pc_2"] and out["leads"][0]["price_usd_low"] == 1.2 and out["leads"][0]["moq_units"] == 500
    assert out["leads"][1]["supplier_name"] is None and all("evidence_score" not in l for l in out["leads"])              # no invented supplier name, no domain score
    assert {c["concept_id"]: c["status"] for c in out["sourcing_coverage"]} == {"pc_1": "sourced", "pc_2": "sourced", "pc_3": "unsourced"}
    assert out["trail_scores"][0]["score"] == 0.61 and len(out["score_refusals"]) == 2                                      # the only score, and the refusals, are TrailSignal's
    assert out["lived_situations"][0]["authority"] == "FIELD_ANCHORED" and out["lived_clusters"][0]["independent_voices"] == 5
    assert out["population_leads"] and out["lenses"] and out["product_opportunity"]["trail_score_refs"] == ["score-1", "score-2", "score-3"]   # the score AND the refusals, by record id


class OneIdeaAgent(Agent):
    """Never offers more than one product idea, however often the portfolio law sends it back."""
    def answer(self, nxt: dict) -> dict:
        out = super().answer(nxt)
        if nxt["step"]["step_id"] == "N_concepts":
            out["product_concepts"] = out["product_concepts"][:1]
        return out


def test_negative_control_an_unlawful_product_set_ends_in_a_typed_refusal_not_a_product(runtime):
    store, trail = runtime
    rid, st, _ = _run(OneIdeaAgent())
    assert st.status == "terminal_gap" and st.gap["code"] == "PRODUCT_PORTFOLIO_LAW_UNSATISFIED" and st.gap["step_id"] == "Z_refuse_concepts"
    assert "3–6 distinct product concepts required, got 1" in st.gap["message"]
    assert "opportunity.score" not in trail.calls and "evidence.admit:supply" not in trail.calls          # nothing was sourced or scored for a product set that never became lawful
    assert [r["step_id"] for r in store.list_steps(None, rid)][-1] == "Z_refuse_concepts"

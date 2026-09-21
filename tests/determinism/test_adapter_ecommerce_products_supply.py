"""Consolidation migration Phase 5c — products and supply behind the domain door: the product-ideation portfolio law (several DISTINCT
concepts, each with variations), one sourcing job per concept per channel, the engine's own price / MOQ parsers, per-concept coverage
and the mechanism × supplier lead join. No score and no verdict leave the domain: qualification and the only score are TrailSignal's.

One operation at a time through the REAL executor. No database, no network.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _sub in ("workers", "shared"):
    sys.path.insert(0, str(ROOT / _sub))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from polymath_shared.adapter import contracts as C  # noqa: E402
from polymath_shared.adapter import manifest as M  # noqa: E402
from polymath_shared.adapter.transitions import RunState  # noqa: E402
import workers.adapter_step_worker as W  # noqa: E402

H1, H2 = "hyp_" + "a" * 12, "hyp_" + "b" * 12
LIVE = [{"hypothesis_id": H1, "revision": 2, "status": "strengthened", "statement": "pockets bounce"},
        {"hypothesis_id": H2, "revision": 1, "status": "weakened", "statement": "gloves block zips"}]
MECHS = [{"id": "m_clip", "name": "glove-operable magnetic clip", "hypothesis_id": H1}, {"id": "m_zip", "name": "oversized zip pull", "hypothesis_id": H2}]
EVIDENCE = ["fev_0001", "fev_0002"]


def _concept(i, form, mech="m_clip", variations=("standard", "reflective"), refs=("fev_0001",)):
    return {"id": f"pc_{i}", "mechanism_id": mech, "name": f"stride {form}", "form_factor": form, "target_moment": "DURING",
            "variations": [{"name": v} for v in variations], "evidence_refs": list(refs)}


CONCEPTS = [_concept(1, "magnetic belt clip"), _concept(2, "wrist pouch"), _concept(3, "shoe-lace key holder")]


def _exec(operation: str, inputs: dict) -> dict:
    raw = {"adapter_id": "fixture.one_op", "adapter_version": "1.0.0", "workflow_version": "1.0.0", "retrieval_policy_version": "1.0.0", "input_schema_version": "1.0.0",
           "output_schema_version": "1.0.0", "description": "one domain operation", "input_schema": {"type": "object"}, "output_schema": {"type": "object"},
           "budgets": {"max_steps": 4, "max_agent_reason": 0, "max_branch_loops": 0}, "entry_step_id": "op", "terminal_step_id": "end",
           "steps": [{"step_id": "op", "type": "DOMAIN_OPERATION", "title": "op", "next": "end",
                      "config": {"domain": "ecommerce", "operation": operation, "inputs": {k: f"outputs.given.{k}" for k in inputs}}},
                     {"step_id": "end", "type": "COMPILE_RESULT", "title": "end", "next": None, "config": {"include": ["lineage"]}}]}
    assert C.validate("adapter_manifest", raw) == [] and M.graph_integrity_errors(raw) == []
    m = M.Manifest(adapter_id=raw["adapter_id"], adapter_version="1.0.0", workflow_version="1.0.0", retrieval_policy_version="1.0.0", input_schema_version="1.0.0",
                   output_schema_version="1.0.0", entry_step_id="op", terminal_step_id="end", budgets=raw["budgets"], steps={s["step_id"]: s for s in raw["steps"]}, raw=raw)
    state = RunState(run_id="adr_" + "4" * 32, adapter_id=raw["adapter_id"], status="running", input={}, outputs={"given": inputs})
    return W.exec_domain({"run_id": state.run_id, "step_id": "op", "sequence": 1, "step_type": "DOMAIN_OPERATION", "context": {}}, state, m)


def test_the_code_under_test_is_this_checkout():
    for mod in (C, M, W):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), f"{mod.__name__} resolved outside {ROOT}: {mod.__file__}"


# ─────────────────────────────────────────────────────────── products
def _validate(concepts, **kw):
    return _exec("products.validate_concepts", {"product_concepts": concepts, "mechanisms": MECHS, "live_hypotheses": LIVE, "field_evidence_ids": EVIDENCE, **kw})["output"]


def test_a_lawful_product_set_is_several_distinct_concepts_each_with_variations():
    ok = _validate(CONCEPTS)
    assert ok["valid"] is True and ok["errors"] == [] and ok["concepts_checked"] == 3 and ok["variations_checked"] == 6


def test_the_portfolio_law_refuses_one_idea_dressed_up_as_many():
    assert any("3–6 distinct product concepts required, got 1" in e for e in _validate(CONCEPTS[:1])["errors"])
    dup = _validate([CONCEPTS[0], _concept(2, "Magnetic Belt-Clip"), CONCEPTS[2]])
    assert any("duplicates pc_1" in e for e in dup["errors"])                                              # a variant is not a direction
    assert any("at least 2 variations required" in e for e in _validate([_concept(1, "magnetic belt clip", variations=("only",)), *CONCEPTS[1:]])["errors"])
    assert any("variations must be distinct" in e for e in _validate([_concept(1, "magnetic belt clip", variations=("Standard", "standard")), *CONCEPTS[1:]])["errors"])
    assert any("evidence_refs must name observation / field_record ids" in e for e in _validate([_concept(1, "magnetic belt clip", refs=("fev_9999",)), *CONCEPTS[1:]])["errors"])


def test_mechanism_support_is_derived_from_the_ledger_never_claimed():
    claimed = [dict(MECHS[0]), {**MECHS[1], "status": "SUPPORTED"}]                                        # the agent CLAIMS the weakened one is supported
    out = _exec("products.validate_concepts", {"product_concepts": [_concept(1, "magnetic belt clip", mech="m_zip"), *CONCEPTS[1:]], "mechanisms": claimed,
                                               "live_hypotheses": LIVE, "field_evidence_ids": EVIDENCE})["output"]
    assert out["valid"] is False and any("'m_zip' is not a SUPPORTED mechanism" in e for e in out["errors"])
    assert out["mechanism_notes"] == [f"m_zip: hypothesis {H2!r} is weakened in the ledger — not eligible"]
    assert _exec("products.validate_concepts", {"mechanisms": MECHS})["gap"]["code"] == "PRODUCT_CONCEPTS_MISSING"


# ─────────────────────────────────────────────────────────── supply planning
SUPPLY_DIRECTIVE = {"objective": "find supply feasibility", "evidence_gaps": [], "geography": None, "language": "en",
                    "search_intents": [{"intent_id": "si_supply", "intent": "find supplier MOQ and unit economics", "evidence_goal": "supply", "evidence_roles": ["supply", "price"]}],
                    "success_condition": "2 suppliers with price and MOQ", "falsification_condition": "no supplier under the target landed cost", "budget": {"max_queries": 5}}


def test_one_sourcing_job_per_concept_per_channel_and_the_directive_is_enriched_within_budget():
    out = _exec("supply.plan", {"product_concepts": CONCEPTS, "mechanisms": MECHS, "live_hypotheses": LIVE, "research_directive": SUPPLY_DIRECTIVE})["output"]
    plan = out["sourcing_plan"]
    assert len(plan) == 6 and {j["concept_id"] for j in plan} == {"pc_1", "pc_2", "pc_3"} and all(j["search_terms"] and j["min_candidates"] >= 1 for j in plan)
    assert all("standard" in j["search_terms"] for j in plan)                                              # variations are search terms too
    d = out["research_directive"]
    assert out["governance_unchanged"] is True and d["search_intents"][0] == SUPPLY_DIRECTIVE["search_intents"][0]
    added = d["search_intents"][1:]
    assert len(d["search_intents"]) == 5 and out["planned"]["dropped_over_budget"] == 2 and out["planned"]["jobs"] == 6
    assert {i["intent_id"].rsplit(":", 1)[-1] for i in added[:3]} == {"pc_1", "pc_2", "pc_3"}                # every concept gets a job before any gets its second
    assert all(set(i["evidence_roles"]) <= {"supply", "price"} and "<term>" not in i["template"] and "concept:" in i["intent"] for i in added)
    assert "research_directive" not in _exec("supply.plan", {"product_concepts": CONCEPTS, "mechanisms": MECHS, "live_hypotheses": LIVE})["output"]   # a plan alone is fine


# ─────────────────────────────────────────────────────────── supply normalization + the lead join
def _supply_world(rows):
    sources = [{"source_id": f"s{i}", "url": url, "source_class": "supplier_listing", "retrieved_at": "2026-09-20T10:00:00Z", "published_at_if_known": None} for i, (url, _) in enumerate(rows)]
    obs = [{"observation_id": f"o{i}", "source_id": f"s{i}", "claim": "listing", "paraphrase_or_excerpt": "listing", "metric_if_present": None, "context": ctx, "evidence_role_claimed": "supply",
            "hypothesis_ids": [H1]} for i, (_, ctx) in enumerate(rows)]
    admitted = [{"admitted_evidence_id": f"fev_s{i}", "observation_id": f"o{i}", "evidence_role": "supply", "freshness": "fresh", "independence_group": f"g{i}", "polarity": "supporting",
                 "hypothesis_ids": [H1]} for i in range(len(rows))]
    admitted.append({"admitted_evidence_id": "fev_friction", "observation_id": "o0", "evidence_role": "friction", "hypothesis_ids": [H1]})       # not supply: ignored
    return {"receipts": [{"sources": sources, "observations": obs}], "admissions": [{"admission_id": "hadm_s", "admitted": admitted}],
            "product_concepts": CONCEPTS, "mechanisms": MECHS, "live_hypotheses": LIVE}


ROWS = [("https://www.alibaba.com/product-detail/a1.html", "listing: magnetic belt clip key holder · supplier: Shenzhen Example Co · price as listed: US$1.20-1.80 / piece · MOQ as listed: 500 pieces · concept: pc_1"),
        ("https://cjdropshipping.com/product/b2.html", "listing: running wrist pouch wallet · supplier: unresolved · price as listed: $4.35 · MOQ as listed:  · concept: pc_2"),
        ("https://www.alibaba.com/product-detail/c3.html", "listing: shoe lace key holder · supplier: Yiwu Example Ltd · price as listed: ¥8.5 · MOQ as listed: 1-10"),
        ("https://www.alibaba.com/product-detail/d4.html", "supplier: Nameless Trading · price as listed: $2")]


def test_admitted_supply_observations_become_parsed_candidates_coverage_and_leads_without_a_score():
    out = _exec("supply.leads", _supply_world(ROWS))["output"]
    by = {c["id"]: c for c in out["supplier_candidates"]}
    assert out["joined"] == {"admitted_supply": 4, "without_observation": 0, "without_supplier_name": 1, "without_listing": 1}     # the friction admission is not supply; the listing-less row is counted
    assert (by["fev_s0"]["price_usd_low"], by["fev_s0"]["price_usd_high"], by["fev_s0"]["moq_units"]) == (1.2, 1.8, 500)           # the engine's own parsers
    assert (by["fev_s1"]["price_usd_low"], by["fev_s1"]["moq_units"], by["fev_s1"]["moq_note"]) == (4.35, 1, "cjdropshipping default MOQ 1")   # a DEFAULT MOQ says so
    assert by["fev_s1"]["supplier_name"] is None                                                           # "unresolved" is not a name; none is invented
    assert (by["fev_s2"]["price_usd_low"], by["fev_s2"]["moq_units"]) == (None, None)                       # non-USD price and an ambiguous "1-10": refuse to guess
    leads = out["leads"]
    assert [l["admitted_evidence_id"] for l in leads] == ["fev_s0", "fev_s1"] and [l["concept_id"] for l in leads] == ["pc_1", "pc_2"]
    assert all(l["mechanism_id"] == "m_clip" for l in leads)                                               # only the mechanism whose hypothesis the ledger still holds
    assert all("evidence_score" not in l and "score" not in l for l in leads) and "verdict" not in out     # LAW 1: no domain score, no domain verdict
    cov = {c["concept_id"]: c["status"] for c in out["sourcing_coverage"]}
    assert cov == {"pc_1": "sourced", "pc_2": "sourced", "pc_3": "unparsed"}                                # an unsourced / unparsed concept is a finding, never borrowed cover
    assert out["authority"].startswith("DOMAIN_JOIN_ONLY")


def test_no_admitted_supply_is_a_state_for_trailsignal_to_refuse_and_a_dead_hypothesis_yields_no_lead():
    world = _supply_world(ROWS)
    none = _exec("supply.leads", {**world, "admissions": [{"admission_id": "x", "admitted": []}]})["output"]
    assert none["leads"] == [] and {c["status"] for c in none["sourcing_coverage"]} == {"unsourced"}
    assert _exec("supply.plan", {"product_concepts": CONCEPTS, "mechanisms": MECHS, "live_hypotheses": LIVE})["output"]["sourcing_plan"]
    dead = _exec("supply.leads", {**world, "live_hypotheses": [{"hypothesis_id": H1, "status": "contradicted"}]})["output"]
    assert dead["leads"] == [] and dead["supplier_candidates"] and any("contradicted" in n for n in dead["mechanism_notes"])

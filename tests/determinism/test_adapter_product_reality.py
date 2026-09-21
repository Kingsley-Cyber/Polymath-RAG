"""Restoration Slice 3 — product-reality fidelity (SEMANTIC_TRANSDUCTION_RESTORATION_REFERENCE §10).

concept -> marketplace research -> competitor evidence -> THAT concept. §10.1 stage order unchanged · §10.2 `product_reality.plan`
(the `supply.plan` pattern) · §10.3 marketplace language from `product_terms` / concept / mechanism / population vocabulary, never a
registry territory id · §10.4 `product_reality.join` by the explicit `concept:` tag · §10.5 an existing product can contest a concept ·
§10.6 acceptance: two concepts -> distinct jobs; competitors join to the right concept; one concept is contested without the other.

No database, no network. The binding runs OUT OF PROCESS through its own protocol; nothing here imports `workers`. The fixture is
run 5's real product stage: the vocabulary the run HAD ("backpack strap camera clip") and never searched."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
from polymath_shared.adapter import manifest as M  # noqa: E402

BINDING = ROOT / "adapters" / "ecommerce" / "binding.py"
H1, H2 = "hyp_4983a2b60d63ee405e9453ac", "hyp_5d3107aca1a541bc5b109baa"
GOVERNANCE = ("objective", "hypothesis_ids", "evidence_gaps", "preferred_source_roles", "disallowed_source_roles", "freshness_requirement", "geography", "language",
              "minimum_independent_sources", "success_condition", "falsification_condition", "budget")

#: TrailSignal's product-reality directive exactly as run 5 received it: no gaps, four templates keyed on an UNBOUND territory
DIRECTIVE = {"objective": "map current products, alternatives, reviews, prices, and saturation", "hypothesis_ids": [H1, H2], "evidence_gaps": [], "geography": None, "language": None,
             "search_intents": [{"intent_id": "q-review", "intent": "Find incumbent deficiencies", "evidence_goal": "competition", "evidence_roles": ["competition"], "template": "{activity} {product_territory} review problem"},
                                {"intent_id": "q-return", "intent": "Find failure and return causes", "evidence_goal": "competition", "evidence_roles": ["competition"], "template": "{product_territory} returned broke leaked"},
                                {"intent_id": "q-price", "intent": "Collect current comparable prices", "evidence_goal": "price", "evidence_roles": ["price"], "template": "{product_territory} price buy"},
                                {"intent_id": "q-best", "intent": "Map incumbents, not validate demand", "evidence_goal": "competition", "evidence_roles": ["competition"], "template": "best {product_territory} for {activity}"}],
             "preferred_source_roles": ["marketplace_listing", "retailer"], "disallowed_source_roles": ["supplier_listing"], "minimum_independent_sources": 2,
             "freshness_requirement": {"max_age_days": 90, "policy_ref": "strictest-routed-source"}, "budget": {"max_queries": 24, "max_sources": 40, "max_observations": 80},
             "success_condition": "3 products or substitute categories compared and 2 current price checks", "falsification_condition": "a dominant incumbent already removes the friction at a lower price"}
MECHANISMS = [{"id": "m_strap_mount", "name": "strap-mounted quick-release camera carry", "hypothesis_id": H1, "evidence_refs": ["fev_1"],
               "product_terms": ["backpack strap camera clip", "camera clip for backpack", "camera holster for hiking"]},
              {"id": "m_rain_wrap", "name": "fast weather wrap", "hypothesis_id": H2, "evidence_refs": ["fev_2"], "product_terms": ["neoprene camera wrap", "camera rain cover"]}]
CONCEPTS = [{"id": "pc_1", "mechanism_id": "m_strap_mount", "name": "Universal-fit strap camera mount", "form_factor": "strap clamp mount", "buyer": "hikers whose pack straps the usual clip does not fit",
             "variations": [{"name": "wide-jaw clamp", "twist": "an adjustable jaw for thick padded straps"}, {"name": "webbing anchor", "twist": "threads onto the pack's webbing"}]},
            {"id": "pc_2", "mechanism_id": "m_strap_mount", "name": "Battery sleeve on the strap", "form_factor": "elastic strap sleeve", "buyer": "photographers who swap batteries on the move"},
            {"id": "pc_3", "mechanism_id": "m_rain_wrap", "name": "One-hand rain wrap", "form_factor": "neoprene wrap", "buyer": "photographers who keep shooting in rain"}]
LIVE = [{"hypothesis_id": H1, "revision": 3, "status": "revised", "statement": "hikers cannot reach the camera with one hand"},
        {"hypothesis_id": H2, "revision": 2, "status": "revised", "statement": "photographers stop shooting in rain"}]
SEMANTICS = [{"hypothesis_id": H1, "statement": LIVE[0]["statement"], "population": "hiking photographers", "activity": "hiking photography", "task": "get the camera ready with one hand",
              "suspected_friction": "camera buried in the pack", "jobs": [{"job": "access: get the camera from carried to shooting with one hand", "mechanism": "strap-mounted carry"}],
              "mechanisms": [], "concepts": [], "territories": [{"territory_id": "pt-06", "territory": "product_territory"}]},
             {"hypothesis_id": H2, "statement": LIVE[1]["statement"], "population": "landscape photographers", "activity": "landscape photography", "task": "keep shooting in rain",
              "suspected_friction": "covers are slow to fit", "jobs": [], "mechanisms": [], "concepts": [], "territories": []}]


def _binding(operation: str, inputs: dict) -> dict:
    req = {"schema_version": "domain_operation_request.v1", "domain": "ecommerce", "operation": operation, "run_id": "adr_" + "3" * 32, "step_id": "op", "input": {}, "inputs": inputs, "config": {}}
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run([sys.executable, str(BINDING)], input=json.dumps(req), capture_output=True, text=True, timeout=120, cwd=str(BINDING.parent), env=env)
    assert proc.returncode == 0, proc.stderr[-800:]
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def planned():
    resp = _binding("product_reality.plan", {"research_directive": DIRECTIVE, "product_concepts": CONCEPTS, "mechanisms": MECHANISMS, "live_hypotheses": LIVE, "semantics": SEMANTICS})
    assert resp["ok"], resp
    return resp["output"]


# ─────────────────────────────────────────────────────────── §10.2 / §10.3 plan
def test_two_concepts_get_distinct_jobs_in_market_language(planned):
    jobs = planned["reality_plan"]
    by_concept = {c: [j for j in jobs if j["concept_id"] == c] for c in ("pc_1", "pc_2", "pc_3")}
    assert all(by_concept.values())
    q1, q2 = {j["query"] for j in by_concept["pc_1"]}, {j["query"] for j in by_concept["pc_2"]}
    assert not (q1 & q2)                                                                   # siblings under ONE mechanism still research differently (form factor)
    review = {j["concept_id"]: j["query"] for j in jobs if j["job_id"] == f"q-review:{j['concept_id']}"}
    assert review["pc_1"] == "hiking photography strap clamp mount backpack camera clip review problem"
    assert review["pc_2"] == "hiking photography elastic strap sleeve backpack camera clip review problem" and "neoprene wrap" in review["pc_3"]
    for j in jobs:                                                                         # the run's own market vocabulary — never a registry id, never a slot
        assert "pt-06" not in j["query"] and "product_territory" not in j["query"] and "{" not in j["query"], j
        assert j["hypothesis_id"] == (H2 if j["concept_id"] == "pc_3" else H1) and j["mechanism_id"] in ("m_strap_mount", "m_rain_wrap")


def test_every_job_keeps_its_lineage_and_variations_have_an_identity(planned):
    jobs = {j["job_id"]: j for j in planned["reality_plan"]}
    assert jobs["q-review:pc_1.v1"]["variation_id"] == "pc_1.v1" and jobs["q-review:pc_1.v1"]["job_class"] == "direct_competitor" and "wide-jaw" in jobs["q-review:pc_1.v1"]["query"]
    sub = jobs["q-review:pc_1:substitute"]
    assert sub["job_class"] == "substitute" and sub["query"].startswith("hiking photographers") and sub["query"].endswith("alternative") and sub["variation_id"] is None
    assert sub["applies_to_concepts"] == ["pc_1", "pc_2"] and "q-review:pc_2:substitute" not in jobs          # the JOB's substitutes: one search per hypothesis, not one per sibling
    intents = {i["intent_id"]: i for i in planned["research_directive"]["search_intents"]}
    assert set(jobs) == set(intents)                                                       # a job IS the intent the harness receives: one id space
    i = intents["q-price:pc_2"]
    assert i["evidence_roles"] == ["price"] and i["evidence_goal"] == "price" and "`concept: pc_2`" in i["intent"] and "relation:" in i["intent"]
    assert "`variation: pc_1.v2`" in intents["q-review:pc_1.v2"]["intent"]


def test_governance_is_trailsignals_and_the_budget_is_respected_fairly(planned):
    d = planned["research_directive"]
    assert all(d[k] == DIRECTIVE[k] for k in GOVERNANCE) and planned["governance_unchanged"] is True
    p = planned["planned"]
    assert len(d["search_intents"]) <= p["intent_cap"] == 24 and p["concepts"] == 3 and p["concepts_without_a_job"] == [] and p["unresolved"] == []
    assert [i["intent_id"] for i in d["search_intents"][:3]] == ["q-review:pc_1:direct", "q-review:pc_2:direct", "q-review:pc_3:direct"]   # who already sells THIS — first, for every concept,
    assert [i["template"] for i in d["search_intents"][:2]] == ["strap clamp mount backpack camera clip", "elastic strap sleeve backpack camera clip"]   # before any concept gets a second job


def test_plan_refusals_are_typed_and_a_concept_without_lineage_is_reported():
    assert _binding("product_reality.plan", {"research_directive": {"objective": "x"}, "product_concepts": CONCEPTS})["code"] == "REALITY_DIRECTIVE_MISSING"
    assert _binding("product_reality.plan", {"research_directive": DIRECTIVE, "product_concepts": []})["code"] == "PRODUCT_CONCEPTS_MISSING"
    orphan = [{"id": "pc_9", "mechanism_id": "m_unknown", "name": "orphan", "form_factor": "thing"}]
    assert _binding("product_reality.plan", {"research_directive": DIRECTIVE, "product_concepts": orphan, "mechanisms": MECHANISMS, "live_hypotheses": LIVE, "semantics": SEMANTICS})["code"] == "REALITY_PLAN_UNBOUND"


# ─────────────────────────────────────────────────────────── §10.4 / §10.5 join
def _receipt_and_admission():
    obs = [("o1", "competition", "Peak Design Capture Clip V3 is sold with about 10,600 ratings: a dominant incumbent for strap-mounted carry.",
            "concept: pc_1 · relation: competitor · product: Peak Design Capture Camera Clip V3 · price as listed: $79.95", "supporting"),
           ("o2", "price", "PGYTECH Beetle Clip V2 fits straps 1 to 20 mm thick and up to 80 mm wide.",
            "concept: pc_1 · variation: pc_1.v1 · relation: solves · product: PGYTECH Beetle Camera Clip V2 · price as listed: $59.95", "supporting"),
           ("o3", "competition", "No strap-mounted battery sleeve was found; photographers use generic belt pouches.",
            "concept: pc_2 · relation: substitute · product: generic belt battery pouch", "supporting"),
           ("o4", "competition", "A neoprene wrap from an unknown seller.", "Marketplace search result.", "supporting"),
           ("o5", "competition", "Tagged with a concept this run never validated.", "concept: pc_77 · relation: competitor · product: X", "supporting")]
    receipt = {"action_id": "hact_pr", "observations": [{"observation_id": i, "source_id": "s1", "claim": claim, "context": ctx, "paraphrase_or_excerpt": ""} for i, _, claim, ctx, _ in obs],
               "sources": [{"source_id": "s1", "url": "https://www.amazon.com/s?k=backpack+strap+camera+clip", "source_class": "marketplace_listing"}]}
    admission = {"admitted": [{"admitted_evidence_id": f"fev_{i}", "observation_id": i, "evidence_role": role, "polarity": pol, "hypothesis_ids": [H1]} for i, role, _, _, pol in obs]}
    return receipt, admission


@pytest.fixture(scope="module")
def joined(planned):
    receipt, admission = _receipt_and_admission()
    resp = _binding("product_reality.join", {"admissions": [admission], "receipts": [receipt], "product_concepts": CONCEPTS, "mechanisms": MECHANISMS, "live_hypotheses": LIVE,
                                             "reality_plan": planned["reality_plan"]})
    assert resp["ok"], resp
    return resp["output"]


def test_products_join_to_the_concept_their_tag_names_and_never_by_name(joined):
    products = {p["id"]: p for p in joined["existing_products"]}
    assert {i: p["concept_id"] for i, p in products.items()} == {"fev_o1": "pc_1", "fev_o2": "pc_1", "fev_o3": "pc_2"}
    assert products["fev_o2"]["variation_id"] == "pc_1.v1" and products["fev_o2"]["product_name"] == "PGYTECH Beetle Camera Clip V2" and products["fev_o2"]["price_raw"] == "$59.95"
    assert products["fev_o1"]["hypothesis_id"] == H1 and products["fev_o1"]["mechanism_id"] == "m_strap_mount" and products["fev_o1"]["url"].startswith("https://www.amazon.com")
    # "a neoprene wrap" LOOKS like concept pc_3 — ownership is never inferred from a name; an unknown tag is not repaired either
    assert {(u["admitted_evidence_id"], u["reason"]) for u in joined["unjoined"]} == {("fev_o4", "NO_CONCEPT_TAG"), ("fev_o5", "UNKNOWN_CONCEPT")}
    assert joined["joined"] == {"admitted": 5, "without_observation": 0, "without_concept_tag": 1, "unknown_concept": 1, "joined": 3}


def test_acceptance_an_existing_product_contests_one_concept_without_touching_its_sibling(joined):
    reality = {c["concept_id"]: c for c in joined["concept_reality"]}
    assert reality["pc_1"]["status"] == "EXISTING_PRODUCT_CONTESTS" and reality["pc_1"]["contested_by"] == ["fev_o2"] and reality["pc_1"]["by_relation"] == {"competitor": 1, "solves": 1}
    assert reality["pc_2"]["status"] == "EXISTING_PRODUCTS_FOUND" and reality["pc_2"]["contested_by"] == [] and reality["pc_2"]["by_relation"] == {"substitute": 1}     # same mechanism, untouched
    assert reality["pc_3"]["status"] == "NO_EXISTING_PRODUCT_JOINED" and reality["pc_3"]["jobs_planned"] > 0
    assert joined["authority"].startswith("DOMAIN_JOIN_ONLY") and not any(k in json.dumps(joined) for k in ('"score"', '"verdict"', '"rank"'))


def test_trailsignals_contradicting_polarity_also_contests_the_concept(planned):
    receipt, admission = _receipt_and_admission()
    admission["admitted"][2]["polarity"] = "contradicting"
    out = _binding("product_reality.join", {"admissions": [admission], "receipts": [receipt], "product_concepts": CONCEPTS, "mechanisms": MECHANISMS, "live_hypotheses": LIVE,
                                            "reality_plan": planned["reality_plan"]})["output"]
    assert {c["concept_id"]: c["status"] for c in out["concept_reality"]}["pc_2"] == "EXISTING_PRODUCT_CONTESTS"


# ─────────────────────────────────────────────────────────── §10.1 the manifest: two steps added, no stage moved
def test_the_manifest_adds_a_plan_and_a_join_step_and_moves_no_stage():
    m = M.load_manifest(ROOT / "config" / "adapters" / "ecommerce.product_research.json")
    order = [s["step_id"] for s in m.raw["steps"]]
    assert order[order.index("N_concepts"):order.index("R_qualify") + 1] == ["N_concepts", "N_concepts_law", "N_concepts_route", "O_territory", "O_plan", "P_reality", "Q_admit", "Q_join", "R_qualify"]
    chain = ["O_territory"]
    while chain[-1] != "R_qualify":
        chain.append(m.steps[chain[-1]]["next"])
    assert chain == ["O_territory", "O_plan", "P_reality", "Q_admit", "Q_join", "R_qualify"]
    assert m.steps["O_plan"]["config"]["inputs"]["semantics"] == "context.semantics.product_reality" and m.steps["Q_join"]["config"]["inputs"]["reality_plan"] == "outputs.O_plan.reality_plan"
    assert {"reality_plan", "mechanisms"} <= set(m.steps["P_reality"]["config"]["show"]) and {"existing_products", "concept_reality"} <= set(m.steps["W_interpret"]["config"]["show"])
    assert {"existing_products", "concept_reality"} <= {k for k in m.steps["X_compile"]["config"]["include"] if isinstance(k, str)}

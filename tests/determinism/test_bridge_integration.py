"""WLK2C C3 — bridge integration (pure). Pins: scout nominations → grounded concepts; tier-1 reuse
(a concept already covered by an admissible existing subquery is not re-compiled); admitted bridges
become BRIDGE-origin subqueries carrying full lineage; eligibility is INTENT-based; q0 + existing
subqueries are never mutated; invented/ineligible cases add nothing; the injected generate is the
single model call.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from polymath_shared.bridge_integration import (
    bridges_to_subqueries,
    concepts_from_nominations,
    covered_concept_keys,
    plan_bridge_expansion,
)
from polymath_shared.bridge_compiler import CompiledBridge, Concept
from polymath_shared.chat_plan import CompiledQuery

Q0 = "make the fake smile readable to the audience"


def _plan(intent="APPLICATION", extra=None):
    qs = [CompiledQuery(id="q0", type="PRIMARY", query=Q0)]
    qs += (extra or [])
    return SimpleNamespace(queries=qs, intent=intent, compiler={})


def _nom(doc_id, surface):
    return SimpleNamespace(doc_id=doc_id, representative_surface=surface, representative_text=surface)


NOMS = [_nom("docFACS", "Facial Action Coding expressions"), _nom("docHooks", "Acting for Animators")]


def _gen_ok(prompt):
    assert "docFACS" in prompt
    return json.dumps([{"bridge_query": "observable facial muscle actions of genuine vs faked smiles",
                        "derived_from": "docFACS", "relation_to_q0": "distinguishes real from performed",
                        "proposed_role": "COMPLEMENTARY", "model_confidence": 0.5}])


# ---- helpers ----

def test_concepts_from_nominations():
    cs = concepts_from_nominations(NOMS)
    assert [c.key for c in cs] == ["docFACS", "docHooks"]
    assert cs[0].label == "Facial Action Coding expressions" and cs[0].source == "docFACS"


def test_covered_by_admissible_existing_subquery():
    existing = CompiledQuery(id="p1", type="ENTITY", query="expression coding action units eyes",
                             origin="PROFILE", inspired_by_profile=["docFACS"])
    covered = covered_concept_keys([CompiledQuery(id="q0", type="PRIMARY", query=Q0), existing], Q0)
    assert covered == {"docFACS"}


def test_paraphrase_existing_subquery_does_not_cover():
    para = CompiledQuery(id="p1", type="ENTITY", query="make the fake smile readable audience",
                         origin="PROFILE", inspired_by_profile=["docFACS"])   # ~ q0 -> not admissible
    assert covered_concept_keys([CompiledQuery(id="q0", type="PRIMARY", query=Q0), para], Q0) == set()


def test_bridges_to_subqueries_carry_lineage():
    b = CompiledBridge(bridge_id="x", bridge_query="asymmetric zygomatic activation in forced smiles",
                       derived_from="docFACS", relation_to_q0="asymmetry betrays the fake",
                       proposed_role="COMPLEMENTARY")
    sq = bridges_to_subqueries([b], {"docFACS": Concept("docFACS", "FACS", "docFACS")})[0]
    assert sq.origin == "BRIDGE" and sq.role == "bridge"          # origin survives (ORIGIN_TYPES extended)
    assert sq.inspired_by_profile == ["docFACS"] and sq.target == "docFACS"
    assert "docFACS" in sq.reason


# ---- orchestration ----

def test_expansion_appends_bridge_subquery_and_preserves_q0():
    plan = _plan()
    diag = plan_bridge_expansion(plan, NOMS, generate=_gen_ok)
    assert diag["added"] == 1 and diag["eligible"] is True
    bridges = [q for q in plan.queries if q.origin == "BRIDGE"]
    assert len(bridges) == 1 and bridges[0].query.startswith("observable facial")
    assert plan.queries[0].type == "PRIMARY" and plan.queries[0].query == Q0   # q0 untouched
    assert plan.compiler["bridge_expansion"]["added"] == 1


def test_factual_intent_skips_compiler():
    called = {"n": 0}
    plan = _plan(intent="DEFINITION")
    diag = plan_bridge_expansion(plan, NOMS, generate=lambda p: called.__setitem__("n", 1))
    assert diag["added"] == 0 and diag["eligible"] is False and called["n"] == 0


def test_no_primary_no_expansion():
    plan = SimpleNamespace(queries=[CompiledQuery(id="s", type="ENTITY", query="sub")], intent="APPLICATION", compiler={})
    assert plan_bridge_expansion(plan, NOMS, generate=_gen_ok)["reason"] == "no_primary"


def test_all_concepts_covered_skips_compiler():
    covered_subs = [CompiledQuery(id="p1", type="ENTITY", query="facial action units around the eyes",
                                  origin="PROFILE", inspired_by_profile=["docFACS"]),
                    CompiledQuery(id="p2", type="ENTITY", query="acting beats for animators performance",
                                  origin="PROFILE", inspired_by_profile=["docHooks"])]
    plan = _plan(extra=covered_subs)
    diag = plan_bridge_expansion(plan, NOMS, generate=_gen_ok)
    assert diag["added"] == 0 and diag["reason"] == "all_concepts_have_admissible_bridge"


def test_invented_bridge_added_nothing():
    def gen_invented(prompt):
        return json.dumps([{"bridge_query": "principles of macroeconomic policy and inflation",
                            "derived_from": "economics", "relation_to_q0": "incentives", "model_confidence": 0.99}])
    plan = _plan()
    diag = plan_bridge_expansion(plan, NOMS, generate=gen_invented)
    assert diag["added"] == 0 and diag["dropped_invented"] == 1
    assert not any(q.origin == "BRIDGE" for q in plan.queries)


def test_dedup_against_existing_query():
    dup = CompiledQuery(id="a1", type="MECHANISM",
                        query="observable facial muscle actions of genuine vs faked smiles", origin="USER")
    plan = _plan(extra=[dup])
    diag = plan_bridge_expansion(plan, NOMS, generate=_gen_ok)
    assert diag["added"] == 0                                     # identical bridge query already present


def test_concept_label_is_the_atom_text_not_its_kind_name():
    """ENRICHMENT-SURFACES-AUDIT defect 2 (E2): the live Scout sets `representative_surface` to the atom KIND (e.g. "THEORY")
    and `representative_text` to the atom's real text. The bridge compiler must receive the text; a kind name tells it
    nothing (24 / 24 live labels were kind names or doc ids). A text-less nomination falls back to its title / source name,
    and only then to the kind or the doc id."""
    live_shaped = SimpleNamespace(doc_id="docFACS", representative_surface="THEORY",
                                  representative_text="Facial muscle actions separate felt from posed smiles")
    titled = SimpleNamespace(doc_id="docHooks", representative_surface=None, representative_text=None, title="Acting for Animators")
    labels = [c.label for c in concepts_from_nominations([live_shaped, titled])]
    assert labels == ["Facial muscle actions separate felt from posed smiles", "Acting for Animators"]

"""CORPUS-EXPLORER-V1 CE2/CE3 — explorer expansion reuses the WLK2C bridge compiler under a distinct
CORPUS_EXPLORE origin; origin survives the enum; lineage rides the BRIDGE fusion class; coexists with
Scout BRIDGE without id collision. Pure (injected generate)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.corpus_activation import ActivationCandidate  # noqa: E402
from polymath_shared.corpus_explore import (  # noqa: E402
    CORPUS_EXPLORE_ORIGIN,
    activations_to_concepts,
    plan_corpus_explore_expansion,
)
from polymath_shared.bridge_integration import plan_bridge_expansion  # noqa: E402
from polymath_shared.chat_plan import ORIGIN_TYPES, CompiledQuery  # noqa: E402
from polymath_shared.ranked_fusion import CLASS_BRIDGE, lineage_class  # noqa: E402

Q0 = "how can this character dominate a room without speaking"


def _plan(intent="APPLICATION", extra=None):
    qs = [CompiledQuery(id="q0", type="PRIMARY", query=Q0)]
    qs += (extra or [])
    return SimpleNamespace(queries=qs, intent=intent, compiler={})


def _acts():
    return [
        ActivationCandidate("spatial-control", "spatial control", ("laban_workbook", "directing_book"),
                            ("atom:CONCEPT",), 0.9, ()),
        ActivationCandidate("blocking", "blocking", ("directing_book",), ("atom:CONCEPT",), 0.6, ()),
    ]


def _gen_ok(prompt):
    assert "spatial-control" in prompt   # concept keys are the allowed derived_from universe
    return json.dumps([{"bridge_query": "movement qualities that communicate dominance through control of space",
                        "derived_from": "spatial-control", "relation_to_q0": "nonverbal dominance via space",
                        "proposed_role": "COMPLEMENTARY", "model_confidence": 0.6}])


# ---- CE3: origin enum + fusion class ----

def test_origin_is_registered_not_coerced():
    assert "CORPUS_EXPLORE" in ORIGIN_TYPES
    q = CompiledQuery(id="ce0", type="ENTITY", query="x", origin="CORPUS_EXPLORE")
    assert q.origin == "CORPUS_EXPLORE"          # MUST-FIX: not silently coerced to USER


def test_corpus_explore_rides_bridge_fusion_class():
    lane = SimpleNamespace(role="bridge", origin="CORPUS_EXPLORE", modality="text")
    assert lineage_class(lane) == CLASS_BRIDGE    # same class/weight as BRIDGE, no new tunable


# ---- CE2: mapping ----

def test_activations_to_concepts():
    cs = activations_to_concepts(_acts())
    assert [c.key for c in cs] == ["spatial-control", "blocking"]
    assert cs[0].label == "spatial control" and cs[0].source == "laban_workbook"


# ---- CE2: expansion ----

def test_expansion_appends_corpus_explore_subquery_preserves_q0():
    plan = _plan()
    diag = plan_corpus_explore_expansion(plan, _acts(), generate=_gen_ok)
    assert diag["added"] == 1 and diag["eligible"] is True and diag["origin"] == CORPUS_EXPLORE_ORIGIN
    ce = [q for q in plan.queries if q.origin == "CORPUS_EXPLORE"]
    assert len(ce) == 1 and ce[0].id.startswith("ce") and ce[0].role == "bridge"
    assert ce[0].derived_from == "spatial-control" and ce[0].inspired_by_profile == ["laban_workbook"]  # E7
    assert ce[0].target is None
    assert plan.queries[0].type == "PRIMARY" and plan.queries[0].query == Q0     # q0 untouched
    assert plan.compiler["corpus_explore_expansion"]["added"] == 1


def test_factual_intent_skips_compiler():
    called = {"n": 0}
    plan = _plan(intent="DEFINITION")
    diag = plan_corpus_explore_expansion(plan, _acts(), generate=lambda p: called.__setitem__("n", 1))
    assert diag["added"] == 0 and diag["eligible"] is False and called["n"] == 0


def test_no_primary_no_expansion():
    plan = SimpleNamespace(queries=[CompiledQuery(id="s", type="ENTITY", query="sub")],
                           intent="APPLICATION", compiler={})
    assert plan_corpus_explore_expansion(plan, _acts(), generate=_gen_ok)["reason"] == "no_primary"


def test_no_concepts_skips_compiler():
    called = {"n": 0}
    plan = _plan()
    diag = plan_corpus_explore_expansion(plan, [], generate=lambda p: called.__setitem__("n", 1))
    assert diag["added"] == 0 and diag["eligible"] is False and called["n"] == 0


def test_invented_derived_from_dropped():
    def gen_invented(prompt):
        return json.dumps([{"bridge_query": "principles of macroeconomic policy",
                            "derived_from": "economics", "relation_to_q0": "incentives", "model_confidence": 0.9}])
    plan = _plan()
    diag = plan_corpus_explore_expansion(plan, _acts(), generate=gen_invented)
    assert diag["added"] == 0 and diag["dropped_invented"] == 1
    assert not any(q.origin == "CORPUS_EXPLORE" for q in plan.queries)


def test_fail_open_when_generate_raises():
    def boom(prompt):
        raise RuntimeError("model down")
    plan = _plan()
    diag = plan_corpus_explore_expansion(plan, _acts(), generate=boom)   # must not raise
    assert diag["added"] == 0
    assert not any(q.origin == "CORPUS_EXPLORE" for q in plan.queries)


def test_dedup_against_existing_query():
    dup = CompiledQuery(id="a1", type="MECHANISM",
                        query="movement qualities that communicate dominance through control of space", origin="USER")
    plan = _plan(extra=[dup])
    assert plan_corpus_explore_expansion(plan, _acts(), generate=_gen_ok)["added"] == 0


def test_coexists_with_bridge_no_id_collision():
    # Scout BRIDGE expansion AND corpus-explore expansion both run: distinct origins, distinct id prefixes.
    plan = _plan()
    noms = [SimpleNamespace(doc_id="docLaban", representative_surface="Laban effort qualities",
                            representative_text="Laban effort qualities")]

    def gen_bridge(prompt):
        return json.dumps([{"bridge_query": "laban effort qualities for silent status",
                            "derived_from": "docLaban", "relation_to_q0": "effort conveys status",
                            "proposed_role": "COMPLEMENTARY", "model_confidence": 0.5}])

    plan_bridge_expansion(plan, noms, generate=gen_bridge)
    plan_corpus_explore_expansion(plan, _acts(), generate=_gen_ok)
    bridge_ids = {q.id for q in plan.queries if q.origin == "BRIDGE"}
    ce_ids = {q.id for q in plan.queries if q.origin == "CORPUS_EXPLORE"}
    assert bridge_ids and ce_ids and not (bridge_ids & ce_ids)   # no id collision
    assert all(i.startswith("br") for i in bridge_ids) and all(i.startswith("ce") for i in ce_ids)
    assert plan.queries[0].query == Q0                            # q0 still primary

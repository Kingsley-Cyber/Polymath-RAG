"""WLK2C C2 — bounded concept-bridge compiler (pure core). Pins the owner locks: ACTIVATION not
invention (a bridge whose derived_from is not a provided concept is dropped, even at confidence 0.99);
confidence and proposed_role are metadata only (never gate); one bounded call, capped ≤4; the LLM call
is injected so the whole path is deterministic. C1 structural gate still applies (paraphrase dropped).
"""
from __future__ import annotations

import json

from polymath_shared.bridge_compiler import (
    BridgeCompilerInput,
    CompiledBridge,
    Concept,
    build_prompt,
    compile_bridges,
    compiler_eligible,
    parse_and_validate,
)

Q0 = "make the fake smile readable to the audience"
CONCEPTS = [Concept(key="docFACS", label="Facial Action Coding", source="docFACS"),
            Concept(key="docHooks", label="Acting for Animators", source="docHooks")]


def _inp(**kw):
    base = dict(q0=Q0, intent="CREATIVE", concepts=CONCEPTS,
                existing_subqueries=["expression timing beats"], graph_relations=[])
    base.update(kw)
    return BridgeCompilerInput(**base)


# ---- eligibility ----

def test_eligibility():
    assert compiler_eligible("CREATIVE", CONCEPTS, [])[0] is True
    assert compiler_eligible("FAST", CONCEPTS, [])[0] is False          # not a latent intent
    assert compiler_eligible("CREATIVE", [], [])[0] is False            # no concepts
    ok, reason = compiler_eligible("CREATIVE", CONCEPTS, ["docFACS", "docHooks"])
    assert ok is False and reason == "all_concepts_have_admissible_bridge"


# ---- prompt ----

def test_prompt_is_grounded_and_forbids_invention():
    p = build_prompt(_inp(), max_bridges=4)
    assert Q0 in p and "docFACS" in p and "Facial Action Coding" in p
    assert "do NOT invent" in p and "ALLOWED CORPUS CONCEPTS" in p
    assert "AT MOST 4" in p and "expression timing beats" in p          # existing subquery listed


# ---- validation: the core guard ----

def test_activation_not_invention_drops_invented_even_at_high_confidence():
    raw = json.dumps([
        {"bridge_id": "b1", "bridge_query": "observable facial muscle actions of genuine vs faked smiles",
         "derived_from": "docFACS", "relation_to_q0": "distinguishes real from performed smiling",
         "proposed_role": "COMPLEMENTARY", "model_confidence": 0.4},
        {"bridge_id": "b2", "bridge_query": "principles of behavioral economics and market incentives",
         "derived_from": "economics", "relation_to_q0": "people respond to incentives",
         "proposed_role": "DIVERGENT", "model_confidence": 0.99},   # INVENTED concept, high confidence
    ])
    bridges, diag = parse_and_validate(raw, _inp())
    assert [b.derived_from for b in bridges] == ["docFACS"]          # only the grounded one survives
    assert diag["dropped_invented"] == 1 and diag["admitted"] == 1


def test_derived_from_matches_by_label_too():
    raw = json.dumps([{"bridge_query": "action units around the eyes in spontaneous smiles",
                       "derived_from": "Facial Action Coding",       # the label, not the key
                       "relation_to_q0": "eye muscles reveal genuine affect", "proposed_role": "x"}])
    bridges, _ = parse_and_validate(raw, _inp())
    assert len(bridges) == 1 and bridges[0].derived_from == "docFACS"
    assert bridges[0].proposed_role == "COMPLEMENTARY"              # invalid role sanitized to hint default


def test_paraphrase_and_empty_and_no_relation_dropped():
    raw = json.dumps([
        {"bridge_query": "make the fake smile readable audience", "derived_from": "docFACS",
         "relation_to_q0": "same thing"},                            # ~ q0 paraphrase -> C1 structural drop
        {"bridge_query": "", "derived_from": "docFACS", "relation_to_q0": "x"},          # empty
        {"bridge_query": "onset apex offset timing of expressions", "derived_from": "docHooks",
         "relation_to_q0": ""},                                      # no relation
    ])
    bridges, diag = parse_and_validate(raw, _inp())
    assert bridges == []
    assert diag["dropped_structural"] == 1 and diag["dropped_empty"] == 1 and diag["dropped_no_relation"] == 1


def test_confidence_is_non_authoritative():
    # a low-confidence but well-formed grounded bridge IS admitted -> confidence never gates.
    raw = json.dumps([{"bridge_query": "asymmetric zygomatic activation in deliberate smiles",
                       "derived_from": "docFACS", "relation_to_q0": "asymmetry signals a forced smile",
                       "model_confidence": 0.02}])
    bridges, _ = parse_and_validate(raw, _inp())
    assert len(bridges) == 1 and bridges[0].model_confidence == 0.02


def test_cap_and_dedup():
    items = [{"bridge_query": f"distinct facial mechanics probe number {i} spontaneous", "derived_from": "docFACS",
              "relation_to_q0": "helps"} for i in range(6)]
    items.append(dict(items[0]))                                     # a duplicate query
    bridges, diag = parse_and_validate(json.dumps(items), _inp(), max_bridges=4)
    assert len(bridges) == 4                                         # capped
    assert diag["admitted"] == 4


def test_loads_tolerates_fences_and_garbage():
    fenced = "```json\n[{\"bridge_query\":\"eye and mouth discrepancy in fake smiles\"," \
             "\"derived_from\":\"docFACS\",\"relation_to_q0\":\"reveals the fake\"}]\n```"
    bridges, _ = parse_and_validate(fenced, _inp())
    assert len(bridges) == 1
    assert parse_and_validate("total garbage, no json here", _inp())[0] == []
    assert parse_and_validate("", _inp())[0] == []


# ---- compile_bridges: injected generate ----

def test_compile_bridges_injected_generate():
    calls = {"n": 0}

    def fake_generate(prompt):
        calls["n"] += 1
        assert "docFACS" in prompt
        return json.dumps([{"bridge_query": "duchenne marker: eye orbicularis in genuine smiles",
                            "derived_from": "docFACS", "relation_to_q0": "genuine smiles engage the eyes"}])
    bridges, diag = compile_bridges(_inp(), generate=fake_generate)
    assert calls["n"] == 1 and len(bridges) == 1 and diag["admitted"] == 1


def test_compile_bridges_no_concepts_no_call():
    called = {"n": 0}
    out, diag = compile_bridges(_inp(concepts=[]), generate=lambda p: called.__setitem__("n", 1))
    assert out == [] and called["n"] == 0 and diag.get("skipped") == "no_concepts"


def test_compile_bridges_generate_failure_fails_open():
    def boom(prompt):
        raise RuntimeError("model down")
    out, diag = compile_bridges(_inp(), generate=boom)
    assert out == [] and "error" in diag


def test_deterministic():
    raw = json.dumps([{"bridge_query": "micro-expression leakage in suppressed affect", "derived_from": "docFACS",
                       "relation_to_q0": "leaked cues betray the fake"}])
    a = [b.to_dict() for b in parse_and_validate(raw, _inp())[0]]
    b = [b.to_dict() for b in parse_and_validate(raw, _inp())[0]]
    assert a == b and isinstance(CompiledBridge(**{**a[0]}), CompiledBridge)

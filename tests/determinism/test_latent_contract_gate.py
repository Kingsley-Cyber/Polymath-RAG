"""Phase A exit gate (plan §4.A.2 + §1.7 amendments): every reject
class, budget trimming, source-hash sensitivity, pre-call ceiling,
deterministic transfer text, and the coverage-floor semantics."""
from __future__ import annotations

import json

from polymath_shared.latent.compiler import (
    CompiledParent,
    ParentInput,
    compile_parents,
)
from polymath_shared.latent.contract import EnrichmentBounds
from polymath_shared.latent.gate import (
    sanitize_enrichment,
    source_hash,
    transfer_text,
)

BOUNDS = EnrichmentBounds()
REFS = [0, 1, 2, 3]


def _payload(**over):
    base = {
        "summary": "A section about lifecycle policies and storage tiers.",
        "children": [{"ref": i, "gist": f"Gist for passage {i}."}
                     for i in REFS],
        "abstraction": "Automated policies move resources between cost "
                       "tiers as value decays.",
        "mechanisms": ["Rules watch age and trigger transitions."],
        "affordances": ["Cut storage cost without manual sweeps."],
        "questions": ["How do libraries archive rarely-used items?"],
    }
    base.update(over)
    return json.dumps(base)


def test_happy_path_accepts_and_orders_gists():
    gate, out = sanitize_enrichment(_payload(), REFS, BOUNDS)
    assert gate.ok and gate.error_class is None
    assert gate.gist_coverage == 1.0
    assert [g.ref for g in out.children] == REFS
    assert out.abstraction.startswith("Automated policies")


def test_unparseable_rejects():
    gate, out = sanitize_enrichment("not json at all", REFS, BOUNDS)
    assert not gate.ok and gate.error_class == "ENRICH_UNPARSEABLE"
    assert out is None


def test_unknown_and_duplicate_refs_hard_reject():
    bad = _payload(children=[{"ref": 9, "gist": "x" * 30}])
    gate, _ = sanitize_enrichment(bad, REFS, BOUNDS)
    assert gate.error_class == "ENRICH_UNKNOWN_REF"
    dup = _payload(children=[{"ref": 0, "gist": "a" * 30},
                             {"ref": 0, "gist": "b" * 30}] +
                            [{"ref": i, "gist": f"g{i}" * 10}
                             for i in (1, 2, 3)])
    gate, _ = sanitize_enrichment(dup, REFS, BOUNDS)
    assert gate.error_class == "ENRICH_UNKNOWN_REF"


def test_missing_gists_are_a_floor_not_a_reject():
    # 3 of 4 covered = 0.75 < 0.8 floor -> reject WITH the coverage
    three = _payload(children=[{"ref": i, "gist": f"Gist {i} words here."}
                               for i in (0, 1, 2)])
    gate, _ = sanitize_enrichment(three, REFS, BOUNDS)
    assert gate.error_class == "ENRICH_GISTS_BELOW_FLOOR"
    assert abs(gate.gist_coverage - 0.75) < 1e-9
    # 0.75 passes a lower floor (the shortfall is COUNTED, not fatal)
    lax = EnrichmentBounds(gist_coverage_floor=0.7)
    gate2, out2 = sanitize_enrichment(three, REFS, lax)
    assert gate2.ok and len(out2.children) == 3


def test_empty_summary_or_abstraction_rejects():
    gate, _ = sanitize_enrichment(_payload(summary="  "), REFS, BOUNDS)
    assert gate.error_class == "ENRICH_EMPTY"


def test_budget_trims_never_reject():
    fat = _payload(mechanisms=[f"mech {i} " + "x" * 300 for i in range(5)],
                   questions=[f"q{i}?" for i in range(9)])
    gate, out = sanitize_enrichment(fat, REFS, BOUNDS)
    assert gate.ok
    assert len(out.mechanisms) == BOUNDS.max_mechanisms
    assert all(len(m) <= BOUNDS.mechanism_chars for m in out.mechanisms)
    assert len(out.questions) == BOUNDS.max_questions
    assert gate.trimmed and gate.trimmed["mechanisms"] == 3


def test_source_hash_changes_iff_child_identity_changes():
    kids = [("chunk_a", 0, "alpha"), ("chunk_b", 1, "beta")]
    h = source_hash(kids)
    assert source_hash(list(kids)) == h
    assert source_hash([("chunk_a", 0, "alpha"),
                        ("chunk_b", 1, "CHANGED")]) != h
    assert source_hash([("chunk_X", 0, "alpha"),
                        ("chunk_b", 1, "beta")]) != h
    assert source_hash(kids[::-1]) != h


def test_transfer_text_is_deterministic():
    _, out = sanitize_enrichment(_payload(), REFS, BOUNDS)
    t1, t2 = transfer_text(out), transfer_text(out)
    assert t1 == t2
    assert t1.startswith("Mechanisms: Rules watch age")
    assert "Useful for:" in t1 and "Answers:" in t1


def test_compiler_ceiling_rejects_before_any_call():
    calls: list = []

    def complete(items):
        calls.extend(items)
        return [(i, _payload(children=[{"ref": 0, "gist": "g" * 25}]), None)
                for i, *_ in items]

    parents = [ParentInput("p_big", [("c1", 0, "word " * 40_000)]),
               ParentInput("p_ok", [("c2", 0, "small text here")])]
    out = compile_parents(complete, parents, BOUNDS,
                          input_token_ceiling=6000)
    assert out[0].status == "INVALID"
    assert out[0].error_class == "ENRICH_INPUT_OVER_CEILING"
    assert all(i[0] != "p_big" for i in calls)      # never sent
    assert out[1].status == "READY"
    assert out[1].child_ref_map == {0: "c2"}        # worker owns the map


def test_compiler_transport_error_and_silence_are_durable():
    def complete(items):
        return [(items[0][0], "", "LIMITER_REFUSED")]   # second item silent

    parents = [ParentInput("p1", [("c1", 0, "text one here now")]),
               ParentInput("p2", [("c2", 0, "text two here now")])]
    out = compile_parents(complete, parents, BOUNDS, 6000)
    assert out[0].status == "INVALID" and out[0].error_class == "LIMITER_REFUSED"
    assert out[1].status == "INVALID" and out[1].error_class == "ENRICH_NO_RESPONSE"


def test_semantic_failover_one_retry_only():
    from polymath_shared.latent.compiler import (
        compile_with_semantic_failover,
    )
    calls = {"a": 0, "b": 0}

    def lane_a(items):
        calls["a"] += len(items)
        return [(i, "utter garbage not json", None) for i, *_ in items]

    def lane_b(items):
        calls["b"] += len(items)
        return [(i, _payload(children=[
            {"ref": 0, "gist": "Recovered gist from the other lane."}]), None)
            for i, *_ in items]

    parents = [ParentInput("p1", [("c1", 0, "some source text here")])]
    out, recovered = compile_with_semantic_failover(
        lane_a, lane_b, parents, BOUNDS, 6000)
    assert recovered == 1 and out[0].status == "READY"
    assert calls == {"a": 1, "b": 1}            # exactly one cross-lane retry

    # both lanes garbage -> typed failure carrying BOTH dispositions
    out2, rec2 = compile_with_semantic_failover(
        lane_a, lane_a, parents, BOUNDS, 6000)
    assert rec2 == 0 and out2[0].status == "INVALID"
    assert "primary=ENRICH_UNPARSEABLE" in out2[0].detail


def test_minimal_gate_accepts_and_rejects():
    from polymath_shared.latent.gate import sanitize_minimal_enrichment
    good = ('{"abstraction": "Automated policies migrate resources '
            'between cost tiers as their value decays over time.", '
            '"transfer": "Applies to caches, archives and staffing '
            'rotations."}')
    gate, out = sanitize_minimal_enrichment(good, BOUNDS)
    assert gate.ok and out.abstraction.startswith("Automated")
    assert out.mechanisms and "caches" in out.mechanisms[0]
    assert out.children == [] and out.summary == ""
    from polymath_shared.latent.gate import transfer_text
    assert transfer_text(out).startswith("Mechanisms: Applies to")
    bad, _ = sanitize_minimal_enrichment('{"abstraction": "too short",'
                                         ' "transfer": "x"}', BOUNDS)
    assert not bad.ok and bad.error_class == "ENRICH_EMPTY"
    junk, _ = sanitize_minimal_enrichment("not json", BOUNDS)
    assert not junk.ok and junk.error_class == "ENRICH_UNPARSEABLE"


def test_hard_case_escape_recovers_on_minimal_contract():
    from polymath_shared.latent.compiler import (
        MINIMAL_CONTRACT,
        compile_with_hard_case_escape,
    )

    def garbage(items):
        return [(i, "utter garbage", None) for i, *_ in items]

    def minimal_ok(items):
        return [(i, '{"abstraction": "Everything decays toward the '
                    'cheapest tier that still meets its access needs.", '
                    '"transfer": "Applies to storage, staffing and '
                    'inventory."}', None) for i, *_ in items]

    parents = [ParentInput("p1", [("c1", 0, "some source text here")])]
    out, fo, rec, term = compile_with_hard_case_escape(
        garbage, garbage, minimal_ok, parents, BOUNDS, 6000)
    assert rec == 1 and term == 0
    assert out[0].status == "READY"
    assert out[0].contract == MINIMAL_CONTRACT      # never masquerades


def test_hard_case_terminal_after_three_lanes():
    from polymath_shared.latent.compiler import (
        compile_with_hard_case_escape,
    )
    from polymath_shared.latent.gate import SEMANTIC_FAILOVER_INELIGIBLE

    def garbage(items):
        return [(i, "junk", None) for i, *_ in items]

    parents = [ParentInput("p1", [("c1", 0, "some source text here")])]
    out, _, rec, term = compile_with_hard_case_escape(
        garbage, garbage, garbage, parents, BOUNDS, 6000)
    assert rec == 0 and term == 1
    assert out[0].status == "INVALID"
    assert out[0].error_class == "ENRICH_HARD_CASE"
    assert "escape=" in out[0].detail
    # terminal by row-truth: sweeps must stop retrying this class
    assert "ENRICH_HARD_CASE" in SEMANTIC_FAILOVER_INELIGIBLE


def test_hard_case_escape_never_fires_for_source_conditions():
    from polymath_shared.latent.compiler import (
        compile_with_hard_case_escape,
    )
    calls = []

    def ok(items):
        return [(i, _payload(children=[{"ref": 0, "gist": "g" * 25}]),
                 None) for i, *_ in items]

    def escape(items):
        calls.extend(items)
        return []

    parents = [ParentInput("p_big", [("c1", 0, "word " * 40_000)]),
               ParentInput("p_ok", [("c2", 0, "small text here")])]
    out, _, rec, term = compile_with_hard_case_escape(
        ok, ok, escape, parents, BOUNDS, 6000)
    assert out[0].error_class == "ENRICH_INPUT_OVER_CEILING"
    assert not calls and rec == 0 and term == 0
    assert out[1].status == "READY"


def test_source_conditions_never_failover():
    from polymath_shared.latent.compiler import (
        compile_with_semantic_failover,
    )
    fb_calls = []

    def lane_a(items):
        return [(i, _payload(children=[
            {"ref": 0, "gist": "fine gist for the small one."}]), None)
            for i, *_ in items]

    def lane_b(items):
        fb_calls.extend(items)
        return []

    parents = [ParentInput("p_big", [("c1", 0, "word " * 40_000)]),
               ParentInput("p_ok", [("c2", 0, "small source text")])]
    out, recovered = compile_with_semantic_failover(
        lane_a, lane_b, parents, BOUNDS, 6000)
    assert out[0].error_class == "ENRICH_INPUT_OVER_CEILING"
    assert not fb_calls                          # bad source: no retry
    assert out[1].status == "READY" and recovered == 0

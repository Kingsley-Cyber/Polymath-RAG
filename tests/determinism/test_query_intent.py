"""QUERY-INTENT-V1 — deterministic intent classification, checked against the plan's own
worked examples (FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 §15–§32) and the tricky precedences.
Pure; no store, no LLM."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "shared",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dataclasses import dataclass  # noqa: E402

from polymath_shared.query_intent import (  # noqa: E402
    INTENT_POLICY,
    INTENTS,
    apply_intent_policy,
    classify_intent,
    intent_of_plan,
    policy_for,
)


@dataclass(frozen=True)
class _FakeBudget:
    dualread_enabled: bool = False
    latent_enabled: bool = False
    atom_kinds: tuple = ()
    other: int = 7  # an unrelated field must be preserved


def test_intent_policy_covers_every_intent():
    assert set(INTENT_POLICY) == set(INTENTS)


def test_apply_intent_policy_sets_the_additive_lanes():
    # MECHANISM → both additive lanes on; EXACT → spine on, latent off (§33).
    b = apply_intent_policy("MECHANISM", _FakeBudget())
    assert b.dualread_enabled is True and b.latent_enabled is True and b.other == 7
    e = apply_intent_policy("EXACT", _FakeBudget())
    assert e.dualread_enabled is True and e.latent_enabled is False
    d = apply_intent_policy("DEFINITION", _FakeBudget())
    assert d.latent_enabled is False


def test_apply_intent_policy_sets_atom_kinds_per_intent():
    # EXACT searches no atoms; MECHANISM the mechanism kinds; EXPLORATORY all 10.
    assert apply_intent_policy("EXACT", _FakeBudget()).atom_kinds == ()
    mech = apply_intent_policy("MECHANISM", _FakeBudget()).atom_kinds
    assert set(mech) == {"THEORY", "CONCEPT", "LATENT_PATTERN", "BOUNDARY"}
    assert len(apply_intent_policy("EXPLORATORY", _FakeBudget()).atom_kinds) == 10
    assert "SEEALSO" in apply_intent_policy("RELATIONSHIP", _FakeBudget()).atom_kinds


def test_apply_intent_policy_unknown_intent_is_identity():
    b = _FakeBudget(dualread_enabled=False, latent_enabled=True)
    assert apply_intent_policy("NOPE", b) is b
    assert apply_intent_policy("", b) is b


def test_policy_for_is_case_insensitive():
    assert policy_for("mechanism") is policy_for("MECHANISM")
    assert policy_for("bogus") is None


def test_plan_worked_examples():
    # (query, kwargs, expected) — drawn from the plan's own §15–§32 examples.
    cases = [
        ("What is AU21?", {"exact_terms": ["AU21"]}, "EXACT"),
        ("What does code 021 return?", {"exact_terms": ["021"]}, "EXACT"),
        ("Tell me about CVE-2026-1234", {"exact_terms": ["CVE-2026-1234"]}, "EXACT"),
        ("What is FACS?", {"exact_terms": ["FACS"]}, "DEFINITION"),          # acronym, no digit → concept
        ("Define anticipation", {}, "DEFINITION"),
        ("Why does this punch look weak?", {}, "MECHANISM"),
        ("How does weight affect perceived impact?", {}, "MECHANISM"),
        ("How are FACS and perceived punch impact connected?", {"graph_useful": True}, "RELATIONSHIP"),
        ("What is the connection between anticipation and force?", {}, "RELATIONSHIP"),
        ("Compare Laban effort qualities and FACS", {}, "COMPARISON"),
        ("Anticipation versus follow-through", {}, "COMPARISON"),
        ("How do I animate a punch convincingly?", {}, "PROCEDURE"),
        ("Steps to rig a facial control", {}, "PROCEDURE"),
        ("Create a prompt for a character whose face was just punched.",
         {"task_type": "CREATE_FROM_KNOWLEDGE", "response_type": "artifact"}, "APPLICATION"),
        ("What do my books say about why movement feels powerful?",
         {"task_type": "GROUNDED_SYNTHESIS"}, "SYNTHESIS"),
        ("Summarize the anatomy book", {}, "SYNTHESIS"),
        ("There was something in my books about systems getting worse when everyone optimizes their own part.",
         {}, "RECALL"),
        ("Tell me something surprising about facial movement", {}, "EXPLORATORY"),
    ]
    for q, kw, expected in cases:
        got = classify_intent(q, **kw)
        assert got == expected, f"{q!r} → {got}, expected {expected}"


def test_synthesis_outranks_embedded_mechanism():
    # "what do my books say about WHY …" must be SYNTHESIS, not MECHANISM (§30 vs §17).
    assert classify_intent("What do my books say about why movement feels powerful?") == "SYNTHESIS"


def test_exact_requires_identifier_like_term_not_bare_acronym():
    assert classify_intent("What is AU21?", exact_terms=["AU21"]) == "EXACT"        # digit → identifier
    assert classify_intent("What is FACS?", exact_terms=["FACS"]) == "DEFINITION"   # bare acronym → concept


def test_exact_yields_to_relational_and_procedural_shapes():
    # an identifier present but the question is relational / procedural → not EXACT.
    assert classify_intent("How does AU21 relate to AU12?", exact_terms=["AU21", "AU12"],
                           graph_useful=True) == "RELATIONSHIP"
    assert classify_intent("How do I use AU21 in a rig?", exact_terms=["AU21"]) == "PROCEDURE"


def test_qtype_signals_drive_intent_without_lexical_cues():
    assert classify_intent("the impact question", qtypes=["PRIMARY", "COMPARISON"]) == "COMPARISON"
    assert classify_intent("the impact question", qtypes=["PRIMARY", "MECHANISM"]) == "MECHANISM"
    assert classify_intent("the impact question", qtypes=["PRIMARY", "BRIDGE"]) == "RELATIONSHIP"


def test_always_returns_a_valid_intent():
    for q in ("", "   ", "asdf qwer", "movement"):
        assert classify_intent(q) in INTENTS


def test_intent_of_plan_duck_typed():
    class _Q:
        def __init__(self, t):
            self.type = t

    class _Plan:
        resolved_request = "How are FACS and impact connected?"
        original_request = "..."
        task_type = "GROUNDED_QA"
        queries = [_Q("PRIMARY"), _Q("BRIDGE")]
        graph_useful = True
        exact_terms = ["FACS"]
        entities = ["FACS"]
        response_type = "answer"

    assert intent_of_plan(_Plan()) == "RELATIONSHIP"


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

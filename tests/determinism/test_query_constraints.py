"""CONSTRAINT-AWARE-RETRIEVAL-V1 (CA0) — deterministic explicit-constraint detection.

Proves detection precision on the named-source failures + the control classes, the strength
model (relationship, not proper-noun presence), the bare-mention correction, and the
ChatPlan wiring + JSON round-trip. Pure shared/ — executed path is this worktree's code.
"""
import json
import pathlib
import sys
from dataclasses import asdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.query_constraints import (  # noqa: E402
    Constraint, CONSTRAINT_STRENGTHS, detect_explicit_constraints)


def _one(q):
    cs = detect_explicit_constraints(q)
    assert len(cs) == 1, f"{q!r} -> {cs}"
    return cs[0]


# --- HARD attribution: the three named-source failures the diagnosis motivates -------------
def test_hard_in_authors_book():
    c = _one("In Walter Murch's book, what is the blink theory of editing?")
    assert (c.kind, c.strength) == ("SOURCE", "HARD")
    assert c.value == "Walter Murch"


def test_hard_what_does_x_say():
    c = _one("What does Sidney Lumet say about making movies and working with actors?")
    assert c.strength == "HARD"
    assert c.value == "Sidney Lumet"


def test_hard_named_method_structure():
    c = _one("What are the fifteen beats in the Save the Cat story structure?")
    assert c.strength == "HARD"
    assert c.value == "Save the Cat"


def test_hard_according_to():
    assert _one("According to Bordwell, how does continuity editing work?").strength == "HARD"


# --- strength from the RELATIONSHIP, not the proper noun (D4) --------------------------------
def test_soft_lens_framing():
    c = _one("Using Murch as a lens, how should we think about pacing?")
    assert c.strength == "SOFT" and c.value == "Murch"


def test_exploratory_framing():
    c = _one("Starting from Murch, what other ideas connect to attention?")
    assert c.strength == "EXPLORATORY" and c.value == "Murch"


def test_bare_mention_is_not_hard():
    # owner correction: a bare author mention is NOT automatically a HARD constraint
    assert detect_explicit_constraints("Murch, editing rhythm, and attention") == []


# --- control classes must stay clean (no fabricated constraint) ------------------------------
def test_control_no_named_source():
    assert detect_explicit_constraints("What is the blink theory of editing?") == []


def test_control_exploratory_topic():
    assert detect_explicit_constraints("How do rhythm and timing connect film editing and music?") == []


def test_control_unsupported_topic():
    # "Python" is a proper noun but not a source reference — must not fire
    assert detect_explicit_constraints("How do I reverse a linked list in Python?") == []


def test_control_plain_definition():
    assert detect_explicit_constraints("What is depth of field?") == []


# --- contract hygiene ----------------------------------------------------------------------
def test_invalid_strength_never_asserts_hard():
    assert Constraint(kind="SOURCE", value="X", strength="BOGUS").strength == "SOFT"
    assert Constraint(kind="BOGUS", value="X", strength="HARD").kind == "SOURCE"


def test_strength_vocabulary():
    for q in ("According to X say", "Using X as a lens", "Starting from X"):
        for c in detect_explicit_constraints(q):
            assert c.strength in CONSTRAINT_STRENGTHS


def test_json_roundtrip_stable():
    c = _one("In Walter Murch's book, what is the blink theory?")
    d = asdict(c)
    again = json.loads(json.dumps(d))
    assert again["resolved_targets"] == [] and again["value"] == "Walter Murch"


# --- ChatPlan wiring: explicit_constraints is populated deterministically --------------------
def test_fallback_plan_populates_constraints():
    from polymath_shared.chat_plan import fallback_plan
    plan = fallback_plan("What does Sidney Lumet say about actors?", reason="test")
    assert len(plan.explicit_constraints) == 1
    assert plan.explicit_constraints[0].strength == "HARD"
    # JSON-native: to_dict round-trips through the receipt
    again = json.loads(json.dumps(plan.to_dict()))
    assert again["explicit_constraints"][0]["value"] == "Sidney Lumet"


def test_fallback_plan_no_constraint_is_empty_list():
    from polymath_shared.chat_plan import fallback_plan
    plan = fallback_plan("What is depth of field?", reason="test")
    assert plan.explicit_constraints == []

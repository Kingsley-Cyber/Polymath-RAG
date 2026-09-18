"""CONSTRAINT-AWARE-RETRIEVAL-V1 (CA1) — deterministic SOURCE-identity resolution.

Proves a CA0 SOURCE constraint resolves to the correct corpus doc_id by IDENTITY (not semantic
search): known sources against the real cinema docmap, relationship-strength preservation, exact
title beats a mention, ambiguity -> unresolved, missing -> fail-open, corpus isolation, bounded
Scout confirmation, and JSON/determinism. Pure shared/ — executed path is this worktree.
"""
import json
import pathlib
import sys
from dataclasses import asdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.query_constraints import (  # noqa: E402
    Constraint, detect_explicit_constraints, resolve_constraint_targets)

_DOCMAP = json.loads((ROOT / "eval/librarian_qualification/cinema_docmap.json").read_text())
CINEMA = dict(_DOCMAP)                                    # {doc_id: source_name}, corpus-scoped


def _docid(substr: str) -> str:
    return next(d for d, s in CINEMA.items() if substr in s)


def _resolve_one(query: str, index=CINEMA, scout=None):
    cs = resolve_constraint_targets(detect_explicit_constraints(query), index, scout_nominations=scout)
    assert len(cs) == 1
    return cs[0]


# --- known named sources resolve to the right cinema doc ------------------------------------
def test_resolves_murch():
    c = _resolve_one("In Walter Murch's book, what is the blink theory of editing?")
    assert c.resolved_targets == [_docid("Walter Murch")]
    assert c.confidence >= 0.85


def test_resolves_save_the_cat():
    c = _resolve_one("What are the fifteen beats in the Save the Cat story structure?")
    assert c.resolved_targets == [_docid("Save the Cat")]


def test_resolves_lumet():
    c = _resolve_one("What does Sidney Lumet say about making movies and working with actors?")
    assert c.resolved_targets == [_docid("Sidney Lumet - Making Movies")]


def test_resolves_by_surname_only():
    c = _resolve_one("According to Murch, how does editing rhythm work?")
    assert c.resolved_targets == [_docid("Walter Murch")]


# --- relationship strength is preserved through resolution (CA1 resolves identity only) -------
def test_strength_preserved_hard():
    assert _resolve_one("What does Murch say about attention?").strength == "HARD"


def test_strength_preserved_soft():
    c = _resolve_one("Using Murch as a lens, how should we think about pacing?")
    assert c.strength == "SOFT" and c.resolved_targets == [_docid("Walter Murch")]


def test_strength_preserved_exploratory():
    c = _resolve_one("Starting from Murch, what ideas connect to attention?")
    assert c.strength == "EXPLORATORY" and c.resolved_targets == [_docid("Walter Murch")]


def test_value_and_reason_unchanged():
    detected = detect_explicit_constraints("According to Murch, why cut?")[0]
    resolved = resolve_constraint_targets([detected], CINEMA)[0]
    assert resolved.value == detected.value and resolved.reason == detected.reason
    assert resolved.kind == "SOURCE"


# --- title identity: the title itself, not a doc that merely mentions the title ---------------
def test_exact_title_beats_mention():
    idx = {"docExact": "Save the Cat.md", "docMention": "Notes about the Save the Cat structure.md"}
    c = resolve_constraint_targets(
        [Constraint(kind="SOURCE", value="Save the Cat", strength="HARD")], idx)[0]
    assert c.resolved_targets == ["docExact"]


# --- ambiguity does not silently guess -------------------------------------------------------
def test_ambiguous_author_unresolved():
    idx = {"docA": "Jane Doe - Book Alpha.md", "docB": "Jane Doe - Book Beta.md"}
    c = resolve_constraint_targets(
        [Constraint(kind="SOURCE", value="Jane Doe", strength="HARD")], idx)[0]
    assert c.resolved_targets == [] and c.confidence == 0.0


def test_ambiguity_scout_does_not_break_identity_tie():
    idx = {"docA": "Jane Doe - Book Alpha.md", "docB": "Jane Doe - Book Beta.md"}
    c = resolve_constraint_targets(
        [Constraint(kind="SOURCE", value="Jane Doe", strength="HARD")], idx,
        scout_nominations=["docA"])[0]
    assert c.resolved_targets == []            # Scout rank alone must not resolve an identity tie


def test_unique_title_amid_same_author_resolves():
    idx = {"docA": "Jane Doe - Book Alpha.md", "docB": "Jane Doe - Book Beta.md"}
    c = resolve_constraint_targets(
        [Constraint(kind="SOURCE", value="Book Alpha", strength="HARD")], idx)[0]
    assert c.resolved_targets == ["docA"]


# --- missing source stays fail-open ----------------------------------------------------------
def test_missing_source_is_empty_no_exception():
    c = resolve_constraint_targets(
        [Constraint(kind="SOURCE", value="Sigmund Freud", strength="HARD")], CINEMA)[0]
    assert c.resolved_targets == []


# --- corpus isolation: a source not in the active index must not resolve ----------------------
def test_corpus_isolation():
    other_corpus = {"docX": "Some Other Author - A Different Book.md"}
    c = resolve_constraint_targets(
        [Constraint(kind="SOURCE", value="Walter Murch", strength="HARD")], other_corpus)[0]
    assert c.resolved_targets == []


# --- Scout confirmation is bounded to weak lexical identity -----------------------------------
def test_weak_identity_needs_scout_confirmation():
    idx = {"docP": "A Field Guide to Story Craft.md"}
    con = Constraint(kind="SOURCE", value="Story Craft", strength="SOFT")
    assert resolve_constraint_targets([con], idx)[0].resolved_targets == []          # weak, unconfirmed
    ok = resolve_constraint_targets([con], idx, scout_nominations=["docP"])[0]
    assert ok.resolved_targets == ["docP"] and ok.confidence == 0.5                  # weak + Scout-confirmed


# --- non-SOURCE constraints pass through untouched -------------------------------------------
def test_non_source_untouched():
    con = Constraint(kind="SCOPE", value="chapter 3", strength="HARD")
    assert resolve_constraint_targets([con], CINEMA)[0].resolved_targets == []


# --- JSON / determinism ----------------------------------------------------------------------
def test_json_and_determinism_stable():
    q = "In Walter Murch's book, what is the blink theory?"
    a = resolve_constraint_targets(detect_explicit_constraints(q), CINEMA)[0]
    b = resolve_constraint_targets(detect_explicit_constraints(q), CINEMA)[0]
    assert asdict(a) == asdict(b)
    again = json.loads(json.dumps(asdict(a)))
    assert again["resolved_targets"] == a.resolved_targets and again["strength"] == "HARD"

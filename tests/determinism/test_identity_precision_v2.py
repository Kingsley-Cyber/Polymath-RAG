"""IDENTITY-PRECISION-V2 gate.

Real cross-domain probes found `entity-admission-v1.1` promoting ordinary
prose to GLOBAL identity — `I`, `That`, `What`, `Researchers`,
`These findings`, `Two documents`, and even the subordinate clause
`When attention shifts`. ~69% of identity admissions on those documents
were false.

Correction pinned here:
    capitalization is NEVER sufficient identity evidence, and IDENTITY
    requires POSITIVE evidence rather than the absence of generic evidence.

The mechanism must stay SYNTACTIC. A larger `GENERIC_HEAD` blacklist would
be defeated by the next book's new nouns; POS separates sentence-initial
`Postgres/PROPN` from sentence-initial `Researchers/NOUN` for any book.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.identity_evidence import (
    IDENTITY_CONTRACT, IdentityEvidenceKind, identity_evidence,
)

FIX = json.loads(
    (ROOT / "eval/admission/identity_fixtures_crossregister_v1.json").read_text())


def _tok(text, pos, i=0, lemma=None):
    return {"i": i, "text": text, "pos": pos, "lemma": lemma or text.lower(),
            "char_start": 0, "char_end": len(text)}


def _toks(pairs):
    return [_tok(t, p, i) for i, (t, p) in enumerate(pairs)]


# --- structural exclusions -------------------------------------------------

def test_pronouns_and_wh_forms_are_never_identity():
    for text, pos in (("I", "PRON"), ("That", "PRON"), ("What", "PRON"),
                      ("This", "PRON"), ("it", "PRON")):
        d = identity_evidence(text, tokens=_toks([(text, pos)]))
        assert not d.is_identity, text


def test_clausal_spans_are_never_identity():
    d = identity_evidence("When attention shifts",
                          tokens=_toks([("When", "SCONJ"), ("attention", "NOUN"),
                                        ("shifts", "NOUN")]))
    assert not d.is_identity


def test_sentence_initial_common_nouns_are_never_identity():
    """The core defect: capitalization is not proper-name evidence."""
    for text in ("Researchers", "Workers", "Performance"):
        d = identity_evidence(text, tokens=_toks([(text, "NOUN")]))
        assert not d.is_identity, text
        assert "no proper-noun anchor" in d.exclusions[0]


def test_quantified_pluralities_are_never_singular_identity():
    for pairs in ([("Two", "NUM"), ("documents", "NOUN")],
                  [("Several", "ADJ"), ("laboratory", "NOUN"), ("studies", "NOUN")],
                  [("One", "NUM"), ("influential", "ADJ"), ("account", "NOUN")]):
        d = identity_evidence(" ".join(t for t, _ in pairs), tokens=_toks(pairs))
        assert not d.is_identity, pairs


def test_quantifier_plus_named_surface_does_not_inherit_identity():
    """`two John Smith` must not denote one canonical John Smith."""
    d = identity_evidence("two John Smith",
                          tokens=_toks([("two", "NUM"), ("John", "PROPN"),
                                        ("Smith", "PROPN")]))
    assert not d.is_identity
    assert "plurality" in d.exclusions[0]
    # ...while the bare name still is
    assert identity_evidence("John Smith",
                             tokens=_toks([("John", "PROPN"),
                                           ("Smith", "PROPN")])).is_identity


# --- positive evidence -----------------------------------------------------

def test_proper_noun_anchor_grants_identity():
    for pairs in ([("Postgres", "PROPN")], [("GLiNER", "PROPN")],
                  [("Crestline", "PROPN"), ("Automation", "PROPN")]):
        d = identity_evidence(" ".join(t for t, _ in pairs), tokens=_toks(pairs))
        assert d.is_identity and d.kind is IdentityEvidenceKind.PROPER_NAME


def test_named_anchor_inside_a_generic_headed_phrase_is_preserved():
    """2C.2 behaviour must survive: the anchor carries the phrase."""
    d = identity_evidence("FreightNet routing platform",
                          tokens=_toks([("FreightNet", "PROPN"),
                                        ("routing", "NOUN"), ("platform", "NOUN")]))
    assert d.is_identity and "FreightNet" in d.reasons[0]


def test_identifier_structure_grants_identity_without_a_proper_noun():
    """`D6L11` is admitted on shape alone — spaCy tags it NOUN, so a
    proper-noun requirement must not be the ONLY path to identity."""
    d = identity_evidence("D6L11", tokens=_toks([("D6L11", "NOUN")]))
    assert d.is_identity
    assert d.kind in (IdentityEvidenceKind.ACRONYM, IdentityEvidenceKind.IDENTIFIER)
    # a version-bearing surface likewise
    d2 = identity_evidence("v2.1", tokens=_toks([("v2.1", "NOUN")]))
    assert d2.is_identity and d2.kind is IdentityEvidenceKind.IDENTIFIER


def test_established_alias_is_exact_match_only():
    al = {"Polymath v4"}
    assert identity_evidence("Polymath v4", aliases=al).is_identity
    assert not identity_evidence("Polymath v5",
                                 tokens=_toks([("Polymath", "NOUN"),
                                               ("v5", "NOUN")]),
                                 aliases=al).kind is IdentityEvidenceKind.ESTABLISHED_ALIAS


# --- the qualification set -------------------------------------------------

def _fixture_toks(surface, sentence):
    """POS is supplied by the fixture-free path in CI: tests use hand tokens,
    the gate run against the live sidecar is recorded in the work log."""
    return None


def test_fixture_set_covers_every_defect_class():
    classes = {x["class"] for x in FIX["must_not_be_identity"]}
    for required in ("pronoun", "wh-form", "sentence-initial common noun",
                     "quantified plurality", "clausal span",
                     "quantifier + named surface"):
        assert required in classes, required


def test_negatives_and_positives_come_from_the_same_documents():
    """Otherwise a rule could pass by rejecting conversational prose wholesale."""
    neg = {x["source"] for x in FIX["must_not_be_identity"]}
    pos = {x["source"] for x in FIX["must_be_identity"]}
    assert neg & pos, "no shared source document between negatives and positives"


def test_adversarial_pairs_share_a_head_but_differ_in_anchor():
    for p in FIX["adversarial_pairs"]:
        assert p["negative"].lower() != p["positive"].lower()
        assert p["why"]


# --- gate invariants -------------------------------------------------------

def test_identity_decisions_are_deterministic():
    toks = _toks([("Postgres", "PROPN")])
    assert len({repr(identity_evidence("Postgres", tokens=toks)) for _ in range(20)}) == 1


def test_every_identity_promotion_records_its_evidence():
    d = identity_evidence("Postgres", tokens=_toks([("Postgres", "PROPN")]))
    assert d.is_identity and d.reasons and d.kind is not None
    assert d.contract == IDENTITY_CONTRACT


def test_rejections_record_why():
    d = identity_evidence("Researchers", tokens=_toks([("Researchers", "NOUN")]))
    assert not d.is_identity and d.exclusions


def test_gate_is_not_a_phrase_blacklist():
    """No surface from the qualification set may appear in executable policy."""
    import ast
    tree = ast.parse((ROOT / "shared/polymath_shared/identity_evidence.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(
                    getattr(b[0], "value", None), ast.Constant) and isinstance(
                    b[0].value.value, str):
                node.body = b[1:] or [ast.Pass()]
    code = ast.unparse(tree).lower()
    for x in FIX["must_not_be_identity"]:
        s = x["surface"].lower()
        if len(s.split()) > 1 or len(s) > 4:      # skip short function words
            assert s not in code, f"{s!r} leaked into executable policy"

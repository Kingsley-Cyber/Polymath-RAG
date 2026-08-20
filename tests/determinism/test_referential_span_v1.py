"""REFERENTIAL-SPAN-V1 (PHASE 2C.1) integration-repair regressions.

Two invariants are pinned here permanently, both discovered by PHASE 2C:

  1. GLiNER strips determiners; the discourse contract keys on them. The
     envelope must RECOVER the determiner from source text, never
     normalise it away — `system` / `the system` / `this system` /
     `our system` are not referentially equivalent.
  2. Harbor/admission evidence must NEVER be recomputed from a normalized
     (lowercased) surface. Doing so demoted every proper noun and lost
     17/17 facts on the first 2C run.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.entity_admission import decide
from polymath_shared.referential_span import derive

# One syntax-evidence-v1 sentence result, hand-built so the test needs no sidecar.
def _syntax(tokens, chunks):
    return {"tokens": tokens, "noun_chunks": chunks}


def _tok(i, text, cs, lemma=None):
    return {"i": i, "text": text, "char_start": cs, "char_end": cs + len(text),
            "lemma": lemma or text.lower()}


def _case(text, proposal, tokens, chunks):
    st = text.index(proposal)
    return derive(proposal, st, st + len(proposal), text, _syntax(tokens, chunks))


def test_definite_determiner_is_recovered():
    text = "Crestline linked the vision system to the database."
    toks = [_tok(0, "Crestline", 0), _tok(1, "linked", 10), _tok(2, "the", 17),
            _tok(3, "vision", 21), _tok(4, "system", 28)]
    chunks = [{"char_start": 17, "char_end": 34, "text": "the vision system", "root_i": 4}]
    r = _case(text, "vision system", toks, chunks)
    assert r.referential_surface == "the vision system"
    assert r.determiner == "the"
    assert r.proposal_surface == "vision system"        # provenance intact
    assert r.expanded


def test_demonstrative_and_possessive_are_preserved():
    text = "This service handles ranking."
    toks = [_tok(0, "This", 0), _tok(1, "service", 5)]
    chunks = [{"char_start": 0, "char_end": 12, "text": "This service", "root_i": 1}]
    r = _case(text, "service", toks, chunks)
    assert r.referential_surface == "This service" and r.determiner == "This"

    text2 = "We upgraded our recommendation engine."
    toks2 = [_tok(0, "We", 0), _tok(1, "upgraded", 3), _tok(2, "our", 12),
             _tok(3, "recommendation", 16), _tok(4, "engine", 31)]
    chunks2 = [{"char_start": 12, "char_end": 37,
                "text": "our recommendation engine", "root_i": 4}]
    r2 = _case(text2, "recommendation engine", toks2, chunks2)
    assert r2.referential_surface == "our recommendation engine"
    assert r2.determiner == "our"


def test_proposal_surface_is_never_rewritten():
    text = "The pump failure stopped the line."
    toks = [_tok(0, "The", 0), _tok(1, "pump", 4), _tok(2, "failure", 9)]
    chunks = [{"char_start": 0, "char_end": 16, "text": "The pump failure", "root_i": 2}]
    r = _case(text, "pump failure", toks, chunks)
    assert r.referential_surface == "The pump failure"
    assert r.proposal_surface == "pump failure"
    assert (r.proposal_start, r.proposal_end) == (4, 16)


def test_no_expansion_without_head_alignment():
    """Containment alone must not expand — the chunk head must BE the
    proposal head, or the envelope could wander across unrelated material."""
    text = "the vision system operator left."
    toks = [_tok(0, "the", 0), _tok(1, "vision", 4), _tok(2, "system", 11),
            _tok(3, "operator", 18)]
    # chunk contains the proposal but is headed by 'operator', not 'system'
    chunks = [{"char_start": 0, "char_end": 26,
               "text": "the vision system operator", "root_i": 3}]
    r = _case(text, "vision system", toks, chunks)
    assert not r.expanded
    assert r.referential_surface == "vision system"


def test_missing_syntax_fails_closed():
    r = derive("vision system", 0, 13, "vision system runs.", None)
    assert not r.expanded and r.determiner is None
    assert "fail closed" in r.reasons[0]


def test_normalized_surface_must_not_drive_admission():
    """PHASE 2C: the first attribution run lost 17/17 facts by recomputing
    admission from `entities.normalized_surface`. Case is load-bearing."""
    for raw, lowered in (("Oakland", "oakland"),                     # proper name
                         ("Model 3", "model 3"),                     # identifier
                         ("Polymath retrieval system",               # named anchor
                          "polymath retrieval system")):
        a = decide(raw, "Technology", 0.9).reference_class
        b = decide(lowered, "Technology", 0.9).reference_class
        assert a != b, (
            f"{raw!r} and {lowered!r} classify identically — the case-bearing "
            f"evidence this test guards would be undetectable")
        # every case is DEMOTED by lowercasing, never promoted
        order = ["MENTION_ONLY", "DOCUMENT_SCOPED", "CORPUS_SCOPED", "GLOBAL"]
        assert order.index(b) < order.index(a), f"{raw!r} {a} -> {lowered!r} {b}"


def test_determiners_are_not_referentially_equivalent():
    """Normalising determiners away would undo PHASE 2B."""
    variants = ["system", "the system", "this system", "our system"]
    assert len({v for v in variants}) == 4
    # and the envelope keeps them distinct rather than collapsing to the head
    text = "our system failed."
    toks = [_tok(0, "our", 0), _tok(1, "system", 4)]
    chunks = [{"char_start": 0, "char_end": 10, "text": "our system", "root_i": 1}]
    r = _case(text, "system", toks, chunks)
    assert r.referential_surface == "our system" != r.proposal_surface

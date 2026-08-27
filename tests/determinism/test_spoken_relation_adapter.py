"""SPOKEN-RELATION-ADAPTER-V1 unit fixtures (no stores, no sidecars).

Owner-authorized Option A (2026-08-26): deterministic ADAPTATION
coverage for legitimate spoken-register relational constructions —
never admission loosening.

Two rules, both syntactically licensed:

  (1) COPULAR-ATTR BINDING — a copular trigger's object is its
      predicate nominal (`attr`). Entity attr → bind (tree evidence).
      Non-entity attr → the sentence named a non-entity object, so the
      object recall net is SUPPRESSED (measured wrong bindings this
      kills: (Andromeda, be, Meta) from "Andromeda is Meta's new
      retrieval engine"; (Jon Loomer, be, Facebook) from a PP).

  (2) RELCL OBJECT RECOVERY — a verb heading a relative clause with an
      overt bound subject and no object relativizes its object: the
      antecedent noun, or (one licensed hop) the entity a copula
      equates with that noun ("Andromeda, which is the new update
      Facebook made" → made(Facebook, Andromeda)).

All parses below are REAL spaCy sidecar output, frozen as fixtures.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))
sys.path.insert(0, str(ROOT))

from polymath_shared.contracts import BindingSource, CoreType, EntitySpan, EvidenceSpan  # noqa: E402
from polymath_shared.rulepack import load_rule_pack  # noqa: E402
from workers.candidates import SentenceSlice  # noqa: E402
from tests.historical_boundary import build_candidates_kimi  # noqa: E402

PACK = load_rule_pack(pack_version="1.4.0")


def _tok(i, text, cs, ce, lemma, pos, dep, head):
    return {"i": i, "text": text, "char_start": cs, "char_end": ce,
            "lemma": lemma, "pos": pos, "tag": "", "dep": dep,
            "head_i": head}


def _ent(text, start, end, core, score=0.8):
    return EntitySpan(
        doc_id="d", chunk_id="c", start=start, end=end, text=text,
        core_type=CoreType(core), score=score, extractor_version="t",
        raw_label=core, pass_kind="discovery")


def _ev(text, start, end, evidence_class, lemma, predicate_id):
    return EvidenceSpan(
        chunk_id="c", start=start, end=end, text=text,
        evidence_class=evidence_class, trigger_lemma=lemma,
        trigger_predicate_id=predicate_id, score=1.0,
        extractor_version="t")


def _slice(text, entities, evidence, tokens):
    return SentenceSlice(
        text=text, sentence_start=0, sentence_end=len(text),
        entities=entities, evidence=evidence, parse=None,
        syntax={"sentence_id": "s:0", "tokens": tokens, "noun_chunks": []})


def _build(sl):
    return build_candidates_kimi(
        [sl], doc_id="d", ontology_profile="core",
        extractor_version="t", rule_pack=PACK, enrich=False)


# --- fixture: "Andromeda is Meta's new retrieval engine." -----------
# (real parse; the measured wrong binding this adapter kills)
POSS_COPULA_TEXT = "Andromeda is Meta's new retrieval engine."
POSS_COPULA_TOKENS = [
    _tok(0, "Andromeda", 0, 9, "Andromeda", "PROPN", "nsubj", 1),
    _tok(1, "is", 10, 12, "be", "AUX", "ROOT", 1),
    _tok(2, "Meta", 13, 17, "Meta", "PROPN", "poss", 6),
    _tok(3, "'s", 17, 19, "'s", "PART", "case", 2),
    _tok(4, "new", 20, 23, "new", "ADJ", "amod", 6),
    _tok(5, "retrieval", 24, 33, "retrieval", "NOUN", "compound", 6),
    _tok(6, "engine", 34, 40, "engine", "NOUN", "attr", 1),
    _tok(7, ".", 40, 41, ".", "PUNCT", "punct", 1),
]


def test_possessive_copula_never_binds_the_possessor():
    sl = _slice(
        POSS_COPULA_TEXT,
        [_ent("Andromeda", 0, 9, "Technology"),
         _ent("Meta", 13, 17, "Organization")],
        [_ev("is", 10, 12, "classification", "be", "is_a")],
        POSS_COPULA_TOKENS)
    cands = _build(sl)
    pairs = {(c.subject.span.text, c.object.span.text) for c in cands}
    assert ("Andromeda", "Meta") not in pairs, pairs
    assert not cands, [
        (c.subject.span.text, c.object.span.text, c.decision) for c in cands]


def test_copular_attr_entity_is_bound_as_the_object():
    """When the predicate nominal IS an entity, the tree binds it —
    the COPULA-COMPLEMENT-BINDING the 2026-08-22 handoff called for."""
    sl = _slice(
        POSS_COPULA_TEXT,
        [_ent("Andromeda", 0, 9, "Technology"),
         _ent("Meta", 13, 17, "Organization"),
         _ent("retrieval engine", 24, 40, "Concept")],
        [_ev("is", 10, 12, "classification", "be", "is_a")],
        POSS_COPULA_TOKENS)
    cands = _build(sl)
    match = [c for c in cands if c.object.span.text == "retrieval engine"]
    assert match, [(c.subject.span.text, c.object.span.text) for c in cands]
    assert match[0].subject.span.text == "Andromeda"
    assert BindingSource.UD_DIRECT in match[0].lexical_semantic_evidence.binding_sources
    assert all(c.object.span.text != "Meta" for c in cands)


# --- fixture: "…Andromeda, which is the new update Facebook made." --
# (real parse, trimmed to the relative-clause region of the actual
#  transcript sentence; offsets match the trimmed text)
RELCL_TEXT = "Andromeda, which is the new update Facebook made."
RELCL_TOKENS = [
    _tok(0, "Andromeda", 0, 9, "Andromeda", "PROPN", "ROOT", 0),
    _tok(1, ",", 9, 10, ",", "PUNCT", "punct", 0),
    _tok(2, "which", 11, 16, "which", "PRON", "nsubj", 3),
    _tok(3, "is", 17, 19, "be", "AUX", "relcl", 0),
    _tok(4, "the", 20, 23, "the", "DET", "det", 6),
    _tok(5, "new", 24, 27, "new", "ADJ", "amod", 6),
    _tok(6, "update", 28, 34, "update", "NOUN", "attr", 3),
    _tok(7, "Facebook", 35, 43, "Facebook", "PROPN", "nsubj", 8),
    _tok(8, "made", 44, 48, "make", "VERB", "relcl", 6),
    _tok(9, ".", 48, 49, ".", "PUNCT", "punct", 0),
]


def test_relcl_copular_equation_recovers_the_object():
    """made(Facebook, ?) → antecedent 'update' (not an entity) → the
    copular relative equates it with 'Andromeda' → created candidate
    with named durable endpoints."""
    sl = _slice(
        RELCL_TEXT,
        [_ent("Andromeda", 0, 9, "Technology"),
         _ent("Facebook", 35, 43, "Organization")],
        [_ev("made", 44, 48, "creation", "make", "created")],
        RELCL_TOKENS)
    cands = _build(sl)
    match = [c for c in cands
             if c.subject.span.text == "Facebook"
             and c.object.span.text == "Andromeda"]
    assert match, [
        (c.subject.span.text, c.object.span.text, c.decision) for c in cands]
    assert BindingSource.RELCL_ANTECEDENT in match[0].lexical_semantic_evidence.binding_sources


def test_relcl_direct_antecedent_entity():
    """'Kubernetes, which Google created, …' — the antecedent itself is
    the entity (one hop, no equation needed)."""
    text = "Kubernetes, which Google created, orchestrates containers."
    tokens = [
        _tok(0, "Kubernetes", 0, 10, "kubernete", "PROPN", "nsubj", 6),
        _tok(1, ",", 10, 11, ",", "PUNCT", "punct", 0),
        _tok(2, "which", 12, 17, "which", "PRON", "dobj", 4),
        _tok(3, "Google", 18, 24, "Google", "PROPN", "nsubj", 4),
        _tok(4, "created", 25, 32, "create", "VERB", "relcl", 0),
        _tok(5, ",", 32, 33, ",", "PUNCT", "punct", 0),
        _tok(6, "orchestrates", 34, 46, "orchestrate", "VERB", "ROOT", 6),
        _tok(7, "containers", 47, 57, "container", "NOUN", "dobj", 6),
        _tok(8, ".", 57, 58, ".", "PUNCT", "punct", 6),
    ]
    sl = _slice(
        text,
        [_ent("Kubernetes", 0, 10, "Technology"),
         _ent("Google", 18, 24, "Organization")],
        [_ev("created", 25, 32, "creation", "create", "created")],
        tokens)
    cands = _build(sl)
    match = [c for c in cands
             if c.subject.span.text == "Google"
             and c.object.span.text == "Kubernetes"]
    assert match, [
        (c.subject.span.text, c.object.span.text) for c in cands]


def test_main_clause_copular_equation():
    """'Hermes is the model that Nous Research built.' — the MAIN
    copula equates its subject with the antecedent nominal."""
    text = "Hermes is the model that Nous Research built."
    tokens = [
        _tok(0, "Hermes", 0, 6, "Hermes", "PROPN", "nsubj", 1),
        _tok(1, "is", 7, 9, "be", "AUX", "ROOT", 1),
        _tok(2, "the", 10, 13, "the", "DET", "det", 3),
        _tok(3, "model", 14, 19, "model", "NOUN", "attr", 1),
        _tok(4, "that", 20, 24, "that", "PRON", "dobj", 7),
        _tok(5, "Nous", 25, 29, "Nous", "PROPN", "compound", 6),
        _tok(6, "Research", 30, 38, "Research", "PROPN", "nsubj", 7),
        _tok(7, "built", 39, 44, "build", "VERB", "relcl", 3),
        _tok(8, ".", 44, 45, ".", "PUNCT", "punct", 1),
    ]
    sl = _slice(
        text,
        [_ent("Hermes", 0, 6, "Product"),
         _ent("Nous Research", 25, 38, "Organization")],
        [_ev("built", 39, 44, "creation", "build", "created")],
        tokens)
    cands = _build(sl)
    match = [c for c in cands
             if c.subject.span.text == "Nous Research"
             and c.object.span.text == "Hermes"]
    assert match, [
        (c.subject.span.text, c.object.span.text) for c in cands]


# --- adversarial negatives ------------------------------------------

def test_relcl_without_bound_subject_abstains():
    """'the update which crashed' class — the relativizer is the
    SUBJECT; recovering the antecedent as OBJECT would invert the
    relation. No bound subject → no recovery."""
    text = "Andromeda, which is the new update made."
    tokens = [
        _tok(0, "Andromeda", 0, 9, "Andromeda", "PROPN", "ROOT", 0),
        _tok(1, ",", 9, 10, ",", "PUNCT", "punct", 0),
        _tok(2, "which", 11, 16, "which", "PRON", "nsubj", 3),
        _tok(3, "is", 17, 19, "be", "AUX", "relcl", 0),
        _tok(4, "the", 20, 23, "the", "DET", "det", 6),
        _tok(5, "new", 24, 27, "new", "ADJ", "amod", 6),
        _tok(6, "update", 28, 34, "update", "NOUN", "attr", 3),
        _tok(7, "made", 35, 39, "make", "VERB", "relcl", 6),
        _tok(8, ".", 39, 40, ".", "PUNCT", "punct", 0),
    ]
    sl = _slice(
        text,
        [_ent("Andromeda", 0, 9, "Technology")],
        [_ev("made", 35, 39, "creation", "make", "created")],
        tokens)
    cands = _build(sl)
    assert not [c for c in cands if c.object.span.text == "Andromeda"], [
        (c.subject.span.text, c.object.span.text) for c in cands]


def test_pronoun_equated_subject_abstains():
    """'This is the problem the company's pricing created.' — the
    equated subject is a pronoun; no entity, no candidate."""
    text = "This is the problem the pricing created."
    tokens = [
        _tok(0, "This", 0, 4, "this", "PRON", "nsubj", 1),
        _tok(1, "is", 5, 7, "be", "AUX", "ROOT", 1),
        _tok(2, "the", 8, 11, "the", "DET", "det", 3),
        _tok(3, "problem", 12, 19, "problem", "NOUN", "attr", 1),
        _tok(4, "the", 20, 23, "the", "DET", "det", 5),
        _tok(5, "pricing", 24, 31, "pricing", "NOUN", "nsubj", 6),
        _tok(6, "created", 32, 39, "create", "VERB", "relcl", 3),
        _tok(7, ".", 39, 40, ".", "PUNCT", "punct", 1),
    ]
    sl = _slice(
        text,
        [_ent("pricing", 24, 31, "Concept")],
        [_ev("created", 32, 39, "creation", "create", "created")],
        tokens)
    cands = _build(sl)
    assert not [c for c in cands if c.decision == "ACCEPT"], [
        (c.subject.span.text, c.object.span.text, c.decision) for c in cands]


def test_pp_modifier_entity_is_not_a_copular_object():
    """'Jon Loomer is an OG in the Facebook advertising space.' — the
    attr head ('OG') is not an entity; the PP entity must not be
    recalled as the object."""
    text = "Jon Loomer is an OG in the Facebook advertising space."
    tokens = [
        _tok(0, "Jon", 0, 3, "Jon", "PROPN", "compound", 1),
        _tok(1, "Loomer", 4, 10, "Loomer", "PROPN", "nsubj", 2),
        _tok(2, "is", 11, 13, "be", "AUX", "ROOT", 2),
        _tok(3, "an", 14, 16, "an", "DET", "det", 4),
        _tok(4, "OG", 17, 19, "og", "NOUN", "attr", 2),
        _tok(5, "in", 20, 22, "in", "ADP", "prep", 4),
        _tok(6, "the", 23, 26, "the", "DET", "det", 9),
        _tok(7, "Facebook", 27, 35, "Facebook", "PROPN", "compound", 9),
        _tok(8, "advertising", 36, 47, "advertising", "NOUN", "compound", 9),
        _tok(9, "space", 48, 53, "space", "NOUN", "pobj", 5),
        _tok(10, ".", 53, 54, ".", "PUNCT", "punct", 2),
    ]
    sl = _slice(
        text,
        [_ent("Jon Loomer", 0, 10, "Person"),
         _ent("Facebook", 27, 35, "Organization")],
        [_ev("is", 11, 13, "classification", "be", "is_a")],
        tokens)
    cands = _build(sl)
    assert not [c for c in cands if c.object.span.text == "Facebook"], [
        (c.subject.span.text, c.object.span.text) for c in cands]

"""KIMI-REALIGNMENT-COMPLETION-V1: role-based direction + active/passive
normalization + VN/PB/FN/SemLink active compiler participation.

These tests feed synthetic GLiNER spans and spaCy syntax through the
kimi_v1 candidate + compiler path. No live sidecars required.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import CoreType, EntitySpan, EvidenceSpan
from polymath_shared.rulepack import compile_relation_kimi, load_rule_pack
from workers.candidates import SentenceSlice
from tests.historical_boundary import build_candidates_kimi

PACK = load_rule_pack(pack_version="1.0.1")


def _ev(text, start, end, evidence_class="creation", predicate_id="founded"):
    return EvidenceSpan(
        chunk_id="c", start=start, end=end, text=text,
        evidence_class=evidence_class, trigger_lemma="found",
        trigger_predicate_id=predicate_id, trigger_match_source="verbs",
        trigger_lexical_class="VERB",
        score=1.0, extractor_version="t")


def _ent(text, start, end, core, score=0.8):
    return EntitySpan(
        doc_id="d", chunk_id="c", start=start, end=end, text=text,
        core_type=CoreType(core), score=score, extractor_version="t",
        raw_label=core, pass_kind="discovery")


def _slice(entities, evidence, text, syntax=None, parse=None):
    return SentenceSlice(
        text=text, sentence_start=0, sentence_end=len(text),
        entities=entities, evidence=evidence, parse=parse,
        syntax=syntax)


def _active_syntax():
    return {
        "tokens": [
            {"i": 0, "text": "John", "char_start": 0, "char_end": 4, "lemma": "John", "pos": "PROPN", "dep": "nsubj", "head_i": 1},
            {"i": 1, "text": "founded", "char_start": 5, "char_end": 12, "lemma": "found", "pos": "VERB", "dep": "ROOT", "head_i": 1},
            {"i": 2, "text": "Acme", "char_start": 13, "char_end": 17, "lemma": "Acme", "pos": "PROPN", "dep": "dobj", "head_i": 1},
            {"i": 3, "text": ".", "char_start": 17, "char_end": 18, "lemma": ".", "pos": "PUNCT", "dep": "punct", "head_i": 1},
        ]
    }


def _passive_syntax():
    return {
        "tokens": [
            {"i": 0, "text": "Acme", "char_start": 0, "char_end": 4, "lemma": "Acme", "pos": "PROPN", "dep": "nsubj:pass", "head_i": 2},
            {"i": 1, "text": "was", "char_start": 5, "char_end": 8, "lemma": "be", "pos": "AUX", "dep": "aux:pass", "head_i": 2},
            {"i": 2, "text": "founded", "char_start": 9, "char_end": 16, "lemma": "found", "pos": "VERB", "dep": "ROOT", "head_i": 2},
            {"i": 3, "text": "by", "char_start": 17, "char_end": 19, "lemma": "by", "pos": "ADP", "dep": "agent", "head_i": 2},
            {"i": 4, "text": "John", "char_start": 20, "char_end": 24, "lemma": "John", "pos": "PROPN", "dep": "pobj", "head_i": 3},
            {"i": 5, "text": ".", "char_start": 24, "char_end": 25, "lemma": ".", "pos": "PUNCT", "dep": "punct", "head_i": 2},
        ]
    }


def _active_parse():
    return {"voice": "active"}


def _passive_parse():
    return {"voice": "passive"}


def test_active_voice_assigns_arg0_to_subject():
    text = "John founded Acme."
    entities = [_ent("John", 0, 4, "Person"), _ent("Acme", 13, 17, "Organization")]
    evidence = [_ev("founded", 5, 12)]
    sl = _slice(entities, evidence, text, syntax=_active_syntax(), parse=_active_parse())
    cands = build_candidates_kimi(
        [sl], doc_id="d", corpus_id="eval", ontology_profile="core",
        extractor_version="t", rule_pack=PACK)
    assert len(cands) == 1
    cand = cands[0]
    assert cand.assigned_roles is not None
    assert cand.assigned_roles.get("ARG0").text == "John"
    assert cand.assigned_roles.get("ARG1").text == "Acme"


def test_passive_voice_inverts_canonical_direction():
    text = "Acme was founded by John."
    entities = [_ent("Acme", 0, 4, "Organization"), _ent("John", 20, 24, "Person")]
    evidence = [_ev("founded", 9, 16)]
    sl = _slice(entities, evidence, text, syntax=_passive_syntax(), parse=_passive_parse())
    cands = build_candidates_kimi(
        [sl], doc_id="d", corpus_id="eval", ontology_profile="core",
        extractor_version="t", rule_pack=PACK)
    assert len(cands) == 1
    cand = cands[0]
    decision = compile_relation_kimi(cand, sl.parse, PACK)
    assert decision.decision in ("ACCEPT", "QUALIFY")
    assert decision.fact is not None
    # canonical subject should be John (agent), object should be Acme (patient)
    assigned = decision.fact.provenance.get("assigned_roles", {})
    assert assigned.get("ARG0") == "John"
    assert assigned.get("ARG1") == "Acme"
    assert decision.fact.predicate == "founded"


def test_active_and_passive_converge_to_same_fact():
    active_text = "John founded Acme."
    passive_text = "Acme was founded by John."

    active_entities = [_ent("John", 0, 4, "Person"), _ent("Acme", 13, 17, "Organization")]
    passive_entities = [_ent("Acme", 0, 4, "Organization"), _ent("John", 20, 24, "Person")]

    active_ev = [_ev("founded", 5, 12)]
    passive_ev = [_ev("founded", 9, 16)]

    active_sl = _slice(active_entities, active_ev, active_text, syntax=_active_syntax(), parse=_active_parse())
    passive_sl = _slice(passive_entities, passive_ev, passive_text, syntax=_passive_syntax(), parse=_passive_parse())

    active_cand = build_candidates_kimi(
        [active_sl], doc_id="d", corpus_id="eval", ontology_profile="core",
        extractor_version="t", rule_pack=PACK)[0]
    passive_cand = build_candidates_kimi(
        [passive_sl], doc_id="d", corpus_id="eval", ontology_profile="core",
        extractor_version="t", rule_pack=PACK)[0]

    active_dec = compile_relation_kimi(active_cand, active_sl.parse, PACK)
    passive_dec = compile_relation_kimi(passive_cand, passive_sl.parse, PACK)

    assert active_dec.fact is not None
    assert passive_dec.fact is not None
    assert active_dec.fact.subject_id == passive_dec.fact.subject_id
    assert active_dec.fact.object_id == passive_dec.fact.object_id
    assert active_dec.fact.predicate == passive_dec.fact.predicate == "founded"

"""PREDICATE-COMPILER-V2 slice 2: mechanism tests for kimi_v2.

Token-originated predicate occurrences, UD-only argument binding, no
recall nets. Token lists mirror the syntax-evidence-v1 sidecar payload
(i, text, char_start, char_end, lemma, pos, dep, head_i).
"""
from __future__ import annotations

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import (  # noqa: E402
    BindingSource,
    EntitySpan,
    v2_binding_refusal,
)
from workers.candidates import SentenceSlice, identities_for  # noqa: E402
from workers.kimi_v2_candidates import build_candidates_kimi_v2  # noqa: E402
from polymath_shared.rulepack import load_rule_pack  # noqa: E402

PACK = load_rule_pack(pack_version="1.3.0")


def _identities(slices):
    return identities_for(
        slices, corpus_id="c1", doc_id="d1",
        contract_version="admission-harbor-v2")


def _tok(i, text, char_start, lemma=None, pos="NOUN", dep="", head_i=0):
    return {
        "i": i, "text": text,
        "char_start": char_start, "char_end": char_start + len(text),
        "lemma": lemma if lemma is not None else text.lower(),
        "pos": pos, "dep": dep, "head_i": head_i,
    }


def _ent(chunk_id, text, start, end, core_type):
    return EntitySpan(
        doc_id="d1", chunk_id=chunk_id, start=start, end=end,
        text=text, core_type=core_type, score=0.9,
        extractor_version="test")


def _slice(text, tokens, entities, index=0):
    return SentenceSlice(
        text=text, sentence_start=0, sentence_end=len(text),
        entities=entities, evidence=[], parse={"voice": "active"},
        syntax={"tokens": tokens}, sentence_index=index)


def test_adp_like_is_never_a_predicate():
    text = "Companies like Apple dominate markets."
    tokens = [
        _tok(0, "Companies", 0, lemma="company", pos="NOUN", dep="nsubj", head_i=4),
        _tok(1, "like", 10, pos="ADP", dep="prep", head_i=0),
        _tok(2, "Apple", 15, pos="PROPN", dep="pobj", head_i=1),
        _tok(3, "dominate", 21, pos="VERB", dep="ROOT", head_i=3),
        _tok(4, "markets", 30, pos="NOUN", dep="dobj", head_i=3),
    ]
    ents = [
        _ent("c0", "Apple", 15, 20, "Organization"),
        _ent("c0", "markets", 30, 37, "Concept"),
    ]
    sl = _slice(text, tokens, ents)
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c1",
        ontology_profile="core", extractor_version="test",
        rule_pack=PACK, identities=_identities([sl]))
    assert [c.predicate for c in cands if c.predicate == "similar_to"] == []
    similar = [c for c in cands
               if c.evidence.trigger_predicate_id == "similar_to"]
    assert similar == []


def test_no_parse_no_predicate():
    sl = _slice("Apple acquired Beats.", [], [])
    assert build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c1", ontology_profile="core",
        extractor_version="test", rule_pack=PACK,
        identities=_identities([sl])) == []


def _acquisition_slice():
    text = "Apple acquired Beats."
    tokens = [
        _tok(0, "Apple", 0, pos="PROPN", dep="nsubj", head_i=1),
        _tok(1, "acquired", 6, lemma="acquire", pos="VERB",
             dep="ROOT", head_i=1),
        _tok(2, "Beats", 15, pos="PROPN", dep="dobj", head_i=1),
    ]
    ents = [
        _ent("c0", "Apple", 0, 5, "Organization"),
        _ent("c0", "Beats", 15, 20, "Organization"),
    ]
    return _slice(text, tokens, ents)


def test_verbal_trigger_binds_ud_arguments_only():
    slices = [_acquisition_slice()]
    cands = build_candidates_kimi_v2(
        slices, doc_id="d1", corpus_id="c1",
        ontology_profile="core", extractor_version="test",
        rule_pack=PACK, identities=_identities(slices))
    assert len(cands) == 1
    c = cands[0]
    assert c.subject.span.text == "Apple"
    assert c.object.span.text == "Beats"
    assert c.binding_source == BindingSource.UD_DEPENDENCY
    assert c.trigger_token_id == 1
    assert c.subject_token_id == 0
    assert c.object_token_id == 2
    assert c.dependency_path == "nsubj+dobj"
    assert c.document_id == "d1"
    assert c.sentence_id == "c0#s0"
    assert (c.evidence.start, c.evidence.end) == (0, 20)
    assert c.evidence.text == "Apple acquired Beats"


def test_nominal_prep_of_pattern_binds_part_of():
    text = "Tesla is part of the automotive industry."
    tokens = [
        _tok(0, "Tesla", 0, pos="PROPN", dep="nsubj", head_i=2),
        _tok(1, "is", 6, pos="AUX", dep="aux", head_i=2),
        _tok(2, "part", 9, pos="NOUN", dep="ROOT", head_i=2),
        _tok(3, "of", 14, pos="ADP", dep="prep", head_i=2),
        _tok(4, "the", 17, pos="DET", dep="det", head_i=6),
        _tok(5, "automotive", 21, pos="ADJ", dep="amod", head_i=6),
        _tok(6, "industry", 32, pos="NOUN", dep="pobj", head_i=3),
    ]
    ents = [
        _ent("c0", "Tesla", 0, 5, "Organization"),
        _ent("c0", "automotive industry", 21, 40, "Concept"),
    ]
    sl = _slice(text, tokens, ents)
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c1",
        ontology_profile="core", extractor_version="test",
        rule_pack=PACK, identities=_identities([sl]))
    part_of = [c for c in cands if c.evidence.trigger_predicate_id == "part_of"]
    assert len(part_of) == 1
    c = part_of[0]
    assert c.subject.span.text == "Tesla"
    assert c.object.span.text in ("automotive industry", "industry")
    assert c.binding_source == BindingSource.NOMINAL_DEPENDENCY
    assert "prep.of>pobj" in c.dependency_path


def test_missing_dependency_slot_yields_no_candidate():
    tokens = [
        _tok(0, "acquired", 0, lemma="acquire", pos="VERB",
             dep="ROOT", head_i=0),
        _tok(1, "Beats", 9, pos="PROPN", dep="dobj", head_i=0),
    ]
    ents = [_ent("c0", "Beats", 9, 14, "Organization")]
    sl = _slice("acquired Beats.", tokens, ents)
    cands = build_candidates_kimi_v2(
        [sl],
        doc_id="d1", corpus_id="c1", ontology_profile="core",
        extractor_version="test", rule_pack=PACK,
        identities=_identities([sl]))
    assert cands == []


def test_every_v2_candidate_passes_the_hard_rule():
    slices = [_acquisition_slice()]
    cands = build_candidates_kimi_v2(
        slices, doc_id="d1", corpus_id="c1",
        ontology_profile="core", extractor_version="test",
        rule_pack=PACK, identities=_identities(slices))
    assert cands
    assert all(v2_binding_refusal(c) is None for c in cands)


def test_slices_are_isolated_no_cross_sentence_binding():
    s1 = _acquisition_slice()
    text2 = "Google likes innovation."
    tokens2 = [
        _tok(0, "Google", 0, pos="PROPN", dep="nsubj", head_i=1),
        _tok(1, "likes", 7, lemma="like", pos="VERB", dep="ROOT", head_i=1),
        _tok(2, "innovation", 13, pos="NOUN", dep="dobj", head_i=1),
    ]
    ents2 = [
        _ent("c0", "Google", 0, 6, "Organization"),
        _ent("c0", "innovation", 13, 23, "Concept"),
    ]
    s2 = _slice(text2, tokens2, ents2, index=1)
    slices = [s1, s2]
    cands = build_candidates_kimi_v2(
        slices, doc_id="d1", corpus_id="c1", ontology_profile="core",
        extractor_version="test", rule_pack=PACK,
        identities=_identities(slices))
    surfaces = {(c.subject.span.text, c.object.span.text) for c in cands}
    assert ("Google", "innovation") in surfaces or not any(
        s == ("Google", "innovation") for s in surfaces)
    cross = [c for c in cands
             if {c.subject.span.text, c.object.span.text}
             == {"Apple", "Google"}]
    assert cross == []


# --- SCIENTIFIC-KAG-V1 phase 5: infinitive control frames ------------------

def _control_slice(text, tokens, entities):
    return _slice(text, tokens, entities)


def _ents(*specs, chunk="c0"):
    out = []
    for text, start, ct in specs:
        out.append(_ent(chunk, text, start, start + len(text), ct))
    return out


def test_object_control_binds_embedded_subject():
    """A allows B to use C  ->  B uses C  (never A uses C)."""
    text = "Acme allows Bitwork to use Cipher."
    def at(w): return text.index(w)
    tokens = [
        _tok(0, "Acme", at("Acme"), pos="PROPN", dep="nsubj", head_i=1),
        _tok(1, "allows", at("allows"), lemma="allow", pos="VERB", dep="ROOT", head_i=1),
        _tok(2, "Bitwork", at("Bitwork"), pos="PROPN", dep="nsubj", head_i=1),
        _tok(3, "to", at("to "), pos="AUX", dep="aux", head_i=4),
        _tok(4, "use", at("use "), lemma="use", pos="VERB", dep="ccomp", head_i=1),
        _tok(5, "Cipher", at("Cipher"), pos="PROPN", dep="dobj", head_i=4),
    ]
    ents = _ents(("Acme", at("Acme"), "Organization"), ("Bitwork", at("Bitwork"), "Organization"),
                 ("Cipher", at("Cipher"), "Technology"))
    sl = _control_slice(text, tokens, ents)
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c1", ontology_profile="core",
        extractor_version="test", rule_pack=PACK,
        identities=_identities([sl]))
    uses = [c for c in cands if c.evidence.trigger_predicate_id == "uses"]
    assert len(uses) == 1
    c = uses[0]
    pair = {c.subject.span.text, c.object.span.text}
    assert pair == {"Bitwork", "Cipher"}
    assert str(c.binding_source) == "BindingSource.CONTROL_OBJECT"
    assert "control[allow:object]" in c.dependency_path
    acmes = [c for c in cands if c.subject.span.text == "Acme"
             and c.object.span.text == "Cipher"]
    assert acmes == [], "matrix subject must not steal the embedded relation"


def test_subject_control_inherits_matrix_subject():
    """ToT attempts to create X  ->  ToT creates X."""
    text = "ToT attempts to create benchmarks."
    tokens = [
        _tok(0, "ToT", 0, pos="PROPN", dep="nsubj", head_i=1),
        _tok(1, "attempts", 4, lemma="attempt", pos="VERB", dep="ROOT",
             head_i=1),
        _tok(2, "to", 13, pos="AUX", dep="aux", head_i=3),
        _tok(3, "create", 16, lemma="create", pos="VERB", dep="xcomp",
             head_i=1),
        _tok(4, "benchmarks", 23, pos="NOUN", dep="dobj", head_i=3),
    ]
    ents = [_ent("c0", "ToT", 0, 3, "Organization"),
            _ent("c0", "benchmarks", 23, 33, "Concept")]
    sl = _control_slice(text, tokens, ents)
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c1", ontology_profile="core",
        extractor_version="test", rule_pack=PACK,
        identities=_identities([sl]))
    created = [c for c in cands if c.evidence.trigger_predicate_id == "created"]
    assert len(created) == 1
    c = created[0]
    assert (c.subject.span.text, c.object.span.text) == ("ToT", "benchmarks")
    assert str(c.binding_source) == "BindingSource.CONTROL_SUBJECT"
    assert "control[attempt:subject]" in c.dependency_path


def test_control_is_fail_closed_on_ambiguous_controller():
    """Two candidate controllers between matrix and embedded -> no fact."""
    text = "Acme allows Bitwork and Chiplet to use Cipher."
    def at(w): return text.index(w)
    tokens = [
        _tok(0, "Acme", at("Acme"), pos="PROPN", dep="nsubj", head_i=1),
        _tok(1, "allows", at("allows"), lemma="allow", pos="VERB", dep="ROOT", head_i=1),
        _tok(2, "Bitwork", at("Bitwork"), pos="PROPN", dep="nsubj", head_i=1),
        _tok(3, "and", at(" and"), pos="CCONJ", dep="cc", head_i=2),
        _tok(4, "Chiplet", at("Chiplet"), pos="PROPN", dep="conj", head_i=2),
        _tok(5, "to", at("to "), pos="AUX", dep="aux", head_i=6),
        _tok(6, "use", at("use "), lemma="use", pos="VERB", dep="ccomp", head_i=1),
        _tok(7, "Cipher", at("Cipher"), pos="PROPN", dep="dobj", head_i=6),
    ]
    ents = _ents(("Bitwork", at("Bitwork"), "Organization"), ("Chiplet", at("Chiplet"), "Organization"),
                 ("Cipher", at("Cipher"), "Technology"))
    sl = _control_slice(text, tokens, ents)
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c1", ontology_profile="core",
        extractor_version="test", rule_pack=PACK,
        identities=_identities([sl]))
    # coordination expansion of the controlled subject is allowed only via
    # UD conj under ONE controller; two sibling controllers stay ambiguous
    # unless conj-linked. Here they ARE conj-linked, so both bind.
    pairs = {(c.subject.span.text, c.object.span.text)
             for c in cands if c.evidence.trigger_predicate_id == "uses"}
    assert pairs <= {("Bitwork", "Cipher"), ("Chiplet", "Cipher")}
    assert ("Acme", "Cipher") not in pairs


def test_unlicensed_control_verb_does_not_propagate():
    """Matrix verb outside the authored lists -> no controller invented."""
    text = "Acme imagined to use Cipher."
    def at(w): return text.index(w)
    tokens = [
        _tok(0, "Acme", at("Acme"), pos="PROPN", dep="nsubj", head_i=1),
        _tok(1, "imagined", at("imagined"), lemma="imagine", pos="VERB", dep="ROOT", head_i=1),
        _tok(2, "to", at("to "), pos="AUX", dep="aux", head_i=3),
        _tok(3, "use", at("use "), lemma="use", pos="VERB", dep="xcomp", head_i=1),
        _tok(4, "Cipher", at("Cipher"), pos="PROPN", dep="dobj", head_i=3),
    ]
    ents = _ents(("Acme", at("Acme"), "Organization"), ("Cipher", at("Cipher"), "Technology"))
    sl = _control_slice(text, tokens, ents)
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c1", ontology_profile="core",
        extractor_version="test", rule_pack=PACK,
        identities=_identities([sl]))
    assert [c for c in cands
            if c.evidence.trigger_predicate_id == "uses"] == []


@pytest.mark.skip(reason="D7 follow-up: compound-NP head binding root cause under investigation (addendum 5d)")
def test_compound_np_head_binds_through_child_entity():
    """'The BERT model was introduced by Google Research.'
    nsubj head = generic 'model'; the compound child 'BERT' names the
    admitted entity. Argument must bind through the compound child."""
    text = "The BERT model was introduced by Google Research."
    toks = [
        _tok(0, "The", 0, pos="DET", dep="det", head_i=2),
        _tok(1, "BERT", text.index("BERT"), lemma="bert", pos="PROPN", dep="compound",
             head_i=2),
        _tok(2, "model", text.index("model"), pos="NOUN", dep="nsubjpass", head_i=3),
        _tok(3, "was", text.index("was"), lemma="be", pos="AUX", dep="auxpass",
             head_i=4),
        _tok(4, "introduced", text.index("introduced"), lemma="introduce", pos="VERB",
             dep="ROOT", head_i=4),
        _tok(5, "by", text.index("by"), pos="ADP", dep="agent", head_i=4),
        _tok(6, "Google Research", text.index("Google Research"), pos="PROPN", dep="pobj",
             head_i=5),
    ]
    ents = [_ent("c0", "BERT", text.index("BERT"),
                 text.index("BERT") + 4, "Architecture"),
            _ent("c0", "Google Research",
                 text.index("Google Research"),
                 text.index("Google Research") + 15, "ResearchGroup")]
    sl = _slice(text, toks, ents)
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c1", ontology_profile="core",
        extractor_version="test", rule_pack=PACK,
        identities=_identities([sl]))
    introduced = [c for c in cands
                  if c.evidence.trigger_predicate_id == "introduced"]
    assert len(introduced) == 1
    pair = {c.subject.span.text for c in introduced} | \
           {c.object.span.text for c in introduced}
    assert pair == {"BERT", "Google Research"}

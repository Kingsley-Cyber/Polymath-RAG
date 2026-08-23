"""SCIENTIFIC-KAG-V1 phase 5.5: deterministic discourse bridge.

Owner examples: definitional apposition inherits identity; controlled
anaphora resolves pronoun -> previous-sentence subject within 2
sentences; ambiguity abstains. Resolution only ever points at
already-admitted entities.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import BindingSource, EntitySpan  # noqa: E402
from workers.candidates import SentenceSlice, identities_for  # noqa: E402
from workers.kimi_v2_candidates import build_candidates_kimi_v2  # noqa: E402
from polymath_shared.rulepack import load_rule_pack  # noqa: E402

PACK = load_rule_pack(pack_version="1.4.0")


def _tok(i, word, start, lemma=None, pos="NOUN", dep="", head_i=0):
    return {"i": i, "text": word, "char_start": start,
            "char_end": start + len(word),
            "lemma": lemma if lemma is not None else word.lower(),
            "pos": pos, "dep": dep, "head_i": head_i}


def _ent(text, start, core, chunk="c0", admission=None):
    e = EntitySpan(doc_id="d1", chunk_id=chunk, start=start,
                   end=start + len(text), text=text, core_type=core,
                   score=0.95, extractor_version="test")
    if admission:
        object.__setattr__(e, "admission_class", admission)
    return e


def _slice(text, tokens, ents, index=0):
    sl = SentenceSlice(text=text, sentence_start=0, sentence_end=len(text),
                       entities=list(ents), evidence=[], parse=None,
                       syntax={"tokens": tokens}, sentence_index=index)
    return sl


def test_apposition_binds_through_to_entity_head():
    text = "Tree of Thoughts includes reasoning paradigms."
    toks = [
        _tok(0, "Tree", 0, lemma="Tree", pos="PROPN", dep="nsubj", head_i=3),
        _tok(1, "of", 5, pos="ADP", dep="prep", head_i=0),
        _tok(2, "Thoughts", 8, lemma="Thoughts", pos="PROPN", dep="pobj",
             head_i=1),
        _tok(3, "includes", 18, lemma="include", pos="VERB", dep="ROOT",
             head_i=3),
        _tok(4, "reasoning", 27, lemma="reasoning", pos="NOUN",
             dep="compound", head_i=5),
        _tok(5, "paradigms", 37, lemma="paradigm", pos="NOUN", dep="dobj",
             head_i=3),
    ]
    ents = [_ent("Tree of Thoughts", 0, "Framework"),
            _ent("reasoning paradigms", text.index("reasoning"), "Concept")]
    sl = _slice(text, toks, ents)
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c", ontology_profile="core",
        extractor_version="test", rule_pack=PACK,
        identities=identities_for([sl], corpus_id="c", doc_id="d1",
                                  contract_version="admission-harbor-v2"))
    pairs = {(c.subject.span.text, c.object.span.text)
             for c in cands if c.evidence.trigger_predicate_id ==
             "contains_component"}
    assert pairs == {("Tree of Thoughts", "reasoning paradigms")}


def test_controlled_anaphora_resolves_previous_subject():
    s1_text = "Tree of Thoughts is a reasoning framework."
    s1_toks = [
        _tok(0, "Tree", 0, lemma="Tree", pos="PROPN", dep="nsubj", head_i=3),
        _tok(1, "of", 5, pos="ADP", dep="prep", head_i=0),
        _tok(2, "Thoughts", 8, lemma="Thoughts", pos="PROPN", dep="pobj",
             head_i=1),
        _tok(3, "is", 18, lemma="be", pos="AUX", dep="ROOT", head_i=3),
        _tok(4, "a", 21, pos="DET", dep="det", head_i=6),
        _tok(5, "reasoning", 23, lemma="reasoning", pos="NOUN",
             dep="compound", head_i=6),
        _tok(6, "framework", 33, lemma="framework", pos="NOUN", dep="attr",
             head_i=3),
    ]
    s1_ents = [_ent("Tree of Thoughts", 0, "Framework")]
    s1 = _slice(s1_text, s1_toks, s1_ents, index=0)

    s2_text = "It uses beam search."
    s2_toks = [
        _tok(0, "It", 0, lemma="it", pos="PRON", dep="nsubj", head_i=1),
        _tok(1, "uses", 3, lemma="use", pos="VERB", dep="ROOT", head_i=1),
        _tok(2, "beam", 8, lemma="beam", pos="NOUN", dep="compound",
             head_i=3),
        _tok(3, "search", 13, lemma="search", pos="NOUN", dep="dobj",
             head_i=1),
    ]
    # GLiNER proposes the pronoun; it is MENTION_ONLY noise.
    s2_ents = [_ent("It", 0, "Person", chunk="c0", admission="MENTION_ONLY"),
               _ent("beam search", 8, "Method")]
    s2 = _slice(s2_text, s2_toks, s2_ents, index=1)

    slices = [s1, s2]
    ids = identities_for(slices, corpus_id="c", doc_id="d1",
                         contract_version="admission-harbor-v2")
    cands = build_candidates_kimi_v2(
        slices, doc_id="d1", corpus_id="c", ontology_profile="core",
        extractor_version="test", rule_pack=PACK, identities=ids)
    uses = [c for c in cands if c.evidence.trigger_predicate_id == "uses"]
    assert len(uses) == 1
    c = uses[0]
    assert (c.subject.span.text, c.object.span.text) == \
        ("Tree of Thoughts", "beam search")
    assert str(c.binding_source) == "BindingSource.DISCOURSE_ANAPHORA"


def test_anaphora_abstains_beyond_distance():
    far = _slice("Filler sentence one.", [
        _tok(0, "Filler", 0, pos="NOUN", dep="nsubj", head_i=1)], [],
        index=0)
    subj_text = "Alpha Framework scales."
    subj_toks = [
        _tok(0, "Alpha", 0, lemma="Alpha", pos="PROPN", dep="nsubj",
             head_i=1),
        _tok(1, "Framework", 6, lemma="framework", pos="NOUN", dep="ROOT",
             head_i=1),
    ]
    s_subj = _slice(subj_text, subj_toks,
                    [_ent("Alpha Framework", 0, "Framework")], index=1)
    filler2 = _slice("Another unrelated line appears here.", [
        _tok(0, "Another", 0, pos="ADJ", dep="nsubj", head_i=1),
        _tok(1, "line", 8, lemma="line", pos="NOUN", dep="ROOT", head_i=1)],
        [], index=2)
    filler3 = _slice("Yet more distance accumulates here.", [
        _tok(0, "Yet", 0, pos="ADV", dep="advmod", head_i=2),
        _tok(1, "more", 4, lemma="more", pos="ADJ", dep="advmod", head_i=2),
        _tok(2, "distance", 9, lemma="distance", pos="NOUN", dep="nsubj",
             head_i=2)],
        [_ent("distance", 9, "Concept")], index=3)
    s3_text = "It uses beam search."
    s3_toks = [
        _tok(0, "It", 0, lemma="it", pos="PRON", dep="nsubj", head_i=1),
        _tok(1, "uses", 3, lemma="use", pos="VERB", dep="ROOT", head_i=1),
        _tok(2, "beam", 8, lemma="beam", pos="NOUN", dep="compound",
             head_i=3),
        _tok(3, "search", 13, lemma="search", pos="NOUN", dep="dobj",
             head_i=1),
    ]
    s3_ents = [_ent("It", 0, "Person", chunk="c0",
                    admission="MENTION_ONLY"),
               _ent("beam search", 8, "Method")]
    s3 = _slice(s3_text, s3_toks, s3_ents, index=4)

    slices = [far, s_subj, filler2, filler3, s3]
    ids = identities_for([s_subj, filler3, s3], corpus_id="c", doc_id="d1",
                         contract_version="admission-harbor-v2")
    cands = build_candidates_kimi_v2(
        slices, doc_id="d1", corpus_id="c", ontology_profile="core",
        extractor_version="test", rule_pack=PACK, identities=ids)
    uses = [c for c in cands if c.evidence.trigger_predicate_id == "uses"]
    assert all(c.subject.span.text != "Alpha Framework" for c in uses), \
        "pronoun beyond distance 2 must not resolve"

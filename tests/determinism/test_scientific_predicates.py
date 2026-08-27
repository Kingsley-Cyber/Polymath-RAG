"""SCIENTIFIC-KAG-V1 phase 4: research predicates in pack v1.4.0.

Direction and signature behavior on the owner's examples, compiled
trigger licensing (train/introduce/propose/evaluate/outperform/release
are NEW claims; implement re-homed to implemented_with), and the
family-expanded signatures.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import EntitySpan  # noqa: E402
from workers.candidates import SentenceSlice, identities_for  # noqa: E402
from workers.kimi_v2_candidates import build_candidates_kimi_v2  # noqa: E402
from polymath_shared.rulepack import load_rule_pack  # noqa: E402
from polymath_shared.rulepack.compiler import compile_relation_kimi  # noqa: E402

PACK = load_rule_pack(pack_version="1.4.0")


def _tok(i, text, word, lemma=None, pos="NOUN", dep="", head_i=0):
    start = text.find(word)
    assert start >= 0, word
    return {"i": i, "text": word,
            "char_start": start, "char_end": start + len(word),
            "lemma": lemma if lemma is not None else word.lower(),
            "pos": pos, "dep": dep, "head_i": head_i}


def _ent(chunk, word, start, core):
    return EntitySpan(doc_id="d1", chunk_id=chunk, start=start,
                      end=start + len(word), text=word, core_type=core,
                      score=0.95, extractor_version="test")


def _run(text, tokens, ents):
    sl = SentenceSlice(text=text, sentence_start=0, sentence_end=len(text),
                       entities=ents, evidence=[], parse=None,
                       syntax={"tokens": tokens})
    ids = identities_for([sl], corpus_id="c", doc_id="d1",
                         contract_version="admission-harbor-v2")
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c", ontology_profile="core",
        extractor_version="test", rule_pack=PACK, identities=ids)
    out = []
    for cand in cands:
        d = compile_relation_kimi(cand, None, PACK, syntax=sl.syntax)
        if d.fact is not None:
            id2s = {cand.subject.resolved_entity_id: cand.subject.span.text,
                    cand.object.resolved_entity_id: cand.object.span.text}
            out.append((d.fact.predicate, id2s[d.fact.subject_id],
                        id2s[d.fact.object_id], d.decision))
        else:
            out.append((None, None, None, d.decision))
    return out


def _make(text, token_specs, ent_specs):
    def at(surface):
        i = text.find(surface)
        assert i >= 0, f"{surface!r} not in {text!r}"
        return i

    toks = [_tok(i, text, **spec) for i, spec in enumerate(token_specs)]
    ents = [_ent("c0", w, at(w), core) for w, core in ent_specs]
    return text, toks, ents


def test_trained_on_direction():
    text, toks, ents = _make(
        "BERT was trained on BooksCorpus.",
        [dict(word="BERT", pos="PROPN", dep="nsubjpass", head_i=2),
         dict(word="was", lemma="be", pos="AUX", dep="auxpass", head_i=2),
         dict(word="trained", lemma="train", pos="VERB", dep="ROOT", head_i=2),
         dict(word="on", pos="ADP", dep="prep", head_i=2),
         dict(word="BooksCorpus", pos="PROPN", dep="pobj", head_i=3)],
        [("BERT", "Model"), ("BooksCorpus", "Dataset")])
    facts = _run(text, toks, ents)
    assert ("trained_on", "BERT", "BooksCorpus", "ACCEPT") in facts


def test_trained_on_reverse_is_rejected():
    text, toks, ents = _make(
        "BooksCorpus was trained on BERT.",
        [dict(word="BooksCorpus", pos="PROPN", dep="nsubjpass", head_i=2),
         dict(word="was", lemma="be", pos="AUX", dep="auxpass", head_i=2),
         dict(word="trained", lemma="train", pos="VERB", dep="ROOT", head_i=2),
         dict(word="on", pos="ADP", dep="prep", head_i=2),
         dict(word="BERT", pos="PROPN", dep="pobj", head_i=3)],
        [("BooksCorpus", "Dataset"), ("BERT", "Model")])
    facts = _run(text, toks, ents)
    trained_accepts = [f for f in facts if f[0] == "trained_on"
                       and f[3] == "ACCEPT"]
    bad = [f for f in trained_accepts if f[1] == "BooksCorpus"]
    assert not bad, facts


def test_introduced_fires():
    text, toks, ents = _make(
        "The paper introduces Tree of Thoughts.",
        [dict(word="The", pos="DET", dep="det", head_i=1),
         dict(word="paper", lemma="paper", pos="NOUN", dep="nsubj", head_i=2),
         dict(word="introduces", lemma="introduce", pos="VERB", dep="ROOT",
              head_i=2),
         dict(word="Tree", lemma="Tree", pos="PROPN", dep="dobj", head_i=2),
         dict(word="of", pos="ADP", dep="prep", head_i=3),
         dict(word="Thoughts", lemma="Thoughts", pos="PROPN", dep="pobj",
              head_i=4)],
        [("paper", "Document"), ("Tree of Thoughts", "Algorithm")])
    facts = _run(text, toks, ents)
    assert any(f[0] == "introduced" and f[3] == "ACCEPT" and
               f[1] == "paper" and f[2] == "Tree of Thoughts"
               for f in facts), facts


def test_released_on_with_temporal_object():
    text, toks, ents = _make(
        "GPT-4 was released in March 2023.",
        [dict(word="GPT-4", pos="PROPN", dep="nsubjpass", head_i=2),
         dict(word="was", lemma="be", pos="AUX", dep="auxpass", head_i=2),
         dict(word="released", lemma="release", pos="VERB", dep="ROOT",
              head_i=2),
         dict(word="in", pos="ADP", dep="prep", head_i=2),
         dict(word="March", lemma="March", pos="PROPN", dep="pobj", head_i=3),
         dict(word="2023", lemma="2023", pos="NUM", dep="nummod", head_i=4)],
        [("GPT-4", "Model"), ("March 2023", "TimeReference")])
    facts = _run(text, toks, ents)
    assert any(f[0] == "released_on" and f[1] == "GPT-4"
               and f[2] == "March 2023" for f in facts), facts


def test_contains_component_via_include():
    text, toks, ents = _make(
        "Tree of Thoughts includes a thought generator.",
        [dict(word="Tree", lemma="Tree", pos="PROPN", dep="nsubj", head_i=3),
         dict(word="of", pos="ADP", dep="prep", head_i=0),
         dict(word="Thoughts", lemma="Thoughts", pos="PROPN", dep="pobj",
              head_i=1),
         dict(word="includes", lemma="include", pos="VERB", dep="ROOT",
              head_i=3),
         dict(word="a", pos="DET", dep="det", head_i=6),
         dict(word="thought", lemma="thought", pos="NOUN", dep="compound",
              head_i=6),
         dict(word="generator", lemma="generator", pos="NOUN", dep="dobj",
              head_i=3)],
        [("Tree of Thoughts", "Framework"),
         ("thought generator", "Component")])
    facts = _run(text, toks, ents)
    assert ("contains_component", "Tree of Thoughts", "thought generator",
            "ACCEPT") in facts, facts


def test_control_trio_with_v140_licensing():
    """Owner's verbatim object-control shape with trained_on licensed."""
    text = "OpenAI enables Bertie to train on WikiText."

    def at(surface):
        i = text.find(surface)
        assert i >= 0
        return i

    toks = [
        _tok(0, text, "OpenAI", pos="PROPN", dep="nsubj", head_i=1),
        _tok(1, text, "enables", lemma="enable", pos="VERB", dep="ROOT",
             head_i=1),
        _tok(2, text, "Bertie", pos="PROPN", dep="nsubj", head_i=1),
        _tok(3, text, "to", pos="AUX", dep="aux", head_i=4),
        _tok(4, text, "train", lemma="train", pos="VERB", dep="ccomp",
             head_i=1),
        _tok(5, text, "on", pos="ADP", dep="prep", head_i=4),
        _tok(6, text, "WikiText", pos="PROPN", dep="pobj", head_i=5),
    ]
    ents = [_ent("c0", "OpenAI", at("OpenAI"), "Organization"),
            _ent("c0", "Bertie", at("Bertie"), "Model"),
            _ent("c0", "WikiText", at("WikiText"), "Dataset")]
    sl = SentenceSlice(text=text, sentence_start=0, sentence_end=len(text),
                       entities=ents, evidence=[], parse=None,
                       syntax={"tokens": toks})
    ids = identities_for([sl], corpus_id="c", doc_id="d1",
                         contract_version="admission-harbor-v2")
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c", ontology_profile="core",
        extractor_version="test", rule_pack=PACK, identities=ids)
    trained = []
    for cand in cands:
        if cand.evidence.trigger_predicate_id != "trained_on":
            continue
        d = compile_relation_kimi(cand, None, PACK, syntax=sl.syntax)
        if d.fact:
            id2s = {cand.subject.resolved_entity_id: cand.subject.span.text,
                    cand.object.resolved_entity_id: cand.object.span.text}
            trained.append((id2s[d.fact.subject_id],
                            id2s[d.fact.object_id]))
    assert ("Bertie", "WikiText") in trained, trained
    assert all(a != "OpenAI" for a, _ in trained), trained


def test_evaluated_on_with_temporal_complement():
    text = "BERT was evaluated on GLUE in March 2023."
    toks = [
        _tok(0, text, "BERT", pos="PROPN", dep="nsubjpass", head_i=2),
        _tok(1, text, "was", lemma="be", pos="AUX", dep="auxpass", head_i=2),
        _tok(2, text, "evaluated", lemma="evaluate", pos="VERB", dep="ROOT",
             head_i=2),
        _tok(3, text, "on", pos="ADP", dep="prep", head_i=2),
        _tok(4, text, "GLUE", pos="PROPN", dep="pobj", head_i=3),
        _tok(5, text, "in", pos="ADP", dep="prep", head_i=2),
        _tok(6, text, "March", lemma="March", pos="PROPN", dep="pobj",
             head_i=5),
        _tok(7, text, "2023", lemma="2023", pos="NUM", dep="nummod",
             head_i=6),
    ]
    ents = [_ent("c0", "BERT", 0, "Model"),
            _ent("c0", "GLUE", text.index("GLUE"), "Benchmark"),
            _ent("c0", "March 2023", text.index("March"), "TimeReference")]
    sl = SentenceSlice(text=text, sentence_start=0, sentence_end=len(text),
                       entities=ents, evidence=[], parse=None,
                       syntax={"tokens": toks})
    ids = identities_for([sl], corpus_id="c", doc_id="d1",
                         contract_version="admission-harbor-v2")
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c", ontology_profile="core",
        extractor_version="test", rule_pack=PACK, identities=ids)
    facts = []
    for cand in cands:
        d = compile_relation_kimi(cand, None, PACK, syntax=sl.syntax)
        if d.fact:
            facts.append((d.fact.predicate, cand.subject.span.text,
                          cand.object.span.text, d.fact.qualifiers))
    primary = [f for f in facts if f[0] == "evaluated_on"
               and f[2] == "GLUE"]
    assert primary and primary[0][3].get("temporal_surface") == "March 2023"
    assert primary[0][3].get("valid_from") == "2023-03"
    leaked = [f for f in facts if f[0] == "evaluated_on"
              and f[2] == "March 2023"]
    assert not leaked, "temporal complement must never become the object"


def test_occurred_at_binds_temporal_endpoint():
    text = "The evaluation occurred in 2024."
    toks = [
        _tok(0, text, "evaluation", lemma="evaluation", pos="NOUN",
             dep="nsubj", head_i=1),
        _tok(1, text, "occurred", lemma="occur", pos="VERB", dep="ROOT",
             head_i=1),
        _tok(2, text, "in", pos="ADP", dep="prep", head_i=1),
        _tok(3, text, "2024", lemma="2024", pos="NUM", dep="pobj", head_i=2),
    ]
    ents = [_ent("c0", "evaluation", text.index("evaluation"), "Event"),
            _ent("c0", "2024", text.index("2024"), "Date")]
    sl = SentenceSlice(text=text, sentence_start=0, sentence_end=len(text),
                       entities=ents, evidence=[], parse=None,
                       syntax={"tokens": toks})
    ids = identities_for([sl], corpus_id="c", doc_id="d1",
                         contract_version="admission-harbor-v2")
    cands = build_candidates_kimi_v2(
        [sl], doc_id="d1", corpus_id="c", ontology_profile="core",
        extractor_version="test", rule_pack=PACK, identities=ids)
    facts = []
    for cand in cands:
        d = compile_relation_kimi(cand, None, PACK, syntax=sl.syntax)
        if d.fact:
            id2s = {cand.subject.resolved_entity_id: cand.subject.span.text,
                    cand.object.resolved_entity_id: cand.object.span.text}
            facts.append((d.fact.predicate, id2s[d.fact.subject_id],
                          id2s[d.fact.object_id]))
    assert ("occurred_at", "evaluation", "2024") in facts, facts

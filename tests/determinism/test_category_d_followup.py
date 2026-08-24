"""Determinism regressions: CATEGORY-D follow-up repairs (2026-08-24).

1. I3R-R3 definite-description head repair: aux/adverb tail stripped
   from the captured NP so "the model was trained..." resolves its head
   as "model" instead of the swallowed auxiliary "was".
2. C3c possessive-theme inheritance: a frame slot token with a UD `poss`
   child recovers the possessor as endpoint when exactly ONE
   type-compatible durable history entity aliases it. Ambiguity and
   pronouns abstain (fail-closed).
"""
from __future__ import annotations

import os
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import pytest

from polymath_shared.contracts import EntitySpan, CoreType
from workers.candidates import _resolve_definite_description


def _ent(text: str, core: str, start: int = 0) -> EntitySpan:
    return EntitySpan(doc_id="d", chunk_id="ch", start=start,
                      end=start + len(text), text=text,
                      core_type=CoreType(core), score=0.9,
                      extractor_version="test")


HISTORY = [
    _ent("Orion Adaptive Reasoning Model", "Model"),
    _ent("Advanced Computational Intelligence Laboratory", "Organization"),
]


def test_definite_head_not_poisoned_by_auxiliary():
    """'The model was trained on X': head must be 'model', not 'was'."""
    resolved = _resolve_definite_description(
        "The model was trained on the HorizonText Research Corpus.",
        14, 0, HISTORY)
    assert resolved is not None
    assert resolved.text == "Orion Adaptive Reasoning Model"


def test_definite_ambiguity_still_abstains():
    """Two type-compatible candidates -> fail closed (unchanged rule)."""
    ambiguous = HISTORY + [_ent("Atlas Reasoning Model", "Model")]
    assert _resolve_definite_description(
        "The model was trained on X.", 9, 0, ambiguous) is None


def test_definite_no_match_still_abstains():
    assert _resolve_definite_description(
        "The model was trained on X.", 9, 0, []) is None


def _build_and_collect(syntax_by_text, text, sentences, ents_per_sentence,
                       evidence_per_sentence, history):
    """Drive build_candidates_kimi exactly like production: one slice at
    a time, absolute offsets, growing doc_entities_history."""
    os_environ_pipeline()
    from workers.candidates import SentenceSlice
    from workers.kimi_candidates import build_candidates_kimi
    from workers.extract_worker import _allocate_identities
    from polymath_shared.rulepack import load_rule_pack

    slices = []
    for s_text in sentences:
        start = text.find(s_text)
        sl = SentenceSlice(text=s_text, sentence_start=start,
                           sentence_end=start + len(s_text),
                           entities=ents_per_sentence[s_text],
                           evidence=list(evidence_per_sentence[s_text]),
                           parse=None, syntax=syntax_by_text[s_text])
        slices.append(sl)
    rows = [{"chunk_id": "ch", "text": text}] * len(slices)
    identities = _allocate_identities(
        list(zip(rows, slices)), "c", "d",
        contract_version="admission-harbor-v2")
    rp = load_rule_pack()
    out = []
    for sl in slices:
        cands = build_candidates_kimi(
            [sl], doc_id="d", corpus_id="c",
            ontology_profile="scientific-v2", extractor_version="test",
            rule_pack=rp, enrich=False,
            doc_entities_history=history, identities=identities)
        out.extend(cands)
        history.extend(sorted(sl.entities, key=lambda e: (e.start, e.end)))
    return {(c.subject.span.text, c.object.span.text) for c in out}


@pytest.fixture(autouse=True)
def _restore_pipeline_env():
    saved = os.environ.get("POLYMATH_RELATION_PIPELINE")
    yield
    if saved is None:
        os.environ.pop("POLYMATH_RELATION_PIPELINE", None)
    else:
        os.environ["POLYMATH_RELATION_PIPELINE"] = saved


def os_environ_pipeline():
    import os
    os.environ["POLYMATH_RELATION_PIPELINE"] = "kimi_v1"


@pytest.mark.skipif(
    not pathlib.Path(
        "/Users/king/Documents/polymath-rebuild/polymath-v4/.venv").exists(),
    reason="requires repo venv")
def test_possession_theme_recovers_unique_history_entity():
    """C3c: 'Orion's performance ... including ReasonBench' binds Orion."""
    if not SpacySidecar.available():
        pytest.skip("spaCy sidecar not reachable")
    pairs = SpacySidecar.possession_case()
    assert ("Orion Adaptive Reasoning Model", "ReasonBench") in pairs


class SpacySidecar:
    """Thin live-sidecar helper for the possession case."""

    @staticmethod
    def available() -> bool:
        try:
            import urllib.request
            urllib.request.urlopen(
                "http://127.0.0.1:8744/ready", timeout=2)
            return True
        except Exception:
            return False

    @staticmethod
    def possession_case():
        sys.path.insert(0, str(ROOT))
        from workers.summarizer import split_sentences
        from workers.candidates import SentenceSlice
        from polymath_shared.clients import SpacySyntaxClient
        from workers.evidence_proposer import propose_frame_evidence

        sent1 = ("The Orion Adaptive Reasoning Model was introduced by "
                 "the Advanced Computational Intelligence Laboratory.")
        sent2 = ("Evaluation studies examined Orion's performance across "
                 "multiple benchmark suites including ReasonBench.")
        text = f"{sent1} {sent2}"
        client = SpacySyntaxClient()
        try:
            resp = client.syntax([{"sentence_id": "ch:0", "text": sent1},
                                  {"sentence_id": "ch:1", "text": sent2}])
        finally:
            client.close()
        syntax = {r["sentence_id"]: r for r in resp["results"]}
        o_i = text.find("Orion Adaptive Reasoning Model")
        r_i = text.find("ReasonBench")
        orion = _ent("Orion Adaptive Reasoning Model", "Model", o_i)
        bench = _ent("ReasonBench", "Benchmark", r_i)
        lab_i = text.find("Advanced Computational Intelligence Laboratory")
        lab = _ent("Advanced Computational Intelligence Laboratory",
                   "Organization", lab_i)
        sents = split_sentences(text)
        ents = {
            sents[0]: [orion, lab],
            sents[1]: [bench],
        }
        evidence = {sents[0]: [], sents[1]: []}
        for fs in propose_frame_evidence(text, "ch"):
            for s in sents:
                i = text.find(s)
                if i <= fs.start < i + len(s):
                    evidence[s].append(fs)
        pairs = _build_and_collect(
            {sents[0]: syntax["ch:0"], sents[1]: syntax["ch:1"]},
            text, sents, ents, evidence, [])
        return pairs

"""I4R-B: missing-argument rescue unit contract (no services).

Only noun chunks occupying trigger-governed grammatical slots qualify;
free-floating NPs never do. Queries use the NORMAL policy vocabulary
(pass-1 label set — never slot-forced types); exact-full-span-only
acceptance; the canonical type of an accepted prediction flows into the
existing type-compatibility machinery untouched.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import CoreType, EntitySpan, EvidenceSpan
from workers.candidates import SentenceSlice
from workers.rescue import apply_missing_arguments, missing_argument_candidates

REV = "40ec419335d09393f298636f471328b722c6da9"
LABELS = ("Person", "Organization", "Location", "Product", "Technology",
          "Concept", "Method", "Event", "Document", "Process",
          "Measurement", "TimeReference")

# Real dependency parse from the live sidecar (spaCy ClearNLP scheme).
SYNTAX_TEAM = {
    "sentence_id": "c:0",
    "tokens": [
        {"i": 0, "text": "The", "char_start": 0, "char_end": 3, "lemma": "the", "pos": "DET", "tag": "DT", "dep": "det", "head_i": 1},
        {"i": 1, "text": "team", "char_start": 4, "char_end": 8, "lemma": "team", "pos": "NOUN", "tag": "NN", "dep": "nsubj", "head_i": 2},
        {"i": 2, "text": "installed", "char_start": 9, "char_end": 18, "lemma": "instal", "pos": "VERB", "tag": "VBD", "dep": "ROOT", "head_i": 2},
        {"i": 3, "text": "robots", "char_start": 19, "char_end": 25, "lemma": "robot", "pos": "NOUN", "tag": "NNS", "dep": "dobj", "head_i": 2},
        {"i": 4, "text": "and", "char_start": 26, "char_end": 29, "lemma": "and", "pos": "CCONJ", "tag": "CC", "dep": "cc", "head_i": 2},
        {"i": 5, "text": "connected", "char_start": 30, "char_end": 39, "lemma": "connect", "pos": "VERB", "tag": "VBD", "dep": "conj", "head_i": 2},
        {"i": 6, "text": "the", "char_start": 40, "char_end": 43, "lemma": "the", "pos": "DET", "tag": "DT", "dep": "det", "head_i": 7},
        {"i": 7, "text": "workflow", "char_start": 44, "char_end": 52, "lemma": "workflow", "pos": "NOUN", "tag": "NN", "dep": "dobj", "head_i": 5},
        {"i": 8, "text": "to", "char_start": 53, "char_end": 55, "lemma": "to", "pos": "ADP", "tag": "IN", "dep": "prep", "head_i": 5},
        {"i": 9, "text": "Manhattan", "char_start": 56, "char_end": 65, "lemma": "Manhattan", "pos": "PROPN", "tag": "NNP", "dep": "compound", "head_i": 10},
        {"i": 10, "text": "Active", "char_start": 66, "char_end": 72, "lemma": "Active", "pos": "PROPN", "tag": "NNP", "dep": "pobj", "head_i": 8},
        {"i": 11, "text": ".", "char_start": 72, "char_end": 73, "lemma": ".", "pos": "PUNCT", "tag": ".", "dep": "punct", "head_i": 2},
    ],
    "noun_chunks": [
        {"char_start": 0, "char_end": 8, "text": "The team", "root_i": 1},
        {"char_start": 19, "char_end": 25, "text": "robots", "root_i": 3},
        {"char_start": 40, "char_end": 52, "text": "the workflow", "root_i": 7},
        {"char_start": 56, "char_end": 72, "text": "Manhattan Active", "root_i": 10},
    ],
}


def _ev(text, start, end, evidence_class="uses"):
    return EvidenceSpan(
        chunk_id="c1", start=start, end=end, text=text,
        evidence_class=evidence_class, trigger_lemma="install",
        score=1.0, extractor_version="lexical-evidence-v1",
    )


def _slice(entities, evidence):
    return SentenceSlice(
        text="The team installed robots and connected the workflow to Manhattan Active.",
        sentence_start=0, sentence_end=73,
        entities=entities, evidence=evidence, parse=None, syntax=SYNTAX_TEAM,
    )


def test_missing_argument_candidates_trigger_governed_only():
    # entity covers "The team"; nothing covers robots / the workflow /
    # Manhattan Active. Triggers: "installed" (8,16) and "connected"
    # (27,35) — both marked as evidence.
    sl = _slice(
        [EntitySpan(doc_id="d", chunk_id="c1", start=4, end=8, text="team",
                    core_type=CoreType.ORGANIZATION, score=0.9,
                    extractor_version="gliner-2pass-v1")],
        [_ev("installed", 9, 18), _ev("connected", 30, 39)],
    )
    found = missing_argument_candidates(sl, REV, LABELS)
    surfaces = sorted(q.text for q, _cs, _ce in found)
    # "team" is entity-covered (skipped); robots (dobj), workflow (dobj),
    # Manhattan Active (prep->pobj hop) are trigger-governed and missing.
    assert surfaces == ["Manhattan Active", "robots", "workflow"]
    for q, _cs, _ce in found:
        assert q.kind == "missing_argument"
        assert q.labels == LABELS
        assert q.threshold == 0.5


def test_free_floating_np_never_qualifies():
    # No evidence spans (no triggers): nothing is trigger-governed.
    sl = _slice([], [])
    assert missing_argument_candidates(sl, REV, LABELS) == []


def test_entity_covered_np_skipped():
    sl = _slice(
        [EntitySpan(doc_id="d", chunk_id="c1", start=19, end=25, text="robots",
                    core_type=CoreType.PRODUCT, score=0.9,
                    extractor_version="gliner-2pass-v1")],
        [_ev("installed", 9, 18)],
    )
    found = missing_argument_candidates(sl, REV, LABELS)
    assert all(q.text != "robots" for q, _cs, _ce in found)


class _FakeGliner:
    responses: dict[str, list[dict]] = {}
    calls: list = []

    def __init__(self, *a, **kw):
        pass

    def verify_pin(self):
        return None

    def manifest(self):
        return {"identity": {"model": {"revision": REV}}}

    def close(self):
        return None

    def infer_rescue_batch(self, requests):
        _FakeGliner.calls.append(requests)
        return [self.responses.get(r["text"], []) for r in requests]


@pytest.fixture()
def fake_gliner(monkeypatch):
    _FakeGliner.responses = {}
    _FakeGliner.calls = []
    monkeypatch.setattr("polymath_shared.clients.GlinerClient", _FakeGliner)
    return _FakeGliner


def test_apply_missing_arguments_accepts_and_types(fake_gliner):
    fake_gliner.responses = {
        "robots": [{"text": "robots", "start": 0, "end": 6, "label": "Technology", "score": 0.77}],
        "workflow": [{"text": "workflow", "start": 0, "end": 8, "label": "Process", "score": 0.66}],
        "Manhattan Active": [{"text": "Manhattan", "start": 0, "end": 9, "label": "Location", "score": 0.95}],
    }
    sl = _slice([], [_ev("installed", 9, 18), _ev("connected", 30, 39)])
    report = apply_missing_arguments([({"doc_id": "d", "chunk_id": "c1"}, sl)], LABELS)
    added = {(e.text, e.core_type.value, e.pass_kind, e.raw_label) for e in sl.entities}
    assert ("robots", "Technology", "missing_argument_rescue", "Technology") in added
    assert ("workflow", "Process", "missing_argument_rescue", "Process") in added
    # partial-span prediction for "Manhattan Active" is a REFUSAL; "team"
    # (no mock prediction) also refuses — both add nothing
    assert all(not e.text.startswith("Manhattan") for e in sl.entities)
    assert all(e.text != "team" for e in sl.entities)
    assert report["counts"]["candidates"] == 4  # team, robots, workflow, Manhattan Active
    assert report["counts"]["accepted"] == 2
    queries = {q["text"]: q for q in report["queries"]}
    assert queries["Manhattan Active"]["outcome"] == "refused"
    assert queries["robots"]["canonical_type"] == "Technology"
    # normal vocabulary, never slot-forced labels
    assert queries["robots"]["labels"] == list(LABELS)


def test_apply_missing_arguments_refused_adds_nothing(fake_gliner):
    sl = _slice([], [_ev("installed", 9, 18)])
    report = apply_missing_arguments([({"doc_id": "d", "chunk_id": "c1"}, sl)], LABELS)
    assert sl.entities == []
    assert report["counts"]["accepted"] == 0

def test_quantified_np_never_qualifies():
    # "two new surgeons": nummod child -> description, not an entity
    syntax = {
        "sentence_id": "q:0",
        "tokens": [
            {"i": 0, "text": "the", "char_start": 0, "char_end": 3, "lemma": "the", "pos": "DET", "tag": "DT", "dep": "det", "head_i": 4},
            {"i": 1, "text": "company", "char_start": 4, "char_end": 11, "lemma": "company", "pos": "NOUN", "tag": "NN", "dep": "nsubj", "head_i": 2},
            {"i": 2, "text": "hired", "char_start": 12, "char_end": 17, "lemma": "hire", "pos": "VERB", "tag": "VBD", "dep": "ROOT", "head_i": 2},
            {"i": 3, "text": "two", "char_start": 18, "char_end": 21, "lemma": "two", "pos": "NUM", "tag": "CD", "dep": "nummod", "head_i": 6},
            {"i": 4, "text": "new", "char_start": 22, "char_end": 25, "lemma": "new", "pos": "ADJ", "tag": "JJ", "dep": "amod", "head_i": 6},
            {"i": 5, "text": "surgeons", "char_start": 26, "char_end": 34, "lemma": "surgeon", "pos": "NOUN", "tag": "NNS", "dep": "dobj", "head_i": 2},
            {"i": 6, "text": ".", "char_start": 34, "char_end": 35, "lemma": ".", "pos": "PUNCT", "tag": ".", "dep": "punct", "head_i": 2},
        ],
        "noun_chunks": [
            {"char_start": 0, "char_end": 11, "text": "the company", "root_i": 1},
            {"char_start": 18, "char_end": 34, "text": "two new surgeons", "root_i": 5},
        ],
    }
    sl = SentenceSlice(
        text="the company hired two new surgeons.",
        sentence_start=0, sentence_end=35, entities=[], evidence=[_ev("hired", 12, 17)],
        parse=None, syntax=syntax,
    )
    found = missing_argument_candidates(sl, REV, LABELS)
    surfaces = [q.text for q, _cs, _ce in found]
    assert "two new surgeons" not in surfaces  # quantified -> excluded
    assert "company" in surfaces               # unquantified -> eligible

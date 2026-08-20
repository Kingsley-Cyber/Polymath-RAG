"""I4R-A: boundary reconciliation unit contract (no services).

spaCy identifies where semantic certainty is missing; GLiNER is
re-queried about that exact phrase; acceptance is exact-full-span-only;
refused rescue means BOUNDARY_UNRESOLVED — durable mention kept, no
argument binding, no fact. No deterministic promotion.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import CoreType, EntitySpan
from workers.candidates import SentenceSlice
from workers.rescue import (
    RescueQuery,
    _accepted,
    _trimmed_noun_chunks,
    apply_boundary,
    apply_rescue,
    boundary_candidates,
)

REV = "40ec419335d09393f298636f471328b722c6da9"


def _syntax_crestline() -> dict:
    return {
        "sentence_id": "c:0",
        "tokens": [
            {"i": 0, "text": "Crestline", "char_start": 0, "char_end": 9, "lemma": "Crestline", "pos": "PROPN", "tag": "NNP", "dep": "compound", "head_i": 1},
            {"i": 1, "text": "Automation", "char_start": 10, "char_end": 20, "lemma": "automation", "pos": "PROPN", "tag": "NNP", "dep": "nsubj", "head_i": 2},
            {"i": 2, "text": "deployed", "char_start": 21, "char_end": 29, "lemma": "deploy", "pos": "VERB", "tag": "VBD", "dep": "ROOT", "head_i": 2},
            {"i": 3, "text": "a", "char_start": 30, "char_end": 31, "lemma": "a", "pos": "DET", "tag": "DT", "dep": "det", "head_i": 4},
            {"i": 4, "text": "controller", "char_start": 32, "char_end": 42, "lemma": "controller", "pos": "NOUN", "tag": "NN", "dep": "dobj", "head_i": 2},
            {"i": 5, "text": ".", "char_start": 42, "char_end": 43, "lemma": ".", "pos": "PUNCT", "tag": ".", "dep": "punct", "head_i": 2},
        ],
        "noun_chunks": [
            {"char_start": 0, "char_end": 20, "text": "Crestline Automation", "root_i": 1},
            {"char_start": 30, "char_end": 42, "text": "a controller", "root_i": 4},
        ],
    }


def _span(text: str, start: int, end: int, core: str = "Organization") -> EntitySpan:
    return EntitySpan(
        doc_id="d1", chunk_id="c1", start=start, end=end, text=text,
        core_type=CoreType(core), score=0.9, extractor_version="gliner-2pass-v1",
    )


_DEFAULT = object()


def _slice(entities, text="Crestline Automation deployed a controller.", start=0, syntax=_DEFAULT):
    return SentenceSlice(
        text=text, sentence_start=start, sentence_end=start + len(text),
        entities=entities, evidence=[], parse=None,
        syntax=_syntax_crestline() if syntax is _DEFAULT else syntax,
    )


def test_determiner_trim_invariant():
    trimmed = _trimmed_noun_chunks(_syntax_crestline(), "Crestline Automation deployed a controller.")
    surfaces = [(s, e, t) for s, e, t in trimmed]
    assert surfaces == [(0, 20, "Crestline Automation"), (32, 42, "controller")]
    text = "Crestline Automation deployed a controller."
    for s, e, surf in trimmed:
        assert text[s:e] == surf


def test_clean_alignment_and_contraction_detection(monkeypatch):
    monkeypatch.setenv("POLYMATH_QUERY_POLICY", "semantic-query-policy-v1")
    sl = _slice([_span("Crestline", 0, 9), _span("controller", 32, 42, "Product")])
    found = boundary_candidates(sl, REV)
    assert len(found) == 1  # "controller" == trimmed NP is clean, not a candidate
    entity, query, cs, ce = found[0]
    assert query.text == "Crestline Automation"
    assert query.labels == ("Organization",)
    assert query.threshold == 0.5
    assert (cs, ce) == (0, 20)
    assert query.identity == RescueQuery(
        kind="boundary", text="Crestline Automation", labels=("Organization",),
        threshold=0.5, model_revision=REV,
        query_policy_version="semantic-query-policy-v1",
    ).identity
    assert query.query_policy_version == "semantic-query-policy-v1"


def test_acceptance_is_exact_full_span_only(monkeypatch):
    monkeypatch.setenv("POLYMATH_QUERY_POLICY", "semantic-query-policy-v1")
    query = RescueQuery(kind="boundary", text="Crestline Automation",
                        labels=("Organization",), threshold=0.5, model_revision=REV,
                        query_policy_version="semantic-query-policy-v1")
    assert _accepted([{"text": "Crestline Automation", "start": 0, "end": 20,
                       "label": "Organization", "score": 0.8}], query)
    # partial span -> rejection (no deterministic promotion)
    assert _accepted([{"text": "Crestline", "start": 0, "end": 9,
                       "label": "Organization", "score": 0.95}], query) is None
    # wrong type -> rejection
    assert _accepted([{"text": "Crestline Automation", "start": 0, "end": 20,
                       "label": "Product", "score": 0.95}], query) is None


class _FakeGliner:
    responses: dict[str, list[dict]] = {}
    calls: list[list[dict]] = []

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


def test_apply_boundary_accepted_expands_and_refused_abstains(fake_gliner):
    fake_gliner.responses = {
        "Crestline Automation": [
            {"text": "Crestline Automation", "start": 0, "end": 20,
             "label": "Organization", "score": 0.87},
        ],
    }
    sl = _slice([_span("Crestline", 0, 9), _span("controller", 32, 42, "Product")])
    report = apply_boundary([({"chunk_id": "c1"}, sl)])
    assert report["counts"] == {"candidates": 1, "accepted": 1, "refused": 0}
    surfaces = [(e.text, e.start, e.end) for e in sl.entities]
    assert ("Crestline Automation", 0, 20) in surfaces
    assert ("Crestline", 0, 9) not in surfaces
    assert ("controller", 32, 42) in surfaces  # clean alignment untouched
    assert report["queries"][0]["outcome"] == "accepted"
    assert report["queries"][0]["score"] == 0.87
    assert report["queries"][0]["accepted_raw_label"] == "Organization"
    assert report["queries"][0]["query_policy_version"] == "semantic-query-policy-v1"
    expanded = next(e for e in sl.entities if e.text == "Crestline Automation")
    assert expanded.raw_label == "Organization" and expanded.pass_kind == "boundary_rescue"


def test_apply_boundary_refused_marks_unresolved(fake_gliner):
    fake_gliner.responses = {"Crestline Automation": [
        {"text": "Crestline", "start": 0, "end": 9, "label": "Organization", "score": 0.9},
    ]}
    sl = _slice([_span("Crestline", 0, 9)])
    report = apply_boundary([({"chunk_id": "c1"}, sl)])
    assert report["counts"]["refused"] == 1
    assert sl.entities == []  # BOUNDARY_UNRESOLVED (ledger row 63: known limitation)


def test_apply_boundary_dedups_identical_queries(fake_gliner, monkeypatch):
    monkeypatch.setenv("POLYMATH_QUERY_POLICY", "semantic-query-policy-v1")
    fake_gliner.responses = {"Crestline Automation": [
        {"text": "Crestline Automation", "start": 0, "end": 20,
         "label": "Organization", "score": 0.8},
    ]}
    sl1 = _slice([_span("Crestline", 0, 9)])
    sl2 = _slice([_span("Crestline", 0, 9)])
    apply_boundary([({"chunk_id": "c1"}, sl1), ({"chunk_id": "c1"}, sl2)])
    assert len(fake_gliner.calls) == 1
    assert len(fake_gliner.calls[0]) == 1


def test_apply_boundary_v2_expands_per_alias_single_label(fake_gliner, monkeypatch):
    """v2: each provider label becomes its own single-label request (the
    only regime where bare-NP firing was measured); any full-span hit
    under any alias of the canonical type accepts."""
    monkeypatch.setenv("POLYMATH_QUERY_POLICY", "semantic-query-policy-v2")
    fake_gliner.responses = {"Crestline Automation": [
        {"text": "Crestline Automation", "start": 0, "end": 20,
         "label": "Company", "score": 0.82},
    ]}
    sl = _slice([_span("Crestline", 0, 9)])
    report = apply_boundary([({"chunk_id": "c1"}, sl)])
    flat = [r for call in fake_gliner.calls for r in call]
    assert {tuple(r["labels"]) for r in flat} == {("Organization",), ("Company",), ("Corporation",)}
    assert report["counts"]["accepted"] == 1
    assert report["queries"][0]["accepted_raw_label"] == "Company"


def test_apply_rescue_requires_syntax_evidence():
    sl = _slice([], syntax=None)
    with pytest.raises(RuntimeError, match="syntax evidence is missing"):
        apply_rescue([({"chunk_id": "c1"}, sl)], ("boundary",))


def test_rescue_settings_stages(monkeypatch):
    from polymath_shared.settings import RescueSettings

    assert RescueSettings().enabled_stages() == ()
    monkeypatch.setenv("POLYMATH_RESCUE", "on")
    assert RescueSettings().stage_enabled("boundary")
    monkeypatch.setenv("POLYMATH_RESCUE", "boundary,type_reconciliation")
    stages = RescueSettings().enabled_stages()
    assert stages == ("boundary", "type_reconciliation")
    monkeypatch.setenv("POLYMATH_RESCUE", "stanza")
    with pytest.raises(ValueError, match="unknown POLYMATH_RESCUE"):
        RescueSettings().enabled_stages()

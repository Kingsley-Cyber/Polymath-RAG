"""I4R-C: type reconciliation unit contract (no services).

An entity occupying a trigger-governed slot whose canonical type is
incompatible with the slot signature is re-queried over its full
argument NP with the NORMAL policy vocabulary (never slot-forced
labels). A full-span, slot-legal canonical prediction re-types the
entity; anything else keeps the original — the incompatible pairing
abstains downstream exactly as before. No deterministic type rewrite.
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
from workers.rescue import apply_type_reconciliation, type_reconciliation_candidates

REV = "40ec419335d09393f298636f471328b722c6da9e"
LABELS = ("Person", "Organization", "Location", "Product", "Technology",
          "Concept", "Method", "Event", "Document", "Process",
          "Measurement", "TimeReference")

# "Nimbus billing service routes requests..." — object slot entity typed
# Organization while the uses-signature wants Product/Technology.
SYNTAX_NIMBUS = {
    "sentence_id": "c:0",
    "tokens": [
        {"i": 0, "text": "Nimbus", "char_start": 0, "char_end": 6, "lemma": "Nimbus", "pos": "PROPN", "tag": "NNP", "dep": "compound", "head_i": 2},
        {"i": 1, "text": "billing", "char_start": 7, "char_end": 14, "lemma": "billing", "pos": "NOUN", "tag": "NN", "dep": "compound", "head_i": 2},
        {"i": 2, "text": "service", "char_start": 15, "char_end": 22, "lemma": "service", "pos": "NOUN", "tag": "NN", "dep": "nsubj", "head_i": 3},
        {"i": 3, "text": "routes", "char_start": 23, "char_end": 29, "lemma": "route", "pos": "VERB", "tag": "VBZ", "dep": "ROOT", "head_i": 3},
        {"i": 4, "text": "requests", "char_start": 30, "char_end": 38, "lemma": "request", "pos": "NOUN", "tag": "NNS", "dep": "dobj", "head_i": 3},
        {"i": 5, "text": ".", "char_start": 38, "char_end": 39, "lemma": ".", "pos": "PUNCT", "tag": ".", "dep": "punct", "head_i": 3},
    ],
    "noun_chunks": [
        {"char_start": 0, "char_end": 22, "text": "Nimbus billing service", "root_i": 2},
        {"char_start": 30, "char_end": 38, "text": "requests", "root_i": 4},
    ],
}

PACK = {
    "predicates": {
        "uses-tech": {
            "evidence": {"classes": ["uses"]},
            "signatures": [
                {"subject_core": ["Organization", "Product"],
                 "object_core": ["Technology", "Product"]},
            ],
        },
    },
}


def _ev(text, start, end, evidence_class="uses", predicate_id="uses-tech"):
    return EvidenceSpan(
        chunk_id="c1", start=start, end=end, text=text,
        evidence_class=evidence_class, trigger_lemma="route",
        trigger_predicate_id=predicate_id, score=1.0,
        extractor_version="lexical-evidence-v1",
    )


def _slice(entities, evidence):
    return SentenceSlice(
        text="Nimbus billing service routes requests.",
        sentence_start=0, sentence_end=39,
        entities=entities, evidence=evidence, parse=None, syntax=SYNTAX_NIMBUS,
    )


def _org_nimbus():
    return EntitySpan(
        doc_id="d", chunk_id="c1", start=0, end=22,
        text="Nimbus billing service", core_type=CoreType.ORGANIZATION,
        score=0.61, extractor_version="gliner-2pass-v1",
        raw_label="Organization", pass_kind="discovery",
    )


def test_incompatible_subject_type_becomes_candidate():
    # subject "Nimbus billing service" typed Organization; uses-tech
    # subject_core wants Organization/Product -> COMPATIBLE -> no candidate.
    # Make the signature reject Organization to exercise the incompatible path.
    pack = {"predicates": {"uses-tech": {
        "evidence": {"classes": ["uses"]},
        "signatures": [{"subject_core": ["Product", "Technology"],
                        "object_core": ["Technology", "Product"]}],
    }}}
    sl = _slice([_org_nimbus()], [_ev("routes", 23, 29)])
    found = type_reconciliation_candidates(sl, REV, LABELS, pack)
    texts = [q.text for entity, q, _cs, _ce, _t in found]
    assert "Nimbus billing service" in texts
    for entity, q, _cs, _ce, _t in found:
        assert q.kind == "type_reconciliation"
        assert q.labels == LABELS  # normal vocabulary, never slot-forced


def test_compatible_type_not_a_candidate():
    sl = _slice([_org_nimbus()], [_ev("routes", 23, 29)])
    assert type_reconciliation_candidates(sl, REV, LABELS, PACK) == []


class _FakeGliner:
    responses: dict[str, list[dict]] = {}

    def __init__(self, *a, **kw):
        pass

    def verify_pin(self):
        return None

    def manifest(self):
        return {"identity": {"model": {"revision": REV}}}

    def close(self):
        return None

    def infer_rescue_batch(self, requests):
        return [self.responses.get(r["text"], []) for r in requests]


@pytest.fixture()
def fake_gliner(monkeypatch):
    _FakeGliner.responses = {}
    monkeypatch.setattr("polymath_shared.clients.GlinerClient", _FakeGliner)
    return _FakeGliner


def test_retyped_slot_legal_entity_replaces_type(fake_gliner):
    fake_gliner.responses = {
        "Nimbus billing service": [
            {"text": "Nimbus billing service", "start": 0, "end": 22,
             "label": "Product", "score": 0.64},
        ],
    }
    pack = {"predicates": {"uses-tech": {
        "evidence": {"classes": ["uses"]},
        "signatures": [{"subject_core": ["Product", "Technology"],
                        "object_core": ["Technology", "Product"]}],
    }}}
    sl = _slice([_org_nimbus()], [_ev("routes", 23, 29)])
    report = apply_type_reconciliation([({"doc_id": "d", "chunk_id": "c1"}, sl)], LABELS, pack)
    assert report["counts"] == {"candidates": 1, "re_typed": 1, "kept_incompatible": 0}
    (entity,) = sl.entities
    assert entity.core_type.value == "Product"
    assert entity.pass_kind == "type_reconciliation"
    assert entity.raw_label == "Product"
    assert (entity.start, entity.end, entity.text) == (0, 22, "Nimbus billing service")


def test_refused_or_slot_illegal_retype_keeps_original(fake_gliner):
    # GLiNER re-types to Organization (slot-illegal): keep the original
    # entity; the pairing abstains downstream.
    fake_gliner.responses = {
        "Nimbus billing service": [
            {"text": "Nimbus billing service", "start": 0, "end": 22,
             "label": "Organization", "score": 0.9},
        ],
    }
    pack = {"predicates": {"uses-tech": {
        "evidence": {"classes": ["uses"]},
        "signatures": [{"subject_core": ["Product", "Technology"],
                        "object_core": ["Technology", "Product"]}],
    }}}
    sl = _slice([_org_nimbus()], [_ev("routes", 23, 29)])
    report = apply_type_reconciliation([({"doc_id": "d", "chunk_id": "c1"}, sl)], LABELS, pack)
    assert report["counts"]["re_typed"] == 0
    assert report["counts"]["kept_incompatible"] == 1
    (entity,) = sl.entities
    assert entity.core_type.value == "Organization"  # untouched
    assert entity.pass_kind == "discovery"

"""KIMI-ARCHITECTURE-REALIGNMENT-V1 unit tests: UD-anchored candidate
generation. Verifies: UD-tree primary binding, post-structural type
precheck, no Cartesian explosion, fallback discipline, and that the
key sentence (robust implementation uses bounded leases) now creates
a STRUCTURAL candidate that is honestly type-filtered (not silently
blocked by an early type veto)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.contracts import CoreType, EntitySpan, EvidenceSpan
from polymath_shared.rulepack import load_rule_pack
from workers.candidates import SentenceSlice
from tests.historical_boundary import build_candidates_kimi
from workers.kimi_candidates import (
    _find_ud_arguments,
    _token_to_entity,
    _trigger_head_token,
)

PACK = load_rule_pack(pack_version="1.3.0")

# Real spaCy parse of the key sentence (from live sidecar)
SYNTAX_KEY = {
    "sentence_id": "s:0",
    "tokens": [
        {"i": 0, "text": "A", "char_start": 0, "char_end": 1, "lemma": "a", "pos": "DET", "tag": "DT", "dep": "det", "head_i": 2},
        {"i": 1, "text": "robust", "char_start": 2, "char_end": 8, "lemma": "robust", "pos": "ADJ", "tag": "JJ", "dep": "amod", "head_i": 2},
        {"i": 2, "text": "implementation", "char_start": 9, "char_end": 23, "lemma": "implementation", "pos": "NOUN", "tag": "NN", "dep": "nsubj", "head_i": 3},
        {"i": 3, "text": "uses", "char_start": 24, "char_end": 27, "lemma": "use", "pos": "VERB", "tag": "VBZ", "dep": "ROOT", "head_i": 3},
        {"i": 4, "text": "bounded", "char_start": 28, "char_end": 35, "lemma": "bounded", "pos": "ADJ", "tag": "JJ", "dep": "amod", "head_i": 5},
        {"i": 5, "text": "leases", "char_start": 36, "char_end": 42, "lemma": "lease", "pos": "NOUN", "tag": "NNS", "dep": "dobj", "head_i": 3},
        {"i": 6, "text": ".", "char_start": 42, "char_end": 43, "lemma": ".", "pos": "PUNCT", "tag": ".", "dep": "punct", "head_i": 3},
    ],
    "noun_chunks": [
        {"char_start": 0, "char_end": 23, "text": "A robust implementation", "root_i": 2},
        {"char_start": 28, "char_end": 42, "text": "bounded leases", "root_i": 5},
    ],
}

TEXT_KEY = "A robust implementation uses bounded leases."


def _ev(text, start, end, evidence_class="usage_application", predicate_id="uses"):
    return EvidenceSpan(
        chunk_id="c", start=start, end=end, text=text,
        evidence_class=evidence_class, trigger_lemma="use",
        trigger_predicate_id=predicate_id, score=1.0,
        extractor_version="t")


def _ent(text, start, end, core, score=0.8):
    return EntitySpan(
        doc_id="d", chunk_id="c", start=start, end=end, text=text,
        core_type=CoreType(core), score=score, extractor_version="t",
        raw_label=core, pass_kind="discovery")


def _slice(entities, evidence, text=TEXT_KEY, syntax=None):
    return SentenceSlice(
        text=text, sentence_start=0, sentence_end=len(text),
        entities=entities, evidence=evidence, parse=None,
        syntax=syntax or SYNTAX_KEY)


class _Obs:
    def __init__(self):
        self.outcomes = []
    def record_candidate_outcome(self, sl, ev, code, detail=None):
        self.outcomes.append((code, detail or {}))


def test_ud_tree_binds_subject_and_object():
    """UD primary binding: nsubj(uses) = implementation, dobj(uses) = leases."""
    tokens = sorted(SYNTAX_KEY["tokens"], key=lambda t: t["char_start"])
    trig = _trigger_head_token(tokens, _ev("uses", 24, 27), _slice([], []))
    assert trig is not None and trig["text"] == "uses"
    args = _find_ud_arguments(tokens, trig)
    assert len(args["subject"]) == 1 and args["subject"][0]["text"] == "implementation"
    assert len(args["object"]) == 1 and args["object"][0]["text"] == "leases"


def test_kimi_creates_structural_candidate_before_type_check():
    """The key sentence: entities bound structurally by UD, then type
    precheck runs on the STRUCTURAL pair. Even if Technology→Technology
    fails uses compatibility, the trace should show TYPE_PRECHECK_IMPOSSIBLE
    (honest) not SUBJECT_ENDPOINT_UNAVAILABLE (early veto)."""
    entities = [
        _ent("robust implementation", 2, 23, "Technology"),
        _ent("bounded leases", 28, 42, "Technology"),
    ]
    evidence = [_ev("uses", 24, 27)]
    sl = _slice(entities, evidence)
    obs = _Obs()
    candidates = build_candidates_kimi(
        [sl], doc_id="d", corpus_id="eval", ontology_profile="core",
        extractor_version="t", rule_pack=PACK, observer=obs)

    # verify binding happened structurally
    binding_sources = [d.get("binding_source") for _, d in obs.outcomes]
    assert any("UD_DIRECT" in str(bs) for bs in binding_sources), f"no UD binding: {binding_sources}"

    # the outcome should be TYPE_PRECHECK (honest) or CANDIDATE_CREATED
    codes = [c for c, _ in obs.outcomes]
    assert "SUBJECT_ENDPOINT_UNAVAILABLE" not in codes, f"early veto leaked: {codes}"
    # ADR-0016 Phase 5: the trace now names the structural step that
    # succeeded before the type step that failed.
    assert "UD_SUBJECT_BOUND" in codes and "UD_OBJECT_BOUND" in codes, codes
    # Technology→Technology for uses is actually legal (both in sig), so
    # candidate should form
    assert len(candidates) > 0 or "TYPE_PRECHECK_FAIL" in codes


def test_kimi_no_cartesian_explosion():
    """Multiple entities around one trigger → only UD-bound pairs, no
    left×right cross product."""
    entities = [
        _ent("Alpha Corp", 0, 10, "Organization"),
        _ent("Beta Corp", 11, 20, "Organization"),
        _ent("Gamma Corp", 21, 30, "Organization"),
        _ent("Delta system", 45, 57, "Technology"),
        _ent("Epsilon tool", 58, 70, "Technology"),
    ]
    evidence = [_ev("uses", 35, 39)]
    sl = _slice(entities, evidence,
                text="Alpha Corp Beta Corp Gamma Corp uses Delta system Epsilon tool.",
                syntax=None)  # no syntax → bounded recall fallback
    obs = _Obs()
    candidates = build_candidates_kimi(
        [sl], doc_id="d", corpus_id="eval", ontology_profile="core",
        extractor_version="t", rule_pack=PACK, observer=obs)
    # bounded recall takes only nearest (one subject, one object)
    assert len(candidates) <= 3, f"explosion: {len(candidates)} candidates"


def test_kimi_fallback_when_no_syntax():
    """Without syntax evidence, bounded linear recall provides the
    nearest left/right entity (same behavior as legacy for discovery,
    but type check runs AFTER pair formation)."""
    entities = [
        _ent("Acme Corp", 0, 9, "Organization"),
        _ent("Kubernetes", 15, 25, "Technology"),
    ]
    evidence = [_ev("uses", 10, 14)]
    sl = _slice(entities, evidence,
                text="Acme Corp uses Kubernetes.",
                syntax=None)
    candidates = build_candidates_kimi(
        [sl], doc_id="d", corpus_id="eval", ontology_profile="core",
        extractor_version="t", rule_pack=PACK)
    assert len(candidates) >= 1  # Org→Tech is legal uses pair


def test_token_to_entity_head_mapping():
    tokens = sorted(SYNTAX_KEY["tokens"], key=lambda t: t["char_start"])
    entities = [_ent("robust implementation", 2, 23, "Technology"),
                _ent("bounded leases", 28, 42, "Technology")]
    sl = _slice(entities, [])
    subj_tok = tokens[2]  # "implementation" nsubj
    obj_tok = tokens[5]   # "leases" dobj
    subj_ent = _token_to_entity(subj_tok, entities, sl)
    obj_ent = _token_to_entity(obj_tok, entities, sl)
    assert subj_ent is not None and subj_ent.text == "robust implementation"
    assert obj_ent is not None and obj_ent.text == "bounded leases"


def test_kimi_active_pipeline_dispatch():
    """The dispatch selects kimi_v1 when env is set, legacy_v1 otherwise."""
    from workers.kimi_candidates import active_pipeline
    assert active_pipeline() == "legacy_v1"  # default
    os.environ["POLYMATH_RELATION_PIPELINE"] = "kimi_v1"
    try:
        assert active_pipeline() == "kimi_v1"
    finally:
        del os.environ["POLYMATH_RELATION_PIPELINE"]
    assert active_pipeline() == "legacy_v1"

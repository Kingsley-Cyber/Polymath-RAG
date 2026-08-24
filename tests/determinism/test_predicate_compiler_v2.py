"""PREDICATE-COMPILER-V2 regression fixtures.

Covers: frame resolution (exact word-boundary, multiword, provenance),
signature validation (type-driven trained_on vs trained_with; negative
examples UNSUPPORTED), compound head inheritance ("BERT model" binds
BERT), and the DOC_003 negative-class guarantees (speculative similarity
must not compile).

These tests ARE the authored fixtures required by the owner's mission
(positive + negative per family).
"""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import pytest

from polymath_shared.rulepack.semantic_frames import (
    resolve_frames,
    resolve_predicate,
    load_ontology,
)
from polymath_shared.rulepack.compound_heads import (
    resolve_compound_heads,
    is_generic_head,
    strip_head_from_subject,
)


# --- frame resolution ---------------------------------------------------

def test_pretrained_resolves_training_frame():
    frames = resolve_frames("The BERT model was pretrained on BooksCorpus.")
    assert [f.frame_id for f in frames] == ["training_event"]
    assert frames[0].surface == "pretrained"
    assert "authored-extension" in frames[0].provenance


def test_introduced_resolves_creation_frame_with_propbank_provenance():
    frames = resolve_frames(
        "The BERT model was introduced by Google Research in 2018.")
    assert frames[0].frame_id == "creation_event"
    assert frames[0].provenance.startswith("propbank:introduce")


def test_multiword_realization_matches_across_whitespace():
    frames = resolve_frames("Neural models rely   on large datasets.")
    assert any(f.surface == "reli es on".replace(" ", "") for f in frames) or \
        any(f.lemma == "rely-on" for f in frames)


def test_word_boundary_no_substring_false_positives():
    # 'rate' is a v1 trigger; ensure ontology surfaces do not fire inside
    # unrelated words (e.g. 'evaluate' must NOT contain-fire 'rate')
    frames = resolve_frames("We evaluate the model.")
    fired = {f.surface for f in frames}
    assert "rate" not in fired
    assert "evaluate" in fired


def test_all_five_families_present_in_ontology():
    frames_ids = set(load_ontology()["frames"])
    assert {"training_event", "evaluation_event", "creation_event",
            "usage_event", "release_event"} <= frames_ids


# --- signature validation ----------------------------------------------

def test_trained_on_requires_dataset_object():
    m = resolve_predicate("training_event", "Model", "Corpus")
    assert m and m["predicate"] == "trained_on"


def test_optimizer_object_never_becomes_trained_on():
    # negative example from the ontology, enforced by types
    assert resolve_predicate("training_event", "Model", "Method") \
        .get("predicate") == "trained_with"
    assert resolve_predicate("training_event", "Model", "Optimizer") is None


def test_evaluation_maps_to_evaluated_on_for_benchmarks():
    assert resolve_predicate("evaluation_event", "Model", "Benchmark") \
        ["predicate"] == "evaluated_on"


def test_unknown_type_pair_is_unsupported_fail_closed():
    assert resolve_predicate("evaluation_event", "Dataset", "Person") is None


def test_none_types_are_unsupported():
    assert resolve_predicate("training_event", None, "Dataset") is None


# --- compound scientific heads ------------------------------------------

def test_generic_head_detected():
    assert is_generic_head("model") and is_generic_head("Framework")


def test_compound_modifier_absorbs_slot_and_head_dropped():
    spans = [
        {"text": "BERT", "start": 4, "end": 8},
        {"text": "model", "start": 9, "end": 14},
    ]
    kept = resolve_compound_heads(spans)
    assert [s["text"] for s in kept] == ["BERT"]


def test_bare_generic_head_is_dropped():
    assert resolve_compound_heads([{"text": "large", "start": 0, "end": 5},
                                   {"text": "model", "start": 6, "end": 11}]) \
        == [{"text": "large", "start": 0, "end": 5}]


def test_non_adjacent_generic_head_not_merged():
    spans = [
        {"text": "BERT", "start": 0, "end": 4},
        {"text": "achieves", "start": 10, "end": 18},
        {"text": "model", "start": 25, "end": 30},
    ]
    kept = resolve_compound_heads(spans)
    assert [s["text"] for s in kept] == ["BERT", "achieves"]


def test_subject_tail_strip_confirms_entity_head():
    assert strip_head_from_subject("BERT model", "BERT")
    assert not strip_head_from_subject("large model", "BERT")


# --- DOC_003 negative class (speculative similarity) --------------------

def test_speculative_similarity_has_no_comparison_mapping():
    # "GPT may appear similar to previous systems" — no realization of
    # evaluation_event fires on appear/similar, so nothing resolves.
    assert resolve_frames("GPT may appear similar to previous systems.") == []


def test_ontology_negative_examples_are_machine_checkable():
    for fid, frame in load_ontology()["frames"].items():
        for m in frame.get("mappings", []):
            for neg in m.get("negative_examples", []):
                assert neg.get("sentence") and neg.get("reason"), (fid, neg)


# --- production splice: proposer frame lane (env-gated) -----------------

def test_frame_lane_off_by_default(monkeypatch):
    import os
    from workers.evidence_proposer import propose_evidence
    monkeypatch.delenv("POLYMATH_PREDICATE_V2", raising=False)
    pack = {"predicate_order": [], "predicates": {}}
    spans = propose_evidence(
        "The BERT model was pretrained on BooksCorpus.", "c1", pack)
    assert spans == [], "frame lane must be OFF unless explicitly enabled"


def test_frame_lane_emits_provenance_anchors(monkeypatch):
    from workers.evidence_proposer import propose_evidence
    monkeypatch.setenv("POLYMATH_PREDICATE_V2", "shadow")
    pack = {"predicate_order": [], "predicates": {}}
    text = "The BERT model was introduced by Google Research in 2018."
    spans = propose_evidence(text, "c1", pack)
    assert spans and all(s.trigger_lexical_class == "FRAME" for s in spans)
    f = spans[0]
    assert f.trigger_match_source.startswith("frame:creation_event|")
    assert "propbank:introduce" in f.trigger_match_source
    assert 0 <= f.start < f.end <= len(text)


def test_trigger_lane_keeps_precedence_on_overlap(monkeypatch):
    from workers.evidence_proposer import propose_evidence
    monkeypatch.setenv("POLYMATH_PREDICATE_V2", "enforce")
    # 'rate' is a v1 trigger surface; construct a pack whose trigger
    # overlaps a frame realization span
    pack = {"predicate_order": ["r1"], "predicates": {"r1": {
        "evidence": {"classes": ["action"], "nouns": ["benchmark"]}}}}
    spans = propose_evidence("We benchmark the model.", "c1", pack)
    bench = [s for s in spans if s.text == "benchmark"]
    assert len(bench) == 1 and bench[0].trigger_match_source == "nouns", (
        "trigger lane must win overlapping spans; frame lane supplements only")


# --- production splice: compiler FRAME branch ---------------------------

def _candidate_for(text, trigger_start, trigger_end, subj_type, obj_type):
    from polymath_shared.contracts import (
        EntitySpan, EvidenceSpan, EntityCandidate, RelationCandidate,
        ScopeFlags, CoreType,
    )
    ev = EvidenceSpan(
        chunk_id="ch", start=trigger_start, end=trigger_end,
        text=text[trigger_start:trigger_end], evidence_class="action",
        trigger_lemma="introduced", trigger_lexical_class="FRAME",
        trigger_predicate_id=None,
        trigger_match_source="frame:creation_event|propbank:introduce.01",
        score=1.0, extractor_version="test")
    sub = EntitySpan(doc_id="d", chunk_id="ch", start=0, end=4, text="BERT",
                     core_type=CoreType(subj_type), score=1.0,
                     extractor_version="test")
    obj = EntitySpan(doc_id="d", chunk_id="ch", start=20, end=35,
                     text="Google Research",
                     core_type=CoreType(obj_type), score=1.0,
                     extractor_version="test")
    return RelationCandidate(
        evidence=ev,
        subject=EntityCandidate(span=sub, resolved_entity_id="ent_x"),
        object=EntityCandidate(span=obj, resolved_entity_id="ent_y"),
        ontology_profile="core",
        scope=ScopeFlags())


def test_compiler_frame_branch_accepts_with_full_provenance():
    from polymath_shared.rulepack.compiler import compile_relation
    c = _candidate_for("The BERT model was introduced by Google Research.",
                       22, 32, "Architecture", "ResearchGroup")
    d = compile_relation(c, None, {"predicate_order": [], "predicates": {}})
    assert d.decision == "ACCEPT"
    assert d.rule_id == "introduced_by"
    for token in ("semantic_frame_id=creation_event",
                  "lexical_resource_source=propbank:introduce.01",
                  "predicate_mapping_rule=introduced_by",
                  "subject_type=Architecture",
                  "object_type=ResearchGroup"):
        assert token in d.reason


def test_compiler_frame_branch_fail_closed_on_bad_types():
    from polymath_shared.rulepack.compiler import compile_relation
    c = _candidate_for("The optimizer trained the model.", 4, 11,
                       "Model", "Metric")
    d = compile_relation(c, None, {"predicate_order": [], "predicates": {}})
    assert d.decision == "UNSUPPORTED"
    assert "frame_unmapped" in d.reason


def test_compiler_frame_branch_rejects_speculative():
    from polymath_shared.contracts import ScopeFlags
    from polymath_shared.rulepack.compiler import compile_relation
    c = _candidate_for("BERT was introduced by Google Research.",
                       9, 19, "Architecture", "ResearchGroup")
    c = c.model_copy(update={"scope": ScopeFlags(speculative=True)})
    d = compile_relation(c, None, {"predicate_order": [], "predicates": {}})
    assert d.decision == "REJECT" and "frame_scope_reject" in d.reason


# --- CATEGORY-C: role-oriented frame binding (frame_roles) --------------

def _tok(i, text, lemma, pos, dep, head_i, cs, ce):
    return {"i": i, "text": text, "lemma": lemma, "pos": pos, "dep": dep,
            "head_i": head_i, "char_start": cs, "char_end": ce}


def _ent(text, start, end, ctype):
    from polymath_shared.contracts import EntitySpan
    return EntitySpan(doc_id="d", chunk_id="ch", start=start, end=end,
                      text=text, core_type=ctype, score=1.0,
                      extractor_version="test")


def test_c1_active_voice_orientation_binds_theme_not_agent():
    """Studies evaluated BERT on GLUE -> subject=BERT(ARG1), never Studies."""
    from polymath_shared.rulepack.frame_roles import (
        orient_frame_slots, detect_voice)
    #        0 Studies  evaluated  BERT   on   GLUE
    toks = [
        _tok(0, "Studies", "study", "NOUN", "nsubj", 1, 0, 7),
        _tok(1, "evaluated", "evaluate", "VERB", "ROOT", -1, 8, 17),
        _tok(2, "BERT", "BERT", "PROPN", "obj", 1, 18, 22),
        _tok(3, "on", "on", "ADP", "prep", 1, 23, 25),
        _tok(4, "GLUE", "GLUE", "PROPN", "pobj", 3, 26, 30),
    ]
    ud = {"subject": [toks[0]], "object": [toks[2]],
          "prep_object": [toks[4]], "oblique": [], "coordination": []}
    assert detect_voice(toks, toks[1]) == "active"
    o = orient_frame_slots(toks, toks[1], ud, "theme_standard")
    assert [t["text"] for t in o["fact_subject"]] == ["BERT"]
    assert [t["text"] for t in o["fact_object"]] == ["GLUE"]


def test_c1_passive_voice_orientation_swaps_correctly():
    from polymath_shared.rulepack.frame_roles import (
        orient_frame_slots, detect_voice)
    # BERT was evaluated on GLUE  /  introduced by Google Research
    toks = [
        _tok(0, "BERT", "BERT", "PROPN", "nsubj:pass", 2, 0, 4),
        _tok(1, "was", "be", "AUX", "aux:pass", 2, 5, 8),
        _tok(2, "introduced", "introduce", "VERB", "ROOT", -1, 9, 19),
        _tok(3, "by", "by", "ADP", "agent", 2, 20, 22),
        _tok(4, "Google", "Google", "PROPN", "pobj", 3, 23, 29),
    ]
    ud = {"subject": [toks[0]], "object": [],
          "prep_object": [toks[4]], "oblique": [], "coordination": []}
    assert detect_voice(toks, toks[2]) == "passive"
    o = orient_frame_slots(toks, toks[2], ud, "theme_by_agent")
    assert [t["text"] for t in o["fact_subject"]] == ["BERT"]
    assert [t["text"] for t in o["fact_object"]] == ["Google"]


def test_c2_head_chain_binds_entity_across_generic_heads():
    from polymath_shared.rulepack.frame_roles import head_chain_theme
    from polymath_shared.contracts import CoreType
    # "Tree of Thoughts is a reasoning framework introduced by Princeton"
    sent = "Tree of Thoughts is a reasoning framework introduced by Princeton"
    ents = [_ent("Tree of Thoughts", 0, 16, CoreType.FRAMEWORK)]
    got = head_chain_theme(sent, ents, trigger_start=sent.index("introduced"))
    assert got is not None and got.text == "Tree of Thoughts"


def test_c2_head_chain_rejects_non_inert_gap():
    from polymath_shared.rulepack.frame_roles import head_chain_theme
    from polymath_shared.contracts import CoreType
    sent = "Tree of Thoughts outperformed baselines and was introduced by Princeton"
    ents = [_ent("Tree of Thoughts", 0, 16, CoreType.FRAMEWORK)]
    assert head_chain_theme(
        sent, ents, trigger_start=sent.index("introduced")) is None


def test_c3_pronoun_resolves_only_when_unique_and_compatible():
    from polymath_shared.rulepack.frame_roles import resolve_pronoun_subject
    from polymath_shared.contracts import CoreType
    pron = _tok(0, "It", "it", "PRON", "nsubj:pass", 2, 0, 2)
    prev = [_ent("BERT", 0, 4, CoreType.ARCHITECTURE)]
    ent, note = resolve_pronoun_subject(pron, prev, {"model", "architecture",
                                                     "system"})
    assert ent is not None and note.startswith("pronoun_resolved_unique")

    # ambiguity: two same-type candidates -> fail closed
    prev2 = [_ent("BERT", 0, 4, CoreType.ARCHITECTURE),
             _ent("GPT", 20, 23, CoreType.MODEL)]
    ent2, note2 = resolve_pronoun_subject(pron, prev2, {"model",
                                                        "architecture"})
    assert ent2 is None and note2.startswith("pronoun_ambiguous")

    # type-incompatible candidate -> no resolution
    prev3 = [_ent("BooksCorpus", 0, 11, CoreType.CORPUS)]
    ent3, _ = resolve_pronoun_subject(pron, prev3, {"model"})
    assert ent3 is None

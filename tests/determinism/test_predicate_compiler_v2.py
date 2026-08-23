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

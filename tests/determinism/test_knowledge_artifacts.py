"""KNOWLEDGE ARTIFACT LAYER fixtures: procedures + concepts."""
from __future__ import annotations

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.knowledge_objects.procedure import (
    compile_procedure, split_step_sentences)
from polymath_shared.knowledge_objects.concept import compile_concepts

GA4 = ("First open GA4 Explore. Select Free Form. Add item added to "
       "cart metric. Add item ID dimensions. Run the report.")


def test_procedure_compiles_steps_with_lineage():
    p = compile_procedure(document_id="d1", corpus_id="c1", text=GA4,
                          title="GA4 report",
                          source_chunk_ids=["ch_1"])
    assert p is not None
    assert len(p["steps"]) >= 4
    assert p["document_id"] == "d1"
    assert p["source_chunk_ids"] == ["ch_1"]
    assert p["artifact_type"] == "PROCEDURE"
    assert p["artifact_id"].startswith("proc_")


def test_step_inline_markers_split_sentences():
    sents = split_step_sentences(
        "Step 1: Install the agent. Step 2: Configure the rules.")
    assert any("Install" in x for x in sents)
    assert any("Configure" in x for x in sents)


def test_sequence_openers_count_as_imperative():
    sents = split_step_sentences("First deploy the cluster using kubeadm.")
    imp = [s for s in sents]
    p = compile_procedure(document_id="d", corpus_id="c",
                          text="First deploy the cluster. Next configure ingress.",
                          title="k8s")
    assert p is not None and len(p["steps"]) >= 2


def test_fail_closed_below_min_steps():
    assert compile_procedure(document_id="d", corpus_id="c",
                             text="Run one thing.", title="x") is None


def test_concept_definition_extraction_strips_articles():
    sents = ["A threat model describes assumptions about attackers.",
             "The dichotomy of control is defined as focusing on "
             "controllable actions."]
    got = compile_concepts(document_id="d", corpus_id="c", sentences=sents)
    names = {c["name"].lower() for c in got}
    assert "threat model" in names
    assert "dichotomy of control" in names


def test_concepts_never_become_facts():
    """Concept compiler output has no fact fields — typed separation."""
    got = compile_concepts(document_id="d", corpus_id="c",
                           sentences=["A hook means a short opening "
                                      "line that captures attention."])
    assert got and all("predicate" not in c for c in got)


def test_no_hallucinated_artifacts_empty_input():
    assert compile_procedure(document_id="d", corpus_id="c", text="",
                             title="x") is None
    assert compile_concepts(document_id="d", corpus_id="c",
                            sentences=[]) == []

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


# ---- TRANSCRIPT-REGISTER-V1 fixtures (additions to the deterministic
# ---- lists require regression fixtures — this is them) --------------

def test_conversational_leads_expose_imperative_steps():
    """Real spoken instructions hide behind leads: 'So click …',
    'Okay, so let's run …', 'Just paste …' are steps."""
    text = ("So click on the free notebook. Okay, so let's run the "
            "next cell. Just paste in the model name.")
    p = compile_procedure(document_id="d", corpus_id="c", text=text,
                          title="transcript")
    assert p is not None
    assert len(p["steps"]) == 3


def test_narrated_actions_are_not_steps():
    """'So we run the tests' narrates; it does not instruct."""
    assert compile_procedure(
        document_id="d", corpus_id="c",
        text="So we run the tests. And then I click the button.",
        title="x") is None


def test_concept_copula_definition_registers():
    sents = [
        "Fine-tuning is adjusting a base model's weights to improve "
        "performance on specific tasks.",
        "HTML stands for hypertext markup language.",
        "We used Unsloth, which is an open source library to "
        "fine-tune any models.",
        "A vector database is a system that stores embeddings for "
        "similarity search.",
    ]
    got = compile_concepts(document_id="d", corpus_id="c", sentences=sents)
    names = {c["name"].lower() for c in got}
    assert "fine-tuning" in names
    assert "html" in names
    assert "unsloth" in names
    assert "vector database" in names


def test_copula_statements_are_not_definitions():
    """Status statements and pronoun/fragment subjects never become
    concepts: definitional REGISTER, not any copula."""
    sents = [
        "The model is training on the dataset right now.",
        "This is a must-have skill for engineers.",
        "But the main thing is torch which stands for pytorch.",
        "It is a nice day outside in the mountains.",
    ]
    got = compile_concepts(document_id="d", corpus_id="c", sentences=sents)
    names = {c["name"].lower() for c in got}
    assert not names & {"model", "this", "it",
                        "but the main thing is torch which"}, names

"""SUMMARY-LAYER S3-S5: document/corpus composition + vocabulary."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.summary_layer import validate_envelope  # noqa: E402
from polymath_shared.summary_workers import (  # noqa: E402
    build_corpus_summary,
    build_document_summary,
    vocabulary_admission,
)


def _parent(pid, summary, entities, concepts):
    return {"artifact_id": f"sum_{pid}", "payload": {
        "summary_type": "parent", "parent_id": pid, "summary": summary,
        "entities": entities, "concepts": concepts,
        "derived_from": [f"child_{pid}_1"]}}


def test_document_summary_consumes_parents_only():
    parents = [
        _parent("p1", "Transformer uses self-attention.",
                ["Transformer"], ["self-attention"]),
        _parent("p2", "BERT was trained on BooksCorpus.",
                ["BERT"], ["pretraining"]),
    ]
    env = build_document_summary(document_id="doc_1", title="Attention 101",
                                 parent_summaries=parents)
    assert not validate_envelope(env)
    p = env["payload"]
    assert p["summary_type"] == "document"
    assert "Attention 101 —" in p["summary"]
    assert set(p["major_entities"]) >= {"Transformer", "BERT"}
    assert set(p["major_concepts"]) >= {"self-attention", "pretraining"}
    assert sorted(p["derived_from"]) == ["p1", "p2"]


def test_corpus_summary_aggregates_documents():
    docs = [
        {"artifact_id": "sum_a", "derived_from": ["parent_1"],
         "payload": {"summary_type": "document",
                     "major_entities": ["BERT", "GPT"],
                     "major_concepts": ["attention", "pretraining"],
                     "predicates": ["trained_on", "evaluated_on"],
                     "summary": "s"}},
        {"artifact_id": "sum_b", "derived_from": ["parent_2"],
         "payload": {"summary_type": "document",
                     "major_entities": ["BERT"],
                     "major_concepts": ["attention"],
                     "predicates": ["evaluated_on"], "summary": "s"}},
    ]
    env = build_corpus_summary(corpus_id="ml_research",
                               document_summaries=docs)
    assert not validate_envelope(env)
    p = env["payload"]
    assert p["summary_type"] == "corpus"
    assert p["important_entities"][0] == "BERT"
    assert set(p["dominant_concepts"]) <= {"attention", "pretraining"}
    assert p["common_predicates"][:1] == ["evaluated_on"]


def test_vocabulary_admission_accumulates_aliases_with_provenance():
    docs = [{"artifact_id": "sum_x",
             "payload": {"summary_type": "document",
                         "major_concepts": ["transformer model"]}}]
    facts = [{"predicate": "trained_on", "fact_id": "fact_001"},
             {"predicate": "evaluated_on", "fact_id": "fact_002"}]
    vocab = vocabulary_admission(document_summaries=docs,
                                 accepted_facts=facts)
    by_cpt = {e["concept"]: e for e in vocab["entries"]}
    tm = by_cpt["transformer_model"]
    assert "transformer model" in tm["aliases"]
    assert "sum_x" in tm["supported_by"]
    tr = by_cpt["trained_on"]
    assert tr["aliases"] == ["trained on"]
    assert tr["supported_by"] == ["fact_001"]

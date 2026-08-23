"""ACCEPTANCE-HARNESS-V1: scorer unit tests on the owner's template."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.acceptance_harness import (  # noqa: E402
    score_acceptance,
)

LABELS = {
    "entities": ["BERT", "BooksCorpus", "GLUE"],
    "facts": [
        {"subject": "BERT", "predicate": "trained_on",
         "object": "BooksCorpus"},
        {"subject": "BERT", "predicate": "evaluated_on", "object": "GLUE"},
    ],
    "events": [{"type": "evaluation", "time": "2023-03"}],
}

SYSTEM_GOOD = {
    "admitted_entities": ["bert", "bookscorpus", "glue", "attention"],
    "admitted_facts": [
        {"subject": "BERT", "predicate": "trained_on",
         "object": "BooksCorpus", "chunk_id": "c1"},
        {"subject": "BERT", "predicate": "evaluated_on", "object": "GLUE",
         "chunk_id": "c2"},
        {"subject": "BERT", "predicate": "uses", "object": "attention",
         "chunk_id": "c3"},
    ],
    "admitted_events": [{"type": "evaluation_event"}],
}


def test_full_agreement_scores_high():
    r = score_acceptance(LABELS, **SYSTEM_GOOD)
    assert r["entity_recall"]["score"] == 1.0
    assert r["predicate_precision"]["score"] == round(2 / 3, 4)
    assert r["event_recall"]["score"] == 1.0
    assert r["evidence_support"]["score"] == 1.0


def test_missing_knowledge_drops_recall():
    system = {"admitted_entities": [],
              "admitted_facts": [],
              "admitted_events": []}
    r = score_acceptance(LABELS, **system)
    assert r["entity_recall"]["score"] == 0.0
    assert r["predicate_precision"]["score"] is None
    assert r["event_recall"]["score"] == 0.0


def test_direction_error_counts_against_precision():
    system = {"admitted_entities": ["bert", "bookscorpus"],
              "admitted_facts": [
                  {"subject": "BooksCorpus", "predicate": "trained_on",
                   "object": "BERT", "chunk_id": "c1"}],
              "admitted_events": []}
    r = score_acceptance(LABELS, **system)
    assert r["predicate_precision"]["score"] == 0.0

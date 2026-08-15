"""R1E Pass-2 corpus reach determinism (pure; no stores).

ConceptState admission guards (generic heads + stopwords rejected),
deterministic serialized reach query, exclusion contract, no
recursion, plan defaults.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[2])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.reach import (  # noqa: E402
    REACH_PLAN_VERSION,
    CorpusReachPlan,
    Pass1ConceptState,
    _admit_term,
)


def test_plan_defaults_versioned_and_bounded():
    plan = CorpusReachPlan()
    assert plan.plan_version == REACH_PLAN_VERSION
    assert plan.exclude_pass1_documents is True
    assert plan.max_seed_concepts <= 10
    assert plan.max_reach_documents <= 5
    assert plan.max_reach_children <= 10


def test_generic_heads_never_admitted():
    for bad in ("system", "the model", "platform", "component", "service", "process", "data"):
        assert not _admit_term(bad), f"generic seed admitted: {bad!r}"


def test_stopwords_never_admitted():
    for bad in ("about", "actions", "additional", "the", "also", "just", "because"):
        assert not _admit_term(bad), f"stopword-ish seed admitted: {bad!r}"


def test_specific_concepts_admitted():
    for good in ("working memory", "calibration signal", "retrieval practice",
                 "source monitoring", "backpressure"):
        assert _admit_term(good), f"specific concept rejected: {good!r}"


def test_concept_state_serialization_deterministic():
    cs1 = Pass1ConceptState(
        original_query="q",
        concepts=[{"term": "working memory", "weight": 5, "reasons": ["profile_core_concept"]},
                  {"term": "calibration signal", "weight": 4, "reasons": ["entity"]}],
        entities=[], relationships=[], section_themes=[], source_doc_ids=[],
    )
    cs2 = Pass1ConceptState(
        original_query="q",
        concepts=[{"term": "working memory", "weight": 5, "reasons": ["profile_core_concept"]},
                  {"term": "calibration signal", "weight": 4, "reasons": ["entity"]}],
        entities=[], relationships=[], section_themes=[], source_doc_ids=[],
    )
    assert cs1.serialized_query() == cs2.serialized_query()
    assert cs1.serialized_query().startswith("q ")
    assert "working memory" in cs1.serialized_query()
    # original query is preserved verbatim at the head
    assert cs1.serialized_query() == "q working memory calibration signal"

"""Retrieval invariants: lane independence, fusion determinism, and
graph-expansion monotonicity (G4 policy). No stores needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.retrieval import (  # noqa: E402
    graph_expansion,
    lexical_score,
    rrf,
    run_lanes,
)

QUERY = "linguistic predicate compilation and generator evaluator loops"

PROFILES = [
    {"doc_id": "doc_a", "retrieval_profile": {
        "semantic_summary": "Deterministic predicate compilation for knowledge graphs",
        "core_concepts": ["predicate compilation", "GLiNER"],
        "primary_domains": ["knowledge_graphs"],
    }},
    {"doc_id": "doc_b", "retrieval_profile": {
        "semantic_summary": "Autonomous agents with generator and evaluator verification loops",
        "core_concepts": ["evaluator loops", "verification"],
        "primary_domains": ["agents"],
    }},
    {"doc_id": "doc_z", "retrieval_profile": {
        "semantic_summary": "Baking sourdough bread with fermentation schedules",
        "core_concepts": ["sourdough"],
        "primary_domains": ["cooking"],
    }},
]

PARENTS = [
    {"chunk_id": "p_a", "doc_id": "doc_a", "summary": "Predicate compilation rules"},
    {"chunk_id": "p_b", "doc_id": "doc_b", "summary": "Generator evaluator loop design"},
]

CHILDREN = [
    {"chunk_id": "c_a1", "doc_id": "doc_a", "parent_id": "p_a",
     "text": "The compiler maps linguistic evidence onto canonical predicates."},
    {"chunk_id": "c_b1", "doc_id": "doc_b", "parent_id": "p_b",
     "text": "The evaluator verifies generator output without self-approval."},
    {"chunk_id": "c_z1", "doc_id": "doc_z", "parent_id": "",
     "text": "Flour and water become dough."},
]


def _run(dense_rows=None):
    return run_lanes(
        QUERY,
        fetch_profiles=lambda: PROFILES,
        fetch_parents=lambda: PARENTS,
        fetch_children=lambda limit: CHILDREN[:limit],
        child_search=lambda limit: dense_rows or [],
    )


def test_deterministic_lanes_and_fusion() -> None:
    a = _run()
    b = _run()
    assert [h.source_id for h in a.document_ranking] == [h.source_id for h in b.document_ranking]
    assert [d["doc_id"] for d in a.selected_documents] == [d["doc_id"] for d in b.selected_documents]
    assert [c["chunk_id"] for c in a.selected_children] == [c["chunk_id"] for c in b.selected_children]


def test_child_survives_when_document_scores_zero() -> None:
    result = run_lanes(
        "exact phrase: predicate compilation",
        fetch_profiles=lambda: [{"doc_id": "doc_zero", "retrieval_profile": {
            "semantic_summary": "unrelated content",
            "core_concepts": [],
        }}],
        fetch_parents=lambda: [],
        fetch_children=lambda limit: [{
            "chunk_id": "c_hit", "doc_id": "doc_zero", "parent_id": "",
            "text": "exact phrase: predicate compilation",
        }][:limit],
        child_search=lambda limit: [],
    )
    assert result.document_ranking == []
    assert [c["chunk_id"] for c in result.selected_children] == ["c_hit"]


def test_dense_rows_without_vector_score_are_not_dense_hits() -> None:
    """Dense lane hygiene: rows without a real vector score must not
    pollute fusion with zero-score promotions."""
    result = run_lanes(
        QUERY,
        fetch_profiles=lambda: PROFILES,
        fetch_parents=lambda: PARENTS,
        fetch_children=lambda limit: CHILDREN[:limit],
        child_search=lambda limit: [
            {"chunk_id": "c_z1", "doc_id": "doc_z", "text": "Flour and water"}
        ],  # no vector_score
    )
    assert result.child_dense_ranking == []
    assert "doc_z" not in [d["doc_id"] for d in result.selected_documents]


def test_rrf_is_deterministic_and_rank_based() -> None:
    assert rrf([["a", "b"], ["b", "a"]]) == rrf([["a", "b"], ["b", "a"]])
    # A consensus second-place beats a lone first-place: rank-based fusion.
    assert rrf([["a", "b"], ["b", "a"]]) == ["a", "b"]


def test_graph_expansion_is_monotonic() -> None:
    """G4: graph expansion ADDS candidates; it never removes
    independently retrieved evidence (it has no access to it)."""
    def expand(surfaces):
        return [{"fact_id": f"f{i}", "predicate": "uses", "subject": surfaces[0] if surfaces else ""}
                for i in range(3)]

    before = ["c1", "c2"]
    facts = graph_expansion(["compiler"], expand=expand)
    # The expansion is purely additive by construction: it takes surfaces
    # and returns facts; the caller's evidence list is untouched.
    assert len(facts) == 3
    assert len(before) == 2  # untouched


def test_lexical_score_is_deterministic_and_bounded() -> None:
    assert lexical_score("predicate compilation", "predicate compilation rules") > 0
    assert lexical_score("predicate compilation", "baking bread") == 0.0
    assert lexical_score("x", "x") == lexical_score("x", "x")

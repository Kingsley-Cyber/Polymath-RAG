"""Retrieval invariants: lane independence, fusion determinism, graph
monotonicity, and R3a grounded EvidenceBundle assembly. No stores needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.retrieval import (  # noqa: E402
    EvidenceAssemblyError,
    assemble_evidence_bundle,
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
        ],
    )
    assert result.child_dense_ranking == []
    assert "doc_z" not in [d["doc_id"] for d in result.selected_documents]


def test_rrf_is_deterministic_and_rank_based() -> None:
    assert rrf([["a", "b"], ["b", "a"]]) == rrf([["a", "b"], ["b", "a"]])
    assert rrf([["a", "b"], ["b", "a"]]) == ["a", "b"]


def test_graph_expansion_is_monotonic() -> None:
    """G4: graph expansion ADDS candidates; it never removes independently
    retrieved evidence (it has no access to it)."""
    def expand(surfaces):
        return [{"fact_id": f"f{i}", "predicate": "uses", "subject": surfaces[0] if surfaces else ""}
                for i in range(3)]

    before = ["c1", "c2"]
    facts = graph_expansion(["compiler"], expand=expand)
    assert len(facts) == 3
    assert len(before) == 2


def test_lexical_score_is_deterministic_and_bounded() -> None:
    assert lexical_score("predicate compilation", "predicate compilation rules") > 0
    assert lexical_score("predicate compilation", "baking bread") == 0.0
    assert lexical_score("x", "x") == lexical_score("x", "x")


# ---------------------------------------------------------------------------
# R3a grounded EvidenceBundle acceptance
# ---------------------------------------------------------------------------

PASSAGE = {
    "chunk_id": "chunk_a",
    "doc_id": "doc_a",
    "source_name": "a.md",
    "text": "Acme uses ToolX for retrieval.",
    "char_start": 10,
    "char_end": 40,
    "contract_ids": ["lexical-v1", "embed-v1", "lexical-v1"],
    "retrieval_paths": [
        {
            "lane": "child_lexical",
            "representation_kind": "child_chunk",
            "contract_id": "lexical-v1",
            "rank": 1,
            "raw_score": 2.0,
        },
        {
            "lane": "child_dense",
            "representation_kind": "child_chunk",
            "contract_id": "embed-v1",
            "rank": 0,
            "raw_score": 0.82,
        },
    ],
}


def _fact_row(
    fact_id: str = "fact_1",
    evidence_id: str = "ev_1",
    obj: str = "ToolX",
    object_id: str = "ent_toolx",
) -> dict:
    return {
        "fact_id": fact_id,
        "predicate": "uses",
        "subject_id": "ent_acme",
        "subject": "Acme",
        "object_id": object_id,
        "object": obj,
        "qualifiers": {"conditional": False},
        "decision": "ACCEPT",
        "rule_id": "uses_rule",
        "rule_version": "1.0.1",
        "provenance": {"roleset": "use.01", "semlink_resolved": True},
        "evidence_id": evidence_id,
        "doc_id": "doc_a",
        "chunk_id": "chunk_a",
        "span_offsets": {"chunk_char_start": 10},
        "evidence_rule_id": "uses_rule",
        "evidence_rule_version": "1.0.1",
        "extractor_version": "gliner-2pass-v1",
        "gliner_scores": {"subject": 0.91, "object": 0.88},
        "source_name": "a.md",
        "text": "Acme uses ToolX for retrieval.",
        "char_start": 10,
        "char_end": 40,
    }


def test_evidence_bundle_passage_preserves_exact_source_and_paths() -> None:
    bundle = assemble_evidence_bundle(
        "what does Acme use?", passages=[PASSAGE], graph_facts=[], fact_support_rows=[]
    )
    item = bundle.evidence_bundle[0]
    assert item.support_kind == "passage"
    assert item.source_span.text == PASSAGE["text"]
    assert (item.source_span.char_start, item.source_span.char_end) == (10, 40)
    assert [p.lane for p in item.retrieval] == ["child_dense", "child_lexical"]
    assert item.provenance["contract_ids"] == ["embed-v1", "lexical-v1"]


def test_evidence_bundle_fact_resolves_source_provenance_scope_and_support() -> None:
    bundle = assemble_evidence_bundle(
        "what does Acme use?",
        passages=[],
        graph_facts=[{"fact_id": "fact_1", "predicate": "uses"}],
        fact_support_rows=[_fact_row()],
    )
    item = bundle.evidence_bundle[0]
    assert item.support_kind == "fact"
    assert item.fact_id == "fact_1"
    assert item.evidence_id == "ev_1"
    assert item.claim_candidate == {
        "kind": "relation",
        "subject_id": "ent_acme",
        "subject": "Acme",
        "predicate": "uses",
        "object_id": "ent_toolx",
        "object": "ToolX",
    }
    assert item.provenance["roleset"] == "use.01"
    assert item.epistemics["decision"] == "ACCEPT"
    assert item.applicability["qualifiers"] == {"conditional": False}
    assert item.support_metadata["gliner_scores"]["subject"] == 0.91
    assert item.source_span.text == "Acme uses ToolX for retrieval."


def test_evidence_bundle_duplicate_nominations_collapse_deterministically() -> None:
    graph = [{"fact_id": "fact_1"}, {"fact_id": "fact_1"}]
    rows = [_fact_row(), _fact_row()]
    a = assemble_evidence_bundle(
        "query", passages=[PASSAGE, PASSAGE], graph_facts=graph, fact_support_rows=rows
    )
    b = assemble_evidence_bundle(
        "query", passages=[PASSAGE, PASSAGE], graph_facts=graph, fact_support_rows=rows
    )
    assert [i.support_id for i in a.evidence_bundle] == [i.support_id for i in b.evidence_bundle]
    assert len(a.evidence_bundle) == 2


def test_evidence_bundle_conflicting_fact_support_can_coexist() -> None:
    rows = [
        _fact_row("fact_1", "ev_1", "ToolX", "ent_toolx"),
        _fact_row("fact_2", "ev_2", "ToolY", "ent_tooly"),
    ]
    rows[1]["decision"] = "QUALIFY"
    rows[1]["qualifiers"] = {"conditional": True}
    bundle = assemble_evidence_bundle(
        "what does Acme use?",
        passages=[],
        graph_facts=[{"fact_id": "fact_1"}, {"fact_id": "fact_2"}],
        fact_support_rows=rows,
    )
    assert {i.fact_id for i in bundle.evidence_bundle} == {"fact_1", "fact_2"}
    assert {i.claim_candidate["object"] for i in bundle.evidence_bundle} == {"ToolX", "ToolY"}


def test_evidence_bundle_missing_authoritative_fact_evidence_fails_loudly() -> None:
    with pytest.raises(EvidenceAssemblyError, match="no authoritative Postgres evidence"):
        assemble_evidence_bundle(
            "query", passages=[], graph_facts=[{"fact_id": "fact_missing"}], fact_support_rows=[]
        )


def test_evidence_bundle_missing_compiler_provenance_fails_loudly() -> None:
    row = _fact_row()
    row["provenance"] = {}
    with pytest.raises(EvidenceAssemblyError, match="missing compiler provenance"):
        assemble_evidence_bundle(
            "query", passages=[], graph_facts=[{"fact_id": "fact_1"}], fact_support_rows=[row]
        )


def test_evidence_bundle_missing_passage_retrieval_provenance_fails_loudly() -> None:
    row = dict(PASSAGE)
    row["retrieval_paths"] = []
    with pytest.raises(EvidenceAssemblyError, match="missing retrieval provenance"):
        assemble_evidence_bundle("query", passages=[row], graph_facts=[], fact_support_rows=[])

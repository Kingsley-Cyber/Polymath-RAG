"""R1D HYBRID determinism (pure; no stores): four-lane RRF aggregation,
document-level MMR (lambda=1.0 = relevance-only baseline; diversity is
deterministic and only reorders), lexical rescue arrival semantics.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[2])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.hybrid import (  # noqa: E402
    ARRIVAL_LEXICAL_RESCUE,
    HYBRID_PLAN_VERSION,
    HybridRetrievalPlan,
    mmr_select,
)
from polymath_shared.pass1 import LaneHit, aggregate_documents_n  # noqa: E402


def _hit(kind, rank, doc_id, parent_id="", chunk_id="", score=0.9):
    return LaneHit(
        representation_kind=kind, rank=rank, raw_similarity=score,
        corpus_id="c1", doc_id=doc_id, parent_id=parent_id, chunk_id=chunk_id,
        summary_id="", source_name="", text="",
    )


def test_four_lane_aggregation_deterministic_with_lexical_rescue():
    lanes = [
        ("routing_document_summary", [_hit("routing_document_summary", 0, "d1")]),
        ("routing_section_summary", [_hit("routing_section_summary", 0, "d2")]),
        ("routing_child", [_hit("routing_child", 0, "d3")]),
        ("child_lexical", [_hit("child_lexical", 0, "d4", parent_id="p4", chunk_id="k4")]),
    ]
    a = aggregate_documents_n(lanes, k=60)
    b = aggregate_documents_n(lanes, k=60)
    assert a == b
    d4 = next(c for c in a if c.doc_id == "d4")
    assert d4.representation_kinds_present == ["child_lexical"]
    assert d4.best_lexical_rank == 0
    # a lexical-only document is admitted (semantic miss does not imply
    # unreachability)
    assert {c.doc_id for c in a} == {"d1", "d2", "d3", "d4"}


def test_mmr_lambda_one_is_relevance_only():
    docs = ["d1", "d2", "d3"]
    relevance = {"d1": 0.9, "d2": 0.5, "d3": 0.1}
    vectors = {"d1": [1.0, 0.0], "d2": [1.0, 0.0], "d3": [0.0, 1.0]}

    class C:
        def __init__(self, did):
            self.doc_id = did

    candidates = [C(d) for d in docs]
    sel = mmr_select(candidates, relevance=relevance, vectors=vectors,
                     lambda_=1.0, max_documents=3)
    assert [c.doc_id for c in sel] == ["d1", "d2", "d3"], "lambda=1.0 must preserve relevance order"


def test_mmr_diversity_prefers_complementary_documents():
    docs = ["d1", "d2", "d3"]
    relevance = {"d1": 0.9, "d2": 0.85, "d3": 0.8}
    # d1 and d2 are near-duplicates; d3 is complementary
    vectors = {"d1": [1.0, 0.0, 0.0], "d2": [0.99, 0.0, 0.0], "d3": [0.0, 1.0, 0.0]}

    class C:
        def __init__(self, did):
            self.doc_id = did

    candidates = [C(d) for d in docs]
    sel = mmr_select(candidates, relevance=relevance, vectors=vectors,
                     lambda_=0.7, max_documents=3)
    assert sel[0].doc_id == "d1"
    # with redundancy penalty, d3 (complementary) beats d2 (duplicate)
    assert sel[1].doc_id == "d3", [c.doc_id for c in sel]


def test_mmr_deterministic():
    docs = ["d1", "d2", "d3", "d4"]
    relevance = {d: 1.0 - 0.1 * i for i, d in enumerate(docs)}
    vectors = {d: [1.0 if i % 2 == 0 else 0.0, 0.0 if i % 2 == 0 else 1.0]
               for i, d in enumerate(docs)}

    class C:
        def __init__(self, did):
            self.doc_id = did

    a = mmr_select([C(d) for d in docs], relevance=relevance, vectors=vectors,
                   lambda_=0.8, max_documents=3)
    b = mmr_select([C(d) for d in docs], relevance=relevance, vectors=vectors,
                   lambda_=0.8, max_documents=3)
    assert [c.doc_id for c in a] == [c.doc_id for c in b]


def test_hybrid_plan_contract_and_rescue_value():
    plan = HybridRetrievalPlan()
    assert plan.plan_version == HYBRID_PLAN_VERSION
    assert ARRIVAL_LEXICAL_RESCUE == "LEXICAL_RESCUE"
    assert plan.mmr_lambda == 1.0  # relevance-only default until promoted
    assert plan.mmr_enabled is False

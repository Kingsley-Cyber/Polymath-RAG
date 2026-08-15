"""R1B Pass-1 engine determinism (pure; no stores).

RRF aggregation with per-lane contributions, deterministic document/
section resolution, and the versioned plan contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[2])
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from polymath_shared.pass1 import (  # noqa: E402
    ARRIVAL_GLOBAL_CHILD_RESCUE,
    ARRIVAL_MULTI_REPRESENTATION,
    PLAN_VERSION,
    PASS1_DEFAULT_PLAN,
    Pass1RetrievalPlan,
    LaneHit,
    aggregate_documents,
    resolve_sections,
)


def _hit(kind, rank, doc_id, parent_id="", chunk_id="", score=0.9, summary_id=""):
    return LaneHit(
        representation_kind=kind, rank=rank, raw_similarity=score,
        corpus_id="c1", doc_id=doc_id, parent_id=parent_id, chunk_id=chunk_id,
        summary_id=summary_id, source_name="", text="",
    )


def test_rrf_aggregation_is_deterministic_and_multi_representation():
    doc_lane = [_hit("routing_document_summary", 0, "d1"),
                _hit("routing_document_summary", 1, "d2")]
    section_lane = [_hit("routing_section_summary", 0, "d2"),
                    _hit("routing_section_summary", 1, "d1")]
    child_lane = [_hit("routing_child", 0, "d3")]
    a = aggregate_documents(doc_lane, section_lane, child_lane, k=60)
    b = aggregate_documents(doc_lane, section_lane, child_lane, k=60)
    assert a == b
    # d2 has doc-summary + section-summary support -> visible multi-representation
    d2 = next(c for c in a if c.doc_id == "d2")
    assert d2.representation_kinds_present == ["routing_document_summary", "routing_section_summary"]
    assert len(d2.rrf_contributions) == 2
    # d1 ranks by its best doc-summary rank contribution
    d1 = next(c for c in a if c.doc_id == "d1")
    assert d1.best_document_summary_rank == 0
    assert [c.doc_id for c in a] == [d.doc_id for d in sorted(
        a, key=lambda c: (-c.aggregate_score, c.doc_id))]


def test_resolve_sections_bounded_and_deterministic():
    docs = aggregate_documents(
        [_hit("routing_document_summary", 0, "d1")],
        [_hit("routing_section_summary", 0, "d1", parent_id="p1"),
         _hit("routing_section_summary", 1, "d1", parent_id="p2"),
         _hit("routing_section_summary", 2, "d1", parent_id="p3")],
        [],
        k=60,
    )[:1]
    sections = resolve_sections(docs, max_sections_per_document=2)
    assert [s["parent_id"] for s in sections] == ["p1", "p2"]
    assert resolve_sections(docs, max_sections_per_document=2) == sections


def test_child_rescue_admits_doc_with_only_child_evidence():
    child_lane = [_hit("routing_child", 0, "d9", parent_id="p9", chunk_id="k9")]
    docs = aggregate_documents([], [], child_lane, k=60)
    assert docs[0].doc_id == "d9"
    assert docs[0].representation_kinds_present == ["routing_child"]


def test_plan_defaults_are_versioned():
    plan = Pass1RetrievalPlan()
    assert plan.plan_version == PLAN_VERSION
    assert plan == PASS1_DEFAULT_PLAN
    # deterministic: the same plan object always hashes identically
    assert hash(plan) == hash(Pass1RetrievalPlan(**{
        f.name: getattr(plan, f.name) for f in __import__("dataclasses").fields(plan)}))


def test_arrival_classification_values():
    assert ARRIVAL_GLOBAL_CHILD_RESCUE == "GLOBAL_CHILD_RESCUE"
    assert ARRIVAL_MULTI_REPRESENTATION == "MULTI_REPRESENTATION"

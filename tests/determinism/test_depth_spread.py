"""EXTRACT-DEPTH-SPREAD-V1 decision gate: spread only when lanes
would otherwise idle; unknown depth or a deep queue keeps per-doc
lane affinity (the consistency-preserving default)."""
from __future__ import annotations

from workers.llm_provider import NEIGHBORHOODS_PER_CALL, spread_decision

MANY = NEIGHBORHOODS_PER_CALL * 3


def test_spreads_only_when_queue_is_shallow():
    assert spread_decision(0, "doc_a", MANY)
    assert spread_decision(1, "doc_a", MANY)      # own ticket only
    assert not spread_decision(2, "doc_a", MANY)  # others waiting
    assert not spread_decision(9, "doc_a", MANY)


def test_unknown_depth_never_spreads():
    assert not spread_decision(None, "doc_a", MANY)


def test_single_batch_or_unrouted_doc_never_spreads():
    assert not spread_decision(0, "doc_a", NEIGHBORHOODS_PER_CALL)
    assert not spread_decision(0, "", MANY)

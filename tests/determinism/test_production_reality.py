"""PRODUCTION-REALITY-V1: the dead-feature gate.

Every historical silent failure in this repo passed its component tests.
This suite encodes the three-level model:

  LEVEL 1  component   — does the function work?          (existing suites)
  LEVEL 2  callsite    — does production pass the shape?  (pin tests)
  LEVEL 3  live effect — given an opportunity, did it act? (this file)

The chaos matrix below replays the ACTUAL historical failure classes.
For each, a gate must fire. A gate that cannot fail is not a gate, so
each case asserts the healthy trace is LIVE and the broken trace is
SUSPECT.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.lane_liveness import (  # noqa: E402
    LANES_BY_NAME,
    STATUS_DISABLED,
    STATUS_LIVE,
    STATUS_NO_OPPORTUNITY,
    STATUS_SUSPECT,
    evaluate,
    evaluate_lane,
)


def healthy_trace() -> dict:
    """A trace from a well-behaved GRAPH query — the widest mode, so
    every promoted lane (including lexical and graph hop1) is enabled
    and contributing."""
    return {
        "mode": "GRAPH",
        "lane_sizes": {"document_summary": 10, "section_summary": 10,
                       "global_child": 20, "child_lexical": 20},
        "pre_g3_order": ["c1", "c2", "c3"],
        "post_g3_order": ["c2", "c1", "c3"],
        "g3_scores": {"c1": 0.4, "c2": 0.9, "c3": 0.1},
        "rerank_enabled": True,
        "rescue_reserved_slots": 2,
        "rescue_candidates": 3,
        "rescue_seated": 2,
        "neighbor_expansion": 1,
        "neighbors_added": 4,
        "demote_noisy_regions": True,
        "noisy_candidates": 5,
        "noisy_demoted": 5,
        "graph_seed_surfaces": ["nmap", "tcp"],
        "graph_fact_count": 6,
    }


def status_of(trace: dict, lane: str) -> str:
    return evaluate_lane(LANES_BY_NAME[lane], trace)["status"]


def test_healthy_trace_has_no_suspects():
    assert evaluate(healthy_trace())["suspect"] == []


# ============================================================ CHAOS MATRIX
# Each case is a real historical failure class from this repository.

def test_chaos_1_rescue_lane_configured_but_delivering_nothing():
    """HISTORICAL: global_child_rescue_max=3 while rescue candidates
    were appended after the truncation point — 0 of 10 delivered."""
    t = healthy_trace()
    t["rescue_seated"] = 0          # the measured production reality
    assert status_of(t, "global_child_rescue") == STATUS_SUSPECT
    assert "global_child_rescue" in evaluate(t)["suspect"]


def test_chaos_2_retrieval_lane_omitted_from_final_union():
    """A configured lane silently missing from the union."""
    t = healthy_trace()
    t["lane_sizes"]["child_lexical"] = 0
    assert status_of(t, "lexical") == STATUS_SUSPECT


def test_chaos_3_summary_written_to_postgres_but_not_qdrant():
    """Projection gap: rows exist, vectors do not, so the routing lane
    returns nothing."""
    t = healthy_trace()
    t["lane_sizes"]["document_summary"] = 0
    assert status_of(t, "document_summary_routing") == STATUS_SUSPECT


def test_chaos_4_projection_payload_loses_representation_kind():
    """If representation_kind is dropped, the section filter can never
    match and that lane silently returns zero."""
    t = healthy_trace()
    t["lane_sizes"]["section_summary"] = 0
    assert status_of(t, "section_summary_routing") == STATUS_SUSPECT


def test_chaos_5_reranker_runs_but_produces_no_scores():
    """Historical shape: the client could not call its own method, so
    every rerank raised and the order silently passed through."""
    t = healthy_trace()
    t["g3_scores"] = {}
    assert status_of(t, "reranker") == STATUS_SUSPECT


def test_chaos_6_neighbor_expansion_enabled_but_never_expands():
    t = healthy_trace()
    t["neighbors_added"] = 0
    assert status_of(t, "neighbor_expansion") == STATUS_SUSPECT


def test_chaos_7_region_demotion_stops_demoting():
    """If the region backfill is lost or the lookup silently returns
    {}, boilerplate quietly starts winning again."""
    t = healthy_trace()
    t["noisy_demoted"] = 0
    assert status_of(t, "region_demotion") == STATUS_SUSPECT


def test_chaos_8_graph_seeds_exist_but_traversal_yields_nothing():
    """Distinguishes a real graph defect from the correct zero."""
    t = healthy_trace()
    t["graph_fact_count"] = 0
    assert status_of(t, "graph_hop1") == STATUS_SUSPECT


# =================================================== CORRECT ZEROS (no alert)
# The gate must not cry wolf: these zeros are legitimate and MUST NOT
# be SUSPECT, or the signal becomes noise and gets ignored.

def test_correct_zero_graph_without_seeds_is_not_suspect():
    t = healthy_trace()
    t["graph_seed_surfaces"] = []
    t["graph_fact_count"] = 0
    assert status_of(t, "graph_hop1") == STATUS_NO_OPPORTUNITY


def test_correct_zero_rescue_without_candidates_is_not_suspect():
    t = healthy_trace()
    t["rescue_candidates"] = 0
    t["rescue_seated"] = 0
    assert status_of(t, "global_child_rescue") == STATUS_NO_OPPORTUNITY


def test_correct_zero_region_demotion_with_clean_pool_is_not_suspect():
    """A corpus with no boilerplate in the candidate pool should demote
    nothing — that is success, not a defect."""
    t = healthy_trace()
    t["noisy_candidates"] = 0
    t["noisy_demoted"] = 0
    assert status_of(t, "region_demotion") == STATUS_NO_OPPORTUNITY


def test_disabled_lane_is_not_suspect():
    """Depth-only features are DISABLED on ordinary queries, and an
    unqualified/rejected mechanism must never alert by producing zero."""
    t = healthy_trace()
    t["neighbor_expansion"] = 0
    assert status_of(t, "neighbor_expansion") == STATUS_DISABLED
    t2 = healthy_trace()
    t2["mode"] = "FAST"
    assert status_of(t2, "graph_hop1") == STATUS_DISABLED


def test_fast_mode_does_not_flag_missing_lexical_lane():
    """FAST has no lexical lane by design."""
    t = healthy_trace()
    t["mode"] = "FAST"
    del t["lane_sizes"]["child_lexical"]
    assert status_of(t, "lexical") == STATUS_DISABLED


# ============================================================== SEMANTICS
@pytest.mark.parametrize("lane", sorted(LANES_BY_NAME))
def test_every_lane_states_why_zero_would_be_a_defect(lane):
    """A lane without a rationale cannot be triaged when it fires."""
    assert len(LANES_BY_NAME[lane].rationale) > 40


def test_evaluate_reports_live_and_suspect_sets():
    t = healthy_trace()
    t["rescue_seated"] = 0
    out = evaluate(t)
    assert out["suspect"] == ["global_child_rescue"]
    assert "document_summary_routing" in out["live"]

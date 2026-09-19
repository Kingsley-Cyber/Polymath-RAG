"""LATENT-QUERY-FUSION-V2 · F3 — the real truncation seam (`_latent_fused_union`, candidate_engine:1066).

These tests exercise the EXACT adapter the engine calls at the `union = fused[:merged_candidate_max]`
seam. The headline case is the actual architectural failure: q0 floods ~100 strong candidates, a bridge
has a locally rank-1 expert chunk, the flatten's global ordering truncates it, and V2 must preserve it
INSIDE the unchanged cap. Also: physical dedup, lineage attachment, strict ceiling, and fail-open — the
owner's F3 checklist, proven where the correction lives (not RRF arithmetic, which is F2's test).
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared",):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from polymath_shared import candidate_engine as ce  # noqa: E402
from polymath_shared.candidate_engine import CandidateEvidence, _latent_fused_union  # noqa: E402
from polymath_shared.ranked_lane import LaneResult, RankedLane  # noqa: E402


def _cand(chunk_id, doc, fused, query_ids, arrivals):
    return CandidateEvidence(chunk_id=chunk_id, doc_id=doc, parent_id=f"{doc}-p", source_name=f"Book {doc}",
                             text=f"text {chunk_id}", arrivals=list(arrivals), query_ids=list(query_ids), fused_score=fused)


def _lane(query_id, role, origin, chunk_ids, lane="GLOBAL_DENSE_CHILD", modality="DENSE"):
    return RankedLane(query_id=query_id, query_text=f"{query_id}", role=role, origin=origin, lane=lane, modality=modality,
                      results=[LaneResult(chunk_id=c, local_rank=i, score=1.0 - 0.001 * i, doc_id="d") for i, c in enumerate(chunk_ids)])


# ── THE actual failure: 100 q0 candidates flood the cap; a bridge's local rank-1 chunk is preserved ──
def test_bridge_local_winner_preserved_inside_unchanged_cap():
    N, CAP = 100, 50
    # `fused` (flatten order): 100 q0 chunks by descending fused_score, then EXPERT dead last (single-lane bridge).
    q0_ids = [f"q0c{i}" for i in range(N)]
    fused = [_cand(c, "dQ", fused=1.0 - 0.001 * i, query_ids=["q0"], arrivals=["GLOBAL_DENSE_CHILD"]) for i, c in enumerate(q0_ids)]
    fused.append(_cand("EXPERT", "dB", fused=0.0001, query_ids=["bA"], arrivals=["GLOBAL_DENSE_CHILD"]))
    budget = ce.CandidateBudget(merged_candidate_max=CAP)
    fallback = fused[:CAP]                                   # what the flatten keeps
    lanes = [_lane("q0", "q0", "USER", q0_ids), _lane("bA", "BRIDGE_CANDIDATE", "BRIDGE", ["EXPERT"])]

    out = _latent_fused_union(fused, lanes, budget, fallback)
    out_ids = [c.chunk_id for c in out]

    assert "EXPERT" not in [c.chunk_id for c in fallback]    # the flatten truncates the expert chunk
    assert "EXPERT" in out_ids                               # V2 preserves it (bridge local winner)
    assert len(out) == CAP                                   # cap UNCHANGED — who survives changed, not the ceiling
    # q0's own local winners also survive (q0 is not starved by preservation)
    assert "q0c0" in out_ids and "q0c1" in out_ids


# ── flag-off fallback is returned verbatim when lanes are empty / fusion yields nothing ────────────
def test_empty_lanes_fall_back_to_the_flatten():
    fused = [_cand(f"c{i}", "d", fused=1.0 - i, query_ids=["q0"], arrivals=["GLOBAL_DENSE_CHILD"]) for i in range(5)]
    budget = ce.CandidateBudget(merged_candidate_max=3)
    fallback = fused[:3]
    assert _latent_fused_union(fused, [], budget, fallback) is fallback


# ── a duplicate chunk found in multiple lanes stays ONE physical candidate; lineage stays attached ──
def test_dedup_and_lineage_attached():
    shared = _cand("shared", "d0", fused=0.9, query_ids=["q0", "bA"], arrivals=["GLOBAL_DENSE_CHILD", "GLOBAL_SPARSE_CHILD"])
    other = _cand("other", "d1", fused=0.5, query_ids=["q0"], arrivals=["GLOBAL_DENSE_CHILD"])
    fused = [shared, other]
    budget = ce.CandidateBudget(merged_candidate_max=10)
    lanes = [_lane("q0", "q0", "USER", ["shared", "other"]),
             _lane("bA", "BRIDGE_CANDIDATE", "BRIDGE", ["shared"])]
    out = _latent_fused_union(fused, lanes, budget, fused[:10])
    ids = [c.chunk_id for c in out]
    assert ids.count("shared") == 1                          # one physical candidate despite two lanes
    seat = next(c for c in out if c.chunk_id == "shared")
    assert seat is shared                                    # same object reused (provenance intact)
    assert set(seat.query_ids) == {"q0", "bA"} and len(seat.arrivals) == 2


# ── fail-open: malformed lane data returns the flatten fallback, never raises ──────────────────────
def test_fail_open_on_malformed_lanes():
    fused = [_cand("c0", "d", fused=1.0, query_ids=["q0"], arrivals=["GLOBAL_DENSE_CHILD"])]
    budget = ce.CandidateBudget(merged_candidate_max=5)
    fallback = fused[:5]

    class _Bad:                                              # not a RankedLane; explodes when fused
        query_id = "x"
        @property
        def results(self):
            raise ValueError("malformed lane")
    assert _latent_fused_union(fused, [_Bad()], budget, fallback) is fallback


# ── the cap is a strict ceiling even with many preserved winners across many queries ──────────────
def test_cap_strict_ceiling_at_the_seam():
    CAP = 8
    fused, lanes = [], []
    for qi in range(6):                                      # 6 queries × 4 chunks each = 24 candidates
        ids = [f"q{qi}c{j}" for j in range(4)]
        for j, c in enumerate(ids):
            fused.append(_cand(c, f"d{qi}", fused=1.0 - qi * 0.1 - j * 0.01, query_ids=[f"q{qi}"], arrivals=["GLOBAL_DENSE_CHILD"]))
        lanes.append(_lane(f"q{qi}", ("q0" if qi == 0 else "MECH"), "USER", ids))
    budget = ce.CandidateBudget(merged_candidate_max=CAP)
    out = _latent_fused_union(fused, lanes, budget, fused[:CAP])
    assert len(out) == CAP                                   # never exceeds merged_candidate_max
    assert len({c.chunk_id for c in out}) == CAP             # and no duplicates

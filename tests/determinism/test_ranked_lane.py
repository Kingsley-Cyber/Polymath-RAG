"""LATENT-QUERY-FUSION-V2 · F1 — RankedLane representation (pure, observability only).

Pins what the pre-V2 flatten destroys and F1 must preserve: (1) each chunk's LOCAL rank within a
query+lane; (2) a chunk's membership in MULTIPLE lanes (q0-dense AND a bridge-dense) kept side by
side, never collapsed to one score; (3) a bridge's LOCAL rank-1 captured as local_rank 0 regardless
of how it would rank in the q0-dominated union. Plus receipt shape, helpers, determinism, and the
skip/score rules. No selection is exercised here (F2 fuses, F3 wires C4/C5).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from polymath_shared.ranked_lane import (
    MODALITY_DENSE,
    MODALITY_GRAPH,
    MODALITY_SPARSE,
    ORIGIN_USER,
    ROLE_Q0,
    RankedLane,
    build_ranked_lanes,
    lane_memberships,
    modality_for,
    ranked_lanes_receipt,
)


@dataclass
class _Cand:
    """Duck-typed stand-in for CandidateEvidence (only the fields the builder reads)."""
    chunk_id: str
    doc_id: str = "d"
    query_ids: list = field(default_factory=list)
    arrivals: list = field(default_factory=list)
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None


def _q0_dense(cid, doc="d0", sim=0.9):
    return _Cand(chunk_id=cid, doc_id=doc, query_ids=["q0"], arrivals=["GLOBAL_DENSE_CHILD"], dense_score=sim)


def _q0_sparse(cid, doc="d0", sim=0.5):
    return _Cand(chunk_id=cid, doc_id=doc, query_ids=["q0"], arrivals=["GLOBAL_SPARSE_CHILD"], sparse_score=sim)


def _bridge_dense(cid, qid="b0", doc="dB", sim=0.8):
    return _Cand(chunk_id=cid, doc_id=doc, query_ids=[qid], arrivals=["GLOBAL_DENSE_CHILD"], dense_score=sim)


def _build(items, meta=None):
    return build_ranked_lanes(items, primary_query_id="q0", primary_query_text="the user question", query_meta=meta)


# ── 1. local ranks preserved (positional within a lane, in retrieval order) ──────────────────────
def test_local_ranks_are_positional_and_ordered():
    lanes = _build([_q0_dense("a"), _q0_dense("b"), _q0_dense("c")])
    assert len(lanes) == 1
    rl = lanes[0]
    assert [(r.chunk_id, r.local_rank) for r in rl.results] == [("a", 0), ("b", 1), ("c", 2)]
    assert rl.role == ROLE_Q0 and rl.origin == ORIGIN_USER and rl.query_text == "the user question"
    assert rl.modality == MODALITY_DENSE


# ── 2. THE unlock: a bridge's local rank-1 is captured as local_rank 0, not lost to the flatten ───
def test_bridge_local_winner_is_captured_rank_zero():
    # q0 has three multi-lane candidates; the bridge finds ONE chunk, its local winner.
    items = [_q0_dense("a"), _q0_dense("b"), _q0_dense("c"), _bridge_dense("Z", qid="b0")]
    lanes = _build(items, meta={"b0": {"text": "bridge concept", "role": "BRIDGE_CANDIDATE"}})
    bridge = [rl for rl in lanes if rl.query_id == "b0"][0]
    assert bridge.role == "BRIDGE_CANDIDATE"
    assert bridge.rank_of("Z") == 0          # local winner, regardless of union/q0 dominance
    assert bridge.top(1)[0].chunk_id == "Z"


# ── 3. multiple lane memberships preserved per chunk (q0-dense AND bridge-dense) ──────────────────
def test_multi_lane_membership_is_not_collapsed():
    # "shared" is found by q0-dense (rank 1) AND by the bridge (rank 0). Both must survive.
    items = [_q0_dense("a"), _q0_dense("shared"), _bridge_dense("shared", qid="b0")]
    lanes = _build(items, meta={"b0": {"text": "bridge", "role": "BRIDGE_CANDIDATE", "origin": "BRIDGE"}})
    mem = lane_memberships(lanes)
    placements = {(p["query_id"], p["local_rank"]) for p in mem["shared"]}
    assert ("q0", 1) in placements and ("b0", 0) in placements   # kept side by side
    assert len(mem["shared"]) == 2
    bridge = [rl for rl in lanes if rl.query_id == "b0"][0]
    assert bridge.origin == "BRIDGE"


# ── 4. sparse lane uses sparse_score; dense uses dense_score ──────────────────────────────────────
def test_lane_score_source_by_modality():
    lanes = _build([_q0_dense("a", sim=0.91), _q0_sparse("a", sim=0.42)])
    by_mod = {rl.modality: rl for rl in lanes}
    assert by_mod[MODALITY_DENSE].results[0].score == 0.91
    assert by_mod[MODALITY_SPARSE].results[0].score == 0.42


# ── 5. lane output order follows first appearance; graph modality mapped ──────────────────────────
def test_lane_order_and_graph_modality():
    graph = _Cand(chunk_id="g", query_ids=["q0"], arrivals=["GRAPH_DEST"], dense_score=0.3)
    lanes = _build([_q0_dense("a"), graph, _q0_dense("b")])
    assert [rl.lane for rl in lanes] == ["GLOBAL_DENSE_CHILD", "GRAPH_DEST"]
    assert modality_for("GRAPH_DEST") == MODALITY_GRAPH
    assert [rl for rl in lanes if rl.lane == "GRAPH_DEST"][0].modality == MODALITY_GRAPH


# ── 6. empty chunk_id items are skipped (never occupy a rank) ─────────────────────────────────────
def test_empty_chunk_ids_skipped():
    items = [_q0_dense("a"), _Cand(chunk_id="", query_ids=["q0"], arrivals=["GLOBAL_DENSE_CHILD"], dense_score=0.1),
             _q0_dense("b")]
    lanes = _build(items)
    assert [(r.chunk_id, r.local_rank) for r in lanes[0].results] == [("a", 0), ("b", 1)]


# ── 7. receipt is JSON-safe with the multi-lane signal and per-lane top-N ─────────────────────────
def test_receipt_shape_and_multilane_count():
    items = [_q0_dense("a"), _q0_dense("shared"), _bridge_dense("shared", qid="b0"), _bridge_dense("Z", qid="b0")]
    lanes = _build(items, meta={"b0": {"text": "bridge", "role": "BRIDGE_CANDIDATE"}})
    rcpt = ranked_lanes_receipt(lanes, top_n=2)
    assert rcpt["contract"] == "ranked-lanes-v1"
    assert rcpt["n_lanes"] == 2 and rcpt["n_queries"] == 2
    assert rcpt["multi_lane_chunks"] == 1          # only "shared" is in >=2 lanes
    json.dumps(rcpt)                                # must serialize
    bridge_receipt = [l for l in rcpt["lanes"] if l["query_id"] == "b0"][0]
    assert bridge_receipt["size"] == 2 and len(bridge_receipt["top"]) == 2


# ── 8. deterministic: identical input twice → identical receipt ───────────────────────────────────
def test_deterministic():
    items = [_q0_dense("a"), _q0_sparse("a"), _bridge_dense("Z", qid="b0"), _q0_dense("b")]
    meta = {"b0": {"text": "bridge", "role": "BRIDGE_CANDIDATE"}}
    r1 = ranked_lanes_receipt(_build(items, meta))
    r2 = ranked_lanes_receipt(_build(items, meta))
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


# ── 9. missing query_ids/arrivals fall back to the primary query / empty lane, never crash ────────
def test_missing_provenance_falls_back_to_primary():
    bare = _Cand(chunk_id="x", dense_score=0.2)     # no query_ids, no arrivals
    lanes = _build([bare])
    assert lanes[0].query_id == "q0" and lanes[0].role == ROLE_Q0
    assert lanes[0].results[0].local_rank == 0

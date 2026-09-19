"""LATENT-QUERY-FUSION-V2 · F2 — lineage-aware weighted RRF over RankedLanes (pure, deterministic).

Pins: the weighted-RRF math; lineage classification + weights; **bounded local-winner preservation**
(a bridge's local rank-1 survives the merged-candidate cap even when its fused score ranks below it —
the exact failure V1 has); many-to-one lineage kept (contributions never collapsed); per-query top-N
reservation; configurable (unfrozen) weights; determinism. F2 orders candidates only — it seats nothing
(C4/C5 gate at F3), so no test here asserts a final seat.
"""
from __future__ import annotations

import json

from polymath_shared.ranked_lane import LaneResult, RankedLane
from polymath_shared.ranked_fusion import (
    CLASS_BRIDGE,
    CLASS_Q0,
    CLASS_PROFILE,
    FusionWeights,
    fuse_ranked_lanes,
    lineage_class,
    preserved_winners,
)

K = 60


def _lane(query_id, role, origin, lane, modality, ranked_ids):
    return RankedLane(
        query_id=query_id, query_text=f"{query_id} text", role=role, origin=origin, lane=lane, modality=modality,
        results=[LaneResult(chunk_id=cid, local_rank=i, score=1.0 - 0.01 * i, doc_id=doc) for i, (cid, doc) in enumerate(ranked_ids)],
    )


def _q0_dense(ranked):
    return _lane("q0", "q0", "USER", "GLOBAL_DENSE_CHILD", "DENSE", ranked)


def _bridge_dense(ranked, qid="b0"):
    return _lane(qid, "BRIDGE_CANDIDATE", "BRIDGE", "GLOBAL_DENSE_CHILD", "DENSE", ranked)


# ── 1. weighted-RRF math is exactly Σ weight/(k+local_rank) ───────────────────────────────────────
def test_weighted_rrf_math():
    lanes = [_q0_dense([("a", "d0"), ("b", "d0")]), _bridge_dense([("a", "dB")])]
    res = fuse_ranked_lanes(lanes, weights=FusionWeights(q0=1.0, bridge=0.5), k=K, cap=100)
    by = {fc.chunk_id: fc for fc in res.ordered}
    # "a": q0-dense rank0 (1.0/(60+0)) + bridge-dense rank0 (0.5/(60+0))
    assert abs(by["a"].fused_score - (1.0 / 60 + 0.5 / 60)) < 1e-9
    # "b": q0-dense rank1 only (1.0/(60+1))
    assert abs(by["b"].fused_score - (1.0 / 61)) < 1e-9
    assert by["a"].fused_score > by["b"].fused_score        # agreement across lanes lifts "a"


# ── 2. lineage classification + weight lookup ─────────────────────────────────────────────────────
def test_lineage_class_and_weights():
    assert lineage_class(_q0_dense([("a", "d")])) == CLASS_Q0
    assert lineage_class(_bridge_dense([("z", "d")])) == CLASS_BRIDGE
    w = FusionWeights(q0=1.0, bridge=0.5)
    assert w.weight_for(CLASS_Q0) == 1.0 and w.weight_for(CLASS_BRIDGE) == 0.5
    # a q0-origin GRAPH lane is still Q0, not GRAPH (role dominates)
    q0_graph = _lane("q0", "q0", "USER", "GRAPH_DEST", "GRAPH", [("g", "d")])
    assert lineage_class(q0_graph) == CLASS_Q0


# ── 3. THE UNLOCK: a bridge's local winner survives the cap although its fused score is below it ───
def test_bridge_local_winner_survives_the_cap():
    # q0 floods 6 strong multi-rank chunks; the bridge finds ONE chunk (its local rank-0), which by
    # fused score sits well outside a cap of 3. Preservation must still carry it through.
    q0_ranked = [(f"q{i}", "d0") for i in range(6)]
    lanes = [_q0_dense(q0_ranked), _lane("q0", "q0", "USER", "GLOBAL_SPARSE_CHILD", "SPARSE", q0_ranked),
             _bridge_dense([("BRIDGEWIN", "dB")])]
    res = fuse_ranked_lanes(lanes, weights=FusionWeights(), k=K, preserve_top_n=1, cap=3)
    ids = res.ids()
    assert "BRIDGEWIN" in ids                                  # preserved through the cut
    win = next(fc for fc in res.ordered if fc.chunk_id == "BRIDGEWIN")
    assert win.preserved is True
    # and it did NOT displace the whole q0 head arbitrarily: q0's own top-1 is preserved too
    assert res.trace["preserved_survived_cap"] >= 2
    # sanity: without preservation the bridge winner would be truncated
    res_off = fuse_ranked_lanes(lanes, weights=FusionWeights(), k=K, preserve_top_n=0, cap=3)
    assert "BRIDGEWIN" not in res_off.ids()


# ── 4. many-to-one lineage is preserved (a shared chunk keeps ALL its query paths) ────────────────
def test_lineage_not_collapsed():
    lanes = [_q0_dense([("shared", "d0")]), _bridge_dense([("shared", "dB")], qid="b0"),
             _bridge_dense([("shared", "dB")], qid="b1")]
    res = fuse_ranked_lanes(lanes, k=K, cap=50)
    shared = next(fc for fc in res.ordered if fc.chunk_id == "shared")
    assert shared.query_ids == ["q0", "b0", "b1"]             # every discovering query retained
    assert len(shared.contributions) == 3                    # not collapsed to one score
    assert {c.lineage_class for c in shared.contributions} == {CLASS_Q0, CLASS_BRIDGE}


# ── 5. per-query top-N reservation covers EACH query, not just q0 ─────────────────────────────────
def test_preserved_winners_per_query():
    lanes = [_q0_dense([("q_a", "d0"), ("q_b", "d0")]), _bridge_dense([("b_a", "dB"), ("b_b", "dB")], qid="b0")]
    pres = preserved_winners(lanes, k=K, top_n=1)
    assert pres == {"q_a", "b_a"}                              # each query's own #1
    pres2 = preserved_winners(lanes, k=K, top_n=2)
    assert pres2 == {"q_a", "q_b", "b_a", "b_b"}


# ── 6. weights are configurable and actually change the ordering (not frozen) ─────────────────────
def test_weights_change_order():
    # one q0 chunk at rank1 vs one bridge chunk at rank0; whoever has more weight×rrf wins.
    lanes = [_q0_dense([("x", "d0"), ("qwin", "d0")]), _bridge_dense([("bwin", "dB")])]
    hi_bridge = fuse_ranked_lanes(lanes, weights=FusionWeights(q0=1.0, bridge=2.0), k=K, cap=50).ids()
    lo_bridge = fuse_ranked_lanes(lanes, weights=FusionWeights(q0=1.0, bridge=0.1), k=K, cap=50).ids()
    assert hi_bridge.index("bwin") < hi_bridge.index("qwin")   # heavy bridge outranks the q0 rank-1 chunk
    assert lo_bridge.index("bwin") > lo_bridge.index("qwin")   # light bridge falls below it


# ── 7. deterministic: identical inputs → identical trace, ties broken by chunk_id ─────────────────
def test_deterministic_and_tie_break():
    # two chunks with identical fused score (same lane, same rank in two separate single-result lanes)
    lanes = [_lane("q0", "q0", "USER", "GLOBAL_DENSE_CHILD", "DENSE", [("zeta", "d")]),
             _lane("s1", "MECH", "USER", "GLOBAL_DENSE_CHILD", "DENSE", [("alpha", "d")])]
    r1 = fuse_ranked_lanes(lanes, weights=FusionWeights(q0=0.7, subquery=0.7), k=K, cap=50)
    r2 = fuse_ranked_lanes(lanes, weights=FusionWeights(q0=0.7, subquery=0.7), k=K, cap=50)
    assert r1.ids() == r2.ids() == ["alpha", "zeta"]           # equal score → chunk_id ascending
    assert json.dumps(r1.trace, sort_keys=True) == json.dumps(r2.trace, sort_keys=True)


# ── 8. empty input is safe ────────────────────────────────────────────────────────────────────────
def test_empty():
    res = fuse_ranked_lanes([], cap=10)
    assert res.ordered == [] and res.preserved_ids == set() and res.trace["n_chunks"] == 0


# ── F4 step-6: config-driven weights; defaults are the A/B-validated values ───────────────────────
def test_fusion_weights_from_env():
    # unset env → the A/B-validated defaults
    d = FusionWeights.from_env({})
    assert (d.q0, d.subquery, d.bridge, d.profile, d.graph, d.other) == (1.0, 0.6, 0.5, 0.6, 0.5, 0.4)
    # override a class; invalid values fall back to the default
    o = FusionWeights.from_env({"POLYMATH_FUSION_W_BRIDGE": "0.9", "POLYMATH_FUSION_W_PROFILE": "notanum"})
    assert o.weight_for(CLASS_BRIDGE) == 0.9 and o.weight_for(CLASS_PROFILE) == 0.6 and o.weight_for(CLASS_Q0) == 1.0


# ── 9. STRICT ceiling: preservation changes who survives, never expands the cap ──────────────────
def test_cap_is_a_strict_ceiling_even_when_preserved_exceeds_it():
    # 5 distinct queries, each contributing 3 chunks; preserve_top_n=3 ⇒ 15 preserved chunks.
    lanes = [_lane(f"q{i}", ("q0" if i == 0 else "MECH"), ("USER"),
                   "GLOBAL_DENSE_CHILD", "DENSE", [(f"q{i}c{j}", f"d{i}") for j in range(3)]) for i in range(5)]
    res = fuse_ranked_lanes(lanes, preserve_top_n=3, cap=8)
    assert len(res.ordered) == 8                               # 15 preserved cannot expand an 8 cap
    assert res.trace["preserved_survived_cap"] <= 8

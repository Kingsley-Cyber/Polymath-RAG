"""WLK2C C4-live/C5-live orchestration (pure over an injected rerank). Pins the end-to-end flow:
a q0-sub-floor bridge candidate with a VALID bridge + strong local relevance is seated COMPLEMENTARY;
an INVALID bridge never grants latent status (anti-hijack); q0↔chunk is reused (never reranked);
the extra rerank budget is 1 (all bridge↔q0) + one call per bridge (bridge↔chunk); fail-open.
"""
from __future__ import annotations

from polymath_shared.latent_selection import grade_and_seat_latent

Q0 = "Q0"
BRIDGES = {"br0": {"query": "BRIDGE0", "proposed_role": "COMPLEMENTARY"}}


def _fake_rerank(score_map):
    calls = []

    def rerank(query, rows):
        calls.append(query)
        return [{**r, "rerank_score": score_map.get((query, r["chunk_id"]))} for r in rows]
    return rerank, calls


def _pool():
    return [
        {"chunk_id": "D1", "parent_id": "p1", "text": "direct answer text", "query_ids": ["q0"], "q0_score": 3.0},
        {"chunk_id": "L1", "parent_id": "p9", "text": "latent bridge text", "query_ids": ["br0"], "q0_score": -3.0},
    ]


def _seat_of(seated, cid):
    return next((s["seat_role"] for s in seated if s["chunk_id"] == cid), None)


def test_valid_bridge_seats_complementary():
    rerank, calls = _fake_rerank({("Q0", "br0"): 2.0,          # bridge valid
                                  ("BRIDGE0", "L1"): 2.0})     # local relevant
    seated, tr = grade_and_seat_latent(q0_text=Q0, pool=_pool(), bridges=BRIDGES, rerank=rerank, capacity=5)
    assert _seat_of(seated, "D1") == "DIRECT" and _seat_of(seated, "L1") == "COMPLEMENTARY"
    assert tr["complementary"] == 1
    assert len(calls) == 2                                      # 1 (bridge↔q0 for all) + 1 (bridge↔chunk per bridge)


def test_ANTIHIJACK_invalid_bridge_never_grants_latent_status():
    rerank, _ = _fake_rerank({("Q0", "br0"): -4.0,             # bridge INVALID
                              ("BRIDGE0", "L1"): 6.0})         # excellent local — must not rescue
    seated, _ = grade_and_seat_latent(q0_text=Q0, pool=_pool(), bridges=BRIDGES, rerank=rerank, capacity=5)
    assert _seat_of(seated, "L1") != "COMPLEMENTARY"           # demoted (RELATED fill), never latent evidence
    assert _seat_of(seated, "D1") == "DIRECT"


def test_q0_chunk_reused_not_reranked():
    # only bridge scoring is reranked; the DIRECT decision uses the pool's q0_score directly.
    rerank, calls = _fake_rerank({("Q0", "br0"): 2.0, ("BRIDGE0", "L1"): 2.0})
    grade_and_seat_latent(q0_text=Q0, pool=_pool(), bridges=BRIDGES, rerank=rerank, capacity=5)
    assert calls.count("Q0") == 1                               # exactly one q0-side call (all bridges batched);
    # that single q0 call scored the BRIDGE (chunk_id 'br0'), never a chunk → q0↔chunk is reused, not reranked.


def test_budget_is_one_plus_num_bridges():
    bridges = {"br0": {"query": "B0"}, "br1": {"query": "B1"}}
    pool = [{"chunk_id": "L1", "parent_id": "p1", "text": "t", "query_ids": ["br0"], "q0_score": -3.0},
            {"chunk_id": "L2", "parent_id": "p2", "text": "t", "query_ids": ["br1"], "q0_score": -3.0}]
    rerank, calls = _fake_rerank({("Q0", "br0"): 2.0, ("Q0", "br1"): 2.0, ("B0", "L1"): 2.0, ("B1", "L2"): 2.0})
    grade_and_seat_latent(q0_text=Q0, pool=pool, bridges=bridges, rerank=rerank, capacity=5)
    assert len(calls) == 1 + 2                                  # one bridge↔q0 batch + one bridge↔chunk per bridge


def test_invariant_B_redundant_direct_yields_to_complementary_end_to_end():
    pool = [{"chunk_id": "D1", "parent_id": "p1", "text": "t", "query_ids": ["q0"], "q0_score": 3.0},
            {"chunk_id": "D2", "parent_id": "p1", "text": "t", "query_ids": ["q0"], "q0_score": 2.5},  # same rep -> redundant
            {"chunk_id": "L1", "parent_id": "p9", "text": "t", "query_ids": ["br0"], "q0_score": -3.0}]
    rerank, _ = _fake_rerank({("Q0", "br0"): 2.0, ("BRIDGE0", "L1"): 2.0})
    seated, _ = grade_and_seat_latent(q0_text=Q0, pool=pool, bridges=BRIDGES, rerank=rerank, capacity=2,
                                      direct_per_rep_cap=1)
    ids = {s["chunk_id"] for s in seated}
    assert ids == {"D1", "L1"}                                  # redundant D2 yielded to complementary L1


def test_fail_open_on_rerank_error_keeps_direct():
    def boom(query, rows):
        raise RuntimeError("reranker down")
    seated, _ = grade_and_seat_latent(q0_text=Q0, pool=_pool(), bridges=BRIDGES, rerank=boom, capacity=5)
    assert _seat_of(seated, "D1") == "DIRECT"                   # DIRECT unaffected
    assert _seat_of(seated, "L1") != "COMPLEMENTARY"            # no latent added on scoring failure


def test_deterministic():
    rerank, _ = _fake_rerank({("Q0", "br0"): 2.0, ("BRIDGE0", "L1"): 2.0})
    a, _ = grade_and_seat_latent(q0_text=Q0, pool=_pool(), bridges=BRIDGES, rerank=rerank, capacity=5)
    rerank2, _ = _fake_rerank({("Q0", "br0"): 2.0, ("BRIDGE0", "L1"): 2.0})
    b, _ = grade_and_seat_latent(q0_text=Q0, pool=_pool(), bridges=BRIDGES, rerank=rerank2, capacity=5)
    assert [s["chunk_id"] for s in a] == [s["chunk_id"] for s in b]


def test_fast_skips_the_bridge_pass_and_the_deeper_modes_run_it(monkeypatch):
    """Owner 2026-09-22: FAST runs no depth pass. Once the bridge subqueries search again (subquery cap 10), re-judging the
    bridge pool costs 3.7–6.2 s a turn (measured: one reranker call for every bridge↔q0 + one per bridge). FAST returns before
    any of it and leaves the evidence list untouched; HYBRID / GRAPH / WILDCARD still run it."""
    import pathlib
    import sys
    import types

    root = pathlib.Path(__file__).resolve().parents[2]
    for sub in ("shared", "orchestrator"):
        if str(root / sub) not in sys.path:
            sys.path.insert(0, str(root / sub))
    from orchestrator.api import fast as fast_api
    from orchestrator.api import ui

    monkeypatch.setenv("POLYMATH_CHAT_LATENT_SELECTION", "1")
    calls: list[str] = []

    def rerank(query, rows):
        calls.append(query)
        return [{**r, "rerank_score": 2.0} for r in rows]       # every bridge valid, every chunk locally relevant

    monkeypatch.setattr(fast_api, "_rerank_children", rerank)
    plan = types.SimpleNamespace(queries=[
        types.SimpleNamespace(id="q0", type="PRIMARY", query=Q0, origin="USER", reason="", weight=1.0),
        types.SimpleNamespace(id="br0", type="ENTITY", query="BRIDGE0", origin="BRIDGE", reason="bridge/complementary <- d9", weight=0.55),
    ])

    def fresh():
        return {"evidence": [{"chunk_id": "D1", "doc_id": "d1", "parent_id": "p1", "text": "direct answer text",
                              "query_ids": ["q0"], "g3_score": 3.0}],
                "latent_pool": [{"chunk_id": "L1", "doc_id": "d9", "parent_id": "p9", "text": "latent bridge text",
                                 "query_ids": ["br0"], "q0_score": -3.0}]}

    fast = fresh()
    before = fast["evidence"]
    assert ui._apply_latent_selection(fast, plan, Q0, mode="FAST") is None
    assert fast["evidence"] is before and calls == []
    for mode in ("HYBRID", "GRAPH", "WILDCARD"):
        fast, calls[:] = fresh(), []
        rec = ui._apply_latent_selection(fast, plan, Q0, mode=mode)
        assert rec and rec.get("enabled") is True and "error" not in rec, (mode, rec)
        assert calls, mode                                                   # the bridge pass judged something
        graded = {g["chunk_id"]: g["c4_state"] for g in rec.get("graded") or []}
        assert graded.get("L1") == "COMPLEMENTARY_ELIGIBLE", (mode, graded)  # q0-sub-floor, both bridge links hold

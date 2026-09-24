"""PROBE-GATE-V1: a probe that misses the user's resolved question is dropped before it spends retrieval (owner design
note: "A vague bridge earns nothing"). Measured 2026-09-24 on five live plans: the four off-topic probes scored 0.02–0.08
against the full question and contributed 0 final chunks; every contributing probe scored ≥ 0.31 — the floor is 0.2."""
from __future__ import annotations

import time

from polymath_shared.candidate_engine import CandidateBudget
from polymath_shared.probe_gate import DEFAULT_FLOOR, gate_probes
from polymath_shared.skeleton_routes import apply_skeleton_routes

Q = "How do editors and directors build suspense without dialogue?"
PROBES = [("q1", "USER", "editing techniques for tension and suspense"),
          ("p0", "PROFILE", "How do television techniques influence film editing and audience perception?"),
          ("br0", "BRIDGE", "How is misdirection used in film editing to manipulate audience expectations?"),
          ("ce0", "CORPUS_EXPLORE", "")]


def judge(q, rows):
    scores = {"p0": -3.0, "br0": 4.0, "q1": 5.0}                 # σ(-3) = 0.047 · σ(4) = 0.982
    return [dict(r, rerank_score=scores[r["chunk_id"]]) for r in rows]


def test_a_probe_below_the_floor_is_dropped_and_the_users_own_facets_are_never_scored():
    seen: list[str] = []

    def spy(q, rows):
        seen.extend(r["chunk_id"] for r in rows)
        return judge(q, rows)

    dropped, rec = gate_probes(Q, PROBES, spy)
    assert dropped == {"p0"} and seen == ["p0", "br0"]           # USER never scored; an empty probe never sent
    assert rec["floor"] == DEFAULT_FLOOR == 0.2 and rec["scored"] == 2 and rec["dropped"] == ["p0"]
    assert rec["scores"]["p0"] == {"origin": "PROFILE", "score": 0.0474} and rec["scores"]["br0"]["score"] > 0.9


def test_the_gate_fails_open():
    def broken(q, rows):
        raise ConnectionError("reranker parked")

    def slow(q, rows):
        time.sleep(0.5)
        return judge(q, rows)

    assert gate_probes(Q, PROBES, broken)[0] == set() and gate_probes(Q, PROBES, broken)[1]["error"] == "ConnectionError"
    dropped, rec = gate_probes(Q, PROBES, slow, timeout_s=0.05)
    assert dropped == set() and rec["error"] == "TimeoutError"
    assert gate_probes(Q, PROBES, lambda q, rows: [dict(r, rerank_score=None) for r in rows])[0] == set()   # unscored = kept


def test_nothing_to_gate_means_no_judge_call():
    def never(q, rows):
        raise AssertionError("the judge must not be called")

    assert gate_probes(Q, [("q1", "USER", "facet")], never)[0] == set()
    assert gate_probes(Q, PROBES, never, floor=0.0)[0] == set()
    assert gate_probes("  ", PROBES, never)[0] == set()


def test_the_switch_rides_the_doors_and_never_touches_fast_or_gnn():
    on = {"POLYMATH_CHAT_SKELETON_ROUTES": "1", "POLYMATH_CHAT_PROBE_GATE": "1"}
    for mode in ("HYBRID", "GRAPH"):
        assert apply_skeleton_routes(CandidateBudget(), mode=mode, env=on).probe_gate_floor == 0.2
    # WILDCARD is exempt: an off-topic probe (0.04) and a non-obvious bridge (0.06) share the band the gate would cut
    assert apply_skeleton_routes(CandidateBudget(), mode="WILDCARD", env=on).probe_gate_floor == 0.0
    assert apply_skeleton_routes(CandidateBudget(), mode="HYBRID", env={"POLYMATH_CHAT_SKELETON_ROUTES": "1"}).probe_gate_floor == 0.0
    for mode in ("FAST", "VECTOR", "GNN"):
        assert apply_skeleton_routes(CandidateBudget(), mode=mode, env=on).probe_gate_floor == 0.0
    assert apply_skeleton_routes(CandidateBudget(), mode="HYBRID", env={"POLYMATH_CHAT_PROBE_GATE": "1"}) == CandidateBudget()

"""SKELETON-ROUTING-V1 route activation (DOCUMENT-SKELETON-V1 §4.3): the skeleton doors follow the plan and the mode, never
one intent word. GRAPH hops through SEEALSO (owner decision D8, one hop); WILDCARD opens every abstract door; FAST and GNN
stay exactly as the owner defined them."""
from __future__ import annotations

from types import SimpleNamespace

from polymath_shared.candidate_engine import CandidateBudget
from polymath_shared.skeleton_routes import apply_skeleton_routes

ON = {"POLYMATH_CHAT_SKELETON_ROUTES": "1"}


def _plan(*origins):
    return SimpleNamespace(queries=[SimpleNamespace(id=f"x{i}", origin=o) for i, o in enumerate(origins)])


def test_flag_off_changes_nothing():
    b = CandidateBudget()
    assert apply_skeleton_routes(b, mode="GRAPH", plan=_plan("PROFILE"), env={}) == b


def test_graph_hops_through_seealso_and_the_graph_destination():
    b = apply_skeleton_routes(CandidateBudget(), mode="GRAPH", plan=_plan("USER"), env=ON)
    assert b.skeleton_paths and b.dualread_enabled and b.seealso_fanout_enabled and b.graph_dest_enabled
    assert "SEEALSO" in b.atom_kinds and "CONCEPT" in b.atom_kinds


def test_wildcard_opens_every_abstract_door():
    b = apply_skeleton_routes(CandidateBudget(), mode="WILDCARD", plan=_plan(), env=ON)
    assert b.latent_enabled and b.seealso_fanout_enabled and b.graph_dest_enabled and b.route_prefix_seats == 3
    assert {"LATENT_PATTERN", "TENSION", "BRIDGE", "INVERSION", "BOUNDARY", "RECALLQ"} <= set(b.atom_kinds)


def test_hybrid_fans_out_when_the_scout_nominated_documents():
    nominated = apply_skeleton_routes(CandidateBudget(), mode="HYBRID", plan=_plan("USER", "PROFILE"), env=ON)
    plain = apply_skeleton_routes(CandidateBudget(), mode="HYBRID", plan=_plan("USER"), env=ON)
    assert nominated.seealso_fanout_enabled and not nominated.graph_dest_enabled
    assert not plain.seealso_fanout_enabled and plain.skeleton_paths and plain.dualread_enabled


def test_fast_and_gnn_stay_as_defined():
    b = CandidateBudget()
    assert apply_skeleton_routes(b, mode="FAST", plan=_plan("PROFILE"), env=ON) == b
    assert apply_skeleton_routes(b, mode="GNN", plan=_plan("PROFILE"), env=ON) == b


def test_the_contextual_judge_has_its_own_switch():
    off = apply_skeleton_routes(CandidateBudget(), mode="HYBRID", plan=_plan(), env=ON)
    on = apply_skeleton_routes(CandidateBudget(), mode="HYBRID", plan=_plan(),
                               env={**ON, "POLYMATH_CHAT_CONTEXTUAL_JUDGE": "1"})
    assert not off.contextual_judge and on.contextual_judge


def test_route_aspects_never_become_coverage_lines():
    from orchestrator.api import ui
    lines = ui._coverage_lines({"q1": {"type": "MECHANISM", "query": "a", "final": 2},
                                "rt:pmap": {"type": "ROUTE", "query": "rt:pmap", "final": 0}})
    assert lines and "rt:pmap" not in lines[0] and "q1" in lines[0]


def test_the_judge_can_be_scoped_to_wildcard():
    env = {**ON, "POLYMATH_CHAT_CONTEXTUAL_JUDGE": "wildcard"}
    assert apply_skeleton_routes(CandidateBudget(), mode="WILDCARD", plan=_plan(), env=env).contextual_judge
    assert not apply_skeleton_routes(CandidateBudget(), mode="HYBRID", plan=_plan(), env=env).contextual_judge
    assert not apply_skeleton_routes(CandidateBudget(), mode="GRAPH", plan=_plan(), env=env).contextual_judge


# ---------------------------------------------------------------- SKELETON-ROUTING-V1.1: the plan's probes drive the skeleton

PROBES = {**ON, "POLYMATH_CHAT_SKELETON_PROBES": "1"}


def test_probe_routes_follow_the_mode_and_run_the_skeleton_lanes_concurrently():
    wild = apply_skeleton_routes(CandidateBudget(), mode="WILDCARD", plan=_plan("PROFILE", "BRIDGE"), env=PROBES)
    hyb = apply_skeleton_routes(CandidateBudget(), mode="HYBRID", plan=_plan("PROFILE"), env=PROBES)
    graph = apply_skeleton_routes(CandidateBudget(), mode="GRAPH", plan=_plan("USER"), env=PROBES)
    assert wild.skeleton_probe_routes == 7 and hyb.skeleton_probe_routes == 4 == graph.skeleton_probe_routes
    assert wild.parallel_route_lanes and hyb.parallel_route_lanes and graph.parallel_route_lanes


def test_probe_routes_need_their_own_flag_and_the_doors():
    doors_only = apply_skeleton_routes(CandidateBudget(), mode="WILDCARD", plan=_plan("PROFILE"), env=ON)
    assert doors_only.skeleton_probe_routes == 0 and doors_only.parallel_route_lanes      # opened doors always run concurrently
    no_doors = apply_skeleton_routes(CandidateBudget(), mode="WILDCARD", plan=_plan("PROFILE"),
                                     env={"POLYMATH_CHAT_SKELETON_PROBES": "1"})
    assert no_doors == CandidateBudget()                                      # probes ride the doors; alone they change nothing
    for mode in ("FAST", "VECTOR", "GNN"):
        assert apply_skeleton_routes(CandidateBudget(), mode=mode, plan=_plan("PROFILE"), env=PROBES) == CandidateBudget()

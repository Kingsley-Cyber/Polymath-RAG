"""WLK2C C0 — query-anchored retrieval lineage (many-to-one, pure).

Pins the two owner-locked invariants: (1) a candidate keeps EVERY discovery path, never collapsed to
one winner (C4 selects later); (2) lineage existence is recorded without judging bridge validity (C1
judges). Plus: pure-q0 is a DIRECT path (bridge_id None); non-primary subqueries become bridge paths
with provenance; discovered_by maps arrivals to lanes; missing signals fail open to a single q0 path;
q0 authority (root_query) is never lost; JSON-native.
"""
from __future__ import annotations

import json

from polymath_shared.retrieval_lineage import (
    DiscoveryPath,
    Lineage,
    annotate_lineage,
    derive_lineage,
    primary_text,
)


def _q(qid, qtype, text, *, origin="USER", weight=1.0, inspired=None):
    return {"id": qid, "type": qtype, "query": text, "origin": origin,
            "weight": weight, "inspired_by_profile": inspired or []}


PLAN = [
    _q("q0", "PRIMARY", "make the fake smile readable"),
    _q("s1", "MECHANISM", "facial mechanics of performed vs genuine smiling", origin="USER", weight=0.8),
    _q("p1", "ENTITY", "expression coding for acting", origin="PROFILE", weight=0.6, inspired=["docFACS"]),
]


def test_pure_q0_candidate_is_a_single_direct_path():
    lin = derive_lineage({"query_ids": ["q0"], "arrivals": ["GLOBAL_DENSE_CHILD"]}, PLAN)
    assert lin.is_direct and len(lin.paths) == 1 and lin.paths[0].is_primary
    assert lin.paths[0].bridge_id is None
    assert lin.paths[0].origin_query == "make the fake smile readable" == lin.root_query
    assert lin.bridge_paths() == []
    assert lin.discovered_by == ["DENSE"]


def test_all_discovery_paths_retained_never_collapsed():
    # the OWNER'S KEY INVARIANT: q0 + PROFILE + a graph bridge all retrieved the same chunk
    plan = PLAN + [_q("g1", "BRIDGE", "movement→status relation", origin="GRAPH", weight=0.9, inspired=[])]
    row = {"query_ids": ["q0", "p1", "g1"], "arrivals": ["GLOBAL_DENSE_CHILD", "GRAPH_DEST"],
           "query_scores": {"q0": 0.2, "p1": 0.5, "g1": 0.7}}
    lin = derive_lineage(row, plan)
    got = {(p.origin, p.bridge_id) for p in lin.paths}
    assert got == {("USER", None), ("PROFILE", "p1"), ("GRAPH", "g1")}     # NONE dropped
    assert lin.is_direct                                                    # q0 path present
    assert {p.bridge_id for p in lin.bridge_paths()} == {"p1", "g1"}
    assert sorted(lin.discovered_by) == ["DENSE", "GRAPH"]
    # per-path score carried; primary sorts first, then by descending weight
    assert lin.paths[0].is_primary
    assert [p.bridge_id for p in lin.paths[1:]] == ["g1", "p1"]             # weight 0.9 > 0.6
    assert lin.paths[1].score == 0.7


def test_non_primary_only_is_not_direct():
    lin = derive_lineage({"query_ids": ["p1"], "arrivals": ["GLOBAL_DENSE_CHILD"]}, PLAN)
    assert not lin.is_direct
    assert len(lin.paths) == 1 and lin.paths[0].bridge_id == "p1" and lin.paths[0].origin == "PROFILE"
    assert lin.paths[0].inspired_by_profile == ["docFACS"]
    assert lin.root_query == "make the fake smile readable"                 # q0 authority preserved


def test_lineage_existence_is_not_bridge_validity():
    # a misdirected PROFILE expansion is RECORDED (provenance retained) — C0 does NOT bless it.
    plan = [_q("q0", "PRIMARY", "make the fake smile readable"),
            _q("bad", "ENTITY", "Augmenting prompts for text-to-video generation", origin="PROFILE", weight=0.5)]
    lin = derive_lineage({"query_ids": ["q0", "bad"], "arrivals": ["GLOBAL_DENSE_CHILD"]}, plan)
    assert any(p.bridge_id == "bad" for p in lin.bridge_paths())            # kept, not discarded
    # no admission decision exists at C0 — Lineage exposes no "admissible"/"valid" flag
    assert not hasattr(lin.paths[0], "admissible")


def test_discovered_by_maps_every_lane():
    cases = {"HIERARCHICAL_ROUTE": "HIERARCHY", "GLOBAL_DENSE_CHILD": "DENSE",
             "GLOBAL_SPARSE_CHILD": "SPARSE", "GRAPH_DEST": "GRAPH",
             "NEIGHBOR_EXPANSION": "NEIGHBOR", "LATENT_RESCUE": "WILDCARD"}
    for arrival, lane in cases.items():
        assert derive_lineage({"query_ids": ["q0"], "arrivals": [arrival]}, PLAN).discovered_by == [lane], arrival


def test_unknown_arrival_ignored_and_singular_key():
    assert derive_lineage({"query_ids": ["q0"], "arrivals": ["NEW", "GLOBAL_SPARSE_CHILD"]}, PLAN).discovered_by == ["SPARSE"]
    assert derive_lineage({"query_ids": ["q0"], "arrival": "GLOBAL_SPARSE_CHILD"}, PLAN).discovered_by == ["SPARSE"]


def test_missing_signals_fail_open_to_single_q0_path():
    for row in ({}, {"query_ids": ["ghost"]}, {"query_ids": []}):
        lin = derive_lineage(row, PLAN)
        assert lin.is_direct and len(lin.paths) == 1 and lin.paths[0].is_primary
    empty = derive_lineage({"query_ids": ["s1"]}, [])
    assert empty.is_direct and empty.root_query == "" and empty.discovered_by == []


def test_duplicate_query_ids_deduped():
    lin = derive_lineage({"query_ids": ["p1", "p1", "q0"], "arrivals": []}, PLAN)
    assert len(lin.paths) == 2                                              # p1 once + q0


def test_object_duck_typing_matches_dict():
    class CQ:
        def __init__(self, **kw): self.__dict__.update(kw)
    plan = [CQ(id="q0", type="PRIMARY", query="root", origin="USER", weight=1.0, inspired_by_profile=[]),
            CQ(id="g1", type="BRIDGE", query="graphish", origin="GRAPH", weight=0.9, inspired_by_profile=[])]
    lin = derive_lineage({"query_ids": ["g1"], "arrivals": ["GRAPH_DEST"]}, plan)
    assert [p.bridge_id for p in lin.bridge_paths()] == ["g1"]
    assert lin.bridge_paths()[0].origin == "GRAPH" and lin.bridge_paths()[0].origin_query == "graphish"


def test_annotate_lineage_in_place_and_json_native():
    rows = [{"chunk_id": "c1", "query_ids": ["q0"], "arrivals": ["GLOBAL_DENSE_CHILD"]},
            {"chunk_id": "c2", "query_ids": ["q0", "p1"], "arrivals": ["GLOBAL_DENSE_CHILD"]}]
    out = annotate_lineage(rows, PLAN)
    assert out is rows and all("lineage" in r for r in rows)
    assert rows[0]["lineage"]["is_direct"] is True and len(rows[0]["lineage"]["paths"]) == 1
    assert {p["bridge_id"] for p in rows[1]["lineage"]["paths"]} == {None, "p1"}
    json.dumps(rows[1]["lineage"])                                          # JSON-native


def test_primary_text_and_origin_sanitized():
    assert primary_text(PLAN) == "make the fake smile readable"
    assert primary_text([_q("x", "MECHANISM", "only sub")]) == "only sub"
    assert primary_text([]) == ""
    assert DiscoveryPath(origin_query="o", origin="NONSENSE", query_id="x", bridge_id="x").origin == "USER"

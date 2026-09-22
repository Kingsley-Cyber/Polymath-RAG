"""GNN-RETRIEVAL-V1 — the query-time route and the engine's lane I, pure (fake Qdrant client, fake child search, the engine's
own fake store). LAW under test: the GNN routes, ORIGINAL children prove, the existing reranker judges — a GNN vector is never
evidence, a wrong contract / dimension / corpus is a typed refusal, the four existing modes are untouched."""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared",):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from polymath_shared import candidate_engine as ce  # noqa: E402
from polymath_shared import gnn_route as gr  # noqa: E402
from polymath_shared import retrieval_modes as rm  # noqa: E402
from test_candidate_engine import CHILD, Fake, _ctx, _row  # noqa: E402  — the engine's own fake corpus


def test_the_code_under_test_is_this_checkout():
    for mod in (ce, gr, rm):
        assert pathlib.Path(mod.__file__).resolve().is_relative_to(ROOT), mod.__file__


# ─────────────────────────────────────────────────────────── the mode registry
def test_gnn_mode_is_accepted_and_existing_modes_unchanged():
    assert rm.MODE_GNN == "GNN" and rm.validate_mode("GNN") == "GNN"
    assert rm.EXPOSED_MODES[:4] == ("FAST", "HYBRID", "GRAPH", "WILDCARD") and rm.DEFAULT_MODE == rm.MODE_LEGACY
    with pytest.raises(ValueError):
        rm.validate_mode("GNN2")


def test_gnn_mode_composition_is_the_gnn_route_alone():
    """The retrieval composition table lives beside the orchestrator; read it as text so this stays DB-free and worktree-safe."""
    src = (ROOT / "orchestrator" / "orchestrator" / "api" / "chat_retrieval.py").read_text(encoding="utf-8")
    assert "MODE_GNN: ()" in src and "def _retrieve_gnn(" in src and 'replace(budget, lanes=(), gnn_enabled=True, latent_enabled=False, dualread_enabled=False, resolution_lift_enabled=False' in src
    for m in ("MODE_VECTOR: (LANE_A, LANE_B)", "MODE_FAST: (LANE_A, LANE_B)", "MODE_HYBRID: LANES", "MODE_GRAPH: LANES", "MODE_WILDCARD: LANES"):
        assert m in src                                                          # the four existing compositions, byte for byte
    ui = (ROOT / "orchestrator" / "orchestrator" / "api" / "ui.py").read_text(encoding="utf-8")
    assert '"FAST", "HYBRID", "GRAPH", "ASK", "WILDCARD", "GNN"' in ui and '"gnn_requires_v2"' in ui


# ─────────────────────────────────────────────────────────── contract-derived naming + refusals
def test_collection_name_is_contract_derived_and_isolated():
    name = gr.collection_name("embed_abc", gr.gnn_contract(gr.FAMILY_M1, gr.VARIANT_REAL))
    assert name == "polymath_gnn_parent_embed_abc_m1-smooth-real" and "document_parent_maps" not in name
    assert gr.collection_name("embed_abc", gr.gnn_contract(gr.FAMILY_M1, gr.VARIANT_SHUFFLED)) != name
    with pytest.raises(gr.GnnRouteRefused):
        gr.gnn_contract(gr.FAMILY_M1, "random")


class _Client:
    def __init__(self, dim=2, contract="embed_abc", kind=gr.PAYLOAD_KIND, hits=(), missing=False):
        self.dim, self.contract, self.kind, self.hits, self.missing, self.searches = dim, contract, kind, list(hits), missing, []

    def get_collection(self, name):
        if self.missing:
            raise RuntimeError("Not found")
        return SimpleNamespace(config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=self.dim))), points_count=len(self.hits))

    def scroll(self, name, limit=1, with_payload=True, with_vectors=False):
        return ([SimpleNamespace(payload={"representation_kind": self.kind, "embedding_contract": self.contract})] if self.hits else [], None)

    def search(self, collection_name, query_vector, query_filter, limit, with_payload, with_vectors):
        self.searches.append((collection_name, tuple(query_vector), limit))
        return [SimpleNamespace(score=s, payload=pl) for s, pl in self.hits][:limit]


def _parent(pid, doc, corpus="c1", score=0.9):
    return (score, {"representation_kind": gr.PAYLOAD_KIND, "corpus_id": corpus, "doc_id": doc, "parent_id": pid, "embedding_contract": "embed_abc",
                    "gnn_contract": "m1-smooth-real", "graph_snapshot_id": "snap_1", "model_digest": "m1"})


def test_wrong_vector_dimension_is_refused():
    with pytest.raises(gr.GnnRouteRefused) as e:
        gr.verify_collection(_Client(dim=3), "coll", expect_dim=2, embedding_contract="embed_abc")
    assert e.value.code == "GNN_VECTOR_DIM_MISMATCH"


def test_wrong_embedding_contract_is_refused_and_a_missing_collection_is_typed():
    with pytest.raises(gr.GnnRouteRefused) as e:
        gr.verify_collection(_Client(contract="embed_OLD", hits=[_parent("p1", "d1")]), "coll", expect_dim=2, embedding_contract="embed_abc")
    assert e.value.code == "GNN_EMBEDDING_CONTRACT_MISMATCH"
    with pytest.raises(gr.GnnRouteRefused) as e2:
        gr.verify_collection(_Client(missing=True), "coll", expect_dim=2, embedding_contract="embed_abc")
    assert e2.value.code == "GNN_COLLECTION_MISSING"
    assert gr.verify_collection(_Client(hits=[_parent("p1", "d1")]), "coll", expect_dim=2, embedding_contract="embed_abc")["dim"] == 2


# ─────────────────────────────────────────────────────────── parent search: routes, never evidence; one corpus
def test_parent_search_returns_routes_not_evidence_and_never_crosses_corpora():
    client = _Client(hits=[_parent("d1-p0", "d1"), _parent("d9-p0", "d9", corpus="other"), _parent("d2-p1", "d2", score=0.7)])
    routes = gr.gnn_parent_search(client, "coll", (0.1, 0.2), corpus_id="c1", limit=8)
    assert [r["parent_id"] for r in routes] == ["d1-p0", "d2-p1"] and [r["rank"] for r in routes] == [1, 3]
    assert set(routes[0]) == {"parent_id", "doc_id", "score", "rank", "gnn_contract", "graph_snapshot_id", "model_digest"}   # no text, no claim
    with pytest.raises(gr.GnnRouteRefused):
        gr.gnn_parent_search(client, "coll", (0.1, 0.2), corpus_id="", limit=8)


def test_parents_hydrate_original_children_through_the_existing_child_search_and_dedupe():
    fake = Fake()

    def child_search(vec, extra, limit):
        return fake.dense(CHILD, limit, extra)

    parents = [{"parent_id": "d1-p0", "doc_id": "d1", "rank": 1, "score": 0.9}, {"parent_id": "d1-p0", "doc_id": "d1", "rank": 2, "score": 0.8},
               {"parent_id": "d2-p1", "doc_id": "d2", "rank": 3, "score": 0.7}]
    rows = gr.hydrate_original_children(child_search, (0.1, 0.2), parents, corpus_id="c1", per_parent=2, cap=3)
    assert [r["payload"]["chunk_id"] for r in rows] == ["d1-p0-k0", "d1-p0-k1", "d2-p1-k0"]              # original children, deduped, capped
    assert all(c[1] == CHILD and c[3]["parent_id"] in ("d1-p0", "d2-p1") and c[3]["corpus_id"] == "c1" for c in fake.calls)   # the SAME routing_child search, filtered
    assert rows[0]["gnn_parent"] == "d1-p0" and rows[0]["gnn_parent_rank"] == 1 and "text of d1-p0-k0" == rows[0]["payload"]["text"]


def test_route_receipt_carries_the_comparison_fields():
    client = _Client(hits=[_parent("d1-p0", "d1")])
    fake = Fake()
    rows, receipt = gr.route(client, "coll", lambda v, extra, limit: fake.dense(CHILD, limit, extra), (0.1, 0.2), corpus_id="c1", parent_k=8, per_parent=2, cap=12)
    assert receipt["parent_k"] == 8 and receipt["parents"][0]["parent_id"] == "d1-p0" and receipt["hydrated_children"] == len(rows) == 2
    assert receipt["gnn_contract"] == "m1-smooth-real" and receipt["graph_snapshot_id"] == "snap_1" and receipt["model_digest"] == "m1" and "elapsed_ms" in receipt


# ─────────────────────────────────────────────────────────── the engine: lane I, arrivals, dedupe, judge
def _gnn_search_from(fake: Fake, parents):
    def gnn_search(qv):
        rows = gr.hydrate_original_children(lambda v, extra, limit: fake.dense(CHILD, limit, extra), qv, parents, corpus_id="c1", per_parent=2, cap=12)
        return rows, {"contract": gr.GNN_ROUTE_CONTRACT, "collection": "coll", "parent_k": len(parents), "parents": parents, "hydrated_children": len(rows), "unique_children": len(rows), "elapsed_ms": 0.1}
    return gnn_search


def test_gnn_candidates_carry_the_gnn_arrival_and_dedupe_against_existing_candidates():
    fake = Fake()
    parents = [{"parent_id": "d2-p0", "doc_id": "d2", "rank": 1, "score": 0.9}, {"parent_id": "d2-p1", "doc_id": "d2", "rank": 2, "score": 0.8}]
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(gnn_enabled=True), dense_search=fake.dense, sparse_search=fake.sparse, gnn_search=_gnn_search_from(fake, parents))
    by = {c.chunk_id: c for c in res.union}
    assert "d2-p0-k0" in by and ce.ARRIVAL_GNN_ROUTE in by["d2-p0-k0"].arrivals and len(by["d2-p0-k0"].arrivals) > 1    # arrived via lane A too: ONE candidate, both arrivals
    assert sum(1 for c in res.union if c.chunk_id == "d2-p0-k0") == 1
    routed = [c for c in res.union if ce.ARRIVAL_GNN_ROUTE in c.arrivals]
    assert [c.chunk_id for c in routed] == ["d2-p0-k0", "d2-p0-k1", "d2-p1-k0", "d2-p1-k1"] and all(len(c.arrivals) >= 2 for c in routed)   # every GNN child fused ONCE with its other arrivals
    assert len(res.union) == len({c.chunk_id for c in res.union})                                                        # no duplicate candidate anywhere
    assert res.trace["lane_sizes"]["gnn_route"] == 4 and res.trace["gnn"]["candidates"] == 4 and res.trace["funnel_lanes"]["gnn_route"] == ["d2-p0-k0", "d2-p0-k1", "d2-p1-k0", "d2-p1-k1"]
    assert ce.synthesis_role([ce.ARRIVAL_GNN_ROUTE]) == "RELATIONAL"


def test_gnn_lane_alone_is_a_measurable_route_and_off_is_byte_identical():
    fake = Fake()
    parents = [{"parent_id": "d3-p1", "doc_id": "d3", "rank": 1, "score": 0.9}]
    only = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lanes=(), gnn_enabled=True), dense_search=fake.dense, sparse_search=fake.sparse, gnn_search=_gnn_search_from(fake, parents))
    assert [c.arrivals for c in only.union] == [[ce.ARRIVAL_GNN_ROUTE]] * len(only.union) and len(only.union) == 2   # the GNN route is the ONLY candidate lane
    fake_off, fake_on = Fake(), Fake()
    off = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake_off.dense, sparse_search=fake_off.sparse)
    on = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(gnn_enabled=False), dense_search=fake_on.dense, sparse_search=fake_on.sparse, gnn_search=_gnn_search_from(fake_on, parents))
    assert [c.chunk_id for c in off.union] == [c.chunk_id for c in on.union] and on.trace["gnn"] == {"enabled": False}


def test_a_failing_gnn_route_is_a_typed_degraded_receipt_never_another_lanes_output():
    fake = Fake()

    def broken(qv):
        raise gr.GnnRouteRefused("GNN_COLLECTION_MISSING", "coll: Not found")

    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lanes=(), gnn_enabled=True), dense_search=fake.dense, sparse_search=fake.sparse, gnn_search=broken)
    assert res.union == [] and res.trace["gnn"]["code"] == "GNN_COLLECTION_MISSING" and "degraded" in res.trace["gnn"]


def test_gnn_evidence_is_judged_by_the_same_reranker():
    fake = Fake()
    parents = [{"parent_id": "d3-p1", "doc_id": "d3", "rank": 1, "score": 0.9}]
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lanes=(), gnn_enabled=True), dense_search=fake.dense, sparse_search=fake.sparse, gnn_search=_gnn_search_from(fake, parents))
    seen = []

    def rerank(q, rows):
        seen.append([r["chunk_id"] for r in rows])
        return [{**r, "rerank_score": 1.0 - i * 0.1} for i, r in enumerate(rows)]

    selected, meta = ce.select_evidence(res, ce.CandidateBudget(lanes=(), gnn_enabled=True), rerank_children=rerank)
    assert seen and set(seen[0]) == {c.chunk_id for c in res.union}                 # every GNN-routed ORIGINAL child went through the judge
    assert all(ce.ARRIVAL_GNN_ROUTE in c.arrivals for c in selected) and selected

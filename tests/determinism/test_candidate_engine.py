"""CANDIDATE-RETRIEVAL-V1 (plan §3.14 / §3.21 / §3.22, P1.a): three lanes,
child-level fusion with provenance, degraded sparse lane, budget shaping on
the resolved request, one bounded rerank. Pure — fake search callables."""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared",):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from polymath_shared import candidate_engine as ce  # noqa: E402

DOC = "routing_document_summary"
SEC = "routing_section_summary"
CHILD = "routing_child"
CARD = "routing_entity"


def _row(kind, i, doc, parent=None, chunk=None, score=None, text=None, **extra):
    pl = {"corpus_id": "c1", "doc_id": doc, "parent_id": parent or f"{doc}-p{i % 2}", "source_name": f"Book {doc}"}
    if kind == CHILD:
        pl["chunk_id"] = chunk or f"{doc}-ch{i}"
        pl["text"] = text or f"text of {pl['chunk_id']}"
    else:
        pl["summary_id"] = f"{kind}-{doc}-{i}"
        pl["text"] = f"summary {kind} {doc}"
    pl.update(extra)
    return {"payload": pl, "score": (1.0 - i * 0.01) if score is None else score}


class Fake:
    """A corpus of 3 documents × 2 sections × 3 children; identifier chunk
    d3-ch9 contains 'RAPO' and is unreachable by dense search."""
    def __init__(self, sparse_fail=False):
        self.calls = []
        self.sparse_fail = sparse_fail

    def dense(self, kind, top_k, extra=None):
        self.calls.append(("dense", kind, top_k, dict(extra or {})))
        if kind == DOC:
            return [_row(DOC, i, d) for i, d in enumerate(("d1", "d2", "d3"))][:top_k]
        if kind == SEC:
            return [_row(SEC, i, d, parent=f"{d}-p{j}") for i, (d, j) in enumerate([("d1", 0), ("d1", 1), ("d2", 0), ("d3", 0)])][:top_k]
        if kind == CARD:
            return [{"payload": {"corpus_id": "c1", "doc_ids": ["d2", "d1"], "summary_id": "card1", "text": "card"}, "score": 0.9}][:top_k]
        if kind == CHILD and extra and extra.get("parent_id"):
            d, p = extra["doc_id"], extra["parent_id"]
            return [_row(CHILD, i, d, parent=p, chunk=f"{p}-k{i}") for i in range(3)][:top_k]
        if kind == CHILD:                                     # global dense children, best first
            rows = [_row(CHILD, 0, "d2", parent="d2-p0", chunk="d2-p0-k0"), _row(CHILD, 1, "d1", parent="d1-p1", chunk="d1-p1-k1"),
                    _row(CHILD, 2, "d3", parent="d3-p1", chunk="d3-deep", text="deep paragraph the summary never mentions"),
                    _row(CHILD, 3, "d1", parent="d1-p0", chunk="d1-p0-k0"), _row(CHILD, 4, "d2", parent="d2-p1", chunk="d2-noise", region_role="front_matter")]
            return rows[:top_k]
        return []

    def sparse(self, top_k):
        self.calls.append(("sparse", top_k))
        if self.sparse_fail:
            raise ConnectionError("no bm25 vector")
        return [_row(CHILD, 0, "d3", parent="d3-p1", chunk="d3-ch9", score=12.4, text="RAPO: reward-aware prompt optimization"),
                _row(CHILD, 1, "d2", parent="d2-p0", chunk="d2-p0-k0", score=9.1)][:top_k]


def _ctx(q="what does RAPO say about prompt optimization"):
    return ce.SearchContext(query=q, corpus_id="c1", collection="coll", qvec=(0.1, 0.2), sparse_query=((1, 2), (0.5, 0.5)), exact_terms=("RAPO",))


def test_every_candidate_carries_lane_provenance_and_multi_lane_chunks_fuse_once():
    fake = Fake()
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse,
                                 region_lookup=lambda ids: {"d2-noise": "front_matter"})
    assert res.union and all(c.arrivals for c in res.union)                              # 100 % provenance
    ids = [c.chunk_id for c in res.union]
    assert len(ids) == len(set(ids))                                                     # deduped by chunk id
    k0 = next(c for c in res.union if c.chunk_id == "d2-p0-k0")
    assert set(k0.arrivals) == {ce.LANE_A, ce.LANE_B, ce.LANE_C}                         # found by all three lanes
    assert k0.hierarchy_rank is not None and k0.dense_rank == 0 and k0.sparse_rank == 1
    single = next(c for c in res.union if c.chunk_id == "d3-deep")
    assert single.arrivals == [ce.LANE_B] and k0.fused_score > single.fused_score      # agreement ranks above single-lane
    assert res.union[0].chunk_id == "d2-p0-k0" and res.union[-1].chunk_id == "d2-noise"  # noisy region sinks, never deleted
    assert res.trace["funnel_lanes"].keys() == {"hierarchical", "global_dense_child", "global_sparse_child"}
    assert res.trace["funnel_union"] == [c.chunk_id for c in res.union] and res.trace["plan"] == "chat-retrieval-v2"
    assert res.trace["multi_lane"] >= 1 and res.degraded == []
    # exactly ONE sparse search and ONE global dense child search per turn (§3.21 #1)
    assert sum(1 for c in fake.calls if c[0] == "sparse") == 1
    assert sum(1 for c in fake.calls if c[0] == "dense" and c[1] == CHILD and not c[3]) == 1


def test_exact_term_chunk_reaches_the_union_through_the_sparse_lane_only():
    fake = Fake()
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse)
    rapo = next(c for c in res.union if c.chunk_id == "d3-ch9")
    assert rapo.arrivals == [ce.LANE_C] and rapo.sparse_rank == 0 and rapo.sparse_score == 12.4
    assert "d3-ch9" in res.trace["funnel_lanes"]["global_sparse_child"] and "d3-ch9" not in res.trace["funnel_lanes"]["global_dense_child"]


def test_hidden_paragraph_reaches_the_union_without_its_document_winning_routing():
    fake = Fake()
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(hierarchy_max_documents=1), dense_search=fake.dense, sparse_search=fake.sparse)
    assert [d.doc_id for d in res.selected_documents] == ["d1"] or len(res.selected_documents) == 1
    deep = next(c for c in res.union if c.chunk_id == "d3-deep")
    assert ce.LANE_B in deep.arrivals and deep.document_rank is None                   # first-class evidence, not a rescue
    assert all(c.doc_id == res.selected_documents[0].doc_id for c in res.lane_a)         # lane A only deepens winning documents


def test_sparse_outage_degrades_the_lane_and_never_scans_postgres():
    fake = Fake(sparse_fail=True)
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse)
    assert res.lane_c == [] and res.degraded and res.degraded[0]["component"] == "sparse_lane"
    assert "ConnectionError" in res.degraded[0]["reason"]
    assert res.lane_a and res.lane_b and res.union                                       # dense lanes intact
    assert res.trace["degraded"] == res.degraded and res.trace["lane_sizes"]["global_sparse_child"] == 0


def test_merged_cap_and_lane_switches():
    fake = Fake()
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(merged_candidate_max=3), dense_search=fake.dense, sparse_search=fake.sparse)
    assert len(res.union) == 3 and len(res.union_ids_uncapped) > 3
    assert res.trace["funnel_union"] == res.union_ids_uncapped                           # the funnel sees the pre-cap union
    fake2 = Fake()
    res2 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lanes=(ce.LANE_B, ce.LANE_C)), dense_search=fake2.dense, sparse_search=fake2.sparse)
    assert res2.lane_a == [] and res2.selected_documents == [] and res2.lane_b and res2.lane_c
    assert not any(c[1] == DOC for c in fake2.calls if c[0] == "dense")                  # lane A off = no document routing searches


def test_budget_shapes_on_the_resolved_request():
    b = ce.CandidateBudget()
    depth = ce.shape_budget("List all the domains and subdomains of CySA+", b)
    assert depth.hierarchy_max_sections_per_document == 8 and depth.neighbor_expansion == 1 and depth.synthesis_max >= 28 and depth.rerank_max >= 28
    meta = ce.shape_budget("who wrote this book?", b)
    assert meta.demote_noisy_regions is False and meta.neighbor_expansion == 0
    assert ce.shape_budget("what is a chroma keyer?", b) == b
    assert b.to_dict()["lanes"] == list(ce.LANES) and b.rerank_max == 20 and b.synthesis_max == 15


def test_selection_reranks_a_bounded_prefix_in_fusion_order_and_expands_neighbours_after():
    fake = Fake()
    budget = ce.CandidateBudget(rerank_max=4, synthesis_max=3, neighbor_expansion=1, neighbor_expansion_max=2)
    res = ce.retrieve_candidates(_ctx(), budget, dense_search=fake.dense, sparse_search=fake.sparse)
    seen = {}

    def rerank(q, rows):
        seen["n"] = len(rows); seen["q"] = q
        return [dict(r, rerank_score=float(i)) for i, r in enumerate(reversed(rows))]     # reverse the prefix

    def neighbours(want, distance):
        return [{"chunk_id": "nbr-1", "doc_id": want[0]["doc_id"], "parent_id": "p", "text": "adjacent"},
                {"chunk_id": want[0]["chunk_id"], "doc_id": want[0]["doc_id"]}]            # duplicate ignored

    final, tr = ce.select_evidence(res, budget, rerank_children=rerank, neighbor_lookup=neighbours)
    assert seen["n"] == 4 and seen["q"] == res.context.query
    assert tr["pre_g3_order"] == [c.chunk_id for c in res.union[:4]] and tr["post_g3_order"] == list(reversed(tr["pre_g3_order"]))
    assert [c.chunk_id for c in final[:3]] == tr["post_g3_order"][:3] and all(c.rerank_score is not None for c in final[:3])
    assert final[-1].chunk_id == "nbr-1" and final[-1].is_neighbor and final[-1].arrivals == [ce.ARRIVAL_NEIGHBOR] and tr["neighbors_added"] == 1
    # degraded reranker (None) → fusion order, same prefix
    final2, tr2 = ce.select_evidence(res, ce.CandidateBudget(rerank_max=4, synthesis_max=3), rerank_children=None)
    assert [c.chunk_id for c in final2] == tr2["pre_g3_order"][:3] and tr2["g3_scores"] == {}
    # a reranker that drops or adds a candidate is a contract violation
    with pytest.raises(AssertionError):
        ce.select_evidence(res, budget, rerank_children=lambda q, rows: rows[:-1])


def test_lane_c_searches_exact_terms_alone_and_strips_function_words_otherwise():
    toks, rule = ce.sparse_query_for("UPA animation studio history style", ["UPA"])
    assert toks == ["upa"] and rule == "exact_terms"                      # measured: the expansion buried the identifier
    toks, rule = ce.sparse_query_for('What does the book say about "RAPO" and "TS410"?', ["RAPO", "TS410"])
    assert toks == ["rapo", "ts410"] and rule == "exact_terms"
    toks, rule = ce.sparse_query_for("what does the book say about making your own chroma keyer", [])
    assert toks == ["book", "say", "making", "chroma", "keyer"] and rule == "topical"   # only function words go; the compiler owns discourse
    toks, rule = ce.sparse_query_for("the of and", None)
    assert toks == ["the", "of", "and"] and rule == "raw"                 # never an empty lane when the text is all function words
    vec, rule = ce.sparse_vector_for("sound editing in cinema", [])
    assert rule == "topical" and vec is not None and len(vec[0]) == 3 and all(v == 1.0 for v in vec[1])
    assert ce.sparse_vector_for("", []) == (None, "raw")

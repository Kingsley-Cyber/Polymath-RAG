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
    assert b.to_dict()["lanes"] == list(ce.LANES) and b.rerank_max == 24 and b.synthesis_max == 15


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
    # P1.c: composition orders by the judge's SCORE (sigmoid + bounded agreement), not by the order the client
    # returned — this fake hands back ascending scores, so the top of the final set is the highest-scored prefix items
    by_score = sorted(tr["post_g3_order"], key=lambda cid: -tr["g3_scores"][cid])
    assert [c.chunk_id for c in final[:3]] == by_score[:3] and all(c.rerank_score is not None for c in final[:3])
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


def _subq(qid, text, weight=1.0, vec=(0.9, 0.1), sparse=((7,), (1.0,))):
    return ce.SubQuery(query_id=qid, qtype="MECHANISM", text=text, weight=weight, qvec=vec, sparse_query=sparse)


class FakeMulti(Fake):
    """Vector-aware: the primary vector sees the base corpus; a subquery vector sees its own children."""
    def dense(self, kind, top_k, extra=None, qvec=None):
        if qvec is not None:                                   # subquery vector: logged once here, never delegated
            self.calls.append(("dense", kind, top_k, dict(extra or {}), qvec))
            if kind == CHILD and not extra:
                tag = "s1" if qvec == (0.9, 0.1) else "s2"
                return [_row(CHILD, 0, "d3", parent="d3-p1", chunk=f"{tag}-hit0"), _row(CHILD, 1, "d3", parent="d3-p1", chunk=f"{tag}-hit1"),
                        _row(CHILD, 2, "d2", parent="d2-p0", chunk="d2-p0-k0")][:top_k]
            return []
        return super().dense(kind, top_k, extra)              # primary: the base fake logs it

    def sparse(self, top_k, sparse_query=None):
        self.calls.append(("sparse", top_k, sparse_query))
        if sparse_query == ((7,), (1.0,)):
            return [_row(CHILD, 0, "d3", parent="d3-p1", chunk="s1-hit0", score=5.0)][:top_k]
        return super().sparse(top_k)


def test_subqueries_run_lanes_b_and_c_only_with_per_query_provenance():
    fake = FakeMulti()
    subs = [_subq("q1", "mechanism of chroma keying"), _subq("q2", "keyer hardware", vec=(0.2, 0.8), sparse=((8,), (1.0,)))]
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse, subqueries=subs)
    sub_calls = [c for c in fake.calls if c[0] == "dense" and len(c) > 4 and c[4] is not None]
    assert sub_calls and all(c[1] == CHILD and not c[3] for c in sub_calls)         # no doc/section routing, no deepening for subqueries
    assert sum(1 for c in fake.calls if c[0] == "dense" and c[1] == DOC) == 1        # lane A once, on the primary
    hit = next(c for c in res.union if c.chunk_id == "s1-hit0")
    assert hit.query_ids == ["q1"] and set(hit.arrivals) == {ce.LANE_B, ce.LANE_C} and "q1" in hit.query_scores
    both = next(c for c in res.union if c.chunk_id == "d2-p0-k0")
    assert {"q0", "q1", "q2"} <= set(both.query_ids)                                  # found by the primary and both subqueries
    asp = res.trace["aspects"]
    assert set(asp) == {"q0", "q1", "q2"} and asp["q1"]["lanes"][ce.LANE_B] == 3 and asp["q1"]["lanes"][ce.LANE_C] == 1 and asp["q1"]["union"] >= 3
    assert res.trace["subqueries"] == 2 and res.trace["second_pass"] is None


def test_fusion_is_normalised_no_document_stacks_a_subquery_vote_and_redundancy_is_bounded():
    fake = FakeMulti()
    subs = [_subq("q1", "a"), _subq("q2", "b", vec=(0.2, 0.8), sparse=((8,), (1.0,))), _subq("q3", "c", vec=(0.9, 0.1))]   # q3 duplicates q1
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse, subqueries=subs)
    by = {c.chunk_id: c for c in res.union}
    # per (subquery, document): exactly one chunk keeps the full contribution, the rest are halved
    for qid in ("q1", "q2", "q3"):
        full = [c for c in res.union if qid in c.query_scores and c.doc_id == "d3"]
        scores = sorted((c.query_scores[qid] for c in full), reverse=True)
        assert len(scores) >= 2 and scores[1] <= scores[0]                             # d3 has two hits under each subquery
    # redundancy bound: a chunk hit by primary + 3 subqueries scores at most 2× its best single contribution
    k0 = by["d2-p0-k0"]
    assert k0.fused_score <= 2 * max(k0.query_scores.values()) + 1e-9
    assert k0.fused_score > max(k0.query_scores.values())                              # agreement still counts, boundedly
    # a single strong primary hit is not beaten by a weak chunk found only by three redundant subqueries
    s1 = by["s1-hit1"]                                                                 # subquery-only, rank 1 in q1 and q3
    assert k0.fused_score > s1.fused_score


def test_second_pass_runs_once_for_the_first_empty_aspect_and_weak_aspects_are_flagged():
    class Empty(FakeMulti):
        def dense(self, kind, top_k, extra=None, qvec=None):
            if qvec == (0.5, 0.5):
                self.calls.append(("dense", kind, top_k, dict(extra or {}), qvec))
                return [_row(CHILD, 0, "d1", parent="d1-p0", chunk="late-hit")] if top_k >= 40 else []   # only the doubled K finds it
            return super().dense(kind, top_k, extra, qvec=qvec)

        def sparse(self, top_k, sparse_query=None):
            if sparse_query == ((9,), (1.0,)):
                return []
            return super().sparse(top_k, sparse_query=sparse_query)
    fake = Empty()
    empty = ce.SubQuery(query_id="q1", qtype="CAUSAL", text="nothing", weight=1.0, qvec=(0.5, 0.5), sparse_query=((9,), (1.0,)))
    empty2 = ce.SubQuery(query_id="q2", qtype="EXAMPLE", text="nothing either", weight=1.0, qvec=(0.5, 0.5), sparse_query=((9,), (1.0,)))
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(subquery_dense_k=20, second_pass_factor=2), dense_search=fake.dense, sparse_search=fake.sparse,
                                 subqueries=[empty, empty2])
    assert res.trace["second_pass"] == {"query_id": "q1", "before": 0, "after": 1}     # one pass, the first empty aspect only
    assert res.trace["aspects"]["q1"].get("second_pass") is True and res.trace["aspects"]["q2"].get("second_pass") is None
    doubled = [c for c in fake.calls if c[0] == "dense" and len(c) > 4 and c[4] == (0.5, 0.5) and c[2] == 40]
    assert len(doubled) == 1
    final, tr = ce.select_evidence(res, ce.CandidateBudget(rerank_max=6, synthesis_max=4))
    assert "q2" in tr["weak_aspects"] and tr["aspect_final"]["q0"] > 0
    assert set(tr["aspect_final"]) == {"q0", "q1", "q2"}


def test_aspect_seats_reach_the_judge_and_the_final_set_or_the_aspect_is_flagged_with_a_reason():
    fake = FakeMulti()
    subs = [_subq("q1", "a"), _subq("q2", "b", vec=(0.2, 0.8), sparse=((8,), (1.0,)))]
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse, subqueries=subs)
    # a short prefix of primary hits; each subquery still gets its 3 judged seats, and with synthesis_max 3 the
    # primary's 2.0-scored chunks fill the final set so q1 (relevant at 0.62 but outranked) needs the aspect seat
    b = ce.CandidateBudget(rerank_max=8, synthesis_max=3, aspect_prefix_seats=3, aspect_weak_floor=0.5)
    seen = {}

    def judge(q, rows):
        seen["n"] = len(rows)
        # every q2 candidate judged irrelevant (its own s2-* chunks and the shared d2-p0-k0), everything else relevant
        bad = {"s2-hit0", "s2-hit1", "d2-p0-k0", "d3-ch9"}                 # = every candidate q2 can reach in the fake
        # q1's own chunks are relevant (logit 0.5 → 0.62) but outranked by the primary's 2.0s: the seat must bring one in
        scored = [dict(r, rerank_score=(-3.0 if r["chunk_id"] in bad else 0.5 if r["chunk_id"].startswith("s1-") else 2.0 - 0.01 * i))
                  for i, r in enumerate(rows)]
        return sorted(scored, key=lambda r: -r["rerank_score"])          # the real reranker returns judge order
    final, tr = ce.select_evidence(res, b, rerank_children=judge)
    assert seen["n"] >= 8 + 2 and tr["aspect_prefix"]["q1"] >= 3 and tr["aspect_prefix"]["q2"] >= 3     # prefix grew for the aspects
    assert "q2" in tr["weak_aspects"] and tr["weak_reasons"]["q2"] == "below_floor"                    # judged and found wanting → flagged
    assert "q1" not in tr["weak_aspects"] and tr["aspect_final"]["q1"] >= 1                            # relevant aspect seated
    assert len(final) == 3 and any(s["query_id"] == "q1" and s["displaced"] for s in tr["aspect_seated"])   # seated by displacing a primary-only item
    assert any(c.chunk_id.startswith("s1-") for c in final)
    assert all(d["query_ids"] for d in tr["final_detail"]) and len(tr["final_detail"]) == 3
    # degraded judge: no floor judgement, seats still reserved, weak only when nothing was retrieved
    final2, tr2 = ce.select_evidence(res, b, rerank_children=None)
    assert tr2["weak_reasons"] == {} and tr2["aspect_prefix"]["q2"] >= 3 and len(final2) == 3
    # an aspect with no candidates at all is weak with reason no_candidates
    empty = ce.SubQuery(query_id="q9", qtype="CAUSAL", text="none", weight=1.0, qvec=(0.5, 0.5), sparse_query=None)
    fake3 = FakeMulti()
    res3 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(second_pass_factor=1), dense_search=lambda k, n, e=None, qvec=None: ([] if qvec == (0.5, 0.5) else fake3.dense(k, n, e, qvec=qvec)), sparse_search=fake3.sparse, subqueries=[empty])
    _, tr3 = ce.select_evidence(res3, ce.CandidateBudget(), rerank_children=None)
    assert tr3["weak_reasons"].get("q9") == "no_candidates" and "q9" in tr3["weak_aspects"]


def test_primary_is_flagged_weak_when_its_best_judged_candidate_is_below_the_floor():
    """R1 requalification of P1.b (the recorded residual: M #5 'FACE OFF'): a dimension named only by the
    PRIMARY query (compare side A after correction D) is flagged `below_floor` when the judge rejects every
    primary candidate — it is never shown as covered. Selection itself does not change: the flag is a receipt
    and a prompt line, not a filter."""
    fake = FakeMulti()
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse, subqueries=[_subq("q1", "a")])
    b = ce.CandidateBudget(rerank_max=8, synthesis_max=3, aspect_prefix_seats=3, aspect_weak_floor=0.5)

    def judge(q, rows):                                       # q1's own chunks relevant, every primary candidate rejected
        scored = [dict(r, rerank_score=(1.0 if r["chunk_id"].startswith("s1-") else -2.0)) for r in rows]
        return sorted(scored, key=lambda r: -r["rerank_score"])
    final, tr = ce.select_evidence(res, b, rerank_children=judge)
    assert tr["weak_reasons"].get("q0") == "below_floor" and "q0" in tr["weak_aspects"]
    assert tr["aspect_best"]["q0"] < 0.5 <= tr["aspect_best"]["q1"] and "q1" not in tr["weak_aspects"]
    assert len(final) == 3 and any(c.chunk_id.startswith("s1-") for c in final)
    assert [d["chunk_id"] for d in tr["final_detail"]] == [c.chunk_id for c in final]
    # a relevant primary is not flagged; a degraded judge (no scores) flags nobody on the floor
    _, tr2 = ce.select_evidence(res, b, rerank_children=lambda q, rows: sorted([dict(r, rerank_score=1.5) for r in rows], key=lambda r: -r["rerank_score"]))
    assert "q0" not in tr2["weak_aspects"] and "q0" not in tr2["weak_reasons"]
    _, tr3 = ce.select_evidence(res, b, rerank_children=None)
    assert tr3["weak_reasons"] == {}


def _cand(cid, doc, score, arrivals=(ce.LANE_B,), qids=("q0",)):
    return ce.CandidateEvidence(chunk_id=cid, doc_id=doc, parent_id=f"{doc}-p", source_name=doc, text=cid,
                                arrivals=list(arrivals), query_ids=list(qids), rerank_score=score)


def test_composer_slots_relevance_then_diversity_then_sparse_then_aspects():
    # judge order: ten d1 chunks (logit 6.0 … 5.1), two d2, two d3, a lane-C winner (d4, accepted), an aspect-only
    # chunk (d5, q2, accepted) and a rejected d1 chunk. Diversity's 4 seats go to d2/d3, so the sparse and aspect
    # winners need their own slots; the rejected chunk is left to the fill step.
    judged = [_cand(f"d1-{i}", "d1", 6.0 - i * 0.1) for i in range(10)]
    judged += [_cand("d2-a", "d2", 4.0), _cand("d2-b", "d2", 3.9), _cand("d3-a", "d3", 3.5), _cand("d3-b", "d3", 3.45),
               _cand("sp-1", "d4", 0.8, arrivals=(ce.LANE_C,)), _cand("asp-q2", "d5", 0.6, qids=("q2",)), _cand("d1-y", "d1", -3.0)]
    b = ce.CandidateBudget(synthesis_max=15, compose_relevance_slots=8, compose_diversity_slots=4, compose_doc_soft_max=3,
                           compose_sparse_slots=3, compose_aspect_slots=3)
    final, tr = ce.compose_evidence(judged, b)
    ids = [c.chunk_id for c in final]
    assert ids[:8] == [f"d1-{i}" for i in range(8)]                                    # pure relevance first, untouched
    assert tr["slots"] == {"relevance": 8, "diversity": 4, "sparse": 1, "aspect": 1, "fill": 1}
    assert {"d2-a", "d2-b", "d3-a", "d3-b"} <= set(ids)                                 # diversity seats other documents
    assert "sp-1" in ids and "asp-q2" in ids and tr["aspect_seats"][0]["query_id"] == "q2"
    assert "d1-y" not in ids and len(ids) == len(set(ids)) == 15                        # rejected chunk never promoted; cap held
    assert tr["doc_counts"]["d1"] == 9 and tr["doc_share_top"] == 0.6 and tr["dominance"] is False
    # a weak aspect is never seated; slots 2–4 never take a judge-rejected chunk even with room to spare
    final2, tr2 = ce.compose_evidence(judged, b, weak_aspects={"q2"})
    # the weak aspect gets no ASPECT seat (aspect slot 0, no seat receipt); its chunk may still arrive through the fill
    # step in judge order once the dominance guard holds d1 at its share cap — that is fill, not coverage
    assert tr2["aspect_seats"] == [] and tr2["slots"]["aspect"] == 0 and tr2["slots"]["fill"] == 2
    small = [_cand("a", "d1", 3.0), _cand("rej", "d2", -2.0), _cand("rej-sp", "d3", -1.5, arrivals=(ce.LANE_C,))]
    final3, tr3 = ce.compose_evidence(small, ce.CandidateBudget(synthesis_max=15, compose_relevance_slots=1))
    assert [c.chunk_id for c in final3] == ["a", "rej-sp", "rej"] and tr3["slots"]["diversity"] == 0 and tr3["slots"]["sparse"] == 0 and tr3["slots"]["fill"] == 2   # fill = judge order


def test_composer_flags_dominance_only_when_three_documents_are_close():
    judged = [_cand(f"d1-{i}", "d1", 2.0) for i in range(12)] + [_cand("d2-a", "d2", 1.95), _cand("d3-a", "d3", 1.9)]
    final, tr = ce.compose_evidence(judged, ce.CandidateBudget(synthesis_max=15))
    assert tr["docs_within_gap"] >= 3
    assert "d2-a" in [c.chunk_id for c in final] and "d3-a" in [c.chunk_id for c in final]
    assert tr["doc_share_top"] <= 0.6 + 1e-9 or tr["dominance"] is True                # the flag is honest either way
    judged2 = [_cand(f"d1-{i}", "d1", 5.0) for i in range(12)] + [_cand("d2-a", "d2", -4.0)]
    final2, tr2 = ce.compose_evidence(judged2, ce.CandidateBudget(synthesis_max=15))
    assert tr2["docs_within_gap"] == 1 and tr2["dominance"] is False and sum(1 for c in final2 if c.doc_id == "d1") == 12   # gap rule: one document may keep the set


def test_agreement_bonus_never_passes_a_clearly_higher_judge_score():
    single = _cand("s", "d1", 2.0)                                                       # sigmoid 0.88
    triple = _cand("t", "d2", 1.9, arrivals=(ce.LANE_A, ce.LANE_B, ce.LANE_C))           # sigmoid 0.87 + 0.04 bonus → passes a near-tie
    far = _cand("f", "d3", 0.5, arrivals=(ce.LANE_A, ce.LANE_B, ce.LANE_C))              # sigmoid 0.62 + 0.04 → never passes 0.88
    b = ce.CandidateBudget()
    assert ce.judged_score(triple, b) > ce.judged_score(single, b) > ce.judged_score(far, b)
    final, _ = ce.compose_evidence([single, triple, far], b)
    assert [c.chunk_id for c in final][:2] == ["t", "s"]
    a, c2 = _cand("a", "d1", None), _cand("c", "d2", None, arrivals=(ce.LANE_A, ce.LANE_B))
    assert ce.judged_score(c2, b) - ce.judged_score(a, b) <= b.compose_agreement_cap    # degraded judge: bonus stays bounded


def test_select_evidence_composes_and_receipts_the_composition():
    fake = Fake()
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse)
    final, tr = ce.select_evidence(res, ce.CandidateBudget(rerank_max=8, synthesis_max=5),
                                   rerank_children=lambda q, rows: sorted([dict(r, rerank_score=1.0 - i * 0.1) for i, r in enumerate(rows)], key=lambda r: -r["rerank_score"]))
    assert len(final) <= 5 and tr["composition"]["slots"]["relevance"] == 5 and len(tr["final_detail"]) == len(final)
    assert all(d["arrivals"] and d["chunk_id"] for d in tr["final_detail"]) and "doc_share_top" in tr["composition"]


def test_fill_step_holds_the_top_document_at_the_share_cap_when_three_documents_are_close():
    # 12 near-equal d1 chunks + 3 close d2 + 3 close d3 (all within 0.1 of the top): relevance takes 8 d1, diversity seats
    # d2/d3 (4), then FILL must not hand the remaining seats back to d1 beyond 60 % of the cap (9 of 15)
    judged = [_cand(f"d1-{i}", "d1", 2.0 - 0.001 * i) for i in range(12)]
    judged += [_cand(f"d2-{i}", "d2", 1.98 - 0.001 * i) for i in range(3)] + [_cand(f"d3-{i}", "d3", 1.97 - 0.001 * i) for i in range(3)]
    final, tr = ce.compose_evidence(judged, ce.CandidateBudget(synthesis_max=15))
    assert tr["docs_within_gap"] >= 3 and len(final) == 15
    assert tr["doc_counts"]["d1"] == 9 and tr["doc_share_top"] <= 0.6 + 1e-9 and tr["dominance"] is False
    assert tr["doc_counts"]["d2"] == 3 and tr["doc_counts"]["d3"] == 3
    # when the other documents run out, the cap lifts so seats are never wasted
    judged2 = [_cand(f"d1-{i}", "d1", 2.0 - 0.001 * i) for i in range(14)] + [_cand("d2-0", "d2", 1.99), _cand("d3-0", "d3", 1.98)]
    final2, tr2 = ce.compose_evidence(judged2, ce.CandidateBudget(synthesis_max=15))
    assert len(final2) == 15 and tr2["doc_counts"]["d1"] == 13 and tr2["dominance"] is True     # honest flag, full set


def test_dominance_is_avoidable_only_when_another_close_document_was_left_out():
    # B #14 shape: the top document holds 12 confident chunks, two other documents within the gap hold 3 in total and all
    # three are seated — the share is 0.8 (literal dominance) but nothing better was available: NOT avoidable
    judged = [_cand(f"d1-{i}", "d1", 6.0 - 0.01 * i) for i in range(12)] + [_cand("d2-a", "d2", 5.95), _cand("d2-b", "d2", 5.9), _cand("d3-a", "d3", 5.85)]
    final, tr = ce.compose_evidence(judged, ce.CandidateBudget(synthesis_max=15))
    assert len(final) == 15 and {"d2-a", "d2-b", "d3-a"} <= {c.chunk_id for c in final}
    assert tr["dominance"] is True and tr["dominance_avoidable"] is False
    # same top document, but the other documents offer more accepted chunks than the composer seated: avoidable — and the
    # guard prevents it (cap 9 of 15 for d1, the rest go to d2/d3)
    judged2 = [_cand(f"d1-{i}", "d1", 6.0 - 0.01 * i) for i in range(12)] + [_cand(f"d2-{i}", "d2", 5.9 - 0.01 * i) for i in range(4)] + [_cand(f"d3-{i}", "d3", 5.8 - 0.01 * i) for i in range(4)]
    final2, tr2 = ce.compose_evidence(judged2, ce.CandidateBudget(synthesis_max=15))
    assert tr2["doc_counts"]["d1"] == 9 and tr2["dominance"] is False and tr2["dominance_avoidable"] is False
    # the sparse and aspect slots respect the cap too: nine relevance seats already put d1 at the cap (9 of 15), so its
    # lane-C winner and its aspect chunk are refused while d2/d3 (within the gap, accepted) take the remaining seats
    judged3 = [_cand(f"d1-{i}", "d1", 6.0 - 0.01 * i) for i in range(9)] + [_cand("d1-sp", "d1", 5.0, arrivals=(ce.LANE_C,)), _cand("d1-q1", "d1", 4.9, qids=("q1",))] \
              + [_cand(f"d2-{i}", "d2", 5.5 - 0.01 * i) for i in range(4)] + [_cand(f"d3-{i}", "d3", 5.4 - 0.01 * i) for i in range(4)]
    final3, tr3 = ce.compose_evidence(judged3, ce.CandidateBudget(synthesis_max=15, compose_relevance_slots=9))
    ids3 = {c.chunk_id for c in final3}
    assert tr3["doc_counts"]["d1"] == 9 and "d1-sp" not in ids3 and "d1-q1" not in ids3 and tr3["slots"]["sparse"] == 0 and tr3["aspect_seats"] == []
    assert len(final3) == 15 and tr3["dominance"] is False and tr3["dominance_avoidable"] is False


# ---------------- P1.d CONCURRENCY-DEADLINES-V1: concurrent lanes, one wall-clock budget, dropped lanes receipted ----------------

import concurrent.futures as _cf  # noqa: E402
import threading as _th  # noqa: E402
import time as _time  # noqa: E402


class Slow(Fake):
    """The base fake with sleeps: `per_call` on every call, plus `sleep` on the lane named by `slow`
    ("child" | "sparse" | "doc" | "section" | "card" | "deep"). Counts in-flight calls to prove overlap."""
    def __init__(self, per_call=0.0, slow=None, sleep=0.0):
        super().__init__()
        self.per_call, self.slow, self.sleep = per_call, slow, sleep
        self._lock, self.inflight, self.max_inflight = _th.Lock(), 0, 0

    def _enter(self):
        with self._lock:
            self.inflight += 1; self.max_inflight = max(self.max_inflight, self.inflight)

    def _exit(self):
        with self._lock:
            self.inflight -= 1

    @staticmethod
    def _lane(kind, extra):
        if kind == CHILD:
            return "deep" if extra and extra.get("parent_id") else "child"
        return {DOC: "doc", SEC: "section", CARD: "card"}.get(kind, kind)

    def dense(self, kind, top_k, extra=None):
        self._enter()
        try:
            _time.sleep(self.per_call + (self.sleep if self._lane(kind, extra) == self.slow else 0.0))
            return super().dense(kind, top_k, extra)
        finally:
            self._exit()

    def sparse(self, top_k):
        self._enter()
        try:
            _time.sleep(self.per_call + (self.sleep if self.slow == "sparse" else 0.0))
            return super().sparse(top_k)
        finally:
            self._exit()


class SlowMulti(FakeMulti):
    """Subquery q1's lanes sleep (`slow_lanes` ⊆ {"dense", "sparse"}); everything else answers at once."""
    def __init__(self, slow_lanes=("dense",), sleep=1.5):
        super().__init__(); self.slow_lanes, self.sleep = set(slow_lanes), sleep

    def dense(self, kind, top_k, extra=None, qvec=None):
        if qvec == (0.9, 0.1) and "dense" in self.slow_lanes:
            _time.sleep(self.sleep)
        return super().dense(kind, top_k, extra, qvec=qvec)

    def sparse(self, top_k, sparse_query=None):
        if sparse_query == ((7,), (1.0,)) and "sparse" in self.slow_lanes:
            _time.sleep(self.sleep)
        return super().sparse(top_k, sparse_query=sparse_query)


def test_primary_lanes_and_deepening_run_concurrently_wall_is_the_slowest_lane_not_the_sum():
    fake = Slow(per_call=0.2)
    t0 = _time.perf_counter()
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse)
    wall = _time.perf_counter() - t0
    calls = len(fake.calls)                                   # 5 primary lanes + one deepening per selected section
    assert calls >= 8 and res.union and res.degraded == []
    assert wall < 0.2 * 4, (wall, calls)                      # sequential = calls × 0.2 s; two concurrent waves ≈ 0.4 s
    assert fake.max_inflight >= 3                             # overlap observed, not inferred
    conc = res.trace["concurrency"]
    assert conc["contract"] == "concurrency-deadlines-v1" and conc["max_workers"] == 8 and conc["timed_out"] == [] and conc["prestarted"] == []
    t = res.trace["timings_ms"]
    assert t["lanes_wall"] < 0.2 * 3 * 1000 and t["core_wall"] >= t["lanes_wall"] and "union" in t and "hierarchical_children" in t
    assert all(k in t for k in ("global_dense_child", "global_sparse_child", "document_summary", "section_summary", "entity_card"))


def test_a_lane_past_its_deadline_is_dropped_receipted_by_name_and_the_turn_completes_on_the_other_lanes():
    # the sparse lane sleeps past the deadline → dropped and named; dense lanes intact; nobody waits for the late result
    fake = Slow(slow="sparse", sleep=1.5)
    t0 = _time.perf_counter()
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lane_deadline_s=0.3), dense_search=fake.dense, sparse_search=fake.sparse)
    wall = _time.perf_counter() - t0
    assert wall < 1.2, wall
    assert [d["component"] for d in res.degraded] == ["global_sparse_child_timeout"]
    assert "lane_deadline_s=0.3" in res.degraded[0]["reason"] and res.degraded[0]["effect"] and res.trace["degraded"] == res.degraded
    assert res.lane_c == [] and res.lane_a and res.lane_b and res.union
    assert res.trace["concurrency"]["timed_out"] == ["global_sparse_child"] and res.trace["lane_sizes"]["global_sparse_child"] == 0
    assert "global_sparse_child_timeout" in res.trace["aspects"]["q0"]["degraded"]
    # the deepening fan-out past the deadline: routing happened, lane A keeps nothing, B + C still answer
    fake2 = Slow(slow="deep", sleep=1.5)
    t0 = _time.perf_counter()
    res2 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lane_deadline_s=0.3), dense_search=fake2.dense, sparse_search=fake2.sparse)
    assert _time.perf_counter() - t0 < 1.2
    assert res2.lane_a == [] and res2.lane_b and res2.lane_c and res2.selected_sections and res2.union
    d = next(x for x in res2.degraded if x["component"] == "hierarchical_children_timeout")
    n = len(res2.selected_sections)
    assert d["effect"].startswith(f"{n} of {n} section deepenings dropped") and res2.trace["concurrency"]["timed_out"] == ["hierarchical_children"]
    # a ROUTING lane past the deadline: the deepening needs it, so routing waits for it up to the deadline; ONE core
    # budget means nothing is left for the fan-out — both drops are receipted, routing still ran on the lanes that
    # answered (documents selected), and B + C carry the turn within the budget
    fake3 = Slow(slow="doc", sleep=1.5)
    t0 = _time.perf_counter()
    res3 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lane_deadline_s=0.3), dense_search=fake3.dense, sparse_search=fake3.sparse)
    assert _time.perf_counter() - t0 < 1.2
    assert [d["component"] for d in res3.degraded] == ["document_summary_timeout", "hierarchical_children_timeout"]
    assert res3.trace["lane_sizes"]["document_summary"] == 0 and res3.selected_documents and res3.selected_sections
    assert res3.lane_a == [] and res3.lane_b and res3.lane_c and res3.union
    assert res3.trace["concurrency"]["timed_out"] == ["document_summary", "hierarchical_children"]
    # a subquery lane past the deadline: the aspect keeps its other lane; no second pass is spent on a lane that was not given time
    fake4 = SlowMulti(("dense",))
    t0 = _time.perf_counter()
    res4 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lane_deadline_s=0.3), dense_search=fake4.dense, sparse_search=fake4.sparse, subqueries=[_subq("q1", "a")])
    assert _time.perf_counter() - t0 < 1.2
    assert [d["component"] for d in res4.degraded] == ["sub_q1_dense_timeout"]
    asp = res4.trace["aspects"]["q1"]
    assert asp["lanes"] == {ce.LANE_B: 0, ce.LANE_C: 1} and asp["degraded"] == ["dense:timeout"] and res4.trace["second_pass"] is None
    hit = next(c for c in res4.union if c.chunk_id == "s1-hit0")
    assert hit.arrivals == [ce.LANE_C] and hit.query_ids == ["q1"]
    fake5 = SlowMulti(("dense", "sparse"))
    res5 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lane_deadline_s=0.3), dense_search=fake5.dense, sparse_search=fake5.sparse, subqueries=[_subq("q1", "a")])
    assert [d["component"] for d in res5.degraded] == ["sub_q1_dense_timeout", "sub_q1_sparse_timeout"]
    assert res5.trace["aspects"]["q1"]["degraded"] == ["dense:timeout", "sparse:timeout"] and res5.trace["second_pass"] is None
    _, tr5 = ce.select_evidence(res5, ce.CandidateBudget(), rerank_children=None)
    assert tr5["weak_reasons"].get("q1") == "no_candidates"


def test_fused_order_does_not_depend_on_completion_order():
    class Jitter(FakeMulti):
        """Completion order reversed relative to submission: later lanes answer first, subqueries last."""
        DELAY = {DOC: 0.12, SEC: 0.09, CARD: 0.03, CHILD: 0.06}

        def dense(self, kind, top_k, extra=None, qvec=None):
            _time.sleep(0.0 if (extra and extra.get("parent_id")) else (0.15 if qvec is not None else self.DELAY.get(kind, 0.0)))
            return super().dense(kind, top_k, extra, qvec=qvec)

    subs = [_subq("q1", "a"), _subq("q2", "b", vec=(0.2, 0.8), sparse=((8,), (1.0,)))]

    def run(fake, **kw):
        res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(**kw), dense_search=fake.dense, sparse_search=fake.sparse, subqueries=subs,
                                     region_lookup=lambda ids: {"d2-noise": "front_matter"})
        assert res.degraded == []
        tr = {k: v for k, v in res.trace.items() if k not in ("timings_ms", "budget", "concurrency")}
        return [c.to_row() for c in res.union], res.union_ids_uncapped, tr, [c.chunk_id for c in res.lane_a]

    ref = run(FakeMulti(), max_workers=1)          # a one-worker pool runs the lanes in submission order = the sequential engine
    assert ref[1] and ref[3]
    assert run(Jitter(), max_workers=8) == ref
    assert run(FakeMulti(), max_workers=8) == ref
    assert run(Jitter(), max_workers=3) == ref     # queueing behind a smaller pool changes nothing either


def test_prestarted_sparse_rows_or_futures_replace_the_lane_c_call():
    pre_rows = [_row(CHILD, 0, "d3", parent="d3-p1", chunk="pre-1", score=9.0)]
    fake = Fake()
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse, prestarted={"global_sparse_child": pre_rows})
    assert [c.chunk_id for c in res.lane_c] == ["pre-1"] and not any(c[0] == "sparse" for c in fake.calls)
    assert res.trace["concurrency"]["prestarted"] == ["global_sparse_child"] and res.degraded == [] and "global_sparse_child" in res.timings_ms
    # a Future resolves the same way (the route hands in the BM25 lane it started before the embedding)
    with _cf.ThreadPoolExecutor(max_workers=2) as pool:
        fut = pool.submit(lambda: pre_rows)
        fake2 = Fake()
        res2 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake2.dense, sparse_search=fake2.sparse, executor=pool,
                                      prestarted={"global_sparse_child": fut})
        assert [c.chunk_id for c in res2.lane_c] == ["pre-1"] and not any(c[0] == "sparse" for c in fake2.calls)
        assert pool.submit(lambda: 1).result(timeout=1) == 1  # a caller-owned pool is never shut down by the engine
    # a pre-started lane that fails degrades exactly like an in-engine sparse failure; one that never answers is dropped by name
    bad = _cf.Future(); bad.set_exception(ConnectionError("no bm25 vector"))
    res3 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=Fake().dense, sparse_search=Fake().sparse, prestarted={"global_sparse_child": bad})
    assert res3.degraded[0]["component"] == "sparse_lane" and "ConnectionError" in res3.degraded[0]["reason"] and res3.lane_c == [] and res3.lane_b
    never = _cf.Future()
    res4 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lane_deadline_s=0.2), dense_search=Fake().dense, sparse_search=Fake().sparse,
                                  prestarted={"global_sparse_child": never})
    assert [d["component"] for d in res4.degraded] == ["global_sparse_child_timeout"] and res4.lane_b and never.cancelled()
    # a pre-started subquery sparse lane is consumed by name; with lane C off, pre-started rows are ignored
    fake5 = FakeMulti()
    res5 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake5.dense, sparse_search=fake5.sparse, subqueries=[_subq("q1", "a")],
                                  prestarted={"sub_q1_sparse": [_row(CHILD, 0, "d3", parent="d3-p1", chunk="pre-q1", score=5.0)]})
    assert any(c.chunk_id == "pre-q1" and c.query_ids == ["q1"] and c.arrivals == [ce.LANE_C] for c in res5.union)
    assert not any(c[0] == "sparse" and len(c) > 2 and c[2] == ((7,), (1.0,)) for c in fake5.calls)     # q1's sparse query never searched
    assert res5.trace["concurrency"]["prestarted"] == ["sub_q1_sparse"]
    fake6 = Fake()
    res6 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lanes=(ce.LANE_A, ce.LANE_B)), dense_search=fake6.dense, sparse_search=fake6.sparse,
                                  prestarted={"global_sparse_child": pre_rows})
    assert res6.lane_c == [] and res6.trace["concurrency"]["prestarted"] == [] and not any(c[0] == "sparse" for c in fake6.calls)


def test_lane_exceptions_keep_the_sequential_semantics_and_per_call_pools_are_released():
    class Broken(Fake):
        def __init__(self, kind):
            super().__init__(); self.kind = kind

        def dense(self, kind, top_k, extra=None):
            if kind == self.kind and not extra:
                raise RuntimeError(f"{kind} down")
            return super().dense(kind, top_k, extra)

    for kind in (CHILD, DOC, SEC):                            # the core dense lanes still fail the turn (typed by the route)
        with pytest.raises(RuntimeError, match="down"):
            ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=Broken(kind).dense, sparse_search=Fake().sparse)
    res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=Broken(CARD).dense, sparse_search=Fake().sparse)
    assert res.trace["lane_sizes"]["entity_card"] == 0 and res.degraded == [] and res.union     # routing votes only: silent, as before
    # per-call pools are released even when a lane raises (no thread leak across turns)
    before = _th.active_count()
    for _ in range(3):
        with pytest.raises(RuntimeError):
            ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=Broken(CHILD).dense, sparse_search=Fake().sparse)
    deadline = _time.perf_counter() + 3.0
    while _th.active_count() > before and _time.perf_counter() < deadline:
        _time.sleep(0.02)
    assert _th.active_count() <= before + 1, (before, _th.active_count())
    assert ce.CandidateBudget().to_dict()["lane_deadline_s"] == 3.0 and ce.CandidateBudget().max_workers == 8

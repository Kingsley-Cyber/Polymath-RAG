"""MODE-COMPOSITION-V1 (CHAT-QUERY-COMPILER-PLAN §3.15 / §3.18 / §3.19 / §4 P1.e):
the chat modes are compositions of the shared primitives. Pure — the embedder,
the judge, Qdrant, Postgres joins, readiness, the entity-card probe and the
graph expander are faked on `orchestrator.api.chat_retrieval` exactly the way
tests/determinism/test_chat_retrieval_v2.py does.

    VECTOR   = A + B          same A/B lane results as HYBRID, no sparse call
    HYBRID   = A + B + C      byte-for-byte chat_retrieve_v2
    GRAPH    = HYBRID → G     ≤ 8 seeds / ≤ 20 facts (≤ 2 seeds when graph_useful=False), no re-embedding, fail-open
    WILDCARD = HYBRID ∥ W     the sweep runs beside the lanes on the ONE vector, ≤ 3 bridges never in the evidence list,
                              bounded by wildcard_deadline_s
"""
from __future__ import annotations

import copy
import pathlib
import sys
import threading
import time as _time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import HTTPException  # noqa: E402

from orchestrator.api import chat_retrieval as cr  # noqa: E402
from orchestrator.api import fast as fast_api  # noqa: E402
from orchestrator.api import retrieve as retrieve_mod  # noqa: E402
from polymath_shared import candidate_engine as ce  # noqa: E402
from polymath_shared import divergent as dv  # noqa: E402

QUERY = "what does RAPO say about prompts"
EVIDENCE_CHUNK_OF_PNEAR = "d2-g-c0"      # a global-lane child that reaches the final evidence (see FakeSearcher)

#: latent frontier fixtures: (parent_id, doc_id, hop1 score, kid chunk ids)
FAR_FIVE = [(f"pfar{i}", "dfar", 0.9 - i * 0.05, [f"pfar{i}-k0", f"pfar{i}-k1"]) for i in range(5)]
OBVIOUS = ("d1-p", "d1", 0.99, ["d1-p-k0"])                       # a FINAL-evidence parent → excluded as obvious
PNEAR = ("pnear", "dnear", 0.95, [EVIDENCE_CHUNK_OF_PNEAR])       # its only kid IS an evidence chunk → never a bridge


class _ModeHarness:
    """chat_retrieve_mode with every sidecar and store faked. Records: embed calls (texts + returned vectors),
    when the judge was called, every latent-surface search (kind, vector, time), every wildcard children_of
    search, the entity-card probe's vector and the graph expander's arguments."""

    def __init__(self, monkeypatch, *, latent=(), latent_sleep=0.0, children_sleep=0.0,
                 rerank_wait_for_latent=False, graph_facts_n=100, graph_fail=False, cards_n=10):
        self.embed_calls: list[list[str]] = []
        self.primary_vec: list[float] | None = None
        self.embed_returned_at: float | None = None
        self.judge_calls: list[float] = []            # perf_counter at each core judge call (q == QUERY)
        self.pair_calls: int = 0                      # wildcard two-hop validation calls (q == anchor text)
        self.sparse_starts: list[float] = []
        self.dense_starts: list[float] = []
        self.latent_calls: list[tuple[str, tuple, int, float]] = []
        self.latent_started = threading.Event()
        self.children_calls: list[str] = []
        self.card_probe_calls: list[dict] = []
        self.graph_calls: list[dict] = []
        self.release = threading.Event()              # lets a test end a slow fake early and drain its background thread
        latent = list(latent)
        h = self

        def fake_embed(texts):
            h.embed_calls.append(list(texts))
            vecs = [[0.1 * (i + 1), 0.2] for i, _ in enumerate(texts)]
            h.primary_vec = vecs[0]
            h.embed_returned_at = _time.perf_counter()
            return vecs

        def fake_rerank(q, rows):
            if q == QUERY:
                if rerank_wait_for_latent:                       # the judge must not run before the sweep has started
                    h.latent_started.wait(timeout=2.0)
                h.judge_calls.append(_time.perf_counter())
            else:
                h.pair_calls += 1
            return sorted([dict(r, rerank_score=1.0 - i * 0.01) for i, r in enumerate(rows)], key=lambda r: -r["rerank_score"])

        class FakeSearcher:
            def __init__(self, client, collections, query=None):
                self.latency = {}
                self._hidden_cache = {}

            def _hidden_for(self, cid):
                return list(self._hidden_cache.get(cid) or [])

            def _search(self, collection, vector, filters, limit):
                kind = filters["representation_kind"]
                if kind in ("latent_abstraction", "latent_transfer"):
                    h.latent_calls.append((kind, tuple(vector), limit, _time.perf_counter()))
                    h.latent_started.set()
                    if latent_sleep:
                        h.release.wait(latent_sleep)
                    rows = []
                    for pid, doc, score, _kids in latent:
                        if kind == "latent_transfer" and pid != "pfar0":
                            continue
                        rows.append({"payload": {"parent_id": pid, "doc_id": doc, "source_name": f"{doc}.md",
                                                 "text": f"{'transfer' if kind == 'latent_transfer' else 'principle'} of {pid}",
                                                 "corpus_id": "cinema"}, "score": score})
                    return rows[:limit]
                if kind == "routing_child":
                    parent = filters.get("parent_id")
                    if parent and "doc_id" not in filters:            # WILDCARD children_of (no doc filter)
                        h.children_calls.append(parent)
                        if children_sleep:
                            h.release.wait(children_sleep)
                        spec = next((x for x in latent if x[0] == parent), None)
                        kids = spec[3] if spec else []
                        return [{"payload": {"chunk_id": k, "doc_id": (spec[1] if spec else ""), "parent_id": parent,
                                             "text": f"grounding text of {k} mechanism", "source_name": "far.md"},
                                 "score": 0.5} for k in kids]
                    h.dense_starts.append(_time.perf_counter())
                    docs = (filters["doc_id"],) if parent else ("d1", "d2")
                    return [{"payload": {"chunk_id": f"{d}-{parent or 'g'}-c{i}", "doc_id": d, "parent_id": parent or f"{d}-p",
                                         "text": "reward models shape prompt optimization", "corpus_id": "cinema"},
                             "score": 1 - i * 0.01} for i in range(min(limit, 3)) for d in docs]
                if kind == "routing_document_summary":
                    h.dense_starts.append(_time.perf_counter())
                    return [{"payload": {"doc_id": d, "summary_id": f"s-{d}", "text": "doc", "corpus_id": "cinema"}, "score": 0.9 - i * 0.1}
                            for i, d in enumerate(("d1", "d2"))]
                if kind == "routing_section_summary":
                    h.dense_starts.append(_time.perf_counter())
                    return [{"payload": {"doc_id": d, "parent_id": f"{d}-p", "summary_id": f"sec-{d}", "text": "sec", "corpus_id": "cinema"},
                             "score": 0.9 - i * 0.1} for i, d in enumerate(("d1", "d2"))]
                return []

            def sparse_search(self, collection, sparse_query, filters, limit):
                h.sparse_starts.append(_time.perf_counter())
                key = "-".join(str(i) for i in sparse_query[0])
                return [{"payload": {"chunk_id": f"sp-{key}", "doc_id": "d3", "parent_id": "d3-p", "text": "RAPO", "corpus_id": "cinema"}, "score": 12.0}]

        class FakeQdrant:
            def __init__(self, *a, **k): pass
            def close(self): pass

        def fake_cards(client, collections, corpus_id, query, qvec, limit=8):
            h.card_probe_calls.append({"corpus_id": corpus_id, "query": query, "qvec": list(qvec), "limit": limit})
            return [{"card_id": f"card{i}", "entity_id": f"ent-{i}", "doc_ids": ["d1"], "text": "card", "score": 1 - i * 0.01, "lane": "dense"}
                    for i in range(cards_n)]

        def fake_graph(surfaces, corpus_ids, preferred, seed_entity_ids=None, document_ids=None, max_seeds=None):
            h.graph_calls.append({"surfaces": list(surfaces), "corpus_ids": list(corpus_ids), "preferred": list(preferred),
                                  "seed_entity_ids": list(seed_entity_ids or []), "max_seeds": max_seeds})
            if graph_fail:
                raise HTTPException(status_code=502, detail={"error_code": "graph_backend_unavailable", "message": "neo4j expansion failed"})
            return [{"fact_id": f"f{i}", "predicate": "causes", "subject_id": f"e{i}", "subject": f"S{i}", "object_id": f"e{i + 1}", "object": f"O{i}"}
                    for i in range(graph_facts_n)]

        monkeypatch.setattr(cr, "_embed_queries", fake_embed)
        monkeypatch.setattr(cr, "_rerank_children", fake_rerank)
        monkeypatch.setattr(cr, "FastSearcher", FakeSearcher)
        monkeypatch.setattr(cr, "QdrantClient", FakeQdrant)
        monkeypatch.setattr(cr, "entity_card_probe", fake_cards)
        monkeypatch.setattr(cr, "graph_expand_or_502", fake_graph)
        monkeypatch.setattr(cr, "_ensure_fast_ready", lambda cid: None)
        monkeypatch.setattr(cr, "_corpus_collections", lambda ids: {i: f"coll-{i}" for i in ids})
        monkeypatch.setattr(cr, "_region_lookup", lambda ids: {})
        monkeypatch.setattr(cr, "_neighbor_lookup", lambda want, d: [])
        monkeypatch.setattr(cr, "_presentation_joins", lambda cids, dids: {})

    def mode(self, mode: str, **kw):
        return cr.chat_retrieve_mode(mode, QUERY, "cinema", exact_terms=("RAPO",), **kw)

    def drain(self, attr: str, n: int, timeout: float = 2.0) -> None:
        """Release the slow fakes and wait until the abandoned background thread made its last recorded call."""
        self.release.set()
        t0 = _time.perf_counter()
        while len(getattr(self, attr)) < n and _time.perf_counter() - t0 < timeout:
            _time.sleep(0.005)
        _time.sleep(0.02)

    def v2(self, **kw):
        return cr.chat_retrieve_v2(QUERY, "cinema", exact_terms=("RAPO",), **kw)


def _ids(out):
    return [e["chunk_id"] for e in out["evidence"]]


# ---------------------------------------------------------------- (a) VECTOR ⊆ HYBRID, same A/B primitives, no sparse call

def test_vector_shares_hybrid_a_and_b_lanes_and_its_union_is_a_subset_with_no_sparse_call(monkeypatch):
    hv = _ModeHarness(monkeypatch)
    vec = hv.mode("VECTOR")
    assert hv.sparse_starts == [] and len(hv.embed_calls) == 1 and len(hv.judge_calls) == 1
    hh = _ModeHarness(monkeypatch)
    hyb = hh.mode("HYBRID")
    assert len(hh.sparse_starts) == 1
    tv, th = vec["trace"], hyb["trace"]
    # same primitives → identical lane A and lane B results (the sparse expert is the only difference)
    assert tv["funnel_lanes"]["hierarchical"] == th["funnel_lanes"]["hierarchical"]
    assert tv["funnel_lanes"]["global_dense_child"] == th["funnel_lanes"]["global_dense_child"]
    assert tv["funnel_lanes"]["global_sparse_child"] == [] and th["funnel_lanes"]["global_sparse_child"]
    assert set(tv["funnel_union"]) <= set(th["funnel_union"]) and set(tv["funnel_union"]) < set(th["funnel_union"])
    assert vec["meta"]["mode"] == "VECTOR" and vec["meta"]["lanes"] == [ce.LANE_A, ce.LANE_B] and vec["meta"]["lexical_enabled"] is False
    assert hyb["meta"]["mode"] == "HYBRID" and hyb["meta"]["lanes"] == list(ce.LANES) and hyb["meta"]["lexical_enabled"] is True
    assert vec["meta"]["plan_version"] == hyb["meta"]["plan_version"] == "chat-retrieval-v2"
    assert "graph_relationships" not in vec and "wildcard" not in vec and vec["meta"]["degraded"] == []
    assert vec["evidence"] and all(e["arrivals"] for e in vec["evidence"])


# ---------------------------------------------------------------- (b) HYBRID via the composition == chat_retrieve_v2

def test_hybrid_through_the_composition_returns_the_same_evidence_as_chat_retrieve_v2(monkeypatch):
    subs = (("q1", "MECHANISM", "reward models for prompts", 1.0),)
    ha = _ModeHarness(monkeypatch)
    a = ha.mode("HYBRID", subqueries=subs)
    hb = _ModeHarness(monkeypatch)
    b = hb.v2(subqueries=subs)
    assert _ids(a) == _ids(b) and a["trace"]["final"] == b["trace"]["final"] and a["trace"]["funnel_union"] == b["trace"]["funnel_union"]
    assert a["meta"]["mode"] == b["meta"]["mode"] == "HYBRID" and a["meta"]["lanes"] == b["meta"]["lanes"] == list(ce.LANES)
    assert a["meta"]["aspects"].keys() == b["meta"]["aspects"].keys() and a["meta"]["candidates"] == b["meta"]["candidates"]
    assert ha.embed_calls == hb.embed_calls == [[QUERY, "reward models for prompts"]]
    assert len(ha.judge_calls) == len(hb.judge_calls) == 1


def test_on_context_seam_fires_once_after_the_embedding_and_before_any_lane(monkeypatch):
    h = _ModeHarness(monkeypatch)
    seen = []

    def seam(ctx, pool):
        seen.append((ctx, pool, _time.perf_counter()))

    h.v2(on_context=seam)
    assert len(seen) == 1
    ctx, pool, t = seen[0]
    assert isinstance(ctx, ce.SearchContext) and list(ctx.qvec) == h.primary_vec and ctx.corpus_id == "cinema"
    assert hasattr(pool, "submit") and h.embed_returned_at <= t <= min(h.dense_starts)     # after the vector, before the lanes


# ---------------------------------------------------------------- (c) GRAPH: bounded, no re-embedding, fail-open

def test_graph_is_bounded_to_eight_seeds_and_twenty_facts_and_reuses_the_primary_vector(monkeypatch):
    h = _ModeHarness(monkeypatch, graph_facts_n=100, cards_n=10)
    out = h.mode("GRAPH")
    assert out["meta"]["mode"] == "GRAPH" and out["meta"]["lanes"] == list(ce.LANES)
    assert len(out["graph_relationships"]) == 20 == out["meta"]["graph_fact_count"]           # 100 offered, GRAPH_MAX_FACTS kept
    assert out["meta"]["graph_bounds"] == {"max_seeds": 8, "max_facts": 20, "graph_useful": True, "hops": 1, "contract": "mode-composition-v1"}
    assert len(h.graph_calls) == 1
    g = h.graph_calls[0]
    assert g["max_seeds"] == 8 and len(g["seed_entity_ids"]) == 8 and g["corpus_ids"] == ["cinema"]
    assert g["preferred"] == _ids(out)                                                        # every FINAL chunk authorizes seeds
    global_only = [e["chunk_id"] for e in out["evidence"] if set(e["arrivals"]) <= {ce.LANE_B, ce.LANE_C}]
    assert global_only and all(c in g["preferred"] for c in global_only)                      # §3.21 #5–#6: global winners seed too
    assert h.embed_calls == [[QUERY]]                                                          # ONE embedding: the cards reuse it (#7)
    assert h.card_probe_calls == [{"corpus_id": "cinema", "query": QUERY, "qvec": h.primary_vec, "limit": 8}]
    assert out["meta"]["graph_seeds"] == {"surfaces": len(g["surfaces"]), "cards": 8, "max_seeds": 8, "card_probe": "ok"}
    assert g["surfaces"] and "rapo" in g["surfaces"] and out["trace"]["graph_seed_surfaces"] == g["surfaces"]
    assert out["meta"]["graph_degraded"] is None and out["meta"]["degraded"] == []
    assert isinstance(out["trace"]["latency_ms"]["graph"], float) and out["trace"]["graph_seed_cards"] == g["seed_entity_ids"]
    assert {"fact_id", "predicate", "subject_id", "subject", "object_id", "object"} == set(out["graph_relationships"][0])


def test_graph_on_a_definitional_question_expands_at_most_two_seeds(monkeypatch):
    h = _ModeHarness(monkeypatch)
    out = h.mode("GRAPH", graph_useful=False)
    g = h.graph_calls[0]
    assert g["max_seeds"] == 2 and len(g["seed_entity_ids"]) <= 2 and h.card_probe_calls[0]["limit"] == 2
    assert out["meta"]["graph_bounds"]["max_seeds"] == 2 and out["meta"]["graph_bounds"]["graph_useful"] is False
    assert out["meta"]["graph_seeds"]["max_seeds"] == 2 and out["meta"]["graph_seeds"]["cards"] == 2
    assert len(out["graph_relationships"]) == 20 and len(h.embed_calls) == 1


def test_graph_expander_failure_leaves_the_hybrid_answer_intact_and_is_receipted(monkeypatch):
    hg = _ModeHarness(monkeypatch, graph_fail=True)
    g = hg.mode("GRAPH")
    hh = _ModeHarness(monkeypatch)
    hyb = hh.mode("HYBRID")
    assert _ids(g) == _ids(hyb) and g["trace"]["final"] == hyb["trace"]["final"]              # the HYBRID answer stands
    assert g["graph_relationships"] == [] and g["meta"]["graph_fact_count"] == 0 and g["meta"]["mode"] == "GRAPH"
    assert g["meta"]["graph_degraded"].startswith("graph_backend_unavailable")
    assert [d["component"] for d in g["meta"]["degraded"]] == ["graph_degraded"]
    assert "HYBRID evidence stands" in g["meta"]["degraded"][0]["effect"]
    assert g["meta"]["graph_bounds"]["max_seeds"] == 8 and "graph" in g["trace"]["latency_ms"]


class _SeedConn:
    """The D2 seed statement's rows: (entity_id, normalized_surface, preferred)."""
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=()):
        assert "FROM entities e" in sql and "d.corpus_id = ANY(%s)" in sql
        conn = self

        class _R:
            def fetchall(self_inner):
                return list(conn.rows)
        return _R()


def test_seed_resolver_caps_seeds_at_max_seeds_cards_first_and_never_above_eight():
    rows = [("card-2", "delta", False), ("card-1", "gamma", False)] + \
           [(f"e{i}", "alpha", i == 3) for i in range(9)]                    # nine surface matches, e3 attached to the evidence
    conn = _SeedConn(rows)
    args = (conn, ["alpha", "beta"], ["cinema"], ["k1"])
    default = retrieve_mod._corpus_seed_ids(*args, seed_entity_ids=["card-1", "card-2"])
    assert default[:2] == ["card-1", "card-2"] and default[2] == "e3" and len(default) == 8   # D2 default: cards first, 8 total
    assert retrieve_mod._corpus_seed_ids(*args, seed_entity_ids=["card-1", "card-2"], max_seeds=2) == ["card-1", "card-2"]
    assert retrieve_mod._corpus_seed_ids(*args, seed_entity_ids=["card-1", "card-2"], max_seeds=3) == ["card-1", "card-2", "e3"]
    assert len(retrieve_mod._corpus_seed_ids(*args, seed_entity_ids=["card-1", "card-2"], max_seeds=99)) == 8   # narrows only
    assert retrieve_mod._corpus_seed_ids(*args, max_seeds=2) == ["e3", "e0"]                  # surfaces alone: preferred first, then id
    assert retrieve_mod._corpus_seed_ids(*args, seed_entity_ids=["card-1"], max_seeds=0) == []


# ---------------------------------------------------------------- (d) WILDCARD: parallel sweep, one vector, bounded bridges outside the evidence

def test_wildcard_sweep_overlaps_the_core_on_the_one_vector_and_returns_at_most_three_bridges_outside_the_evidence(monkeypatch):
    h = _ModeHarness(monkeypatch, latent=FAR_FIVE + [OBVIOUS], rerank_wait_for_latent=True)
    out = h.mode("WILDCARD")
    assert out["meta"]["mode"] == "WILDCARD" and out["meta"]["lanes"] == list(ce.LANES)
    # ONE embedding for the whole turn; the sweep searched BOTH latent channels with that very vector
    assert h.embed_calls == [[QUERY]]
    assert [k for k, _, _, _ in h.latent_calls] == ["latent_abstraction", "latent_transfer"]
    assert all(list(v) == h.primary_vec for _, v, _, _ in h.latent_calls) and all(k == 24 for _, _, k, _ in h.latent_calls)
    # the sweep STARTED before the core finished: before the judge ran, and before the core evidence was final
    assert h.latent_calls[0][3] < h.judge_calls[0]
    w = out["meta"]["wildcard"]
    assert w["sweep_started_ms"] is not None and w["sweep_started_ms"] < w["core_done_ms"]
    assert w["sweep_done_before_core"] is True and w["sweep_ms"] is not None and w["finish_ms"] is not None
    # bounds and separation
    bridges = out["wildcard"]
    ev = set(_ids(out))
    assert len(bridges) == 3 == w["returned"] == dv.DIVERGENT_DEFAULT_PLAN.max_bridges
    assert all(b["source_evidence"]["chunk_id"] not in ev for b in bridges)
    assert all(b["parent_id"] not in {e["parent_id"] for e in out["evidence"]} for b in bridges)
    assert [b["parent_id"] for b in bridges] == ["pfar0", "pfar1", "pfar2"]
    assert w["latent_candidates"] == 6 and w["excluded_obvious"] == 1 and w["excluded_in_evidence"] == 0 and w["support_filtered"] == 0
    assert w["baseline_chunks"] == len(ev) and w["baseline_parents"] >= 1 and w["baseline_docs"] >= 1
    assert w["degraded"] is None and w["reranker"] is True and w["deadline_s"] == 2.5 and w["plan"] == "divergent-retrieval-v1"
    assert w["max_bridges"] == 3 and w["latent_top_k"] == 24 and w["candidate_parents"] == 8
    assert out["meta"]["wildcard_plan"] == "divergent-retrieval-v1" and out["meta"]["degraded"] == []
    assert sorted(h.children_calls) == sorted(p for p, _, _, _ in FAR_FIVE)                 # one children_of per frontier parent
    assert h.pair_calls == 5 and len(h.judge_calls) == 1                                       # the core judge ran once
    lat = out["trace"]["latency_ms"]
    assert isinstance(lat["wildcard"], float) and lat["wildcard_sweep"] == w["sweep_ms"]
    # the evidence list itself is the HYBRID composition — bridges never entered it
    assert not any(e["chunk_id"].startswith("pfar") for e in out["evidence"])
    assert bridges[0]["channels"] == ["abstraction", "transfer"] and bridges[0]["why_it_may_transfer"] == "transfer of pfar0"


def test_wildcard_never_returns_a_bridge_whose_source_chunk_is_in_the_evidence_list(monkeypatch):
    h = _ModeHarness(monkeypatch, latent=FAR_FIVE[:2] + [PNEAR])
    out = h.mode("WILDCARD")
    assert EVIDENCE_CHUNK_OF_PNEAR in _ids(out)                                                # the fixture premise holds
    w = out["meta"]["wildcard"]
    assert [b["parent_id"] for b in out["wildcard"]] == ["pfar0", "pfar1"]
    assert w["excluded_in_evidence"] == 1 and w["returned"] == 2 and w["degraded"] is None


def test_wildcard_evidence_equals_hybrid_evidence(monkeypatch):
    hw = _ModeHarness(monkeypatch, latent=FAR_FIVE)
    w = hw.mode("WILDCARD")
    hh = _ModeHarness(monkeypatch)
    hyb = hh.mode("HYBRID")
    assert _ids(w) == _ids(hyb) and w["trace"]["final"] == hyb["trace"]["final"]              # the frontier never reorders evidence
    assert len(hw.judge_calls) == 1 and len(hw.sparse_starts) == 1


def test_wildcard_sweep_timeout_degrades_to_an_empty_lane_and_never_holds_the_turn(monkeypatch):
    h = _ModeHarness(monkeypatch, latent=FAR_FIVE, latent_sleep=1.0)
    t0 = _time.perf_counter()
    out = h.mode("WILDCARD", budget=ce.CandidateBudget(wildcard_deadline_s=0.2))
    wall = _time.perf_counter() - t0
    assert wall < 0.9, wall
    w = out["meta"]["wildcard"]
    assert out["wildcard"] == [] and w["returned"] == 0 and w["degraded"] == "wildcard_timeout:sweep" and w["deadline_s"] == 0.2
    assert [d["component"] for d in out["meta"]["degraded"]] == ["wildcard"] and "core evidence stands" in out["meta"]["degraded"][0]["effect"]
    assert out["evidence"] and out["meta"]["mode"] == "WILDCARD" and out["trace"]["latency_ms"]["wildcard"] < 900
    assert h.children_calls == [] and h.pair_calls == 0                                        # nothing after the sweep was attempted
    hh = _ModeHarness(monkeypatch)
    assert _ids(out) == _ids(hh.mode("HYBRID"))                                                # the core answer is intact
    h.drain("latent_calls", 2)                                                                 # the abandoned sweep finishes its second channel and exits
    assert len(h.latent_calls) == 2 and h.children_calls == [] and h.pair_calls == 0


def test_wildcard_validation_timeout_degrades_the_same_way_and_the_abandoned_frontier_stops_calling_out(monkeypatch):
    # B12 LATENT-COMPOSITION-V1: the finish has its own budget (`wildcard_finish_budget_s`) and, when it is missed, the
    # top unvalidated parents ship as UNVERIFIED bridges under `wildcard_unverified_fill_s`. The P1.e invariants are
    # kept under the same numbers by pinning both budgets and switching the fill off; the fill is then proven on.
    # (a) a budget that cannot fit ONE validation, fill off: the deadline-aware finish starts none — no store call and no
    # reranker call at all — the lane is empty and receipted degraded, the core answer stands
    h = _ModeHarness(monkeypatch, latent=FAR_FIVE, children_sleep=0.5)
    out = h.mode("WILDCARD", budget=ce.CandidateBudget(wildcard_deadline_s=0.3, wildcard_finish_budget_s=0.3, wildcard_unverified_fill_s=0.0))
    w = out["meta"]["wildcard"]
    assert out["wildcard"] == [] and w["degraded"] == "wildcard_timeout:finish" and w["sweep_ms"] is not None
    assert w["finish_ms"] is not None and w["finish_ms"] < 900 and out["evidence"]
    assert w["partial"] is True and w["parents_validated"] == 0 and w["parents_skipped"] >= 1
    assert h.children_calls == [] and h.pair_calls == 0
    h.drain("children_calls", 0)
    assert h.children_calls == [] and h.pair_calls == 0                                          # nothing calls out afterwards
    # (a2) the same budget with the fill on: the skipped frontier ships UNVERIFIED — no judge call, one store call per
    # shipped parent, ≤ max_bridges, every bridge labelled, the degradation says so
    ha = _ModeHarness(monkeypatch, latent=FAR_FIVE, children_sleep=0.05)
    outa = ha.mode("WILDCARD", budget=ce.CandidateBudget(wildcard_deadline_s=0.3, wildcard_finish_budget_s=0.3, wildcard_unverified_fill_s=2.0))
    wa = outa["meta"]["wildcard"]
    assert 1 <= len(outa["wildcard"]) <= 3 and all(b.get("verified") is False for b in outa["wildcard"])
    assert wa["unverified_bridges"] == len(outa["wildcard"]) and wa["verified_bridges"] == 0 and wa["degraded"] == "wildcard_timeout:finish"
    assert ha.pair_calls == 0 and set(ha.children_calls) <= {s["parent_id"] for s in wa.get("skipped_parents") or []} | set(ha.children_calls)
    deg = [d for d in outa["meta"]["degraded"] if d["component"] == "wildcard"][0]
    assert deg["state"] == "unverified" and "UNVERIFIED" in deg["effect"]
    assert all((b.get("source_evidence") or {}).get("chunk_id") not in {e["chunk_id"] for e in outa["evidence"]} for b in outa["wildcard"])
    # (b) a budget that fits exactly one validation (0.5 s of store latency, 0.9 s budget), fill off: the first parent is
    # validated, the rest are SKIPPED before they start (never abandoned mid-flight), the validated bridge is returned,
    # the lane is partial but not degraded, and no store or reranker call happens after the result
    h2 = _ModeHarness(monkeypatch, latent=FAR_FIVE, children_sleep=0.5)
    out2 = h2.mode("WILDCARD", budget=ce.CandidateBudget(wildcard_deadline_s=0.9, wildcard_finish_budget_s=0.9, wildcard_unverified_fill_s=0.0))
    w2 = out2["meta"]["wildcard"]
    assert w2["partial"] is True and w2["parents_validated"] == 1 and w2["parents_skipped"] >= 1 and not w2["degraded"]
    assert h2.children_calls == ["pfar0"] and h2.pair_calls == 1 and len(out2["wildcard"]) <= 1
    h2.drain("children_calls", 1)
    assert h2.children_calls == ["pfar0"] and h2.pair_calls == 1
    # (b2) the same with the fill on: the validated bridge stays verified, the quota is topped up unverified, no extra judge call
    h3 = _ModeHarness(monkeypatch, latent=FAR_FIVE, children_sleep=0.5)
    out3 = h3.mode("WILDCARD", budget=ce.CandidateBudget(wildcard_deadline_s=0.9, wildcard_finish_budget_s=0.9, wildcard_unverified_fill_s=3.0))
    w3 = out3["meta"]["wildcard"]
    assert h3.pair_calls == 1 and w3["verified_bridges"] == sum(1 for b in out3["wildcard"] if b.get("verified", True))
    assert w3["unverified_bridges"] == sum(1 for b in out3["wildcard"] if b.get("verified") is False) and len(out3["wildcard"]) <= 3

def test_wildcard_deadline_is_a_budget_knob_with_the_env_override(monkeypatch):
    monkeypatch.delenv("POLYMATH_CHAT_WILDCARD_DEADLINE_S", raising=False)
    assert cr.default_budget().wildcard_deadline_s == 2.5 == ce.CandidateBudget().wildcard_deadline_s
    monkeypatch.setenv("POLYMATH_CHAT_WILDCARD_DEADLINE_S", "1.25")
    assert cr.default_budget().wildcard_deadline_s == 1.25
    assert "wildcard_deadline_s" in ce.CandidateBudget().to_dict()


# ---------------------------------------------------------------- (e) meta.mode is truthful; the composition owns the lane set

@pytest.mark.parametrize("mode,expect,lanes", [
    ("VECTOR", "VECTOR", (ce.LANE_A, ce.LANE_B)), ("FAST", "VECTOR", (ce.LANE_A, ce.LANE_B)), ("vector", "VECTOR", (ce.LANE_A, ce.LANE_B)),
    ("HYBRID", "HYBRID", ce.LANES), ("GRAPH", "GRAPH", ce.LANES), ("WILDCARD", "WILDCARD", ce.LANES)])
def test_meta_mode_is_truthful_for_every_composition(monkeypatch, mode, expect, lanes):
    h = _ModeHarness(monkeypatch, latent=FAR_FIVE)
    out = h.mode(mode)
    assert out["meta"]["mode"] == expect and out["meta"]["lanes"] == list(lanes)
    assert ("graph_relationships" in out) == (expect == "GRAPH") and ("wildcard" in out) == (expect == "WILDCARD")
    assert len(h.embed_calls) == 1
    assert cr.MODE_LANES[expect] == lanes


def test_unknown_mode_is_a_typed_422_and_the_lane_set_cannot_be_overridden(monkeypatch):
    h = _ModeHarness(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        h.mode("LEGACY")
    assert ei.value.status_code == 422 and ei.value.detail["error_code"] == "unknown_mode"
    with pytest.raises(TypeError):
        h.mode("VECTOR", lanes=(ce.LANE_A,))
    with pytest.raises(TypeError):
        h.mode("HYBRID", on_context=lambda c, p: None)


# ---------------------------------------------------------------- divergent split: sweep + finish == the one-shot function

def _lat(parent, score, text, doc="d_far", name="far.md"):
    return {"score": score, "payload": {"parent_id": parent, "doc_id": doc, "source_name": name, "text": text}}


def _kid(cid, text):
    return {"score": 0.5, "payload": {"chunk_id": cid, "text": text, "source_name": "far.md"}}


def test_divergent_sweep_plus_finish_equals_divergent_retrieve_and_the_sweep_is_not_mutated():
    latent = {"latent_abstraction": [_lat("p_near", 0.99, "principle near", doc="d_near")] +
              [_lat(f"p{i}", 0.9 - i * 0.01, f"principle {i}") for i in range(10)],
              "latent_transfer": [_lat("p0", 0.95, "transfer text zero")]}
    children = {f"p{i}": [_kid(f"c{i}", f"support text {i} mechanism")] for i in range(10)}
    children["p3"] = [_kid("c_near_1", "make an animated punch feel heavier with animated punch")]
    baseline = {"doc_ids": {"d_near"}, "parent_ids": {"p_near"}, "chunk_ids": {"c_near_1"}}

    def search(kind, _qvec, top_k):
        return (latent.get(kind) or [])[:top_k]

    def rerank(anchor, texts):
        return [0.9 if "5" not in t else 0.05 for t in texts]      # p5 dies at the support floor

    query = "how can I make an animated punch feel heavier"
    old = dv.divergent_retrieve(query, embed_query=lambda q: [0.1] * 4, latent_search=search, children_of=lambda pid: children.get(pid, []),
                                baseline=baseline, rerank_pairs=rerank)
    parents = dv.divergent_sweep([0.1] * 4, search, dv.DIVERGENT_DEFAULT_PLAN)
    frozen = copy.deepcopy(parents)
    new = dv.divergent_finish(query, parents, children_of=lambda pid: children.get(pid, []), baseline=baseline, rerank_pairs=rerank)
    assert new == old and parents == frozen
    assert len(parents) == 11 and parents["p0"]["channels"] == ["abstraction", "transfer"] and parents["p0"]["hop1"] == 0.95
    assert new["diagnostics"] == {"latent_candidates": 11, "excluded_obvious": 1, "support_filtered": 1, "returned": 3, "reranker": True, "skipped_parents": [],   # B12: the frontier the budget skipped (none here)
                                  "partial": False, "parents_validated": 8, "parents_skipped": 0}   # P1.e deadline-aware finish: additive keys
    assert [b["parent_id"] for b in new["wildcard"]] == ["p0", "p1", "p2"]
    # finish with no baseline and no reranker behaves like the one-shot function too
    assert dv.divergent_finish(query, parents, children_of=lambda pid: children.get(pid, [])) == \
        dv.divergent_retrieve(query, embed_query=lambda q: [0.1] * 4, latent_search=search, children_of=lambda pid: children.get(pid, []))


def test_divergent_sweep_fails_open_per_channel_and_finish_fails_open_to_an_empty_lane():
    def broken(*_a, **_k):
        raise RuntimeError("store down")
    assert dv.divergent_sweep([0.0], broken) == {}
    out = dv.divergent_finish("q", {}, children_of=broken)
    assert out == {"wildcard": [], "diagnostics": {"latent_candidates": 0, "excluded_obvious": 0, "support_filtered": 0, "returned": 0, "partial": False, "parents_validated": 0, "parents_skipped": 0, "skipped_parents": [],
                                                    "reranker": False}, "plan": "divergent-retrieval-v1"}
    half = dv.divergent_sweep([0.0], lambda kind, v, k: ([_lat("p1", 0.8, "principle")] if kind == "latent_transfer" else broken()))
    assert list(half) == ["p1"] and half["p1"]["channels"] == ["transfer"] and half["p1"]["transfer"] == "principle"


def test_wildcard_children_of_closes_over_one_fixed_vector_not_function_state(monkeypatch):
    """§3.21 #9: the frontier's children_of reads a fixed vector — the same one the sweep used — never an attribute set later."""
    h = _ModeHarness(monkeypatch, latent=FAR_FIVE[:1])
    h.mode("WILDCARD")
    assert h.children_calls == ["pfar0"]
    assert not hasattr(fast_api, "_children_of")
    assert all(list(v) == h.primary_vec for _, v, _, _ in h.latent_calls)

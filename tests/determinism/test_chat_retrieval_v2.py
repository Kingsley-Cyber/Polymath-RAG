"""CHAT-RETRIEVAL-V2 route (P1.a): the shared FastSearcher filter builder is
the one place corpus / generation isolation lives (§3.21 #11, §5b 15–16);
no sparse companion probe when built without a query (#1); live: the chat
path retrieves on chat-retrieval-v2 with provenance on every candidate and
the v1 rollback still answers."""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from orchestrator.api import fast as fast_api  # noqa: E402
from orchestrator.api.chat_retrieval import chat_retrieval_flag  # noqa: E402


class _Pts:
    def __init__(self, points):
        self.points = points


class FakeClient:
    def __init__(self):
        self.calls = []

    def query_points(self, **kw):
        self.calls.append(kw)
        return _Pts([])


def _filters_of(kw):
    f = kw["query_filter"]
    must = sorted((c.key, getattr(c.match, "value", None) or tuple(getattr(c.match, "any", []) or [])) for c in f.must)
    must_not = sorted((c.key, getattr(c.match, "value", None) or tuple(getattr(c.match, "any", []) or [])) for c in f.must_not)
    return must, must_not


def test_dense_and_sparse_searches_share_one_filter_builder_and_no_companion_probe_without_a_query():
    client = FakeClient()
    s = fast_api.FastSearcher(client, {"cinema": "coll"})            # no query → no sparse companion (§3.21 #1)
    s._hidden_cache = {"cinema": ["gen-rebuilding"]}                 # GENERATION-SWAP-V1 hidden generation, no DB
    filters = {"representation_kind": "routing_child", "corpus_id": "cinema"}
    s._search("coll", [0.1, 0.2], filters, limit=7)
    s.sparse_search("coll", ((1, 2, 3), (0.5, 0.4, 0.3)), filters, limit=9)
    assert len(client.calls) == 2                                    # ONE dense + ONE sparse call, nothing else
    dense, sparse = client.calls
    assert _filters_of(dense) == _filters_of(sparse)
    must, must_not = _filters_of(dense)
    assert ("corpus_id", "cinema") in must and ("representation_kind", "routing_child") in must
    assert ("chunk_contract_version", "gen-rebuilding") in must_not  # rebuilding projection chunks never leak (§5b 16)
    assert dense["limit"] == 7 and sparse["limit"] == 9 and sparse["using"] == "bm25"
    # deepening filters (doc + parent) travel through the same builder
    s._search("coll", [0.1], {**filters, "doc_id": "d1", "parent_id": "p1"}, limit=3)
    must3, _ = _filters_of(client.calls[-1])
    assert ("doc_id", "d1") in must3 and ("parent_id", "p1") in must3
    # no sparse query → typed failure, never a silent empty lane
    with pytest.raises(RuntimeError):
        s.sparse_search("coll", None, filters, limit=5)


def test_companion_probe_still_fires_for_the_v1_routes_built_with_a_query(monkeypatch):
    client = FakeClient()
    s = fast_api.FastSearcher(client, {"cinema": "coll"})
    s._sparse_query = ([1], [1.0])                                   # what the v1 constructor sets from the query text
    s._hidden_cache = {"cinema": []}
    s._search("coll", [0.1], {"representation_kind": "routing_child", "corpus_id": "cinema"}, limit=5)
    assert len(client.calls) == 2 and client.calls[1].get("using") == "bm25"   # v1 behaviour untouched


def test_flag_defaults_to_v2_and_accepts_overrides(monkeypatch):
    monkeypatch.delenv("POLYMATH_CHAT_RETRIEVAL", raising=False)
    assert chat_retrieval_flag() == "v2" and chat_retrieval_flag("v1") == "v1" and chat_retrieval_flag("nonsense") == "v2"
    assert chat_retrieval_flag("v2-single") == "v2-single"
    monkeypatch.setenv("POLYMATH_CHAT_RETRIEVAL", "v1")
    assert chat_retrieval_flag() == "v1" and chat_retrieval_flag("v2") == "v2"


# ---------------- live ----------------

def _stream(body: dict) -> tuple[list[dict], dict]:
    req = urllib.request.Request("http://127.0.0.1:7200/chat/stream", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    phases, answer, cur = [], {}, None
    with urllib.request.urlopen(req, timeout=420) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("event:"):
                cur = line[6:].strip()
            elif line.startswith("data:") and cur == "phase":
                phases.append(json.loads(line[5:].strip()))
            elif line.startswith("data:") and cur == "answer":
                answer = json.loads(line[5:].strip())
    return phases, answer


@pytest.mark.parametrize("retrieval", ["v2", "v1"])
def test_live_chat_hybrid_retrieves_on_v2_with_provenance_and_v1_still_answers(retrieval):
    try:
        urllib.request.urlopen("http://127.0.0.1:7200/ready", timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"orchestrator not reachable: {exc}")
    phases, answer = _stream({"message": "What does the book say about making your own chroma keyer?", "corpus_id": "cinema",
                              "mode": "HYBRID", "compiler": "on", "retrieval": retrieval, "synthesizer": "deterministic-template-v3"})
    ret = answer.get("retrieval") or {}
    done = next((p for p in phases if p.get("stage") == "retrieve_done"), {})
    if retrieval == "v2":
        assert ret.get("engine") == "chat-retrieval-v2" and done.get("plan") == "chat-retrieval-v2", (ret.get("engine"), done)
        lanes = ret.get("funnel", {}).get("lane_counts") or {}
        assert lanes.get("global_dense_child", 0) > 0 and lanes.get("hierarchical", 0) > 0, lanes
        arrivals = ret.get("arrivals") or {}
        assert arrivals and all(v for v in arrivals.values()), arrivals             # 100 % of final candidates have arrivals
        assert set(arrivals) == {c for c in ret.get("used_evidence", [])} | set(arrivals)
        assert ret["funnel"]["counts"]["union"] >= ret["funnel"]["counts"]["pre_rerank"] >= ret["funnel"]["counts"]["selected"] > 0
    else:
        assert ret.get("engine") == "hybrid-retrieval-v1" and ret.get("funnel", {}).get("counts", {}).get("selected", 0) > 0


def test_embed_queries_makes_one_sidecar_call_for_all_distinct_texts(monkeypatch):
    calls = []

    class FakeEmbedder:
        def __init__(self, *a, **k): pass
        def ready(self): return True
        def verify_pin(self): pass
        def close(self): pass
        def embed(self, texts, kind):
            calls.append((list(texts), kind))
            return {"vectors": [[float(i)] for i, _ in enumerate(texts)]}
    import polymath_shared.clients as clients
    monkeypatch.setattr(clients, "EmbedderClient", FakeEmbedder)
    vecs = fast_api._embed_queries(["primary", "sub one", "sub two"])
    assert calls == [(["primary", "sub one", "sub two"], "query")] and vecs == [[0.0], [1.0], [2.0]]
    assert fast_api._embed_queries([]) == [] and len(calls) == 1


# ---------------- P1.d CONCURRENCY-DEADLINES-V1: route spies (every sidecar and store faked) ----------------

import threading  # noqa: E402
import time as _time  # noqa: E402

from polymath_shared import candidate_engine as ce  # noqa: E402


class _RouteHarness:
    """chat_retrieve_v2 with the embedder, judge, Qdrant, Postgres joins and readiness faked. Records: embed calls
    (texts), when the embedding returned, when each sparse search STARTED, and how many judge calls were made."""
    def __init__(self, monkeypatch, *, embed_wait_for_sparse=False, rerank_sleep=0.0, rerank_note=None):
        from orchestrator.api import chat_retrieval as cr
        self.cr = cr
        self.embed_calls: list[list[str]] = []
        self.embed_returned_at: float | None = None
        self.sparse_starts: list[tuple[tuple, float]] = []
        self.sparse_started = threading.Event()
        self.rerank_calls = 0
        h = self

        def fake_embed(texts):
            h.embed_calls.append(list(texts))
            if embed_wait_for_sparse:                       # the embedder is slow; lane C must already be running
                h.sparse_started.wait(timeout=2.0); _time.sleep(0.05)
            h.embed_returned_at = _time.perf_counter()
            return [[0.1 * (i + 1), 0.2] for i, _ in enumerate(texts)]

        def fake_rerank(q, rows):
            h.rerank_calls += 1
            if rerank_sleep:
                _time.sleep(rerank_sleep)
            if rerank_note:
                fast_api._RERANK_DEGRADED.set(rerank_note)  # what _rerank_children does on RerankUnavailable — in the pool thread
            return sorted([dict(r, rerank_score=1.0 - i * 0.01) for i, r in enumerate(rows)], key=lambda r: -r["rerank_score"])

        class FakeSearcher:
            def __init__(self, client, collections, query=None):
                self.latency = {}

            def _hidden_for(self, cid):
                return []

            def _search(self, collection, vector, filters, limit):
                kind = filters["representation_kind"]
                if kind == "routing_child":
                    parent = filters.get("parent_id")
                    docs = (filters["doc_id"],) if parent else ("d1", "d2")
                    return [{"payload": {"chunk_id": f"{d}-{parent or 'g'}-c{i}", "doc_id": d, "parent_id": parent or f"{d}-p", "text": "t", "corpus_id": "cinema"},
                             "score": 1 - i * 0.01} for i in range(min(limit, 3)) for d in docs]
                if kind == "routing_document_summary":
                    return [{"payload": {"doc_id": d, "summary_id": f"s-{d}", "text": "doc", "corpus_id": "cinema"}, "score": 0.9 - i * 0.1} for i, d in enumerate(("d1", "d2"))]
                if kind == "routing_section_summary":
                    return [{"payload": {"doc_id": d, "parent_id": f"{d}-p", "summary_id": f"sec-{d}", "text": "sec", "corpus_id": "cinema"}, "score": 0.9 - i * 0.1} for i, d in enumerate(("d1", "d2"))]
                return []

            def sparse_search(self, collection, sparse_query, filters, limit):
                h.sparse_starts.append((tuple(sparse_query[0]), _time.perf_counter()))
                h.sparse_started.set()
                key = "-".join(str(i) for i in sparse_query[0])
                return [{"payload": {"chunk_id": f"sp-{key}", "doc_id": "d3", "parent_id": "d3-p", "text": "RAPO", "corpus_id": "cinema"}, "score": 12.0}]

        class FakeQdrant:
            def __init__(self, *a, **k): pass
            def close(self): pass

        monkeypatch.setattr(cr, "_embed_queries", fake_embed)
        monkeypatch.setattr(cr, "_rerank_children", fake_rerank)
        monkeypatch.setattr(cr, "FastSearcher", FakeSearcher)
        monkeypatch.setattr(cr, "QdrantClient", FakeQdrant)
        monkeypatch.setattr(cr, "_ensure_fast_ready", lambda cid: None)
        monkeypatch.setattr(cr, "_corpus_collections", lambda ids: {i: f"coll-{i}" for i in ids})
        monkeypatch.setattr(cr, "_region_lookup", lambda ids: {})
        monkeypatch.setattr(cr, "_neighbor_lookup", lambda want, d: [])
        monkeypatch.setattr(cr, "_presentation_joins", lambda cids, dids: {})

    def run(self, **kw):
        return self.cr.chat_retrieve_v2("what does RAPO say about prompts", "cinema", exact_terms=("RAPO",), **kw)


def test_route_one_embedding_per_distinct_text_one_judge_call_and_lane_c_starts_before_the_embedding_returns(monkeypatch):
    """§4 P1.d gate, spy form: exactly 1 embedding per distinct query text, exactly 1 rerank call per turn, BM25 first."""
    h = _RouteHarness(monkeypatch, embed_wait_for_sparse=True)
    # Pin rerank_deadline_s explicitly: this repo's .env ships
    # POLYMATH_CHAT_RERANK_DEADLINE_S=12 (an intentional, live operational tuning
    # value chat_retrieval.py's _FLOAT_KNOBS reads at runtime), overriding
    # CandidateBudget's own code default of 8.0 that this test's assertions below
    # expect. Matches the explicit-budget pattern the sibling
    # test_route_rerank_deadline_falls_back_to_fusion_order_... test already uses,
    # so this test's expectations are independent of the ambient environment.
    out = h.run(subqueries=(("q1", "MECHANISM", "reward models for prompts", 1.0), ("q2", "EXAMPLE", "what does RAPO say about prompts", 0.8)),
               budget=ce.CandidateBudget(lane_deadline_s=3.0, rerank_deadline_s=8.0))
    assert h.embed_calls == [["what does RAPO say about prompts", "reward models for prompts"]]     # ONE call, distinct texts only
    assert h.rerank_calls == 1                                                                       # ONE judge call per turn
    # lane C — the primary's exact terms AND the subquery's own sparse query — STARTED before the embedding returned
    assert len(h.sparse_starts) == 2 and all(t < h.embed_returned_at for _, t in h.sparse_starts), (h.sparse_starts, h.embed_returned_at)
    assert out["meta"]["plan_version"] == "chat-retrieval-v2" and out["meta"]["degraded"] == []
    assert out["meta"]["lanes"] == list(ce.LANES) and out["meta"]["deadlines"]["contract"] == "concurrency-deadlines-v1"
    assert out["meta"]["deadlines"]["lane_deadline_s"] == 3.0 and out["meta"]["deadlines"]["rerank_deadline_s"] == 8.0
    assert out["trace"]["concurrency"]["prestarted"] == ["global_sparse_child", "sub_q1_sparse"]
    assert any(e["chunk_id"].startswith("sp-") for e in out["evidence"])                             # the pre-started lane reached the answer
    assert out["meta"]["aspects"]["q1"]["lanes"]["GLOBAL_SPARSE_CHILD"] == 1 and out["meta"]["aspects"]["q1"]["lanes"]["GLOBAL_DENSE_CHILD"] > 0
    lat = out["trace"]["latency_ms"]
    assert {"embed", "embedded_texts", "sparse_prestart", "lanes", "union", "rerank", "compose", "rerank_select", "total"} <= set(lat)
    assert lat["embedded_texts"] == 2 and lat["total"] >= lat["embed"] and lat["sparse_prestart"] is not None
    assert "lane_global_dense_child" in lat and "lane_sub_q1_dense" in lat and "lane_hierarchical_children" in lat
    assert abs((lat["rerank"] + lat["compose"]) - lat["rerank_select"]) < 0.2


def test_route_rerank_deadline_falls_back_to_fusion_order_with_a_receipt_and_never_hangs(monkeypatch):
    h = _RouteHarness(monkeypatch, rerank_sleep=1.0)
    t0 = _time.perf_counter()
    out = h.run(budget=ce.CandidateBudget(rerank_deadline_s=0.2))
    wall = _time.perf_counter() - t0
    assert wall < 0.9, wall                                                              # the late judge never holds the turn
    assert h.rerank_calls == 1
    d = [x for x in out["meta"]["degraded"] if x["component"] == "rerank_timeout"]
    assert len(d) == 1 and "0.2" in d[0]["reason"] and "fusion" in d[0]["effect"]
    tr = out["trace"]
    assert tr["post_g3_order"] == tr["pre_g3_order"] and all(v is None for v in tr["g3_scores"].values())
    assert out["evidence"] and all(e["g3_score"] is None for e in out["evidence"])
    assert [e["chunk_id"] for e in out["evidence"]] == tr["pre_g3_order"][:len(out["evidence"])]   # fusion order stands
    assert tr["latency_ms"]["rerank"] < 900
    # ACCEPTANCE FINDING A1: an unjudged turn names its unverified coverage — every aspect with candidates is flagged
    # `unjudged` (receipt + prompt line; the selection above stayed in fusion order)
    assert tr["judge"] == "unjudged" and tr["weak_reasons"] and set(tr["weak_reasons"].values()) == {"unjudged"}
    assert "q0" in tr["weak_reasons"] and set(out["meta"]["weak_aspects"]) >= set(tr["weak_reasons"])


def test_route_carries_a_pool_thread_reranker_degradation_into_meta(monkeypatch):
    """_rerank_children notes a parked sidecar in a ContextVar; run in a pool thread that note would stay in the
    worker's context — the route must still report it in meta.degraded (the owner's NEVER-ERROR-ON-A-COLD-MODEL receipt)."""
    h = _RouteHarness(monkeypatch, rerank_note="reranker parked: sidecar unavailable")
    out = h.run()
    assert h.rerank_calls == 1
    assert [x["component"] for x in out["meta"]["degraded"]] == ["reranker"]
    assert "parked" in out["meta"]["degraded"][0]["reason"]


def test_route_lanes_restriction_makes_no_sparse_call_and_rejects_unknown_lanes(monkeypatch):
    h = _RouteHarness(monkeypatch)
    out = h.run(lanes=("HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD"), subqueries=(("q1", "MECHANISM", "reward models for prompts", 1.0),))
    assert h.sparse_starts == [] and len(h.embed_calls) == 1 and h.rerank_calls == 1                # VECTOR = A + B: no BM25 at all
    assert out["meta"]["lanes"] == ["HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD"] and out["meta"]["lexical_enabled"] is False
    assert out["trace"]["lane_sizes"]["global_sparse_child"] == 0 and out["evidence"] and out["meta"]["degraded"] == []
    assert out["trace"]["concurrency"]["prestarted"] == [] and out["trace"]["latency_ms"]["sparse_prestart"] is None
    assert out["meta"]["aspects"]["q1"]["lanes"] == {"GLOBAL_DENSE_CHILD": 6, "GLOBAL_SPARSE_CHILD": 0}   # B ran (3 × 2 docs), C never
    # lane order is canonical regardless of how the caller spelled it; unknown lanes are a typed 422
    out2 = h.run(lanes=("GLOBAL_SPARSE_CHILD", "HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD"))
    assert out2["meta"]["lanes"] == list(ce.LANES) and h.sparse_starts
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        h.run(lanes=("GLOBAL_DENSE_CHILD", "BOGUS"))
    assert ei.value.status_code == 422 and ei.value.detail["error_code"] == "unknown_lane"


def test_default_budget_reads_the_p1d_knobs_through_the_existing_env_pattern(monkeypatch):
    from orchestrator.api.chat_retrieval import default_budget
    for k in ("LANE_DEADLINE_S", "RERANK_DEADLINE_S", "EMBED_DEADLINE_S", "MAX_WORKERS", "RERANK_MAX"):
        monkeypatch.delenv(f"POLYMATH_CHAT_{k}", raising=False)
    b = default_budget()
    assert (b.embed_deadline_s, b.lane_deadline_s, b.rerank_deadline_s, b.max_workers) == (2.5, 3.0, 8.0, 8)
    monkeypatch.setenv("POLYMATH_CHAT_LANE_DEADLINE_S", "1.25")
    monkeypatch.setenv("POLYMATH_CHAT_MAX_WORKERS", "4")
    monkeypatch.setenv("POLYMATH_CHAT_RERANK_DEADLINE_S", "nonsense")
    b2 = default_budget()
    assert b2.lane_deadline_s == 1.25 and b2.max_workers == 4 and b2.rerank_deadline_s == 8.0 and b2.rerank_max == 24

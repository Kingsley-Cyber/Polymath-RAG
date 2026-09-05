"""P1.d part 4 — tests: engine concurrency + deadline degradation; route spies (one embedding per distinct text,
one judge call per turn, lane C overlaps the embedding); scaffold + README. Apply after p1d_route_patch.py."""
import pathlib
ROOT = pathlib.Path("/Users/king/Documents/polymath-rebuild/polymath-v4")
p = ROOT / "tests/determinism/test_candidate_engine.py"; t = p.read_text(encoding="utf-8")
t += '''

def test_lanes_run_concurrently_and_a_slow_lane_is_degraded_not_awaited():
    import concurrent.futures as cf, threading, time as _t

    class Slow(Fake):
        def __init__(self, slow_kind=None, sleep=0.0, per_call=0.0):
            super().__init__(); self.slow_kind, self.sleep, self.per_call = slow_kind, sleep, per_call
            self.lock = threading.Lock(); self.inflight = 0; self.max_inflight = 0

        def _enter(self):
            with self.lock:
                self.inflight += 1; self.max_inflight = max(self.max_inflight, self.inflight)

        def _exit(self):
            with self.lock:
                self.inflight -= 1

        def dense(self, kind, top_k, extra=None, qvec=None):
            self._enter()
            try:
                _t.sleep(self.per_call)
                if kind == self.slow_kind and not extra:
                    _t.sleep(self.sleep)
                return super().dense(kind, top_k, extra)
            finally:
                self._exit()

        def sparse(self, top_k, sparse_query=None):
            self._enter()
            try:
                _t.sleep(self.per_call)
                if self.slow_kind == "sparse":
                    _t.sleep(self.sleep)
                return super().sparse(top_k)
            finally:
                self._exit()

    # concurrency: 5 primary lanes at 0.15 s each finish in well under 5 × 0.15 s, and overlap is observed
    fake = Slow(per_call=0.15)
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        t0 = _t.perf_counter()
        res = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake.dense, sparse_search=fake.sparse, executor=pool)
        wall = _t.perf_counter() - t0
    assert res.union and res.degraded == [] and res.trace["concurrent"] is True
    assert fake.max_inflight >= 3 and wall < 0.15 * 5, (fake.max_inflight, wall)     # lanes overlapped
    # deadline: the sparse lane sleeps past lane_timeout_s → degraded `global_sparse_child_timeout`, dense lanes intact, no waiting
    fake2 = Slow(slow_kind="sparse", sleep=2.0)
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        t0 = _t.perf_counter()
        res2 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(lane_timeout_s=0.4), dense_search=fake2.dense, sparse_search=fake2.sparse, executor=pool)
        wall2 = _t.perf_counter() - t0
    assert any(d["reason"] == "global_sparse_child_timeout" for d in res2.degraded), res2.degraded
    assert res2.lane_c == [] and res2.lane_a and res2.lane_b and wall2 < 1.5, wall2
    assert res2.trace["degraded"] == res2.degraded
    # pre-fetched sparse rows replace the lane C call (the route overlaps it with the embedding)
    fake3 = Slow()
    res3 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=fake3.dense, sparse_search=fake3.sparse,
                                  prefetched_sparse=[_row(CHILD, 0, "d3", parent="d3-p1", chunk="pre-1", score=9.0)])
    assert [c.chunk_id for c in res3.lane_c] == ["pre-1"] and not any(c[0] == "sparse" for c in fake3.calls)
    # inline (no executor) path is unchanged
    res4 = ce.retrieve_candidates(_ctx(), ce.CandidateBudget(), dense_search=Fake().dense, sparse_search=Fake().sparse)
    assert res4.trace["concurrent"] is False and res4.union
'''
p.write_text(t, encoding="utf-8")

p = ROOT / "tests/determinism/test_chat_retrieval_v2.py"; t = p.read_text(encoding="utf-8")
t += '''

def test_route_spies_one_embedding_per_distinct_text_one_judge_call_and_lane_c_overlaps_the_embedding(monkeypatch):
    """§4 P1.d gate (spy tests) on the route itself, with every sidecar and store faked."""
    import threading, time as _t
    from orchestrator.api import chat_retrieval as cr
    calls = {"embed": [], "rerank": 0, "sparse_started_at": None, "embed_started_at": None}

    def fake_embed(texts, wake_budget_s=None):
        calls["embed"].append((list(texts), wake_budget_s)); calls["embed_started_at"] = _t.perf_counter()
        _t.sleep(0.3)                                                    # the embedder is slow; lane C must not wait for it
        return [[0.1 * (i + 1), 0.2] for i, _ in enumerate(texts)]

    def fake_rerank(q, rows):
        calls["rerank"] += 1
        return sorted([dict(r, rerank_score=1.0 - i * 0.01) for i, r in enumerate(rows)], key=lambda r: -r["rerank_score"])

    class FakeSearcher:
        def __init__(self, client, collections, query=None):
            self.latency = {}
        def _hidden_for(self, cid):
            return []
        def _search(self, collection, vector, filters, limit):
            kind = filters["representation_kind"]
            if kind == "routing_child":
                return [{"payload": {"chunk_id": f"c{i}-{filters.get('parent_id', 'g')}", "doc_id": "d1", "parent_id": filters.get("parent_id", "p1"), "text": "t", "corpus_id": "cinema"}, "score": 1 - i * 0.01} for i in range(min(limit, 5))]
            if kind == "routing_document_summary":
                return [{"payload": {"doc_id": "d1", "summary_id": "s", "text": "doc", "corpus_id": "cinema"}, "score": 0.9}]
            if kind == "routing_section_summary":
                return [{"payload": {"doc_id": "d1", "parent_id": "p1", "summary_id": "s", "text": "sec", "corpus_id": "cinema"}, "score": 0.9}]
            return []
        def sparse_search(self, collection, sparse_query, filters, limit):
            calls["sparse_started_at"] = _t.perf_counter()
            return [{"payload": {"chunk_id": "sp1", "doc_id": "d2", "parent_id": "p2", "text": "RAPO", "corpus_id": "cinema"}, "score": 12.0}]

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
    monkeypatch.setattr(cr, "degradations", lambda: [])
    out = cr.chat_retrieve_v2("what does RAPO say about prompts", "cinema", exact_terms=("RAPO",),
                              subqueries=(("q1", "MECHANISM", "reward models for prompts", 1.0), ("q2", "EXAMPLE", "what does RAPO say about prompts", 0.8)))
    assert len(calls["embed"]) == 1 and calls["embed"][0][0] == ["what does RAPO say about prompts", "reward models for prompts"]   # distinct texts, ONE call
    assert calls["embed"][0][1] == cr.EMBED_WAKE_BUDGET_INTERACTIVE_S                                                   # interactive wake budget
    assert calls["rerank"] == 1                                                                                          # ONE judge call per turn
    assert calls["sparse_started_at"] is not None and calls["sparse_started_at"] < calls["embed_started_at"] + 0.25      # lane C did not wait for the vector
    assert out["meta"]["plan_version"] == "chat-retrieval-v2" and out["evidence"] and out["meta"]["budgets"]["concurrent"] is True
    assert "sp1" in {e["chunk_id"] for e in out["evidence"]} and out["trace"]["concurrent"] is True
    assert out["trace"]["latency_ms"]["embedded_texts"] == 2 and "lane_lanes_wall" in out["trace"]["latency_ms"]
'''
p.write_text(t, encoding="utf-8")
# scaffold + README
p = ROOT / "scripts/scaffold_polymath_v4.py"; s = p.read_text(encoding="utf-8")
anchor = '    ("docs/wiki/experiments/chat-baseline-p1c-M-after.md", "md", None),\n'; assert s.count(anchor) == 1
add = ''.join(f'    ("{f}", "{f.rsplit(".",1)[1]}", None),\n' for f in [
    "docs/wiki/work-log/2026-09-05-p1d-concurrency.md",
    "docs/wiki/experiments/chat-baseline-p1d-B-vector.json", "docs/wiki/experiments/chat-baseline-p1d-B-vector.md",
    "docs/wiki/experiments/chat-baseline-p1d-B-hybrid.json", "docs/wiki/experiments/chat-baseline-p1d-B-hybrid.md"])
p.write_text(s.replace(anchor, anchor + add), encoding="utf-8")
p = ROOT / "scripts/README.md"; s = p.read_text(encoding="utf-8")
line = [l for l in s.split("\n") if l.startswith("| `scripts/chat_baseline.py`")][0]
if "--lanes" not in line:
    s = s.replace(line, line.rstrip(" |") + " P1.d: `--lanes AB|ABC` (VECTOR vs HYBRID on the v2 engine). |")
    p.write_text(s, encoding="utf-8")
print("P1.d tests + scaffold applied")

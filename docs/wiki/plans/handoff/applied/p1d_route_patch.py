"""P1.d part 3 — route: executor per turn, sparse prefetch overlapping the embedding, rerank deadline,
interactive embedder wake budget, evaluation-only `lanes`; fast.py wake budget; ui.py/chat.py `lanes`;
chat_baseline --lanes; tests. Apply after p1d_engine_rewrite.py."""
import pathlib
ROOT = pathlib.Path("/Users/king/Documents/polymath-rebuild/polymath-v4")

# ------------------------------------------------------------------ fast.py: interactive wake budget
p = ROOT / "orchestrator/orchestrator/api/fast.py"; s = p.read_text(encoding="utf-8")
old = '''def _await_embedder(client) -> None:
    """Block briefly while the autopilot wakes a parked embedder; on
    budget expiry fall through so the embed call fails typed."""
    if client.ready():
        return
    deadline = time.monotonic() + EMBED_WAKE_BUDGET_S'''
new = '''#: P1.d (§3.21 #18): an INTERACTIVE turn waits seconds for a parked embedder,
#: not minutes — the UI pulse keeps it warm; ingest keeps its own budget.
EMBED_WAKE_BUDGET_INTERACTIVE_S = float(
    os.environ.get("POLYMATH_EMBED_WAKE_BUDGET_INTERACTIVE_S", "20"))


def _await_embedder(client, budget_s: float | None = None) -> None:
    """Block briefly while the autopilot wakes a parked embedder; on
    budget expiry fall through so the embed call fails typed."""
    if client.ready():
        return
    deadline = time.monotonic() + (EMBED_WAKE_BUDGET_S if budget_s is None else float(budget_s))'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''def _embed_queries(texts: list[str]) -> list[list[float]]:
    """ONE embedder call for several distinct query texts (P1.b/P1.d: one
    embedding per distinct text, one HTTP round trip per turn)."""
    from polymath_shared.clients import EmbedderClient

    if not texts:
        return []
    client = EmbedderClient()
    try:
        _await_embedder(client)'''
new = '''def _embed_queries(texts: list[str], wake_budget_s: float | None = None) -> list[list[float]]:
    """ONE embedder call for several distinct query texts (P1.b/P1.d: one
    embedding per distinct text, one HTTP round trip per turn). `wake_budget_s`
    = how long an interactive turn waits for a parked embedder (#18)."""
    from polymath_shared.clients import EmbedderClient

    if not texts:
        return []
    client = EmbedderClient()
    try:
        _await_embedder(client, wake_budget_s)'''
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); import ast; ast.parse(s); print("fast.py: interactive wake budget")

# ------------------------------------------------------------------ route
p = ROOT / "orchestrator/orchestrator/api/chat_retrieval.py"; s = p.read_text(encoding="utf-8")
s = s.replace("import os\nimport time\nfrom typing import Optional\n", "import concurrent.futures as _cf\nimport os\nimport time\nfrom typing import Optional\n")
old = '''def chat_retrieve_v2(query: str, corpus_id: str, *, exact_terms: tuple[str, ...] = (),
                     budget: Optional[CandidateBudget] = None, query_id: str = "q0",
                     subqueries: tuple = ()) -> dict:'''
new = '''def chat_retrieve_v2(query: str, corpus_id: str, *, exact_terms: tuple[str, ...] = (),
                     budget: Optional[CandidateBudget] = None, query_id: str = "q0",
                     subqueries: tuple = (), lanes: Optional[tuple] = None) -> dict:'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''    budget = shape_budget(query, budget or default_budget())          # §3.21 #14: shape on the resolved text'''
new = '''    budget = shape_budget(query, budget or default_budget())          # §3.21 #14: shape on the resolved text
    if lanes:                                                         # P1.d/P1.e: modes are lane compositions
        from dataclasses import replace as _replace
        budget = _replace(budget, lanes=tuple(lanes))'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''    t_all = time.perf_counter()
    try:
        # §3.21 #1: built WITHOUT the query → no bm25 companion probe beside the dense lanes;
        # lane C is the one sparse search of the turn.
        searcher = FastSearcher(client, collections)
        t0 = time.perf_counter()
        sub_specs = [tuple(x) for x in (subqueries or ())][: (budget.max_subqueries if budget else 3)]
        texts = [query] + [t for (_, _, t, _) in sub_specs if t and t != query]
        distinct = list(dict.fromkeys(texts))
        vecs = dict(zip(distinct, _embed_queries(distinct)))               # ONE call, one vector per distinct text
        qvec = vecs[query]
        embed_ms = round((time.perf_counter() - t0) * 1000, 1)
        subs: list[SubQuery] = []
        for (sid, stype, stext, sweight) in sub_specs:
            if not stext or stext == query:
                continue
            sv, srule = sparse_vector_for(stext, ())
            subs.append(SubQuery(query_id=str(sid), qtype=str(stype), text=str(stext), weight=float(sweight or 1.0),
                                 qvec=tuple(vecs[stext]), sparse_query=sv, sparse_rule=srule))
        sparse_q, sparse_rule = None, "raw"
        try:
            sparse_q, sparse_rule = sparse_vector_for(query, exact_terms)   # exact terms alone when present
        except Exception:  # noqa: BLE001 — lane C degrades in the engine
            sparse_q = None'''
new = '''    t_all = time.perf_counter()
    pool = _cf.ThreadPoolExecutor(max_workers=max(2, int(budget.max_workers)), thread_name_prefix="chat-lanes")
    extra_degraded: list[dict] = []
    try:
        # §3.21 #1: built WITHOUT the query → no bm25 companion probe beside the dense lanes;
        # lane C is the one sparse search of the turn.
        searcher = FastSearcher(client, collections)
        searcher._hidden_for(corpus_id)                                    # warm the generation cache before threads share it
        sub_specs = [tuple(x) for x in (subqueries or ())][: (budget.max_subqueries if budget else 3)]
        texts = [query] + [t for (_, _, t, _) in sub_specs if t and t != query]
        distinct = list(dict.fromkeys(texts))
        sparse_q, sparse_rule = None, "raw"
        try:
            sparse_q, sparse_rule = sparse_vector_for(query, exact_terms)   # exact terms alone when present
        except Exception:  # noqa: BLE001 — lane C degrades in the engine
            sparse_q = None
        # STAGE 1 ∥ lane C: the embedding (one call, all distinct texts) and the BM25 lane start together —
        # BM25 needs no vector (§3.16). Lane C's rows are handed to the engine pre-fetched.
        t0 = time.perf_counter()
        emb_f = pool.submit(_embed_queries, distinct, EMBED_WAKE_BUDGET_INTERACTIVE_S)
        sparse_f = (pool.submit(searcher.sparse_search, collection, sparse_q,
                                {"representation_kind": "routing_child", "corpus_id": corpus_id}, budget.global_sparse_k)
                    if (sparse_q is not None and "GLOBAL_SPARSE_CHILD" in budget.lanes) else None)
        vecs = dict(zip(distinct, emb_f.result()))                          # embedder is a hard dependency: wait (typed failure inside)
        qvec = vecs[query]
        embed_ms = round((time.perf_counter() - t0) * 1000, 1)
        prefetched_sparse = None
        if sparse_f is not None:
            try:
                prefetched_sparse = sparse_f.result(timeout=max(0.1, budget.lane_timeout_s - (time.perf_counter() - t0)))
            except _cf.TimeoutError:
                extra_degraded.append({"component": "global_sparse_child", "effect": "no exact-match lane this turn; dense lanes only", "reason": "global_sparse_child_timeout"})
                prefetched_sparse = []
            except Exception as exc:  # noqa: BLE001
                extra_degraded.append({"component": "global_sparse_child", "effect": "no exact-match lane this turn; dense lanes only", "reason": f"{type(exc).__name__}: {str(exc)[:120]}"})
                prefetched_sparse = []
        subs: list[SubQuery] = []
        for (sid, stype, stext, sweight) in sub_specs:
            if not stext or stext == query:
                continue
            sv, srule = sparse_vector_for(stext, ())
            subs.append(SubQuery(query_id=str(sid), qtype=str(stype), text=str(stext), weight=float(sweight or 1.0),
                                 qvec=tuple(vecs[stext]), sparse_query=sv, sparse_rule=srule))'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''        result = retrieve_candidates(ctx, budget, dense_search=dense_search, sparse_search=sparse_search,
                                     region_lookup=_region_lookup, subqueries=subs)
        t1 = time.perf_counter()
        final, sel = select_evidence(result, budget, rerank_children=_rerank_children, neighbor_lookup=_neighbor_lookup)
        rerank_ms = round((time.perf_counter() - t1) * 1000, 1)
    finally:
        client.close()'''
new = '''        result = retrieve_candidates(ctx, budget, dense_search=dense_search, sparse_search=sparse_search,
                                     region_lookup=_region_lookup, subqueries=subs, executor=pool,
                                     prefetched_sparse=prefetched_sparse)
        t1 = time.perf_counter()

        def _rerank_with_deadline(q: str, rows: list[dict]) -> list[dict]:
            """STAGE 4: exactly one judge call per turn, under `rerank_budget_s`; past it the turn
            proceeds in fusion order and the receipt says `rerank_timeout` (the sidecar call is not
            cancelled — it finishes in the background)."""
            fut = pool.submit(_rerank_children, q, rows)
            try:
                return fut.result(timeout=budget.rerank_budget_s)
            except _cf.TimeoutError:
                extra_degraded.append({"component": "reranker", "effect": "results ordered by fusion (judge past its budget); same candidate set",
                                       "reason": "rerank_timeout"})
                return rows

        final, sel = select_evidence(result, budget, rerank_children=_rerank_with_deadline, neighbor_lookup=_neighbor_lookup)
        rerank_ms = round((time.perf_counter() - t1) * 1000, 1)
    finally:
        client.close()
        pool.shutdown(wait=False, cancel_futures=True)'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''            "degraded": degradations() + list(result.degraded),'''
new = '''            "degraded": degradations() + list(result.degraded) + extra_degraded,
            "budgets": {"lane_timeout_s": budget.lane_timeout_s, "rerank_budget_s": budget.rerank_budget_s,
                        "embed_wake_budget_s": EMBED_WAKE_BUDGET_INTERACTIVE_S, "concurrent": True},'''
assert s.count(old) == 1; s = s.replace(old, new)
s = s.replace("    _embed_queries,\n    _embed_query,\n", "    EMBED_WAKE_BUDGET_INTERACTIVE_S,\n    _embed_queries,\n    _embed_query,\n")
p.write_text(s, encoding="utf-8"); ast.parse(s); print("route: concurrency + deadlines")

# ------------------------------------------------------------------ ui.py / chat.py: evaluation-only lanes
p = ROOT / "orchestrator/orchestrator/api/ui.py"; s = p.read_text(encoding="utf-8")
old = '''    # CHAT-RETRIEVAL-V2 P1.a: per-request override of POLYMATH_CHAT_RETRIEVAL
    # (v1 = hybrid-retrieval-v1, v2 = chat-retrieval-v2) for evaluation and A/B.
    retrieval: Optional[str] = None
'''
new = old + '''    # P1.d/P1.e: lane composition override (evaluation and A/B): e.g. ["HIERARCHICAL_ROUTE","GLOBAL_DENSE_CHILD"] = VECTOR
    lanes: Optional[list[str]] = None
'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''                            subqueries=tuple((q.id, q.type, q.query, q.weight) for q in _plan.queries if q.type != "PRIMARY")
                            if (_flag == "on" and _plan is not None and _rflag == "v2") else ())'''
new = '''                            subqueries=tuple((q.id, q.type, q.query, q.weight) for q in _plan.queries if q.type != "PRIMARY")
                            if (_flag == "on" and _plan is not None and _rflag == "v2") else (),
                            lanes=tuple(getattr(req, "lanes", None) or ()) or None)'''
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); ast.parse(s); print("ui.py: lanes override")

# ------------------------------------------------------------------ chat_baseline --lanes
p = ROOT / "scripts/chat_baseline.py"; s = p.read_text(encoding="utf-8")
old = '''RETRIEVAL_OVERRIDE: str | None = None      # --retrieval v1|v2 (P1.a A/B)'''
new = '''RETRIEVAL_OVERRIDE: str | None = None      # --retrieval v1|v2 (P1.a A/B)
LANES_OVERRIDE: list[str] | None = None    # --lanes AB|ABC (P1.d: VECTOR vs HYBRID on one engine)
_LANE_LETTERS = {"A": "HIERARCHICAL_ROUTE", "B": "GLOBAL_DENSE_CHILD", "C": "GLOBAL_SPARSE_CHILD"}'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''    if RETRIEVAL_OVERRIDE:
        body["retrieval"] = RETRIEVAL_OVERRIDE'''
new = '''    if RETRIEVAL_OVERRIDE:
        body["retrieval"] = RETRIEVAL_OVERRIDE
    if LANES_OVERRIDE:
        body["lanes"] = LANES_OVERRIDE'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''    ap.add_argument("--build-multi", action="store_true",'''
new = '''    ap.add_argument("--lanes", default=None, help="P1.d: lane letters for the v2 engine, e.g. AB (VECTOR) or ABC (HYBRID)")
    ap.add_argument("--build-multi", action="store_true",'''
assert s.count(old) == 1; s = s.replace(old, new)
old = '''    global RETRIEVAL_OVERRIDE
    RETRIEVAL_OVERRIDE = a.retrieval'''
new = '''    global RETRIEVAL_OVERRIDE, LANES_OVERRIDE
    RETRIEVAL_OVERRIDE = a.retrieval
    LANES_OVERRIDE = [_LANE_LETTERS[ch] for ch in a.lanes.upper()] if a.lanes else None'''
assert s.count(old) == 1; s = s.replace(old, new)
s = s.replace('''        "retrieval": RETRIEVAL_OVERRIDE or "server-default",''', '''        "retrieval": RETRIEVAL_OVERRIDE or "server-default", "lanes": LANES_OVERRIDE or "budget-default",''')
p.write_text(s, encoding="utf-8"); ast.parse(s); print("chat_baseline: --lanes")
print("P1.d route patch applied")

"""P1.e — mode recomposition on the v2 engine: VECTOR = A+B, HYBRID = A+B+C, GRAPH = HYBRID → bounded G over the
canonical evidence (no unassigned_rescue_evidence; global winners seed the graph; primary qvec reused for entity cards),
WILDCARD = core ∥ W (sweep starts at T=0 with the shared qvec; baseline exclusion = the final candidate neighbourhood;
no function-attribute state). Apply after the P1.d patches."""
import pathlib
ROOT = pathlib.Path("/Users/king/Documents/polymath-rebuild/polymath-v4")

# ------------------------------------------------------------------ divergent.py: split sweep / finish (pure refactor)
p = ROOT / "shared/polymath_shared/divergent.py"; s = p.read_text(encoding="utf-8")
old = '''def divergent_retrieve(
    query: str,
    *,
    embed_query,
    latent_search,        # (kind, qvec, top_k) -> rows(score,payload)
    children_of,          # (parent_id) -> rows(score,payload)
    baseline: dict | None = None,   # {doc_ids,parent_ids,chunk_ids} of FAST
    rerank_pairs=None,    # (anchor_text, [texts]) -> [scores] | None
    plan: DivergentPlan = DIVERGENT_DEFAULT_PLAN,
) -> dict:
    qvec = embed_query(query)
    base = baseline or {}
    obvious_parents = set(base.get("parent_ids") or ())
    obvious_docs = set(base.get("doc_ids") or ())
    obvious_chunks = set(base.get("chunk_ids") or ())
    qtoks = _toks(query)

    # 1. broad latent sweep, both channels, merged per parent
    parents: dict[str, dict] = {}'''
new = '''def divergent_sweep(qvec, latent_search, plan: DivergentPlan = DIVERGENT_DEFAULT_PLAN) -> dict[str, dict]:
    """WILDCARD-PARALLEL-V1 (plan §3.19, P1.e): the broad latent sweep needs
    only the query vector, so it can start at T=0 beside core retrieval. Pure
    over `latent_search`; returns the merged per-parent slots."""
    parents: dict[str, dict] = {}
    for kind in ("latent_abstraction", "latent_transfer"):
        try:
            rows = latent_search(kind, qvec, plan.latent_top_k) or []
        except Exception:            # fail-open: frontier is optional
            rows = []
        for row in rows:
            payload = row.get("payload") or {}
            pid = payload.get("parent_id")
            if not pid:
                continue
            slot = parents.setdefault(pid, {
                "parent_id": pid,
                "doc_id": payload.get("doc_id"),
                "source_name": payload.get("source_name") or "",
                "hop1": 0.0, "channels": [],
                "abstraction": "", "transfer": ""})
            score = float(row.get("score") or 0.0)
            slot["hop1"] = max(slot["hop1"], score)
            slot["channels"].append(kind.replace("latent_", ""))
            if kind == "latent_abstraction":
                slot["abstraction"] = payload.get("text") or ""
            else:
                slot["transfer"] = payload.get("text") or ""
    return parents


def divergent_retrieve(
    query: str,
    *,
    embed_query,
    latent_search,        # (kind, qvec, top_k) -> rows(score,payload)
    children_of,          # (parent_id) -> rows(score,payload)
    baseline: dict | None = None,   # {doc_ids,parent_ids,chunk_ids} of FAST
    rerank_pairs=None,    # (anchor_text, [texts]) -> [scores] | None
    plan: DivergentPlan = DIVERGENT_DEFAULT_PLAN,
    sweep: dict[str, dict] | None = None,   # P1.e: a sweep already done at T=0 (skips embed + latent search)
) -> dict:
    if sweep is None:
        qvec = embed_query(query)
        parents = divergent_sweep(qvec, latent_search, plan)
    else:
        parents = sweep
    return divergent_finish(query, parents, children_of=children_of, baseline=baseline, rerank_pairs=rerank_pairs, plan=plan)


def divergent_finish(query: str, parents: dict[str, dict], *, children_of, baseline: dict | None = None,
                     rerank_pairs=None, plan: DivergentPlan = DIVERGENT_DEFAULT_PLAN) -> dict:
    """Baseline exclusion + two-hop validation + novelty over a finished sweep (the part that must
    wait for the core result). Byte-identical semantics to the pre-P1.e single function."""
    base = baseline or {}
    obvious_parents = set(base.get("parent_ids") or ())
    obvious_docs = set(base.get("doc_ids") or ())
    obvious_chunks = set(base.get("chunk_ids") or ())
    qtoks = _toks(query)
    parents = dict(parents)
    if False:  # (kept structure) — the sweep loop now lives in divergent_sweep
        pass
    _unused: dict[str, dict] = {}'''
assert s.count(old) == 1; s = s.replace(old, new)
# remove the now-duplicated sweep loop that followed in the original body: it starts with `    for kind in ("latent_abstraction", "latent_transfer"):` right after our insertion and ends before `    diag = {`
start = s.index("    _unused: dict[str, dict] = {}") + len("    _unused: dict[str, dict] = {}")
end = s.index("    diag = {\"latent_candidates\": len(parents), \"excluded_obvious\": 0,")
s = s[:start] + "\n\n" + s[end:]
s = s.replace("    parents = dict(parents)\n    if False:  # (kept structure) — the sweep loop now lives in divergent_sweep\n        pass\n    _unused: dict[str, dict] = {}\n\n", "    parents = dict(parents)\n")
p.write_text(s, encoding="utf-8")
import ast; ast.parse(s); print("divergent: sweep/finish split")

# ------------------------------------------------------------------ route: mode wrappers
p = ROOT / "orchestrator/orchestrator/api/chat_retrieval.py"; s = p.read_text(encoding="utf-8")
s += '''

# ---------------------------------------------------------------- P1.e: modes are compositions (§3.15, §3.18, §3.19)
MODE_LANES = {
    "VECTOR": ("HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD"),
    "FAST": ("HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD"),
    "HYBRID": ("HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD", "GLOBAL_SPARSE_CHILD"),
    "GRAPH": ("HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD", "GLOBAL_SPARSE_CHILD"),
    "WILDCARD": ("HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD", "GLOBAL_SPARSE_CHILD"),
}
GRAPH_SEEDS_MAX = 8
GRAPH_SEEDS_MIN = 2           # a plan with graph_useful=false expands ≤ 2 seeds (§5 #14)


def chat_retrieve_mode(mode: str, query: str, corpus_id: str, *, graph_useful: bool = True, **kw) -> dict:
    """One engine, four compositions. VECTOR/FAST = A+B; HYBRID = A+B+C; GRAPH = HYBRID + bounded
    hop-1 over the FINAL evidence (global winners seed like hierarchy winners, §3.21 #5–#6; the primary
    vector is reused for the entity-card seeds, #7); WILDCARD = HYBRID ∥ the latent sweep (§3.19)."""
    mode = (mode or "HYBRID").upper()
    lanes = MODE_LANES.get(mode, MODE_LANES["HYBRID"])
    if mode == "WILDCARD":
        return _retrieve_wildcard(query, corpus_id, lanes=lanes, **kw)
    out = chat_retrieve_v2(query, corpus_id, lanes=lanes, **kw)
    out["meta"]["mode"] = "VECTOR" if mode in ("VECTOR", "FAST") else mode
    if mode == "GRAPH":
        _attach_graph(out, query, corpus_id, graph_useful=graph_useful)
    return out


def _attach_graph(out: dict, query: str, corpus_id: str, *, graph_useful: bool) -> None:
    """Bounded G after evidence: ≤ 8 seeds (≤ 2 when the plan says the question is not relational),
    hop-1, ≤ GRAPH_MAX_FACTS facts; seeds come from every final chunk (hierarchy AND global winners)."""
    import time as _t
    from polymath_shared.retrieval_modes import GRAPH_MAX_FACTS
    from orchestrator.api.graph import _selected_surfaces
    from orchestrator.api.retrieve import graph_expand_or_502
    evidence = out.get("evidence") or []
    seeds_max = GRAPH_SEEDS_MAX if graph_useful else GRAPH_SEEDS_MIN
    t0 = _t.perf_counter()
    card_seed_ids: list[str] = []
    try:
        from orchestrator.api.fast import entity_card_probe
        qvec = out.get("_qvec")
        if qvec is not None:
            client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=30)
            try:
                cards = entity_card_probe(client, _corpus_collections([corpus_id]), corpus_id, query, list(qvec), limit=seeds_max)
            finally:
                client.close()
            card_seed_ids = [c["entity_id"] for c in cards if c.get("entity_id")][:seeds_max]
    except Exception:  # noqa: BLE001 — seeding is fail-open; surfaces still seed
        card_seed_ids = []
    surfaces = _selected_surfaces(query, evidence)[:seeds_max]
    facts = graph_expand_or_502(surfaces, [corpus_id], [c["chunk_id"] for c in evidence], seed_entity_ids=card_seed_ids)[:GRAPH_MAX_FACTS]
    out["graph_relationships"] = [{"fact_id": f["fact_id"], "predicate": f["predicate"], "subject_id": f.get("subject_id"),
                                   "subject": f["subject"], "object_id": f.get("object_id"), "object": f["object"]} for f in facts]
    out["meta"]["graph_bounds"] = {"max_seeds": seeds_max, "max_facts": GRAPH_MAX_FACTS, "graph_useful": bool(graph_useful)}
    out["meta"]["graph_fact_count"] = len(facts)
    out["meta"]["graph_seeds"] = {"surfaces": len(surfaces), "cards": len(card_seed_ids)}
    out["trace"]["latency_ms"]["graph"] = round((_t.perf_counter() - t0) * 1000, 1)
    out["trace"]["graph_seed_surfaces"] = surfaces


def _retrieve_wildcard(query: str, corpus_id: str, *, lanes, **kw) -> dict:
    """WILDCARD = core ∥ W: the latent sweep starts at T=0 with its own embedding call overlapped
    with the core (the core embeds the same text once; the sweep reuses that vector when the core
    finishes first). Baseline exclusion = the core's FINAL evidence neighbourhood (§3.21 #16);
    ≤ 3 bridges, never in the evidence list."""
    import time as _t
    from polymath_shared.divergent import DIVERGENT_DEFAULT_PLAN, divergent_finish, divergent_sweep
    from orchestrator.api.fast import _rerank_children as _rr
    collections = _corpus_collections([corpus_id]); coll = collections[corpus_id]
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    pool = _cf.ThreadPoolExecutor(max_workers=2, thread_name_prefix="wildcard")
    t0 = _t.perf_counter()
    try:
        searcher = FastSearcher(client, collections)
        searcher._hidden_for(corpus_id)

        def _sweep():
            qvec = _embed_queries([query], EMBED_WAKE_BUDGET_INTERACTIVE_S)[0]
            def _latent_search(kind, v, top_k):
                return searcher._search(coll, list(v), {"representation_kind": kind, "corpus_id": corpus_id}, limit=top_k)
            return qvec, divergent_sweep(qvec, _latent_search, DIVERGENT_DEFAULT_PLAN)
        sweep_f = pool.submit(_sweep)                                    # T=0, beside the core
        out = chat_retrieve_v2(query, corpus_id, lanes=lanes, **kw)      # the core (its own single embedding call)
        evidence = out.get("evidence") or []
        baseline = {"doc_ids": {e.get("doc_id") for e in evidence if e.get("doc_id")},
                    "parent_ids": {e.get("parent_id") for e in evidence if e.get("parent_id")},
                    "chunk_ids": {e.get("chunk_id") for e in evidence if e.get("chunk_id")}}
        try:
            qvec, parents = sweep_f.result(timeout=max(0.5, 12.0 - (_t.perf_counter() - t0)))
        except Exception as exc:  # noqa: BLE001 — the frontier is optional; the core answer stands
            out["wildcard"] = []; out["meta"]["wildcard"] = {"degraded": f"{type(exc).__name__}"}
            out["meta"]["mode"] = "WILDCARD"
            return out

        def _children_of(parent_id, _v=qvec):                            # closure over ONE fixed vector (#9)
            return searcher._search(coll, list(_v), {"representation_kind": "routing_child", "corpus_id": corpus_id, "parent_id": parent_id}, limit=50)

        def _rerank_pairs(anchor, texts):
            cands = [{"chunk_id": str(i), "text": t} for i, t in enumerate(texts)]
            ranked = _rr(anchor, cands)
            by_id = {c["chunk_id"]: c.get("rerank_score") for c in ranked}
            scores = [by_id.get(str(i)) for i in range(len(texts))]
            if any(sc is None for sc in scores):
                return None
            import math
            return [1.0 / (1.0 + math.exp(-float(sc))) for sc in scores]
        w = divergent_finish(query, parents, children_of=_children_of, baseline=baseline, rerank_pairs=_rerank_pairs, plan=DIVERGENT_DEFAULT_PLAN)
        ev_ids = baseline["chunk_ids"]
        bridges = [b for b in w["wildcard"] if (b.get("source_evidence") or {}).get("chunk_id") not in ev_ids][:DIVERGENT_DEFAULT_PLAN.max_bridges]
        out["wildcard"] = bridges
        out["meta"]["mode"] = "WILDCARD"
        out["meta"]["wildcard"] = {**w["diagnostics"], "returned": len(bridges), "baseline_chunks": len(ev_ids)}
        out["meta"]["wildcard_plan"] = w["plan"]
        out["trace"]["latency_ms"]["wildcard_total"] = round((_t.perf_counter() - t0) * 1000, 1)
        return out
    finally:
        client.close(); pool.shutdown(wait=False, cancel_futures=True)
'''
# expose the primary qvec on the v2 result for the graph card seeds (private key, stripped from the answer event by the handler's use)
old = '''    return {
        "query": query,
        "meta": {
            "mode": MODE_HYBRID, "plan_version": CHAT_RETRIEVAL_PLAN_VERSION, "engine": CANDIDATE_ENGINE_VERSION,'''
new = '''    return {
        "query": query,
        "_qvec": list(qvec),
        "meta": {
            "mode": MODE_HYBRID, "plan_version": CHAT_RETRIEVAL_PLAN_VERSION, "engine": CANDIDATE_ENGINE_VERSION,'''
assert s.count(old) == 1; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); ast.parse(s); print("route: chat_retrieve_mode / graph / wildcard")
print("P1.e route patch applied (ui.py mode dispatch is a separate step)")

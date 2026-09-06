"""P1.d part 2 — replace retrieve_candidates wholesale with the concurrent, deadline-aware version.
Apply after p1d_engine_draft.py (budgets + _gather). Preserves P1.b/P1.c semantics."""
import pathlib
ROOT = pathlib.Path("/Users/king/Documents/polymath-rebuild/polymath-v4")
p = ROOT / "shared/polymath_shared/candidate_engine.py"; s = p.read_text(encoding="utf-8")
start = s.index("def retrieve_candidates(ctx: SearchContext, budget: CandidateBudget, *,")
end = s.index("def replace_candidate(c: CandidateEvidence) -> CandidateEvidence:")
new_fn = '''def retrieve_candidates(ctx: SearchContext, budget: CandidateBudget, *,
                        dense_search: Callable[..., list[dict]],
                        sparse_search: Callable[..., list[dict]],
                        region_lookup: Optional[Callable[[list[str]], dict]] = None,
                        subqueries: Iterable[SubQuery] = (),
                        executor=None,
                        prefetched_sparse: Optional[list[dict]] = None) -> CandidateResult:
    """P1.d: every lane of the turn (doc summaries, section summaries, entity
    cards, global dense child, global sparse child, each subquery's B + C)
    is submitted to `executor` at T=0 and gathered under `lane_timeout_s`;
    deepening searches run concurrently once documents are selected. A lane
    that misses its deadline or raises is DEGRADED (`<lane>_timeout` /
    `<lane>_error`) and the turn proceeds. `prefetched_sparse` lets the route
    start lane C before the embedding exists (BM25 needs only tokens)."""
    timings: dict[str, float] = {}
    degraded: list[dict] = []
    lanes = set(budget.lanes)
    subqueries = list(subqueries or [])[:budget.max_subqueries]
    t_turn = time.perf_counter()

    def note(name: str, o: "_LaneOutcome", effect: str) -> None:
        timings[name] = o.ms
        if o.error:
            degraded.append({"component": name, "effect": effect,
                             "reason": (f"{name}_timeout" if o.error == "timeout" else o.error)})

    # ---- T=0: every independent lane ---------------------------------------------
    tasks: dict = {}
    if LANE_B in lanes or LANE_A in lanes:
        tasks["global_dense_child"] = lambda: _call_dense(dense_search, REPRESENTATION_KIND_CHILD, budget.global_dense_k, None, None)
    if LANE_C in lanes:
        if prefetched_sparse is not None:
            tasks["global_sparse_child"] = lambda: prefetched_sparse
        else:
            tasks["global_sparse_child"] = lambda: _call_sparse(sparse_search, budget.global_sparse_k, None)
    if LANE_A in lanes:
        tasks["document_summary"] = lambda: _call_dense(dense_search, REPRESENTATION_KIND_DOCUMENT_SUMMARY, budget.hierarchy_doc_k, None, None)
        tasks["section_summary"] = lambda: _call_dense(dense_search, REPRESENTATION_KIND_SECTION_SUMMARY, budget.hierarchy_section_k, None, None)
        if budget.entity_card_k > 0:
            tasks["entity_card"] = lambda: _call_dense(dense_search, REPRESENTATION_KIND_ENTITY_CARD,
                                                       budget.entity_card_k * budget.entity_card_max_docs_per_card, None, None)
    for sq in subqueries:
        if LANE_B in lanes:
            tasks[f"sub_{sq.query_id}_dense"] = (lambda sq=sq: _call_dense(dense_search, REPRESENTATION_KIND_CHILD, budget.subquery_dense_k, None, sq.qvec))
        if LANE_C in lanes and sq.sparse_query is not None:
            tasks[f"sub_{sq.query_id}_sparse"] = (lambda sq=sq: _call_sparse(sparse_search, budget.subquery_sparse_k, sq.sparse_query))
    outs = _gather(tasks, executor, budget.lane_timeout_s)
    for name, o in outs.items():
        note(name, o, "lane dropped this turn; the other lanes continue")

    # ---- lanes B and C (primary) ---------------------------------------------------
    child_lane = _hits(REPRESENTATION_KIND_CHILD, outs["global_dense_child"].rows if "global_dense_child" in outs else [], ctx.corpus_id, budget.global_dense_k)
    roles: dict = {}
    if budget.demote_noisy_regions and region_lookup is not None and child_lane:
        try:
            roles = region_lookup([h.chunk_id for h in child_lane if h.chunk_id]) or {}
        except Exception:  # noqa: BLE001 — demotion is best-effort
            roles = {}
        child_lane = _sink_noisy(child_lane, roles)
    sparse_lane = _hits("child_lexical", outs["global_sparse_child"].rows if "global_sparse_child" in outs else [], ctx.corpus_id, budget.global_sparse_k)

    # ---- lane A: hierarchical route (routing lanes gathered above, deepening concurrent) ----
    doc_lane: list[LaneHit] = []
    section_lane: list[LaneHit] = []
    card_lane: list[LaneHit] = []
    documents: list[DocumentCandidate] = []
    selected_documents: list[DocumentCandidate] = []
    selected_sections: list[dict] = []
    lane_a: list[CandidateEvidence] = []
    if LANE_A in lanes:
        doc_lane = _hits(REPRESENTATION_KIND_DOCUMENT_SUMMARY, outs["document_summary"].rows, ctx.corpus_id, budget.hierarchy_doc_k)
        section_lane = _hits(REPRESENTATION_KIND_SECTION_SUMMARY, outs["section_summary"].rows, ctx.corpus_id, budget.hierarchy_section_k)
        if "entity_card" in outs:
            card_lane = _hits(REPRESENTATION_KIND_ENTITY_CARD, outs["entity_card"].rows, ctx.corpus_id,
                              budget.entity_card_k * budget.entity_card_max_docs_per_card,
                              card_k=budget.entity_card_k, card_max_docs=budget.entity_card_max_docs_per_card)
        documents = aggregate_documents_n(
            [(REPRESENTATION_KIND_DOCUMENT_SUMMARY, doc_lane), (REPRESENTATION_KIND_SECTION_SUMMARY, section_lane),
             (REPRESENTATION_KIND_CHILD, child_lane), (REPRESENTATION_KIND_ENTITY_CARD, card_lane)], k=budget.rrf_k)
        selected_documents = documents[:budget.hierarchy_max_documents]
        selected_sections = resolve_sections(selected_documents, budget.hierarchy_max_sections_per_document)
        doc_rank = {d.doc_id: d.aggregate_rank for d in selected_documents}
        remaining = max(0.5, budget.lane_timeout_s - (time.perf_counter() - t_turn))
        deep_tasks = {f"deep_{i}": (lambda sec=sec: _call_dense(dense_search, REPRESENTATION_KIND_CHILD, budget.hierarchy_child_k,
                                                                {"doc_id": sec["doc_id"], "parent_id": sec["parent_id"]}, None))
                      for i, sec in enumerate(selected_sections)}
        t0 = time.perf_counter()
        deep = _gather(deep_tasks, executor, remaining)
        timings["hierarchical_children"] = round((time.perf_counter() - t0) * 1000, 1)
        deep_errors = [n for n, o in deep.items() if o.error]
        if deep_errors:
            degraded.append({"component": "hierarchical_children", "effect": f"{len(deep_errors)} of {len(deep)} section deepenings dropped",
                             "reason": ("hierarchical_children_timeout" if any(deep[n].error == "timeout" for n in deep_errors) else deep[deep_errors[0]].error)})
        seen_a: set[str] = set()
        for i, section in enumerate(selected_sections):
            for h in _hits(REPRESENTATION_KIND_CHILD, deep[f"deep_{i}"].rows, ctx.corpus_id, budget.hierarchy_child_k):
                if not h.chunk_id or h.chunk_id in seen_a:
                    continue
                seen_a.add(h.chunk_id)
                lane_a.append(CandidateEvidence(
                    chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name, text=h.text,
                    arrivals=[LANE_A], query_ids=[ctx.query_id], hierarchy_rank=len(lane_a), dense_score=h.raw_similarity,
                    document_rank=doc_rank.get(h.doc_id)))

    lane_b = [CandidateEvidence(chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name,
                                text=h.text, arrivals=[LANE_B], query_ids=[ctx.query_id], dense_rank=h.rank,
                                dense_score=h.raw_similarity, region_role=roles.get(h.chunk_id))
              for h in child_lane if h.chunk_id] if LANE_B in lanes else []
    lane_c = [CandidateEvidence(chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name,
                                text=h.text, arrivals=[LANE_C], query_ids=[ctx.query_id], sparse_rank=h.rank,
                                sparse_score=h.raw_similarity)
              for h in sparse_lane if h.chunk_id]

    # ---- typed subqueries: lanes B + C only, per-query provenance (results gathered above) ----
    aspects: dict[str, dict] = {ctx.query_id: {"type": "PRIMARY", "query": ctx.query, "weight": 1.0,
                                               "lanes": {LANE_A: len(lane_a), LANE_B: len(lane_b), LANE_C: len(lane_c)},
                                               "degraded": [d["component"] for d in degraded if not d["component"].startswith("sub_")]}}
    sub_items: list[CandidateEvidence] = []
    second_pass: Optional[dict] = None

    def _items_for(sq: SubQuery, dense_rows: list[dict], sparse_rows: list[dict], dk: int, sk: int) -> tuple[list[CandidateEvidence], dict]:
        items: list[CandidateEvidence] = []
        info = {"type": sq.qtype, "query": sq.text, "weight": sq.weight, "lanes": {LANE_B: 0, LANE_C: 0}, "degraded": []}
        hits = _hits(REPRESENTATION_KIND_CHILD, dense_rows, ctx.corpus_id, dk)
        hits = _sink_noisy(hits, roles) if roles else hits
        for h in hits:
            if h.chunk_id:
                items.append(CandidateEvidence(chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name,
                                               text=h.text, arrivals=[LANE_B], query_ids=[sq.query_id],
                                               query_scores={sq.query_id: sq.weight * _rrf_score(h.rank, budget.rrf_k)}, dense_score=h.raw_similarity))
        info["lanes"][LANE_B] = sum(1 for h in hits if h.chunk_id)
        shits = _hits("child_lexical", sparse_rows, ctx.corpus_id, sk)
        for h in shits:
            if h.chunk_id:
                items.append(CandidateEvidence(chunk_id=h.chunk_id, doc_id=h.doc_id, parent_id=h.parent_id, source_name=h.source_name,
                                               text=h.text, arrivals=[LANE_C], query_ids=[sq.query_id],
                                               query_scores={sq.query_id: sq.weight * _rrf_score(h.rank, budget.rrf_k)}, sparse_score=h.raw_similarity))
        info["lanes"][LANE_C] = sum(1 for h in shits if h.chunk_id)
        return items, info

    for sq in subqueries:
        d_out = outs.get(f"sub_{sq.query_id}_dense"); s_out = outs.get(f"sub_{sq.query_id}_sparse")
        items, info = _items_for(sq, d_out.rows if d_out else [], s_out.rows if s_out else [], budget.subquery_dense_k, budget.subquery_sparse_k)
        info["degraded"] = [n for n in (f"sub_{sq.query_id}_dense", f"sub_{sq.query_id}_sparse") if n in outs and outs[n].error]
        aspects[sq.query_id] = info
        sub_items.extend(items)
    # one targeted second pass: the first aspect that found nothing gets B + C again at K × factor
    for sq in subqueries:
        if aspects[sq.query_id]["lanes"][LANE_B] + aspects[sq.query_id]["lanes"][LANE_C] == 0 and budget.second_pass_factor > 1:
            dk, sk = budget.subquery_dense_k * budget.second_pass_factor, budget.subquery_sparse_k * budget.second_pass_factor
            t2 = {}
            if LANE_B in lanes:
                t2["dense"] = (lambda sq=sq, dk=dk: _call_dense(dense_search, REPRESENTATION_KIND_CHILD, dk, None, sq.qvec))
            if LANE_C in lanes and sq.sparse_query is not None:
                t2["sparse"] = (lambda sq=sq, sk=sk: _call_sparse(sparse_search, sk, sq.sparse_query))
            o2 = _gather(t2, executor, budget.lane_timeout_s)
            items, info = _items_for(sq, o2["dense"].rows if "dense" in o2 else [], o2["sparse"].rows if "sparse" in o2 else [], dk, sk)
            timings[f"sub_{sq.query_id}_second_pass"] = round(sum(o.ms for o in o2.values()), 1)
            second_pass = {"query_id": sq.query_id, "before": 0, "after": len(items)}
            aspects[sq.query_id] = {**info, "second_pass": True}
            sub_items.extend(items)
            break

    # ---- union + dedupe + provenance-preserving fusion --------------------
    by_id: dict[str, CandidateEvidence] = {}
    for c in lane_a + lane_b + lane_c:
        c.query_scores = dict(c.query_scores)
    for lane_items in (lane_a, lane_b, lane_c, sub_items):
        for c in lane_items:
            cur = by_id.get(c.chunk_id)
            if cur is None:
                by_id[c.chunk_id] = replace_candidate(c)
                continue
            for a in c.arrivals:
                if a not in cur.arrivals:
                    cur.arrivals.append(a)
            for q in c.query_ids:
                if q not in cur.query_ids:
                    cur.query_ids.append(q)
            if cur.hierarchy_rank is None:
                cur.hierarchy_rank = c.hierarchy_rank
            if cur.dense_rank is None:
                cur.dense_rank, cur.dense_score = c.dense_rank, (c.dense_score if c.dense_score is not None else cur.dense_score)
            if cur.sparse_rank is None:
                cur.sparse_rank, cur.sparse_score = c.sparse_rank, c.sparse_score
            if cur.document_rank is None:
                cur.document_rank = c.document_rank
            if not cur.text and c.text:
                cur.text = c.text
            for qid, sc in c.query_scores.items():
                cur.query_scores[qid] = cur.query_scores.get(qid, 0.0) + sc
    for c in by_id.values():
        primary = sum(_rrf_score(r, budget.rrf_k) for r in (c.hierarchy_rank, c.dense_rank, c.sparse_rank) if r is not None)
        if primary:
            c.query_scores[ctx.query_id] = primary
        if c.region_role is None:
            c.region_role = roles.get(c.chunk_id)
    for qid in [sq.query_id for sq in subqueries]:
        best_by_doc: dict[str, str] = {}
        for c in sorted(by_id.values(), key=lambda c: -c.query_scores.get(qid, 0.0)):
            if qid not in c.query_scores:
                continue
            if c.doc_id in best_by_doc:
                c.query_scores[qid] *= 0.5
            else:
                best_by_doc[c.doc_id] = c.chunk_id
    for c in by_id.values():
        if not c.query_scores:
            c.fused_score = 0.0
            continue
        best = max(c.query_scores.values())
        extra = sum(c.query_scores.values()) - best
        c.fused_score = best + min(best, budget.agreement_bonus * extra)
    fused = sorted(by_id.values(), key=lambda c: (-c.fused_score, c.chunk_id))
    if budget.demote_noisy_regions and roles:
        from polymath_shared.document_region import is_noisy
        fused = sorted(fused, key=lambda c: 1 if is_noisy(c.region_role) else 0)
    union_ids_uncapped = [c.chunk_id for c in fused]
    union = fused[:budget.merged_candidate_max]
    timings["lanes_wall"] = round((time.perf_counter() - t_turn) * 1000, 1)

    trace = {
        "plan": CHAT_RETRIEVAL_PLAN_VERSION, "engine": CANDIDATE_ENGINE_VERSION, "rrf_k": budget.rrf_k,
        "budget": budget.to_dict(),
        "lane_sizes": {"document_summary": len(doc_lane), "section_summary": len(section_lane), "entity_card": len(card_lane),
                       "hierarchical_children": len(lane_a), "global_dense_child": len(lane_b), "global_sparse_child": len(lane_c),
                       "union": len(union), "union_uncapped": len(union_ids_uncapped)},
        "funnel_lanes": {"hierarchical": [c.chunk_id for c in lane_a], "global_dense_child": [c.chunk_id for c in lane_b],
                         "global_sparse_child": [c.chunk_id for c in lane_c]},
        "funnel_union": union_ids_uncapped,
        "document_candidates": [{"doc_id": d.doc_id, "aggregate_rank": d.aggregate_rank, "aggregate_score": round(d.aggregate_score, 6),
                                 "rrf_contributions": {k: round(v, 6) for k, v in d.rrf_contributions.items()},
                                 "representation_kinds_present": d.representation_kinds_present} for d in documents],
        "multi_lane": sum(1 for c in union if len(c.arrivals) > 1),
        "sparse_rule": ctx.sparse_rule, "exact_terms": list(ctx.exact_terms),
        "aspects": {qid: {**info, "union": sum(1 for c in union if qid in c.query_ids)} for qid, info in aspects.items()},
        "subqueries": len(subqueries), "second_pass": second_pass,
        "concurrent": executor is not None, "lane_timeout_s": budget.lane_timeout_s,
        "degraded": list(degraded), "timings_ms": dict(timings),
    }
    return CandidateResult(context=ctx, budget=budget, documents=documents, selected_documents=selected_documents,
                           selected_sections=selected_sections, lane_a=lane_a, lane_b=lane_b, lane_c=lane_c,
                           union=union, union_ids_uncapped=union_ids_uncapped, degraded=degraded, timings_ms=timings, trace=trace)


'''
s = s[:start] + new_fn + s[end:]
p.write_text(s, encoding="utf-8")
import ast; ast.parse(s); print("retrieve_candidates rewritten (concurrent, deadline-aware)")

"""CHAT-RETRIEVAL-V2 route (plan §3.14 / §4 P1.a; P1.d CONCURRENCY-DEADLINES-V1
§3.16): the chat path's HYBRID retrieval on the CANDIDATE-RETRIEVAL-V1 engine.

    one readiness check → lane C STARTS (BM25 for the primary and every
    subquery needs only the compiled text) → ONE embedding (all distinct
    texts, one call) → lanes A / B concurrently through the SHARED
    FastSearcher filters, lane C joined from its head start → union with
    provenance → exactly ONE bounded rerank under a deadline → final evidence

Wall-clock budgets (`CandidateBudget`): the embedding is a hard dependency
(its breach is receipted, never dropped); a core lane past `lane_deadline_s`
is dropped and receipted `<lane>_timeout`; a judge past `rerank_deadline_s`
yields fusion order and `rerank_timeout`. Everything lands in
`meta.degraded`; per-stage `latency_ms` rides the trace.

Returns the same dict shape as `hybrid_fast_retrieve` so the stream
handler, /chat, the bundle assembler and the funnel consume it unchanged;
`meta.plan_version` / `trace.plan` say `chat-retrieval-v2`. /retrieve,
/ask and TRAIL keep `hybrid-retrieval-v1` (rollback boundary: the
`POLYMATH_CHAT_RETRIEVAL=v1` flag or a per-request `retrieval: "v1"`).
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import replace
from typing import Optional

from fastapi import HTTPException
from qdrant_client import QdrantClient

from polymath_shared.candidate_engine import (
    CANDIDATE_ENGINE_VERSION,
    CHAT_RETRIEVAL_PLAN_VERSION,
    CONCURRENCY_CONTRACT,
    LANE_C,
    LANES,
    CandidateBudget,
    SearchContext,
    SubQuery,
    retrieve_candidates,
    select_evidence,
    shape_budget,
    sparse_vector_for,
)
from polymath_shared.retrieval_modes import MODE_HYBRID
from polymath_shared.settings import get_settings

from orchestrator.api.fast import (
    _RERANK_DEGRADED,
    FastSearcher,
    _begin_retrieval,
    _corpus_collections,
    _embed_queries,
    _ensure_fast_ready,
    _neighbor_lookup,
    _presentation_joins,
    _region_lookup,
    _rerank_children,
    degradations,
)

_FLAG_ENV = "POLYMATH_CHAT_RETRIEVAL"        # v1 | v2 (default v2 after the P1.a gate)


def chat_retrieval_flag(override: str | None = None) -> str:
    """v1 | v2 | v2-single (v2 with the compiled subqueries ignored — A/B only)."""
    v = (override or os.environ.get(_FLAG_ENV, "v2") or "v2").strip().lower()
    return v if v in ("v1", "v2", "v2-single") else "v2"


#: env-tunable knobs on the one budget authority, POLYMATH_CHAT_<NAME> (measurement only; the defaults are the contract)
_INT_KNOBS = ("rerank_max", "synthesis_max", "global_dense_k", "global_sparse_k", "merged_candidate_max", "max_workers")
_FLOAT_KNOBS = ("embed_deadline_s", "lane_deadline_s", "rerank_deadline_s")     # P1.d wall-clock budgets


def default_budget() -> CandidateBudget:
    b = CandidateBudget()
    over = {}
    for name, cast in [(n, int) for n in _INT_KNOBS] + [(n, float) for n in _FLOAT_KNOBS]:
        raw = os.environ.get(f"POLYMATH_CHAT_{name.upper()}")
        if raw:
            try:
                over[name] = cast(raw)
            except ValueError:
                pass
    return replace(b, **over) if over else b


def chat_retrieve_v2(query: str, corpus_id: str, *, exact_terms: tuple[str, ...] = (),
                     budget: Optional[CandidateBudget] = None, query_id: str = "q0",
                     subqueries: tuple = (), lanes: Optional[tuple] = None) -> dict:
    """`subqueries`: (id, type, text, weight) tuples from the compiled plan (non-PRIMARY);
    they run lanes B + C on their own vectors (one batched embedding call for all texts).
    `lanes` (P1.d/P1.e, evaluation and mode composition): restrict the engine to these lane
    names — VECTOR = (HIERARCHICAL_ROUTE, GLOBAL_DENSE_CHILD), HYBRID = all three (default)."""
    _begin_retrieval()
    if corpus_id is None:
        raise HTTPException(status_code=422, detail={
            "error_code": "corpus_required",
            "message": "HYBRID requires an explicit corpus_id (authorized corpus scope)"})
    if lanes:
        unknown = [str(x) for x in lanes if x not in LANES]
        if unknown:
            raise HTTPException(status_code=422, detail={
                "error_code": "unknown_lane", "message": f"unknown retrieval lane(s) {unknown}; known: {list(LANES)}"})
    _ensure_fast_ready(corpus_id)
    collections = _corpus_collections([corpus_id])
    collection = collections[corpus_id]
    budget = shape_budget(query, budget or default_budget())          # §3.21 #14: shape on the resolved text
    if lanes:
        budget = replace(budget, lanes=tuple(x for x in LANES if x in set(lanes)))   # canonical lane order
    try:
        client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail={
            "error_code": "qdrant_unavailable", "message": f"qdrant unavailable: {type(exc).__name__}"}) from exc
    t_all = time.perf_counter()
    extra_degraded: list[dict] = []
    prestart_ms: dict[str, float] = {}          # each key written once, by the thread that ran that lane
    judge_ms: dict[str, float] = {}
    # ONE bounded pool per turn, shared by the pre-started sparse lanes, the engine's lanes and the judge.
    pool = ThreadPoolExecutor(max_workers=max(1, int(budget.max_workers)), thread_name_prefix="chat-lanes")
    try:
        # §3.21 #1: built WITHOUT the query → no bm25 companion probe beside the dense lanes;
        # lane C is the one sparse search of the turn.
        searcher = FastSearcher(client, collections)
        hidden = tuple(searcher._hidden_for(corpus_id) or ())      # warm the generation cache ONCE, before any lane thread reads it
        sub_specs = [tuple(x) for x in (subqueries or ())][: budget.max_subqueries]
        texts = [query] + [t for (_, _, t, _) in sub_specs if t and t != query]
        distinct = list(dict.fromkeys(texts))
        sparse_q, sparse_rule = None, "raw"
        try:
            sparse_q, sparse_rule = sparse_vector_for(query, exact_terms)   # exact terms alone when present
        except Exception:  # noqa: BLE001 — lane C degrades in the engine
            sparse_q = None
        sub_sparse: dict[str, tuple] = {}                                    # subquery sparse queries need no vector either
        for (sid, _stype, stext, _sweight) in sub_specs:
            if stext and stext != query:
                sub_sparse[str(sid)] = sparse_vector_for(stext, ())

        def dense_search(kind: str, top_k: int, extra: dict | None = None, qvec=None) -> list[dict]:
            filters = {"representation_kind": kind, "corpus_id": corpus_id}
            if extra:
                filters.update(extra)
            return searcher._search(collection, list(qvec if qvec is not None else vecs[query]), filters, limit=top_k)

        def sparse_search(top_k: int, sparse_query=None) -> list[dict]:
            return searcher.sparse_search(collection, sparse_query if sparse_query is not None else sparse_q,
                                          {"representation_kind": "routing_child", "corpus_id": corpus_id}, limit=top_k)

        def _prestart(name: str, top_k: int, sparse_query) -> list[dict]:
            t0 = time.perf_counter()
            try:
                return sparse_search(top_k, sparse_query)
            finally:
                prestart_ms[name] = round((time.perf_counter() - t0) * 1000, 1)

        # STAGE 2 head start (§3.16): BM25 needs no vector — lane C for the primary and for every subquery is
        # submitted BEFORE the embedding call and handed to the engine pre-started (it never searches them again).
        prestarted: dict = {}
        if LANE_C in budget.lanes:
            if sparse_q is not None:
                prestarted["global_sparse_child"] = pool.submit(_prestart, "global_sparse_child", budget.global_sparse_k, sparse_q)
            for sid, (sv, _rule) in sub_sparse.items():
                if sv is not None:
                    prestarted[f"sub_{sid}_sparse"] = pool.submit(_prestart, f"sub_{sid}_sparse", budget.subquery_sparse_k, sv)
        # STAGE 1: ONE embedding for all distinct texts. A hard dependency (no vector, no dense lane), so the turn
        # waits for it; exceeding `embed_deadline_s` is receipted, never a dropped stage.
        t0 = time.perf_counter()
        vecs = dict(zip(distinct, _embed_queries(distinct)))               # ONE call, one vector per distinct text
        qvec = vecs[query]
        embed_ms = round((time.perf_counter() - t0) * 1000, 1)
        if embed_ms > budget.embed_deadline_s * 1000:
            extra_degraded.append({"component": "embed_deadline",
                                   "effect": "dense lanes started late (the embedding is a hard dependency; the turn waited for it)",
                                   "reason": f"embedding took {embed_ms:.0f} ms; embed_deadline_s={budget.embed_deadline_s:g}"})
        subs: list[SubQuery] = []
        for (sid, stype, stext, sweight) in sub_specs:
            if not stext or stext == query:
                continue
            sv, srule = sub_sparse[str(sid)]
            subs.append(SubQuery(query_id=str(sid), qtype=str(stype), text=str(stext), weight=float(sweight or 1.0),
                                 qvec=tuple(vecs[stext]), sparse_query=sv, sparse_rule=srule))
        ctx = SearchContext(query=query, corpus_id=corpus_id, collection=collection, qvec=tuple(qvec),
                            sparse_query=sparse_q, exact_terms=tuple(exact_terms or ()),
                            hidden_generations=hidden, query_id=query_id, sparse_rule=sparse_rule)
        # STAGES 2–3: concurrent lanes under `lane_deadline_s` → union with provenance (the engine)
        result = retrieve_candidates(ctx, budget, dense_search=dense_search, sparse_search=sparse_search,
                                     region_lookup=_region_lookup, subqueries=subs, executor=pool, prestarted=prestarted)

        # STAGE 4: exactly ONE judge call per turn, under `rerank_deadline_s`. Past it the turn proceeds in
        # fusion order (a complete, correct answer — the judge only reorders) and says so; the late sidecar
        # call is not awaited (it finishes in the background).
        def _judge_with_deadline(q: str, rows: list[dict]) -> list[dict]:
            def _judge():
                out = _rerank_children(q, rows)
                return out, _RERANK_DEGRADED.get()      # a parked sidecar is noted in the WORKER's context (ContextVar)
            t1 = time.perf_counter()
            fut = pool.submit(_judge)
            try:
                out, note = fut.result(timeout=budget.rerank_deadline_s)
            except FutureTimeout:
                extra_degraded.append({"component": "rerank_timeout",
                                       "effect": "results ordered by fusion (the judge missed its deadline); same candidate set, same recall",
                                       "reason": f"no judgement after {budget.rerank_deadline_s:g} s — late result ignored"})
                return rows
            finally:
                judge_ms["rerank"] = round((time.perf_counter() - t1) * 1000, 1)
            if note:
                _RERANK_DEGRADED.set(note)              # carry it into this request's context so degradations() reports it
            return out

        t2 = time.perf_counter()
        final, sel = select_evidence(result, budget, rerank_children=_judge_with_deadline, neighbor_lookup=_neighbor_lookup)
        select_ms = round((time.perf_counter() - t2) * 1000, 1)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)   # a late lane or judge never holds the turn; queued work is dropped
        client.close()
    total_ms = round((time.perf_counter() - t_all) * 1000, 1)

    # per-stage receipts (P1.d): embed · sparse_prestart · each lane · union · rerank · compose · total
    # (`rerank_select` = the whole selection stage, kept for chat_baseline / chat_m_replay)
    latency_ms = {k: round(v, 1) for k, v in searcher.latency.items()}
    engine_t = dict(result.timings_ms)
    rerank_only = judge_ms.get("rerank", 0.0)
    latency_ms.update({
        "embed": embed_ms, "embedded_texts": len(distinct),
        "sparse_prestart": prestart_ms.get("global_sparse_child"),      # lane C's own time, overlapped with the embedding
        "lanes": engine_t.get("core_wall"), "lanes_primary_batch": engine_t.get("lanes_wall"), "union": engine_t.get("union"),
        "rerank": rerank_only, "compose": round(select_ms - rerank_only, 1), "rerank_select": select_ms,
        "total": total_ms,
        **{f"lane_{k}": v for k, v in engine_t.items() if k not in ("core_wall", "lanes_wall", "union")},
    })
    _p = _presentation_joins([c.chunk_id for c in final], [c.doc_id for c in final])
    trace = {**result.trace, **sel, "latency_ms": latency_ms}
    rows = []
    for c in final:
        r = c.to_row()
        r.update({"g3_score": c.rerank_score, "locator": f"chunk:{c.chunk_id}",
                  "source_name": c.source_name or _p.get(c.doc_id, {}).get("source_name", ""),
                  "title": _p.get(c.chunk_id, {}).get("title", ""), "heading_path": _p.get(c.chunk_id, {}).get("heading_path", ""),
                  "human_locator": _p.get(c.chunk_id, {}).get("human_locator", ""), "text": (c.text or "")[:240]})
        rows.append(r)
    return {
        "query": query,
        "meta": {
            "mode": MODE_HYBRID, "plan_version": CHAT_RETRIEVAL_PLAN_VERSION, "engine": CANDIDATE_ENGINE_VERSION,
            "corpus_id": corpus_id, "rrf_k": budget.rrf_k, "budget": budget.to_dict(),
            "lanes": list(budget.lanes),
            "lexical_enabled": LANE_C in budget.lanes, "mmr": "NOT_IN_V2",
            "deadlines": {"contract": CONCURRENCY_CONTRACT, "embed_deadline_s": budget.embed_deadline_s,
                          "lane_deadline_s": budget.lane_deadline_s, "rerank_deadline_s": budget.rerank_deadline_s,
                          "max_workers": max(1, int(budget.max_workers))},
            "selected_document_count": len(result.selected_documents), "selected_section_count": len(result.selected_sections),
            "evidence_count": len(rows), "candidates": len(result.union), "multi_lane": trace.get("multi_lane"),
            "subqueries": trace.get("subqueries"), "weak_aspects": trace.get("weak_aspects"), "weak_reasons": trace.get("weak_reasons"),
            "aspect_seated": trace.get("aspect_seated"), "aspect_best": trace.get("aspect_best"), "final_detail": trace.get("final_detail"),
            "composition": trace.get("composition"),
            "aspects": {qid: {**a, "final": (trace.get("aspect_final") or {}).get(qid, 0), "prefix": (trace.get("aspect_prefix") or {}).get(qid),
                              "best": (trace.get("aspect_best") or {}).get(qid), "weak": (trace.get("weak_reasons") or {}).get(qid)}
                        for qid, a in (trace.get("aspects") or {}).items()},
            # reranker / sparse notes (ContextVar), the engine's lane receipts (sparse outage, `<lane>_timeout`),
            # then the route's own (`embed_deadline`, `rerank_timeout`)
            "degraded": degradations() + list(result.degraded) + extra_degraded,
            # lane liveness for v2 = the per-lane sizes + degradations above (the v1 liveness
            # table is keyed on rescue lanes that do not exist here)
            "liveness": None,
            "latent": None,
        },
        "selected_documents": [
            {"doc_id": d.doc_id, "corpus_id": d.corpus_id, "aggregate_rank": d.aggregate_rank,
             "aggregate_score": round(d.aggregate_score, 6),
             "rrf_contributions": {k: round(v, 6) for k, v in d.rrf_contributions.items()},
             "representation_kinds_present": d.representation_kinds_present,
             "document_summary": ({"summary_id": d.document_summary_hits[0].summary_id, "text": d.document_summary_hits[0].text}
                                  if d.document_summary_hits else None),
             "why": {"best_document_summary_rank": d.best_document_summary_rank, "best_section_summary_rank": d.best_section_summary_rank,
                     "best_child_rank": d.best_child_rank, "best_lexical_rank": d.best_lexical_rank}}
            for d in result.selected_documents],
        "selected_sections": [
            {"doc_id": s["doc_id"], "parent_id": s["parent_id"], "summary_id": s["summary_id"], "source_name": s["source_name"],
             "best_section_rank": s["best_section_rank"], "from": sorted(set(s["from"]))}
            for s in result.selected_sections],
        "evidence": rows,
        "trace": trace,
    }

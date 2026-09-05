"""CHAT-RETRIEVAL-V2 route (plan §3.14 / §4 P1.a): the chat path's HYBRID
retrieval on the CANDIDATE-RETRIEVAL-V1 engine.

    one readiness check → one embedding → one sparse tokenization →
    lanes A / B / C through the SHARED FastSearcher filters → union with
    provenance → one bounded rerank → final evidence

Returns the same dict shape as `hybrid_fast_retrieve` so the stream
handler, /chat, the bundle assembler and the funnel consume it unchanged;
`meta.plan_version` / `trace.plan` say `chat-retrieval-v2`. /retrieve,
/ask and TRAIL keep `hybrid-retrieval-v1` (rollback boundary: the
`POLYMATH_CHAT_RETRIEVAL=v1` flag or a per-request `retrieval: "v1"`).
"""
from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import HTTPException
from qdrant_client import QdrantClient

from polymath_shared.candidate_engine import (
    CANDIDATE_ENGINE_VERSION,
    CHAT_RETRIEVAL_PLAN_VERSION,
    CandidateBudget,
    SearchContext,
    retrieve_candidates,
    select_evidence,
    shape_budget,
    sparse_vector_for,
)
from polymath_shared.retrieval_modes import MODE_HYBRID
from polymath_shared.settings import get_settings

from orchestrator.api.fast import (
    FastSearcher,
    _begin_retrieval,
    _corpus_collections,
    _embed_query,
    _ensure_fast_ready,
    _neighbor_lookup,
    _presentation_joins,
    _region_lookup,
    _rerank_children,
    degradations,
)

_FLAG_ENV = "POLYMATH_CHAT_RETRIEVAL"        # v1 | v2 (default v2 after the P1.a gate)


def chat_retrieval_flag(override: str | None = None) -> str:
    v = (override or os.environ.get(_FLAG_ENV, "v2") or "v2").strip().lower()
    return v if v in ("v1", "v2") else "v2"


def default_budget() -> CandidateBudget:
    """Env-tunable knobs on the one budget authority (measurement only;
    the defaults are the contract)."""
    b = CandidateBudget()
    over = {}
    for name in ("rerank_max", "synthesis_max", "global_dense_k", "global_sparse_k", "merged_candidate_max"):
        raw = os.environ.get(f"POLYMATH_CHAT_{name.upper()}")
        if raw:
            try:
                over[name] = int(raw)
            except ValueError:
                pass
    from dataclasses import replace
    return replace(b, **over) if over else b


def chat_retrieve_v2(query: str, corpus_id: str, *, exact_terms: tuple[str, ...] = (),
                     budget: Optional[CandidateBudget] = None, query_id: str = "q0") -> dict:
    _begin_retrieval()
    if corpus_id is None:
        raise HTTPException(status_code=422, detail={
            "error_code": "corpus_required",
            "message": "HYBRID requires an explicit corpus_id (authorized corpus scope)"})
    _ensure_fast_ready(corpus_id)
    collections = _corpus_collections([corpus_id])
    collection = collections[corpus_id]
    budget = shape_budget(query, budget or default_budget())          # §3.21 #14: shape on the resolved text
    try:
        client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail={
            "error_code": "qdrant_unavailable", "message": f"qdrant unavailable: {type(exc).__name__}"}) from exc
    t_all = time.perf_counter()
    try:
        # §3.21 #1: built WITHOUT the query → no bm25 companion probe beside the dense lanes;
        # lane C is the one sparse search of the turn.
        searcher = FastSearcher(client, collections)
        t0 = time.perf_counter()
        qvec = _embed_query(query)                                        # the ONE embedding
        embed_ms = round((time.perf_counter() - t0) * 1000, 1)
        sparse_q, sparse_rule = None, "raw"
        try:
            sparse_q, sparse_rule = sparse_vector_for(query, exact_terms)   # exact terms alone when present
        except Exception:  # noqa: BLE001 — lane C degrades in the engine
            sparse_q = None
        ctx = SearchContext(query=query, corpus_id=corpus_id, collection=collection, qvec=tuple(qvec),
                            sparse_query=sparse_q, exact_terms=tuple(exact_terms or ()),
                            hidden_generations=tuple(searcher._hidden_for(corpus_id) or ()), query_id=query_id,
                            sparse_rule=sparse_rule)

        def dense_search(kind: str, top_k: int, extra: dict | None = None) -> list[dict]:
            filters = {"representation_kind": kind, "corpus_id": corpus_id}
            if extra:
                filters.update(extra)
            return searcher._search(collection, list(qvec), filters, limit=top_k)

        def sparse_search(top_k: int) -> list[dict]:
            return searcher.sparse_search(collection, sparse_q, {"representation_kind": "routing_child", "corpus_id": corpus_id}, limit=top_k)

        result = retrieve_candidates(ctx, budget, dense_search=dense_search, sparse_search=sparse_search, region_lookup=_region_lookup)
        t1 = time.perf_counter()
        final, sel = select_evidence(result, budget, rerank_children=_rerank_children, neighbor_lookup=_neighbor_lookup)
        rerank_ms = round((time.perf_counter() - t1) * 1000, 1)
    finally:
        client.close()
    total_ms = round((time.perf_counter() - t_all) * 1000, 1)

    latency_ms = {k: round(v, 1) for k, v in searcher.latency.items()}
    latency_ms.update({"embed": embed_ms, "rerank_select": rerank_ms, "total": total_ms, **{f"lane_{k}": v for k, v in result.timings_ms.items()}})
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
            "lexical_enabled": "GLOBAL_SPARSE_CHILD" in budget.lanes, "mmr": "NOT_IN_V2",
            "selected_document_count": len(result.selected_documents), "selected_section_count": len(result.selected_sections),
            "evidence_count": len(rows), "candidates": len(result.union), "multi_lane": trace.get("multi_lane"),
            "degraded": degradations() + list(result.degraded),
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

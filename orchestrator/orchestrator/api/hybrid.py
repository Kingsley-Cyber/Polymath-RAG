"""R1D HYBRID production route (orchestrator-owned HTTP reads).

HYBRID = FAST + lexical + (MMR rejected by R1D qualification — the
promoted plan is lambda 1.0, relevance-only). Reuses the FAST service
primitives and the shared hybrid engine; one HYBRID result feeds
/retrieve, /evidence, and /chat.

Lexical failure semantics: the lexical subsystem is an in-memory
corpus scan over Postgres; if Postgres rows are unavailable the
request fails loudly (never silently degrades HYBRID to FAST).
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from fastapi import HTTPException
from qdrant_client import QdrantClient

from polymath_shared.db import tx
from polymath_shared.hybrid import HybridRetrievalPlan, hybrid_retrieve
from polymath_shared.pass1 import LaneHit
from polymath_shared.retrieval import lexical_score
from polymath_shared.retrieval_modes import MODE_HYBRID, hybrid_mode_plan
from polymath_shared.settings import get_settings

from polymath_shared.query_shape import plan_for_query

from orchestrator.api.fast import (
    _begin_retrieval,
    _embed_query,
    _ensure_fast_ready,
    _neighbor_lookup,
    _region_lookup,
    _liveness,
    _rerank_children,
    _corpus_collections,
    degradations,
    FastSearcher,
)


def _sparse_lexical_search(query: str, corpus_id: str, top_k: int) -> list[LaneHit]:
    """SPARSE-BM25 child lexical lane (§11.6): query the routing
    collection's named `bm25` sparse vector with the SHARED tokenizer —
    server-side IDF scoring over the augmented index text (chunk text +
    attested entity surfaces + parent head). Raises on any shortfall so
    the caller can fall back to the in-memory scan (legacy dense-only
    collections)."""
    from qdrant_client.models import (
        FieldCondition, Filter, MatchValue, SparseVector,
    )
    from polymath_shared.sparse_bm25 import SPARSE_VECTOR_NAME, sparse_vector

    idx, vals = sparse_vector(query)
    if not idx:
        return []
    collections = _corpus_collections([corpus_id])
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=30)
    try:
        out: list[LaneHit] = []
        flt = Filter(must=[
            FieldCondition(key="representation_kind",
                           match=MatchValue(value="routing_child")),
            FieldCondition(key="corpus_id", match=MatchValue(value=corpus_id)),
        ])
        for collection in collections:
            pts = client.query_points(
                collection_name=collection,
                query=SparseVector(indices=idx, values=vals),
                using=SPARSE_VECTOR_NAME,
                query_filter=flt,
                limit=top_k,
                with_payload=True,
            ).points
            for i, p in enumerate(pts):
                pl = p.payload or {}
                out.append(LaneHit(
                    representation_kind="child_lexical", rank=i,
                    raw_similarity=float(p.score or 0.0), corpus_id=corpus_id,
                    doc_id=pl.get("doc_id", ""),
                    parent_id=pl.get("parent_id", ""),
                    chunk_id=pl.get("chunk_id", ""),
                    summary_id="", source_name=pl.get("source_name", ""),
                    text=pl.get("text", ""),
                ))
        out.sort(key=lambda h: (-h.raw_similarity, h.chunk_id))
        for i, h in enumerate(out):
            h.rank = i
        return out[:top_k]
    finally:
        client.close()


def _lexical_search(query: str, corpus_id: str, top_k: int) -> list[LaneHit]:
    """HYBRID child lexical lane: BM25 sparse first (§11.6 — uses the
    projected index, exact-name recall on the augmented text); the
    in-memory `lexical_score` scan remains the fallback for legacy
    dense-only collections."""
    try:
        hits = _sparse_lexical_search(query, corpus_id, top_k)
        if hits:
            return hits
    except Exception:
        pass  # legacy collection without the bm25 vector: fall through
    with tx() as conn:
        rows = conn.execute(
            """
            SELECT ch.chunk_id, ch.doc_id, ch.parent_id, ch.text
              FROM chunks ch
              JOIN documents d ON d.doc_id = ch.doc_id
             WHERE d.corpus_id = %s AND ch.tier = 'child'
            """,
            (corpus_id,),
        ).fetchall()
    scored = []
    for chunk_id, doc_id, parent_id, text in rows:
        s = lexical_score(query, text)
        if s > 0:
            scored.append((s, chunk_id, doc_id, parent_id, text))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [
        LaneHit(
            representation_kind="child_lexical", rank=i,
            raw_similarity=s, corpus_id=corpus_id, doc_id=doc_id,
            parent_id=parent_id, chunk_id=chunk_id,
            summary_id="", source_name="", text=text,
        )
        for i, (s, chunk_id, doc_id, parent_id, text) in enumerate(scored[:top_k])
    ]


def hybrid_fast_retrieve(
    query: str,
    corpus_id: str,
    plan: Optional[HybridRetrievalPlan] = None,
) -> dict:
    """Production HYBRID: one qualified hybrid execution."""
    _begin_retrieval()
    plan = plan or hybrid_mode_plan(MODE_HYBRID)
    if corpus_id is None:
        raise HTTPException(status_code=422, detail={
            "error_code": "corpus_required",
            "message": "HYBRID requires an explicit corpus_id (authorized corpus scope)",
        })

    _ensure_fast_ready(corpus_id)

    collections = _corpus_collections([corpus_id])
    try:
        client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "error_code": "qdrant_unavailable",
            "message": f"qdrant unavailable: {type(exc).__name__}",
        }) from exc
    try:
        searcher = FastSearcher(client, collections, query=query)
        t0 = time.time()
        shaped = plan_for_query(
            query,
            HybridRetrievalPlan(**{**plan.__dict__, "corpus_ids": (corpus_id,)}),
        )
        result = hybrid_retrieve(
            query,
            plan=shaped,
            embed_query=_embed_query,
            routing_search=searcher,
            lexical_search=lambda q, k: _lexical_search(q, corpus_id, k),
            rerank_children=_rerank_children if shaped.rerank_enabled else None,
            summary_vectors=None,  # MMR rejected; lambda 1.0 promoted
            neighbor_lookup=_neighbor_lookup,
            region_lookup=_region_lookup,
        )
        total_ms = (time.time() - t0) * 1000
    finally:
        client.close()

    latency_ms = {k: round(v, 1) for k, v in searcher.latency.items()}
    latency_ms["total"] = round(total_ms, 1)
    return {
        "query": query,
        "meta": {
            "mode": MODE_HYBRID,
            "plan_version": result.plan.plan_version,
            "corpus_id": corpus_id,
            "rrf_k": result.plan.rrf_k,
            "lexical_enabled": result.plan.lexical_enabled,
            "mmr": "REJECTED_BY_R1D" if not result.plan.mmr_enabled else result.plan.mmr_lambda,
            "selected_document_count": len(result.selected_documents),
            "selected_section_count": len(result.selected_sections),
            "evidence_count": len(result.final_evidence),
            "degraded": degradations(),
            "liveness": _liveness(result.trace, MODE_HYBRID),
        },
        "selected_documents": [
            {
                "doc_id": d.doc_id,
                "corpus_id": d.corpus_id,
                "aggregate_rank": d.aggregate_rank,
                "aggregate_score": round(d.aggregate_score, 6),
                "rrf_contributions": {k: round(v, 6) for k, v in d.rrf_contributions.items()},
                "representation_kinds_present": d.representation_kinds_present,
                "document_summary": {
                    "summary_id": d.document_summary_hits[0].summary_id,
                    "text": d.document_summary_hits[0].text,
                } if d.document_summary_hits else None,
                "why": {
                    "best_document_summary_rank": d.best_document_summary_rank,
                    "best_section_summary_rank": d.best_section_summary_rank,
                    "best_child_rank": d.best_child_rank,
                    "best_lexical_rank": d.best_lexical_rank,
                },
            }
            for d in result.selected_documents
        ],
        "selected_sections": [
            {
                "doc_id": s["doc_id"],
                "parent_id": s["parent_id"],
                "summary_id": s["summary_id"],
                "source_name": s["source_name"],
                "best_section_rank": s["best_section_rank"],
                "from": sorted(set(s["from"])),
            }
            for s in result.selected_sections
        ],
        "evidence": [
            {
                "chunk_id": c["chunk_id"],
                "doc_id": c["doc_id"],
                "parent_id": c["parent_id"],
                "source_name": c["source_name"],
                "arrival": c.get("arrival"),
                "document_rank": c.get("document_rank"),
                "g3_score": c.get("rerank_score"),
                "locator": f"chunk:{c['chunk_id']}",
            }
            for c in result.final_evidence
        ],
        "trace": {
            "lane_sizes": result.trace["lane_sizes"],
            "pre_g3_order": result.trace["pre_g3_order"],
            "post_g3_order": result.trace["post_g3_order"],
            "latency_ms": latency_ms,
        },
    }

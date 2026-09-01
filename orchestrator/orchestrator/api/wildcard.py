"""WILDCARD mode service (DIVERGENT-RETRIEVAL-V1, owner-blessed
2026-09-01): the answer evidence comes from FAST — untouched, wildcard
NEVER displaces it — and the `wildcard` lane carries at most three
source-grounded frontier bridges from the latent surfaces. All
retrieval logic lives in polymath_shared.divergent; this module only
wires the live stores and the cross-encoder in."""
from __future__ import annotations

from fastapi import HTTPException

from polymath_shared.divergent import (
    DIVERGENT_DEFAULT_PLAN,
    divergent_retrieve,
)


def wildcard_retrieve(query: str, corpus_id: str) -> dict:
    from qdrant_client import QdrantClient

    from polymath_shared.settings import get_settings
    from orchestrator.api.fast import FastSearcher, fast_retrieve
    from orchestrator.api.hybrid import (
        _corpus_collections,
        _embed_query,
        _rerank_children,
    )

    if corpus_id is None:
        raise HTTPException(status_code=422, detail={
            "error_code": "corpus_required",
            "message": "WILDCARD requires an explicit corpus_id"})

    # 1. the ANSWER: plain FAST — also defines the obvious neighborhood
    fast = fast_retrieve(query, [corpus_id])
    evidence = fast.get("evidence") or []
    baseline = {
        "doc_ids": {e.get("doc_id") for e in evidence if e.get("doc_id")},
        "parent_ids": {e.get("parent_id") for e in evidence
                       if e.get("parent_id")},
        "chunk_ids": {e.get("chunk_id") for e in evidence
                      if e.get("chunk_id")},
    }

    # 2. the FRONTIER
    collections = _corpus_collections([corpus_id])
    coll = collections[corpus_id]
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    try:
        searcher = FastSearcher(client, collections, query=query)

        def _latent_search(kind, qvec, top_k):
            return searcher(coll, qvec, {
                "representation_kind": kind,
                "corpus_id": corpus_id})[:top_k]

        def _children_of(parent_id):
            return searcher(coll, _children_of._qvec, {
                "representation_kind": "routing_child",
                "corpus_id": corpus_id,
                "parent_id": parent_id})

        def _embed(q):
            v = _embed_query(q)
            _children_of._qvec = v
            return v

        def _rerank_pairs(anchor, texts):
            # the cross-encoder stays the sole relevance authority —
            # here it scores (latent surface, source child) support
            cands = [{"chunk_id": str(i), "text": t}
                     for i, t in enumerate(texts)]
            ranked = _rerank_children(anchor, cands)
            by_id = {c["chunk_id"]: c.get("rerank_score")
                     for c in ranked}
            scores = [by_id.get(str(i)) for i in range(len(texts))]
            if any(s is None for s in scores):
                return None
            # the sidecar returns raw cross-encoder logits; squash to
            # 0-1 so the engine's support floor and the multiplicative
            # WildcardValue live on one scale
            import math
            return [1.0 / (1.0 + math.exp(-float(s))) for s in scores]

        out = divergent_retrieve(
            query,
            embed_query=_embed,
            latent_search=_latent_search,
            children_of=_children_of,
            baseline=baseline,
            rerank_pairs=_rerank_pairs,
            plan=DIVERGENT_DEFAULT_PLAN)
    finally:
        client.close()

    meta = dict(fast.get("meta") or {})
    meta["mode"] = "WILDCARD"
    meta["wildcard"] = out["diagnostics"]
    meta["wildcard_plan"] = out["plan"]
    return {**fast, "meta": meta, "wildcard": out["wildcard"]}

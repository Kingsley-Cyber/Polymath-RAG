"""G3: cross-representation reranking over FUSED retrieval candidates.

Candidate integration only (never a production default). The reranker
scores (query, candidate) pairs and reorders the fused document list
and child-evidence list; rank-based RRF fusion upstream is untouched —
the cross-encoder scores are applied ordinally, with no calibrated
weights invented here.

Provenance: every reordered candidate records rerank_score,
reranker model id + revision, and the deterministic rerank version.
The reranker never adds or removes candidates: it only reorders the
set fusion already produced (recall cannot drop).
"""
from __future__ import annotations

from typing import Optional

RERANK_VERSION = "g3-cross-representation-v1"


class RerankUnavailable(RuntimeError):
    """The reranker sidecar could not be reached (caller degrades)."""


def rerank_fused(
    query: str,
    selected_documents: list[dict],
    selected_children: list[dict],
    *,
    client,
) -> tuple[list[dict], list[dict]]:
    """Reorder fused documents and child evidence by cross-encoder score.

    Deterministic given identical (query, candidates, sidecar) — the
    sidecar returns fixed scores per pair. Candidates never appear or
    disappear: ordering only. Each candidate gains rerank provenance.
    """
    doc_ids = [d.get("doc_id") or "" for d in selected_documents]
    doc_surfaces = [d.get("semantic_summary") or "" for d in selected_documents]
    child_ids = [c.get("chunk_id") or "" for c in selected_children]
    child_surfaces = [c.get("text") or "" for c in selected_children]

    reranked_docs = list(selected_documents)
    reranked_children = list(selected_children)

    if doc_surfaces:
        resp = client.rerank(query, doc_surfaces)
        order = resp["order"]
        scores = resp["scores"]
        reranked_docs = [
            dict(selected_documents[i],
                 rerank_score=round(float(scores[i]), 6),
                 rerank_model_id=resp["model_id"],
                 rerank_model_revision=resp["model_revision"],
                 rerank_version=RERANK_VERSION)
            for i in order
        ]

    if child_surfaces:
        resp = client.rerank(query, child_surfaces)
        order = resp["order"]
        scores = resp["scores"]
        reranked_children = [
            dict(selected_children[i],
                 rerank_score=round(float(scores[i]), 6),
                 rerank_model_id=resp["model_id"],
                 rerank_model_revision=resp["model_revision"],
                 rerank_version=RERANK_VERSION)
            for i in order
        ]

    return reranked_docs, reranked_children


def rerank_enabled() -> bool:
    from polymath_shared.settings import get_settings

    return get_settings().sidecars.g3_reranker


def apply_rerank(
    query: str,
    selected_documents: list[dict],
    selected_children: list[dict],
    *,
    client_factory=None,
) -> tuple[list[dict], list[dict]]:
    """Apply reranking when the G3 candidate is enabled; otherwise return
    the fused lists untouched. A sidecar failure degrades loudly to the
    caller (no silent reordering, no silent dropping)."""
    if not rerank_enabled():
        return selected_documents, selected_children
    from polymath_shared.clients import RerankerClient

    client = None
    try:
        client = client_factory() if client_factory else RerankerClient()
        return rerank_fused(
            query, selected_documents, selected_children, client=client,
        )
    except Exception as exc:
        raise RerankUnavailable(f"reranker unavailable: {type(exc).__name__}") from exc
    finally:
        if client is not None:
            client.close()

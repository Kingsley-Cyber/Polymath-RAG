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

#: RERANK-BATCHING-V1 (2026-08-26): one sidecar call carried EVERY
#: candidate surface; on a book corpus the single batch allocated
#: 1.87 GiB and blew the reranker's 3 GiB MPS pool (measured:
#: release-books-v1 GRAPH → 500 → rerank_unavailable). The cross-
#: encoder scores each (query, passage) pair independently, so chunked
#: calls are SCORE-IDENTICAL; the global order is recomputed
#: deterministically from the merged scores (ties by original index).
#: Same remedy class as the embedder's 64-batching (book-scale finding
#: #3). Operational bound only — no scoring semantics change.
RERANK_BATCH_SIZE = 16

#: The batch pads to its LONGEST passage: one pathological 77,125-char
#: chunk (release-books-v1 chunking outlier; corpus p99 = 1,245 chars)
#: forced a ~19k-token sequence and the same 1.87 GiB allocation at
#: ANY batch size. The cross-encoder scores relevance on a bounded
#: prefix; the candidate itself is never altered — this bounds only
#: the scoring input.
RERANK_MAX_SURFACE_CHARS = 4000


class RerankUnavailable(RuntimeError):
    """The reranker sidecar could not be reached (caller degrades)."""


def _slot_alive(name: str) -> bool | None:
    """Best-effort read of the supervisor's slot state; None if unknown."""
    import json
    import os

    path = os.environ.get("POLYMATH_FLEET_STATE",
                          "/tmp/polymath_fleet/supervisor_state.json")
    try:
        with open(path) as fh:
            for slot in json.load(fh).get("slots", []):
                if slot.get("name") == name:
                    return bool(slot.get("alive"))
    except Exception:
        return None
    return None


def _await_reranker(client) -> None:
    """WAKE-ON-QUERY for the reranker (2026-08-27). The autopilot parks
    the reranker when demand ends, and its measured cold start is
    ~60 s — the first query after idle found a dead socket and failed
    typed (`rerank_unavailable ... Connection refused`) while the query
    itself was the wake trigger. Block for the wake: autopilot
    reconcile ≤15 s + ~60 s cold start fits the 90 s budget.

    NO POINTLESS WAITING: the reranker and GLiNER cannot coexist inside
    the memory ceiling, so while extraction is running the autopilot
    will NEVER wake the reranker. Waiting the full budget there buys a
    slower path to the same degraded answer — so when GLiNER holds the
    ceiling and the reranker is parked, return immediately and let the
    caller degrade to fusion order."""
    import os
    import time

    if client.ready():
        return
    if _slot_alive("sidecar_reranker") is False and _slot_alive("sidecar_gliner"):
        # Extraction owns the ceiling; no wake is coming. Skip both the
        # budget AND the client's own retry backoff — the caller
        # degrades to fusion order either way.
        raise RerankUnavailable(
            "reranker parked while extraction holds the memory ceiling; "
            "no wake is scheduled")
    budget = float(os.environ.get("POLYMATH_RERANK_WAKE_BUDGET_S", "90"))
    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        time.sleep(2.0)
        if client.ready():
            return


def _batched_scores(client, query: str, surfaces: list[str]) -> dict:
    """Score all surfaces in bounded batches; merge into one response
    shape (order recomputed globally, deterministic)."""
    scores: list[float] = []
    model_id = model_revision = None
    surfaces = [(s or "")[:RERANK_MAX_SURFACE_CHARS] for s in surfaces]
    for i in range(0, len(surfaces), RERANK_BATCH_SIZE):
        resp = client.rerank(query, surfaces[i:i + RERANK_BATCH_SIZE])
        scores.extend(float(s) for s in resp["scores"])
        model_id = resp["model_id"]
        model_revision = resp["model_revision"]
    order = sorted(range(len(surfaces)), key=lambda j: (-scores[j], j))
    return {"order": order, "scores": scores,
            "model_id": model_id, "model_revision": model_revision}


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
        resp = _batched_scores(client, query, doc_surfaces)
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
        resp = _batched_scores(client, query, child_surfaces)
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
        if client_factory is None:
            _await_reranker(client)
        return rerank_fused(
            query, selected_documents, selected_children, client=client,
        )
    except RerankUnavailable:
        raise  # already typed and messaged (e.g. the no-wake shortcut)
    except Exception as exc:
        # Carry the MESSAGE, not just the type. `reranker unavailable:
        # AttributeError` was the only symptom of a client that could not
        # call its own method, and it named neither the attribute nor the
        # class -- turning a one-line fix into an investigation.
        raise RerankUnavailable(
            f"reranker unavailable: {type(exc).__name__}: {exc}") from exc
    finally:
        if client is not None:
            client.close()

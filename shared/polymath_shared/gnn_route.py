"""GNN-RETRIEVAL-V1 — the query-time half of the experimental graph-neural PARENT route (docs/wiki/plans/GNN-RETRIEVAL-V1.md).

LAW: **the GNN routes, ORIGINAL children prove, the existing reranker judges.** Nothing here is evidence: a GNN vector is never
a citation, a GNN score is never factual confidence. This module returns PARENT nominations (routing metadata only) and hydrates
them through the caller's EXISTING original-child search; the candidate engine unions those children LAST with the arrival
`GNN_ROUTE`, and the same cross-encoder judges them beside every other lane.

Offline half (graph snapshot → propagation / shallow GNN → isolated Qdrant collection): `eval/gnn_route/`. The two halves meet
on ONE contract: the collection name (`collection_name`), the payload (`PAYLOAD_KIND`, `gnn_contract`, `graph_snapshot_id`,
`model_digest`) and the vector dimension, which MUST equal the live embedding contract's — a mismatch is a typed refusal, never a
silent fallback. Pure: no store client is created here (the caller passes its Qdrant client and its child search).
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable, Mapping, Sequence
from polymath_shared.code.scope import scope_kwargs  # K1: pass a role scope only when it narrows

#: bump when the routing contract (payload, naming, hydration rule) changes — NOT when a model is retrained (that is `model_digest`)
GNN_ROUTE_CONTRACT = "gnn-route-v1"
PAYLOAD_KIND = "experimental_gnn_parent"
ARRIVAL = "GNN_ROUTE"
COLLECTION_PREFIX = "polymath_gnn_parent"
#: the experiment arms — each is its OWN isolated collection (the production parent-MAP collection is never written)
VARIANT_REAL, VARIANT_NOGRAPH, VARIANT_SHUFFLED = "real", "nograph", "shuffled"
VARIANTS = (VARIANT_REAL, VARIANT_NOGRAPH, VARIANT_SHUFFLED)
#: the model families the offline builder can project (`gnn_contract` = f"{family}-{variant}")
FAMILY_M0, FAMILY_M1, FAMILY_M2 = "m0-identity", "m1-smooth", "m2-hsage"
DEFAULT_FAMILY = os.environ.get("POLYMATH_GNN_FAMILY", FAMILY_M1)


class GnnRouteRefused(RuntimeError):
    """A typed refusal (never a fallback): the experimental collection does not match the live contract."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def gnn_contract(family: str = DEFAULT_FAMILY, variant: str = VARIANT_REAL) -> str:
    if variant not in VARIANTS:
        raise GnnRouteRefused("GNN_UNKNOWN_VARIANT", f"{variant!r} not in {VARIANTS}")
    return f"{family}-{variant}"


def collection_name(embedding_contract: str, contract: str) -> str:
    """`polymath_gnn_parent_<embedding_contract>_<gnn_contract>` — contract-derived, isolated from every production collection."""
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in contract)
    return f"{COLLECTION_PREFIX}_{embedding_contract}_{safe}"


def verify_collection(client: Any, collection: str, *, expect_dim: int, embedding_contract: str) -> dict:
    """Refuse a collection whose vector dimension or embedding contract is not the live one (G11 / wrong-contract gates)."""
    try:
        info = client.get_collection(collection)
    except Exception as exc:  # noqa: BLE001 — absence is a typed refusal
        raise GnnRouteRefused("GNN_COLLECTION_MISSING", f"{collection}: {type(exc).__name__}") from exc
    vectors = info.config.params.vectors
    dim = getattr(vectors, "size", None)
    if dim is None and isinstance(vectors, Mapping):
        dim = next(iter(vectors.values())).size
    if int(dim or 0) != int(expect_dim):
        raise GnnRouteRefused("GNN_VECTOR_DIM_MISMATCH", f"{collection} has dim {dim}, the query contract needs {expect_dim}")
    sample = client.scroll(collection, limit=1, with_payload=True, with_vectors=False)[0]
    if sample:
        pl = sample[0].payload or {}
        if pl.get("embedding_contract") not in (None, embedding_contract):
            raise GnnRouteRefused("GNN_EMBEDDING_CONTRACT_MISMATCH", f"{collection} was projected for {pl.get('embedding_contract')!r}, live is {embedding_contract!r}")
        if pl.get("representation_kind") != PAYLOAD_KIND:
            raise GnnRouteRefused("GNN_PAYLOAD_KIND_MISMATCH", f"{collection} holds {pl.get('representation_kind')!r}")
    return {"collection": collection, "dim": int(dim or 0), "points": getattr(info, "points_count", None)}


def gnn_parent_search(client: Any, collection: str, qvec: Sequence[float], *, corpus_id: str, limit: int = 8,
                      scope=None) -> list[dict]:
    """Experimental PARENT nominations for ONE query vector, inside ONE corpus (G12). Routing metadata only — no source text,
    no claims, no evidence semantics: `parent_id, doc_id, score, rank, gnn_contract, graph_snapshot_id, model_digest`."""
    from qdrant_client import models as M  # local: keeps this module importable in the DB-free tests

    if not corpus_id:
        raise GnnRouteRefused("GNN_CORPUS_REQUIRED", "a corpus_id is required (no cross-corpus GNN retrieval)")
    from polymath_shared.code.scope import scope_or_all
    flt = scope_or_all(scope).apply(      # K1: the knowledge-role scope
        M.Filter(must=[M.FieldCondition(key="representation_kind", match=M.MatchValue(value=PAYLOAD_KIND)),
                       M.FieldCondition(key="corpus_id", match=M.MatchValue(value=corpus_id))]))
    hits = client.search(collection_name=collection, query_vector=list(qvec), query_filter=flt, limit=int(limit), with_payload=True, with_vectors=False)
    out: list[dict] = []
    for rank, h in enumerate(hits, 1):
        pl = getattr(h, "payload", None) or {}
        if pl.get("corpus_id") != corpus_id:      # belt and braces: a cross-corpus point is a defect, never a candidate
            continue
        out.append({"parent_id": str(pl.get("parent_id") or ""), "doc_id": str(pl.get("doc_id") or ""), "score": float(getattr(h, "score", 0.0)),
                    "rank": rank, "gnn_contract": pl.get("gnn_contract"), "graph_snapshot_id": pl.get("graph_snapshot_id"), "model_digest": pl.get("model_digest")})
    return [r for r in out if r["parent_id"]]


def hydrate_original_children(child_search: Callable[..., list[dict]], qvec: Sequence[float], parents: Sequence[Mapping[str, Any]], *,
                              corpus_id: str, per_parent: int = 2, cap: int = 12) -> list[dict]:
    """Deepen every nominated parent through the caller's EXISTING original-child search (the same `routing_child` lane every
    other route uses), filtered by corpus + doc + parent. The rows ARE the original children; the route only annotates them
    (`gnn_parent`, `gnn_parent_rank`, `gnn_parent_score`) so the receipt can show the path. Dedupes by chunk_id; bounded."""
    rows: list[dict] = []
    seen: set[str] = set()
    for p in parents:
        extra = {"representation_kind": "routing_child", "corpus_id": corpus_id, "parent_id": p["parent_id"]}
        if p.get("doc_id"):
            extra["doc_id"] = p["doc_id"]
        for r in child_search(list(qvec), extra, int(per_parent)) or []:
            pl = r.get("payload") if isinstance(r.get("payload"), Mapping) else r
            cid = str(pl.get("chunk_id") or "")
            if not cid or cid in seen or pl.get("corpus_id") not in (None, corpus_id):
                continue
            seen.add(cid)
            row = dict(r)
            row["gnn_parent"], row["gnn_parent_rank"], row["gnn_parent_score"] = p["parent_id"], p.get("rank"), p.get("score")
            rows.append(row)
            if len(rows) >= int(cap):
                return rows
    return rows


def route(client: Any, collection: str, child_search: Callable[..., list[dict]], qvec: Sequence[float], *, corpus_id: str,
          parent_k: int = 8, per_parent: int = 2, cap: int = 12, scope=None) -> tuple[list[dict], dict]:
    """The whole query-time route: parents → ORIGINAL children, with the receipt the engine attaches to `trace.gnn`."""
    t0 = time.perf_counter()
    parents = gnn_parent_search(client, collection, qvec, corpus_id=corpus_id, limit=parent_k, **scope_kwargs(scope))
    children = hydrate_original_children(child_search, qvec, parents, corpus_id=corpus_id, per_parent=per_parent, cap=cap)
    receipt = {"contract": GNN_ROUTE_CONTRACT, "collection": collection, "parent_k": int(parent_k), "parents": [{k: p[k] for k in ("parent_id", "doc_id", "score", "rank")} for p in parents],
               "gnn_contract": parents[0]["gnn_contract"] if parents else None, "graph_snapshot_id": parents[0]["graph_snapshot_id"] if parents else None,
               "model_digest": parents[0]["model_digest"] if parents else None, "hydrated_children": len(children),
               "unique_children": len({str((r.get("payload") or r).get("chunk_id")) for r in children}), "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}
    return children, receipt

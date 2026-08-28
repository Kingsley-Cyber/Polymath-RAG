"""R1C FAST production route (orchestrator-owned HTTP reads).

Production FAST is the qualified Pass-1 engine (pass1-retrieval-v1)
over the neural routing projection. Thin client adapters only — the
engine itself lives in polymath_shared.pass1 and is shared with
qualification. No hash-embed fallback: an incomplete neural routing
projection is a loud, explicit failure.

Failure semantics (existing conventions):
  - embedder/G3/Qdrant unavailable  -> 502 with typed error_code
  - unknown corpus                  -> 502 unknown_corpus
  - corpus not query_ready          -> 502 corpus_not_ready
  - routing projection incomplete   -> 502 routing_projection_not_ready
"""
from __future__ import annotations

import logging
import os
import time
from contextvars import ContextVar
from typing import Optional

import httpx
import psycopg
from fastapi import HTTPException
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from polymath_shared.db import tx
from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT
from polymath_shared.pass1 import Pass1RetrievalPlan, pass1_retrieve
from polymath_shared.projection_contracts import qdrant_collection_name
from polymath_shared.query_shape import plan_for_query
from polymath_shared.rerank import RerankUnavailable, apply_rerank
from polymath_shared.retrieval_modes import MODE_FAST, mode_plan
from polymath_shared.settings import get_settings

log = logging.getLogger("orchestrator-retrieval")


def _fail(detail: dict, status_code: int = 502) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


class FastSearcher:
    """Corpus-filtered neural routing search (payload filters)."""

    def __init__(self, client: QdrantClient, collections: dict[str, str]):
        self.client = client
        self.collections = collections
        self.latency: dict[str, float] = {}

    def _search(self, collection: str, vector: list[float], filters: dict, limit: int) -> list[dict]:
        must = [
            FieldCondition(key="representation_kind",
                           match=MatchValue(value=filters["representation_kind"])),
        ]
        for key in ("corpus_id", "doc_id", "parent_id"):
            if filters.get(key):
                must.append(FieldCondition(key=key, match=MatchValue(value=filters[key])))
        must_not = []
        if filters.get("exclude_doc_ids"):
            from qdrant_client.models import MatchAny
            must_not.append(FieldCondition(
                key="doc_id", match=MatchAny(any=list(filters["exclude_doc_ids"]))))
        t0 = time.time()
        try:
            points = self.client.query_points(
                collection_name=collection,
                query=vector,
                query_filter=Filter(must=must, must_not=must_not),
                limit=limit,
                with_payload=True,
            ).points
        finally:
            key = "doc" if filters["representation_kind"] == "routing_document_summary" \
                else "deep" if filters.get("parent_id") \
                else "child" if filters["representation_kind"] == "routing_child" \
                else "section"
            self.latency[key] = self.latency.get(key, 0.0) + (time.time() - t0) * 1000
        out = [{"payload": p.payload, "score": p.score} for p in points]
        out.sort(key=lambda r: -(r["score"] or 0.0))
        return out

    def __call__(self, collection: str, vector: list[float], filters: dict) -> list[dict]:
        # collection is resolved by the service; ignore the passed name
        # (single-corpus FAST) — the engine passes the collection the
        # service selected.
        return self._search(collection, vector, filters, limit=50)


def _corpus_collections(corpus_ids: list[str]) -> dict[str, str]:
    return {
        cid: qdrant_collection_name(cid, NEURAL_EMBED_CONTRACT.contract_id)
        for cid in corpus_ids
    }


def _ensure_fast_ready(corpus_id: str) -> None:
    """Readiness: corpus must exist, have a query_ready run, and have a
    populated neural routing collection (never hash fallback)."""
    with tx() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE corpus_id = %s AND status = 'query_ready'",
            (corpus_id,),
        ).fetchone()
        if not row or row[0] == 0:
            raise _fail({
                "error_code": "corpus_not_ready",
                "message": f"corpus {corpus_id!r} has no query_ready run; FAST requires a converged corpus",
            })
    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    try:
        collection = qdrant_collection_name(corpus_id, NEURAL_EMBED_CONTRACT.contract_id)
        if not client.collection_exists(collection):
            raise _fail({
                "error_code": "routing_projection_not_ready",
                "message": f"corpus {corpus_id!r} has no neural routing projection",
            })
        count = client.count(collection_name=collection).count
        if count == 0:
            raise _fail({
                "error_code": "routing_projection_not_ready",
                "message": f"corpus {corpus_id!r} neural routing projection is empty",
            })
    finally:
        client.close()


#: WAKE-ON-QUERY (2026-08-27). The autopilot parks the embedder when
#: ingest demand ends, so the FIRST query after an idle period found a
#: dead socket and failed typed (`embedder_unavailable`) — while that
#: very request's activity signal was what told the autopilot to wake
#: the sidecar. Budget: the signal lands before the handler runs
#: (orchestrator.main middleware), the supervisor reconciles within
#: 15 s, and the measured embedder cold start is ~20 s.
#:
#: The embedder is a HARD dependency — no vector, no retrieval — so it
#: cannot degrade like the reranker: the only correct behaviour is to
#: wait. The budget is deliberately generous (owner rule: waiting on a
#: cold model is fine, erroring is not) and env-tunable; a genuinely
#: dead sidecar still fails typed when it expires.
EMBED_WAKE_BUDGET_S = float(
    os.environ.get("POLYMATH_EMBED_WAKE_BUDGET_S", "150"))


def _await_embedder(client) -> None:
    """Block briefly while the autopilot wakes a parked embedder; on
    budget expiry fall through so the embed call fails typed."""
    if client.ready():
        return
    deadline = time.monotonic() + EMBED_WAKE_BUDGET_S
    while time.monotonic() < deadline:
        time.sleep(2.0)
        if client.ready():
            return


def _embed_query(query: str) -> list[float]:
    from polymath_shared.clients import EmbedderClient

    client = EmbedderClient()
    try:
        _await_embedder(client)
        client.verify_pin()
        return client.embed([query], "query")["vectors"][0]
    except Exception as exc:
        raise _fail({
            "error_code": "embedder_unavailable",
            "message": f"embedder sidecar unavailable: {type(exc).__name__}",
        }) from exc
    finally:
        client.close()


#: NEVER-ERROR-ON-A-COLD-MODEL (2026-08-27, owner rule): an idle-parked
#: model must cost the user WAITING, never a failed query. `_embed_query`
#: waits for the embedder because a vector is a hard dependency — no
#: vector, no retrieval. Reranking is different: it only REORDERS what
#: RRF fusion already produced (it can neither add nor drop candidates),
#: so fusion order is a complete, correct answer. When the reranker
#: cannot be reached even after the wake budget — the real case is
#: active ingest, where GLiNER holds the memory ceiling and the
#: autopilot deliberately refuses to wake the reranker at all — the
#: lane DEGRADES to fusion order and says so in meta.degraded, instead
#: of throwing `rerank_unavailable` at someone who just asked a
#: question.
_RERANK_DEGRADED: "ContextVar[str | None]" = ContextVar(
    "rerank_degraded", default=None)


def _begin_retrieval() -> None:
    """Reset per-request degradation state (call once per retrieve)."""
    _RERANK_DEGRADED.set(None)


def degradations() -> list[dict]:
    """Degradations recorded for the current request, for meta."""
    note = _RERANK_DEGRADED.get()
    return [] if not note else [{
        "component": "reranker",
        "effect": "results ordered by RRF fusion (no cross-encoder rerank); "
                  "same candidate set, same recall",
        "reason": note,
    }]


def _neighbor_lookup(want: list[dict], distance: int) -> list[dict]:
    """NEIGHBOR-EXPANSION-V1 source: chunks adjacent (chunk_index ± n,
    same document, child tier) to the seed chunks.

    One set-based query for the whole seed set — never a per-seed loop
    (the repo has paid for that pattern before). Ordered deterministically
    so the same seeds always expand to the same rows."""
    if not want or distance <= 0:
        return []
    doc_ids = [w["doc_id"] for w in want]
    chunk_ids = [w["chunk_id"] for w in want]
    with tx() as conn:
        rows = conn.execute(
            """
            WITH seeds AS (
                SELECT c.doc_id, c.chunk_index
                  FROM chunks c
                  JOIN unnest(%s::text[], %s::text[]) AS w(doc_id, chunk_id)
                    ON c.doc_id = w.doc_id AND c.chunk_id = w.chunk_id
            )
            SELECT DISTINCT n.chunk_id, n.doc_id, n.parent_id, n.text,
                   d.source_name, n.chunk_index
              FROM chunks n
              JOIN seeds s ON n.doc_id = s.doc_id
              JOIN documents d ON d.doc_id = n.doc_id
             WHERE n.tier = 'child'
               AND n.chunk_index BETWEEN s.chunk_index - %s AND s.chunk_index + %s
             ORDER BY n.doc_id, n.chunk_index
            """,
            (doc_ids, chunk_ids, distance, distance),
        ).fetchall()
    return [
        {"chunk_id": r[0], "doc_id": r[1], "parent_id": r[2],
         "text": r[3], "source_name": r[4]}
        for r in rows
    ]


def _liveness(trace: dict, mode: str) -> dict:
    """Evaluate promoted-lane liveness for this query's trace."""
    from polymath_shared.lane_liveness import evaluate

    out = evaluate({**trace, "mode": mode})
    if out["suspect"]:
        log.warning("promoted lane(s) had an opportunity and contributed "
                    "nothing: %s", ",".join(out["suspect"]),
                    extra={"error_code": "lane_suspect"})
    return {"suspect": out["suspect"], "live": out["live"]}


def _region_lookup(chunk_ids: list[str]) -> dict:
    """DOCUMENT-REGION-V1 source: persisted document role per chunk.

    One set-based query over the bounded candidate set. A chunk with no
    role (ingested before the contract, or a corpus not yet backfilled)
    returns nothing and is therefore never demoted."""
    if not chunk_ids:
        return {}
    with tx() as conn:
        rows = conn.execute(
            """SELECT chunk_id, region_role FROM chunks
                WHERE chunk_id = ANY(%s) AND region_role IS NOT NULL""",
            (chunk_ids,)).fetchall()
    return {r[0]: r[1] for r in rows}


def _rerank_children(query: str, children: list[dict]) -> list[dict]:
    try:
        _, reranked = apply_rerank(query, [], children)
        return reranked
    except RerankUnavailable as exc:
        _RERANK_DEGRADED.set(str(exc)[:300])
        log.warning("reranker unavailable; degrading to fusion order",
                    extra={"error_code": "rerank_degraded"})
        return children


def fast_retrieve(
    query: str,
    corpus_id: str,
    plan: Optional[Pass1RetrievalPlan] = None,
) -> dict:
    """Production FAST: one qualified Pass-1 execution with explicit
    readiness, corpus filtering, and a hierarchical trace."""
    _begin_retrieval()
    plan = plan or mode_plan(MODE_FAST)
    if corpus_id is None:
        raise _fail({
            "error_code": "corpus_required",
            "message": "FAST requires an explicit corpus_id (authorized corpus scope)",
        }, status_code=422)

    _ensure_fast_ready(corpus_id)

    collections = _corpus_collections([corpus_id])
    try:
        client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    except Exception as exc:
        raise _fail({
            "error_code": "qdrant_unavailable",
            "message": f"qdrant unavailable: {type(exc).__name__}",
        }) from exc
    try:
        searcher = FastSearcher(client, collections)

        def routing_search(collection: str, vector: list[float], filters: dict) -> list[dict]:
            return searcher(collection, vector, filters)

        # QUERY-SHAPE-V1: breadth by default; the depth profile engages
        # only for completeness questions ("all the domains and
        # subdomains…"), which the breadth caps structurally truncate.
        shaped = plan_for_query(
            query,
            Pass1RetrievalPlan(**{**plan.__dict__, "corpus_ids": (corpus_id,)}),
        )
        result = pass1_retrieve(
            query,
            plan=shaped,
            embed_query=_embed_query,
            routing_search=routing_search,
            rerank_children=_rerank_children if shaped.rerank_enabled else None,
            neighbor_lookup=_neighbor_lookup,
            region_lookup=_region_lookup,
        )
    finally:
        client.close()

    latency_ms = {k: round(v, 1) for k, v in searcher.latency.items()}
    return {
        "query": query,
        "meta": {
            "mode": MODE_FAST,
            "plan_version": result.plan.plan_version,
            "corpus_id": corpus_id,
            "rrf_k": result.plan.rrf_k,
            "selected_document_count": len(result.selected_documents),
            "selected_section_count": len(result.selected_sections),
            "evidence_count": len(result.final_evidence),
            "degraded": degradations(),
            # PRODUCTION-REALITY-V1: per-query lane liveness. A lane that
            # was enabled, had a genuine opportunity and contributed
            # nothing shows up as SUSPECT here instead of silently
            # delivering zero for weeks.
            "liveness": _liveness(result.trace, MODE_FAST),
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

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
from polymath_shared.generation import chunk_visible_sql, hidden_generations
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

    def __init__(self, client: QdrantClient, collections: dict[str, str],
                 query: str | None = None):
        self.client = client
        self.collections = collections
        self.latency: dict[str, float] = {}
        # SPARSE-BREADTH-V1: one tokenization per query, shared tokenizer
        self._sparse_query = None
        if query:
            try:
                from polymath_shared.sparse_bm25 import sparse_vector
                idx, vals = sparse_vector(query)
                if idx:
                    self._sparse_query = (idx, vals)
            except Exception:
                self._sparse_query = None

    def _hidden_for(self, corpus_id: str | None) -> list[str]:
        if not corpus_id:
            return []
        cache = getattr(self, "_hidden_cache", None)
        if cache is None:
            cache = self._hidden_cache = {}
        if corpus_id not in cache:
            try:
                with tx() as conn:
                    cache[corpus_id] = hidden_generations(conn, corpus_id)
            except Exception:  # noqa: BLE001 — never fail a query on the guard
                cache[corpus_id] = []
        return cache[corpus_id]

    def _search(self, collection: str, vector: list[float], filters: dict, limit: int) -> list[dict]:
        must = [
            FieldCondition(key="representation_kind",
                           match=MatchValue(value=filters["representation_kind"])),
        ]
        for key in ("corpus_id", "doc_id", "parent_id"):
            if filters.get(key):
                must.append(FieldCondition(key=key, match=MatchValue(value=filters[key])))
        must_not = []
        # GENERATION-SWAP-V1: hide chunk generations a blue/green successor
        # is still building (legacy points without the field pass).
        for g in self._hidden_for(filters.get("corpus_id")):
            must_not.append(FieldCondition(key="chunk_contract_version",
                                           match=MatchValue(value=g)))
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
        # SPARSE-BREADTH-V1 (audit F4): every routing lane gets a bm25
        # companion probe — exact-name queries stop depending on embedding
        # luck at the ROUTING tier. Dense ordering stays authoritative
        # (scores are not comparable across spaces); sparse-only hits the
        # dense lane missed APPEND after it, a pure recall addition where
        # RRF can still vote them up. Fail-open: legacy dense-only
        # collections skip silently.
        if self._sparse_query is not None:
            t1 = time.time()
            try:
                from qdrant_client.models import SparseVector
                from polymath_shared.sparse_bm25 import SPARSE_VECTOR_NAME
                spts = self.client.query_points(
                    collection_name=collection,
                    query=SparseVector(indices=self._sparse_query[0],
                                       values=self._sparse_query[1]),
                    using=SPARSE_VECTOR_NAME,
                    query_filter=Filter(must=must, must_not=must_not),
                    limit=limit,
                    with_payload=True,
                ).points
                seen = {(r["payload"] or {}).get("summary_id")
                        or (r["payload"] or {}).get("chunk_id") for r in out}
                for p in spts:
                    pl = p.payload or {}
                    key_id = pl.get("summary_id") or pl.get("chunk_id")
                    if key_id not in seen:
                        out.append({"payload": pl, "score": p.score})
                        seen.add(key_id)
            except Exception:
                pass
            finally:
                self.latency["sparse"] = self.latency.get("sparse", 0.0) \
                    + (time.time() - t1) * 1000
        return out

    def __call__(self, collection: str, vector: list[float], filters: dict) -> list[dict]:
        # collection is resolved by the service; ignore the passed name
        # (single-corpus FAST) — the engine passes the collection the
        # service selected.
        return self._search(collection, vector, filters, limit=50)


def entity_card_probe(client, collections: dict[str, str], corpus_id: str,
                      query: str, qvec: list[float],
                      limit: int = 8) -> list[dict]:
    """ENTITY-CARD-PROBE (shared): dense + sparse search over
    routing_entity cards, deduped by card keeping the best score.
    Consumers: FAST's advisory lane, GRAPH seed resolution (F1). Returns
    [{card_id, entity_id, doc_ids, text, score, lane}] best-first."""
    from qdrant_client.models import (
        FieldCondition, Filter, MatchValue, SparseVector,
    )
    from polymath_shared.sparse_bm25 import (
        SPARSE_VECTOR_NAME, sparse_vector as _sv,
    )
    card_filter = Filter(must=[
        FieldCondition(key="representation_kind",
                       match=MatchValue(value="routing_entity")),
        FieldCondition(key="corpus_id", match=MatchValue(value=corpus_id)),
    ])
    seen: dict[str, dict] = {}
    si, svals = _sv(query)
    for collection in collections.values():
        probes = [(qvec, None)]
        if si:
            probes.append((SparseVector(indices=si, values=svals),
                           SPARSE_VECTOR_NAME))
        for qv, using in probes:
            try:
                pts = client.query_points(
                    collection_name=collection, query=qv, using=using,
                    query_filter=card_filter, limit=limit,
                    with_payload=True).points
            except Exception:
                continue
            for p in pts:
                pl = p.payload or {}
                cid = pl.get("summary_id") or str(p.id)
                cur = seen.get(cid)
                if cur is None or float(p.score or 0) > cur["score"]:
                    seen[cid] = {
                        "card_id": cid,
                        "entity_id": pl.get("entity_id", ""),
                        "doc_ids": pl.get("doc_ids") or [],
                        "text": pl.get("text", ""),
                        "score": float(p.score or 0.0),
                        "lane": "sparse" if using else "dense",
                    }
    return sorted(seen.values(), key=lambda c: -c["score"])[:limit]


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
               AND """ + chunk_visible_sql("n", "d") + """
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


def _presentation_joins(chunk_ids: list[str],
                        doc_ids: list[str]) -> dict:
    """UI-V3 §3.2 (best-effort, fail-open): one query each for the
    chunks' heading paths and the documents' names; returns
    {chunk_id|doc_id: {...}} for response decoration. NULL heading_path
    (legacy ingests) degrades to source-name-only human locators."""
    out: dict = {}
    if not chunk_ids and not doc_ids:
        return out
    try:
        with tx() as conn:
            for did, name in conn.execute(
                    "SELECT doc_id, source_name FROM documents "
                    "WHERE doc_id = ANY(%s)", (sorted(set(doc_ids)),)):
                out[did] = {"source_name": name or ""}
            rows = conn.execute(
                "SELECT c.chunk_id, c.heading_path, d.source_name "
                "FROM chunks c JOIN documents d ON d.doc_id = c.doc_id "
                "WHERE c.chunk_id = ANY(%s)",
                (sorted(set(chunk_ids)),)).fetchall()
        for cid, path_raw, name in rows:
            if isinstance(path_raw, (list, tuple)):
                path = " › ".join(str(x) for x in path_raw if x)
            else:
                path = str(path_raw) if path_raw else ""
            title = path.rsplit("›", 1)[-1].strip() if path else ""
            human = (f"{name} › {title}" if (name and title)
                     else (name or ""))
            out[cid] = {"title": title, "heading_path": path,
                        "human_locator": human}
    except Exception as exc:            # presentation must never fail a query
        import logging as _logging
        _logging.getLogger("fast").warning(
            "presentation join failed open: %s: %s",
            type(exc).__name__, exc)
    return out


def fast_retrieve(
    query: str,
    corpus_id,
    plan: Optional[Pass1RetrievalPlan] = None,
) -> dict:
    """Production FAST: one qualified Pass-1 execution with explicit
    readiness, corpus filtering, and a hierarchical trace.

    MULTI-CORPUS-FAST-V1 (audit F8): `corpus_id` is a corpus id or a
    list of them. The pass1 engine already fans lanes out per corpus
    (per-corpus rank cut, similarity merge), so a wider authorized
    scope retrieves instead of 422ing. Readiness stays PER CORPUS and
    fails closed — one unready corpus fails the whole query rather
    than silently narrowing the scope. HYBRID/GRAPH remain
    single-corpus engines (in-memory lexical scan / graph seeding are
    corpus-local) and keep the 422 gate."""
    _begin_retrieval()
    plan = plan or mode_plan(MODE_FAST)
    corpus_ids = [corpus_id] if isinstance(corpus_id, str) \
        else list(corpus_id or [])
    if not corpus_ids:
        raise _fail({
            "error_code": "corpus_required",
            "message": "FAST requires an explicit corpus scope (authorized corpus ids)",
        }, status_code=422)

    for cid in corpus_ids:
        _ensure_fast_ready(cid)

    collections = _corpus_collections(corpus_ids)
    try:
        client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    except Exception as exc:
        raise _fail({
            "error_code": "qdrant_unavailable",
            "message": f"qdrant unavailable: {type(exc).__name__}",
        }) from exc
    try:
        searcher = FastSearcher(client, collections, query=query)

        def routing_search(collection: str, vector: list[float], filters: dict) -> list[dict]:
            return searcher(collection, vector, filters)

        # QUERY-SHAPE-V1: breadth by default; the depth profile engages
        # only for completeness questions ("all the domains and
        # subdomains…"), which the breadth caps structurally truncate.
        shaped = plan_for_query(
            query,
            Pass1RetrievalPlan(**{**plan.__dict__,
                                  "corpus_ids": tuple(corpus_ids)}),
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
        # ENTITY-CARD-LANE (pass1-retrieval-v2): the card lane is now a
        # FUSED fourth RRF lane inside the engine — its votes show up in
        # rrf_contributions["routing_entity"], not as a post-hoc re-sort
        # (the advisory doc-vote re-rank this replaced double-counted
        # against RRF and hid attribution). The probe below only
        # SURFACES the matched cards for the ask layer and the
        # response; it never reorders documents. Fail-open.
        entity_cards: list[dict] = []
        qvec_cards = _embed_query(query)
        for cid in corpus_ids:
            try:
                entity_cards.extend(entity_card_probe(
                    client, collections, cid, query, qvec_cards))
            except Exception as exc:    # display lane: never fails the query
                import logging as _logging
                _logging.getLogger("fast").warning(
                    "entity card display probe failed open (%s): %s: %s",
                    cid, type(exc).__name__, exc)
    finally:
        client.close()

    latency_ms = {k: round(v, 1) for k, v in searcher.latency.items()}
    _p = _presentation_joins(
        [c["chunk_id"] for c in result.final_evidence],
        [c["doc_id"] for c in result.final_evidence])
    return {
        "query": query,
        "meta": {
            "mode": MODE_FAST,
            "plan_version": result.plan.plan_version,
            "corpus_id": corpus_ids[0] if len(corpus_ids) == 1 else None,
            "corpus_ids": corpus_ids,
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
            "entity_card_votes": len(entity_cards),
        },
        "entity_card_lane": [
            {k: v for k, v in c.items() if k != "doc_ids"}
            for c in entity_cards
        ],
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
                # UI-V3 §1B: child routing points carry no source_name in
                # their payload — the durable documents row does; the
                # presentation join fixes the measured source_name:"" bug.
                "source_name": c["source_name"] or _p.get(
                    c["doc_id"], {}).get("source_name", ""),
                "arrival": c.get("arrival"),
                "document_rank": c.get("document_rank"),
                "g3_score": c.get("rerank_score"),
                "locator": f"chunk:{c['chunk_id']}",
                "title": _p.get(c["chunk_id"], {}).get("title", ""),
                "heading_path": _p.get(c["chunk_id"], {}).get("heading_path", ""),
                "human_locator": _p.get(c["chunk_id"], {}).get("human_locator", ""),
                "text": (c.get("text") or "")[:240],
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

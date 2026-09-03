"""Chat API. POST /chat — R3b grounded answer generation.

Flow: user query -> R3a EvidenceBundle -> answer synthesis ->
claim/evidence validation -> final answer + citations.

The synthesizer receives ONLY the assembled bundle (never Postgres /
Neo4j / Qdrant handles), and the deterministic validator decides which
claims may render. No factual assertion survives into the answer
unless supported by one or more bundle items. Assembly failures stay
loud (502), as in R3a.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from polymath_shared.answer_synthesis import grounded_answer
from polymath_shared.db import tx
from polymath_shared.evidence_assembly import (
    AssemblyError,
    assemble_evidence_bundle,
)
from polymath_shared.retrieval import graph_expansion, run_lanes

from .evidence import (
    _resolve_chunk,
    _resolve_document,
    _resolve_entity,
    _resolve_evidence_rows,
    _resolve_fact,
)
from .retrieve import (
    _entity_surfaces,
    _fetch_children_rows,
    _fetch_parents,
    _fetch_profiles,
    _qdrant_search,
    graph_expand_or_502,
    resolve_http_scope,
    single_corpus_or_422,
)

from polymath_shared.query_receipts import Timer, record_query_receipt

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    corpus_id: str | None = None
    corpus_ids: list[str] | None = None
    workspace: str | None = None
    all_authorized: bool = False
    mode: str | None = None
    latent: bool | None = None
    utility: bool | None = None


async def _chat_impl(req: ChatRequest) -> dict:
    query = req.message.strip()
    if not query:
        raise HTTPException(status_code=422, detail="message is required")

    with tx() as conn:
        scope = resolve_http_scope(conn, req)

    # R1C: FAST mode consumes the SAME qualified Pass-1 result as
    # /retrieve and /evidence (one control-plane path). FAST excludes
    # graph expansion by contract: the bundle's graph lane stays empty.
    from polymath_shared.retrieval_modes import MODE_FAST, MODE_GRAPH, MODE_HYBRID, validate_mode

    mode = validate_mode(req.mode)
    if mode == MODE_GRAPH:
        # GRAPH: one GRAPH retrieval result feeds the existing bundle
        # (graph lane = qualified facts; text lane = HYBRID evidence).
        # No synthesis change: EvidenceBundle v2 semantics as-is.
        from orchestrator.api.graph import graph_retrieve

        g = graph_retrieve(query, single_corpus_or_422(scope, mode),
                           latent=getattr(req, 'latent', None),
                           utility=getattr(req, 'utility', None))
        graph_facts = [
            {"fact_id": f["fact_id"], "predicate": f["predicate"],
             "subject": f["subject"], "object": f["object"]}
            for f in g["graph_relationships"]
        ]
        child_evidence = [
            {"chunk_id": c["chunk_id"], "doc_id": d["doc_id"]}
            for d in g["documents"]
            for s in d["sections"]
            for c in s["evidence"]
        ]
        evidence_order = [c["chunk_id"] for c in child_evidence]
        document_summaries = [
            {"doc_id": d["doc_id"], "summary": d["document_summary"] or ""}
            for d in g["documents"] if d["document_summary"]
        ]
        section_summaries = [
            {"chunk_id": s["parent_id"], "doc_id": d["doc_id"],
             "summary": s["summary"] or ""}
            for d in g["documents"] for s in d["sections"]
        ]
        try:
            stale: list[dict] = []
            bundle = assemble_evidence_bundle(
                query,
                graph_facts,
                child_evidence,
                evidence_order=evidence_order,
                resolve_fact=lambda fid: _resolve_fact(fid),
                resolve_evidence=lambda fid: _resolve_evidence_rows(fid),
                resolve_entity=lambda eid: _resolve_entity(eid),
                resolve_document=lambda did: _resolve_document(did),
                resolve_chunk=lambda cid: _resolve_chunk(cid),
                unresolved=stale,
                document_summaries=document_summaries,
                section_summaries=section_summaries,
            )
        except AssemblyError as exc:
            raise HTTPException(status_code=502, detail={
                "error_code": type(exc).__name__, "message": str(exc),
            }) from exc
        return grounded_answer(bundle, query)
    if mode in (MODE_FAST, MODE_HYBRID):
        if mode == MODE_FAST:
            from orchestrator.api.fast import fast_retrieve

            fast = fast_retrieve(query, list(scope.corpus_ids))  # F8: multi-corpus
        else:
            from orchestrator.api.hybrid import hybrid_fast_retrieve

            fast = hybrid_fast_retrieve(query, single_corpus_or_422(scope, mode),
                                        latent=getattr(req, 'latent', None),
                           utility=getattr(req, 'utility', None))
        child_evidence = [
            {"chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "parent_id": c["parent_id"]}
            for c in fast["evidence"]
        ]
        evidence_order = [c["chunk_id"] for c in fast["evidence"]]
        document_summaries = [
            {"doc_id": d["doc_id"], "summary": (d.get("document_summary") or {}).get("text", "")}
            for d in fast["selected_documents"] if d.get("document_summary")
        ]
        parent_ids = [s["parent_id"] for s in fast["selected_sections"]]
        with tx() as conn:
            rows = conn.execute(
                "SELECT chunk_id, doc_id, summary FROM chunks WHERE chunk_id = ANY(%s)",
                (parent_ids,),
            ).fetchall()
            section_summaries = [
                {"chunk_id": r[0], "doc_id": r[1], "summary": r[2] or ""} for r in rows
            ]
        try:
            stale: list[dict] = []
            bundle = assemble_evidence_bundle(
                query,
                [],
                child_evidence,
                evidence_order=evidence_order,
                resolve_fact=lambda fid: _resolve_fact(fid),
                resolve_evidence=lambda fid: _resolve_evidence_rows(fid),
                resolve_entity=lambda eid: _resolve_entity(eid),
                resolve_document=lambda did: _resolve_document(did),
                resolve_chunk=lambda cid: _resolve_chunk(cid),
                unresolved=stale,
                document_summaries=document_summaries,
                section_summaries=section_summaries,
            )
        except AssemblyError as exc:
            raise HTTPException(status_code=502, detail={
                "error_code": type(exc).__name__, "message": str(exc),
            }) from exc
        return grounded_answer(bundle, query)

    corpus_ids = list(scope.corpus_ids)
    with tx() as conn:
        profiles = _fetch_profiles(conn, corpus_ids)
        children_rows = _fetch_children_rows(conn, corpus_ids)
        children = [r for r in children_rows if r["tier"] == "child"]
        parent_rows = [r for r in children_rows if r["tier"] == "parent"]
        parents = [
            {"chunk_id": r["chunk_id"], "doc_id": r["doc_id"], "summary": r["summary"]}
            for r in parent_rows
        ]

    result = run_lanes(
        query,
        fetch_profiles=lambda: profiles,
        fetch_parents=lambda: parents,
        fetch_children=lambda limit: children[:limit],
        child_search=lambda limit: _qdrant_search(query, corpus_ids, limit),
    )

    graph_facts = graph_expansion(
        _entity_surfaces(query, result),
        expand=lambda surfaces: graph_expand_or_502(
            surfaces, corpus_ids,
            [c["chunk_id"] for c in result.selected_children[:10]],
        ),
    )

    # G3 candidate: rerank the fused candidates feeding the bundle.
    # NEVER-ERROR-ON-A-COLD-MODEL: an unreachable reranker degrades to
    # fusion order (same candidate set, same recall) instead of
    # failing an answer the user is waiting on.
    from polymath_shared.rerank import RerankUnavailable, apply_rerank

    from orchestrator.api.fast import _RERANK_DEGRADED

    try:
        _reranked_documents, selected_children = apply_rerank(
            query, result.selected_documents, result.selected_children,
        )
    except RerankUnavailable as exc:
        _RERANK_DEGRADED.set(str(exc)[:300])
        selected_children = result.selected_children

    try:
        _evidence_order = None
        if selected_children and all("rerank_score" in c for c in selected_children):
            _evidence_order = [c["chunk_id"] for c in selected_children]
        stale: list[dict] = []
        bundle = assemble_evidence_bundle(
            query,
            graph_facts,
            selected_children,
            evidence_order=_evidence_order,
            resolve_fact=lambda fid: _resolve_fact(fid),
            resolve_evidence=lambda fid: _resolve_evidence_rows(fid),
            resolve_entity=lambda eid: _resolve_entity(eid),
            resolve_document=lambda did: _resolve_document(did),
            resolve_chunk=lambda cid: _resolve_chunk(cid),
            unresolved=stale,
            document_summaries=[
                {"doc_id": p["doc_id"],
                 "summary": (p.get("retrieval_profile") or {}).get("semantic_summary") or ""}
                for p in profiles
            ],
            section_summaries=[
                {"chunk_id": p["chunk_id"], "doc_id": p["doc_id"],
                 "summary": p.get("summary") or ""}
                for p in parents
            ],
        )
    except AssemblyError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": type(exc).__name__,
                "message": str(exc),
            },
        ) from exc

    return grounded_answer(bundle, query)


@router.post("/chat")
async def chat(req: ChatRequest, request: Request) -> dict:
    """QUERY-RECEIPTS-V1 wrapper: serve exactly as before, then record one
    durable receipt (latency, scope, mode, verdict, citations, error) —
    best effort, off the critical path (see polymath_shared.query_receipts)."""
    question = req.message
    scope_corpora, scope_kind = (([req.corpus_id] if getattr(req, "corpus_id", None) else list(getattr(req, "corpus_ids", None) or [])), ("corpus" if getattr(req, "corpus_id", None) else "corpora" if getattr(req, "corpus_ids", None) else "workspace" if getattr(req, "workspace", None) else "all_authorized" if getattr(req, "all_authorized", False) else None))
    client = request.headers.get("user-agent", "")
    with Timer() as t:
        try:
            out = await _chat_impl(req)
        except Exception as exc:  # noqa: BLE001 — record, then re-raise unchanged
            detail = getattr(exc, "detail", None)
            record_query_receipt(tx, kind="chat", question=question, req=req,
                                 scope_corpora=scope_corpora, scope_kind=scope_kind,
                                 wall_ms=(__import__("time").perf_counter() - t.t0) * 1000.0,
                                 error=f"{type(exc).__name__}: {detail if detail is not None else exc}",
                                 client=client)
            raise
    record_query_receipt(tx, kind="chat", question=question, req=req,
                         scope_corpora=scope_corpora, scope_kind=scope_kind,
                         wall_ms=t.ms, out=out, client=client)
    return out

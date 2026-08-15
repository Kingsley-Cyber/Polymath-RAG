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

from fastapi import APIRouter, HTTPException
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
    _neo4j_expand,
    _qdrant_search,
)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    corpus_id: str | None = None
    mode: str | None = None


@router.post("/chat")
async def chat(req: ChatRequest) -> dict:
    query = req.message.strip()
    if not query:
        raise HTTPException(status_code=422, detail="message is required")
    corpus_id = req.corpus_id

    # R1C: FAST mode consumes the SAME qualified Pass-1 result as
    # /retrieve and /evidence (one control-plane path). FAST excludes
    # graph expansion by contract: the bundle's graph lane stays empty.
    from polymath_shared.retrieval_modes import MODE_FAST, validate_mode

    if validate_mode(req.mode) == MODE_FAST:
        from orchestrator.api.fast import fast_retrieve

        fast = fast_retrieve(query, corpus_id)
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
                document_summaries=document_summaries,
                section_summaries=section_summaries,
            )
        except AssemblyError as exc:
            raise HTTPException(status_code=502, detail={
                "error_code": type(exc).__name__, "message": str(exc),
            }) from exc
        return grounded_answer(bundle, query)

    with tx() as conn:
        profiles = _fetch_profiles(conn, corpus_id)
        children_rows = _fetch_children_rows(conn, corpus_id)
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
        child_search=lambda limit: _qdrant_search(query, corpus_id, limit),
    )

    graph_facts = graph_expansion(
        _entity_surfaces(query, result),
        expand=lambda surfaces: _neo4j_expand(
            surfaces,
            corpus_id=corpus_id,
            preferred_chunk_ids=[c["chunk_id"] for c in result.selected_children[:10]],
        ),
    )

    # G3 candidate: rerank the fused candidates feeding the bundle.
    from polymath_shared.rerank import RerankUnavailable, apply_rerank

    try:
        _reranked_documents, selected_children = apply_rerank(
            query, result.selected_documents, result.selected_children,
        )
    except RerankUnavailable as exc:
        raise HTTPException(status_code=502, detail={
            "error_code": "rerank_unavailable",
            "message": str(exc),
        }) from exc

    try:
        _evidence_order = None
        if selected_children and all("rerank_score" in c for c in selected_children):
            _evidence_order = [c["chunk_id"] for c in selected_children]
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

"""Evidence API: POST /evidence — R3a grounded evidence-bundle assembly.

Runs the same four retrieval lanes as /retrieve plus the graph
expansion lane, then assembles a deterministic EvidenceBundle via
shared/polymath_shared/evidence_assembly.py. Every candidate claim in
the bundle is traceable to fact/entity IDs, source document, exact
evidence span, provenance, epistemics, scope, and retrieval lane.

Boundary rule (R3a): this endpoint assembles evidence. It does NOT
decide final answer prose — R3b (/chat) owns that.

Missing provenance or unresolvable references fail LOUDLY (502 with an
error code); they are never silently dropped.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from polymath_shared.db import tx
from polymath_shared.evidence_assembly import (
    AssemblyError,
    assemble_evidence_bundle,
)
from polymath_shared.retrieval import graph_expansion, run_lanes

from .retrieve import (
    _entity_surfaces,
    _fetch_children_rows,
    _fetch_parents,
    _fetch_profiles,
    _neo4j_expand,
    _qdrant_search,
)

router = APIRouter()


class EvidenceRequest(BaseModel):
    query: str
    corpus_id: Optional[str] = None
    limit: int = 10


@router.post("/evidence")
async def evidence(req: EvidenceRequest) -> dict:
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    corpus_id = req.corpus_id

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

    return bundle


def _resolve_fact(fact_id: str) -> Optional[dict]:
    with tx() as conn:
        row = conn.execute(
            """
            SELECT fact_id, predicate, subject_id, object_id, qualifiers,
                   decision, rule_id, rule_version, provenance
              FROM facts WHERE fact_id = %s
            """,
            (fact_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "fact_id": row[0], "predicate": row[1], "subject_id": row[2],
        "object_id": row[3], "qualifiers": row[4] or {},
        "decision": row[5], "rule_id": row[6], "rule_version": row[7],
        "provenance": row[8] or {},
    }


def _resolve_evidence_rows(fact_id: str) -> list[dict]:
    with tx() as conn:
        rows = conn.execute(
            """
            SELECT evidence_id, fact_id, doc_id, chunk_id, span_offsets,
                   rule_id, extractor_version, rule_version
              FROM evidence WHERE fact_id = %s
            """,
            (fact_id,),
        ).fetchall()
    return [
        {
            "evidence_id": r[0], "fact_id": r[1], "doc_id": r[2],
            "chunk_id": r[3], "span_offsets": r[4] or {},
            "rule_id": r[5], "extractor_version": r[6], "rule_version": r[7],
        }
        for r in rows
    ]


def _resolve_entity(entity_id: str) -> Optional[dict]:
    with tx() as conn:
        row = conn.execute(
            "SELECT entity_id, core_type, normalized_surface FROM entities WHERE entity_id = %s",
            (entity_id,),
        ).fetchone()
    if row is None:
        return None
    return {"entity_id": row[0], "core_type": row[1], "normalized_surface": row[2]}


def _resolve_document(doc_id: str) -> Optional[dict]:
    with tx() as conn:
        row = conn.execute(
            "SELECT doc_id, corpus_id, source_name FROM documents WHERE doc_id = %s",
            (doc_id,),
        ).fetchone()
    if row is None:
        return None
    return {"doc_id": row[0], "corpus_id": row[1], "source_name": row[2]}


def _resolve_chunk(chunk_id: str) -> Optional[dict]:
    with tx() as conn:
        row = conn.execute(
            "SELECT chunk_id, doc_id, text, char_start, char_end FROM chunks WHERE chunk_id = %s",
            (chunk_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "chunk_id": row[0], "doc_id": row[1], "text": row[2],
        "char_start": row[3], "char_end": row[4],
    }

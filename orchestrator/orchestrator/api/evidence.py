"""R3a grounded EvidenceBundle assembly.

Consumes the trace emitted by /retrieve, then re-resolves every selected
passage and graph fact against authoritative Postgres state.  This endpoint
never writes an answer and never treats Neo4j/Qdrant as provenance.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from polymath_shared.db import tx
from polymath_shared.evidence_bundle import (
    EvidenceAssemblyError,
    assemble_evidence_bundle,
)

router = APIRouter()


class EvidenceBundleRequest(BaseModel):
    query: str
    child_evidence: list[dict[str, Any]] = Field(default_factory=list)
    graph_facts: list[dict[str, Any]] = Field(default_factory=list)
    child_dense_lane: list[dict[str, Any]] = Field(default_factory=list)
    child_lexical_lane: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/evidence-bundle")
async def evidence_bundle(req: EvidenceBundleRequest) -> dict:
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is required")

    child_ids = _stable_ids(req.child_evidence, "chunk_id")
    fact_ids = _stable_ids(req.graph_facts, "fact_id")

    with tx() as conn:
        passage_rows = _fetch_passage_support(conn, child_ids)
        fact_rows = _fetch_fact_support(conn, fact_ids)

    selected_by_id = {
        str(item.get("chunk_id")): item
        for item in req.child_evidence
        if item.get("chunk_id")
    }
    passage_by_id = {row["chunk_id"]: row for row in passage_rows}

    grounded_passages: list[dict[str, Any]] = []
    for rank, chunk_id in enumerate(child_ids):
        row = passage_by_id.get(chunk_id)
        if row is None:
            raise HTTPException(
                status_code=409,
                detail=f"grounding invariant failed: chunk {chunk_id} not found in Postgres",
            )
        selected = selected_by_id.get(chunk_id, {})
        enriched = dict(row)
        enriched["contract_ids"] = list(selected.get("contract_ids") or [])
        enriched["retrieval_paths"] = _retrieval_paths(
            chunk_id,
            selected,
            req.child_dense_lane,
            req.child_lexical_lane,
            fallback_rank=rank,
        )
        grounded_passages.append(enriched)

    try:
        bundle = assemble_evidence_bundle(
            query,
            passages=grounded_passages,
            graph_facts=req.graph_facts,
            fact_support_rows=fact_rows,
        )
    except EvidenceAssemblyError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"grounding invariant failed: {exc}",
        ) from exc

    return bundle.model_dump()


def _stable_ids(items: list[dict[str, Any]], key: str) -> list[str]:
    return list(dict.fromkeys(
        str(item[key]) for item in items if item.get(key)
    ))


def _retrieval_paths(
    chunk_id: str,
    selected: dict[str, Any],
    dense_lane: list[dict[str, Any]],
    lexical_lane: list[dict[str, Any]],
    *,
    fallback_rank: int,
) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    for lane_name, lane in (
        ("child_dense", dense_lane),
        ("child_lexical", lexical_lane),
    ):
        for hit in lane:
            if hit.get("chunk_id") != chunk_id:
                continue
            paths.append({
                "lane": lane_name,
                "representation_kind": hit.get("representation_kind", "child_chunk"),
                "contract_id": hit.get("contract_id", ""),
                "rank": int(hit.get("rank", -1)),
                "raw_score": hit.get("raw_score"),
                "parent_id": hit.get("parent_id", ""),
            })

    # run_lanes adds siblings under a retrieved parent after direct fusion.
    # Those siblings are valid source evidence but are not direct lane hits.
    if not paths:
        parent_id = str(selected.get("parent_id") or "")
        paths.append({
            "lane": "parent_sibling_expansion",
            "representation_kind": "child_chunk",
            "contract_id": "structural-parent-expansion-v1",
            "rank": fallback_rank,
            "raw_score": None,
            "parent_id": parent_id,
        })
    return paths


def _fetch_passage_support(conn, chunk_ids: list[str]) -> list[dict[str, Any]]:
    if not chunk_ids:
        return []
    rows = conn.execute(
        """
        SELECT c.chunk_id, c.doc_id, d.source_name, c.text,
               c.char_start, c.char_end
          FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
         WHERE c.chunk_id = ANY(%s)
         ORDER BY c.chunk_id
        """,
        (chunk_ids,),
    ).fetchall()
    return [
        {
            "chunk_id": r[0],
            "doc_id": r[1],
            "source_name": r[2],
            "text": r[3],
            "char_start": r[4],
            "char_end": r[5],
        }
        for r in rows
    ]


def _fetch_fact_support(conn, fact_ids: list[str]) -> list[dict[str, Any]]:
    if not fact_ids:
        return []
    rows = conn.execute(
        """
        SELECT f.fact_id, f.predicate,
               f.subject_id, s.normalized_surface,
               f.object_id, o.normalized_surface,
               f.qualifiers, f.decision, f.rule_id, f.rule_version,
               f.provenance,
               e.evidence_id, e.doc_id, e.chunk_id, e.span_offsets,
               e.rule_id, e.extractor_version,
               d.source_name, c.text, c.char_start, c.char_end
          FROM facts f
          JOIN entities s ON s.entity_id = f.subject_id
          JOIN entities o ON o.entity_id = f.object_id
          JOIN evidence e ON e.fact_id = f.fact_id
          JOIN chunks c ON c.chunk_id = e.chunk_id
          JOIN documents d ON d.doc_id = e.doc_id
         WHERE f.fact_id = ANY(%s)
         ORDER BY f.fact_id, e.evidence_id
        """,
        (fact_ids,),
    ).fetchall()
    return [
        {
            "fact_id": r[0],
            "predicate": r[1],
            "subject_id": r[2],
            "subject": r[3],
            "object_id": r[4],
            "object": r[5],
            "qualifiers": r[6] or {},
            "decision": r[7],
            "rule_id": r[8],
            "rule_version": r[9],
            "provenance": r[10] or {},
            "evidence_id": r[11],
            "doc_id": r[12],
            "chunk_id": r[13],
            "span_offsets": r[14] or {},
            "evidence_rule_id": r[15],
            "extractor_version": r[16],
            "source_name": r[17],
            "text": r[18],
            "char_start": r[19],
            "char_end": r[20],
        }
        for r in rows
    ]

"""R1F GRAPH production route: promoted HYBRID + qualified graph lane.

GRAPH =
  promoted HYBRID Pass-1 (hybrid-retrieval-v1, lexical on, MMR off)
  + evidence-authorized, corpus-authorized canonical bidirectional
    hop1 graph expansion (the D2-qualified machinery: seeds resolved
    from entities attached to in-scope evidence, authorized-fact
    filtering, HIGH_MEDIUM allowlist, 8-seed / 20-fact caps, SPO
    orientation preserved).

The response carries the hierarchical synthesis context:
  per selected document: document summary (routing context) + sections
  with section summaries + exact child evidence; GRAPH_RELATIONSHIPS
  as a separate lane. Summaries are context, children are exact
  evidence, graph facts are relationships — never conflated.

Reuses orchestrator.api.fast readiness/failure semantics and the
existing _neo4j_expand (no second graph implementation).
"""
from __future__ import annotations

import time
from typing import Optional

from fastapi import HTTPException
from qdrant_client import QdrantClient

from polymath_shared.db import tx
from polymath_shared.hybrid import HybridRetrievalPlan
from polymath_shared.retrieval_modes import (
    GRAPH_MAX_FACTS,
    GRAPH_PLAN_VERSION,
    MODE_GRAPH,
    hybrid_mode_plan,
)
from polymath_shared.settings import get_settings

from polymath_shared.query_shape import plan_for_query

from orchestrator.api.fast import (
    _begin_retrieval,
    _embed_query,
    _ensure_fast_ready,
    _neighbor_lookup,
    _region_lookup,
    _rerank_children,
    _corpus_collections,
    degradations,
    FastSearcher,
)
from orchestrator.api.hybrid import _lexical_search


def _selected_surfaces(query: str, evidence: list[dict]) -> list[str]:
    """Query + selected-evidence terms for seed-surface matching
    (the qualified seed-resolution input convention)."""
    from polymath_shared.retrieval import tokens

    surfaces: list[str] = []
    for term in tokens(query):
        if len(term) > 3:
            surfaces.append(term)
    for c in evidence[:10]:
        for term in tokens(c.get("text") or ""):
            if len(term) > 5:
                surfaces.append(term)
    return list(dict.fromkeys(surfaces))[:12]


def graph_retrieve(query: str, corpus_id: str) -> dict:
    """Production GRAPH: one promoted HYBRID Pass-1 + qualified hop1."""
    _begin_retrieval()
    if corpus_id is None:
        raise HTTPException(status_code=422, detail={
            "error_code": "corpus_required",
            "message": "GRAPH requires an explicit corpus_id (authorized corpus scope)",
        })

    _ensure_fast_ready(corpus_id)

    from polymath_shared.hybrid import hybrid_retrieve

    plan = hybrid_mode_plan(MODE_GRAPH)
    collections = _corpus_collections([corpus_id])
    try:
        client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    except Exception as exc:
        raise HTTPException(status_code=502, detail={
            "error_code": "qdrant_unavailable",
            "message": f"qdrant unavailable: {type(exc).__name__}",
        }) from exc
    try:
        searcher = FastSearcher(client, collections)
        t0 = time.time()
        shaped = plan_for_query(
            query,
            HybridRetrievalPlan(**{**plan.__dict__, "corpus_ids": (corpus_id,)}),
        )
        result = hybrid_retrieve(
            query,
            plan=shaped,
            embed_query=_embed_query,
            routing_search=searcher,
            lexical_search=lambda q, k: _lexical_search(q, corpus_id, k),
            rerank_children=_rerank_children if shaped.rerank_enabled else None,
            neighbor_lookup=_neighbor_lookup,
            region_lookup=_region_lookup,
        )
        pass1_ms = (time.time() - t0) * 1000
    finally:
        client.close()

    evidence = result.final_evidence

    # qualified evidence-authorized corpus-authorized hop1 (D2 machinery)
    # FAILURE-TRANSPARENCY-V1: a Neo4j failure is a typed 502, never an
    # empty "no graph knowledge" result.
    from orchestrator.api.retrieve import graph_expand_or_502

    t0 = time.time()
    graph_facts = graph_expand_or_502(
        _selected_surfaces(query, evidence),
        [corpus_id],
        [c["chunk_id"] for c in evidence],
    )[:GRAPH_MAX_FACTS]
    graph_ms = (time.time() - t0) * 1000

    # hierarchical synthesis context: documents -> sections -> exact
    # evidence; graph facts as a separate lane
    with tx() as conn:
        section_rows = conn.execute(
            "SELECT chunk_id, summary FROM chunks WHERE chunk_id = ANY(%s)",
            ([s["parent_id"] for s in result.selected_sections],),
        ).fetchall()
    section_summary = {r[0]: r[1] or "" for r in section_rows}

    documents: list[dict] = []
    used_chunks: set[str] = set()
    for doc in result.selected_documents:
        doc_evidence = [c for c in evidence if c["doc_id"] == doc.doc_id]
        sections = []
        for s in result.selected_sections:
            if s["doc_id"] != doc.doc_id:
                continue
            sections.append({
                "parent_id": s["parent_id"],
                "summary": section_summary.get(s["parent_id"], ""),
                "summary_id": s["summary_id"],
                "evidence": [
                    {
                        "chunk_id": c["chunk_id"],
                        "locator": f"chunk:{c['chunk_id']}",
                        "arrival": c.get("arrival"),
                        "g3_score": c.get("rerank_score"),
                    }
                    for c in doc_evidence if c["parent_id"] == s["parent_id"]
                ],
            })
        orphan_evidence = [
            c for c in doc_evidence
            if c["parent_id"] not in {s["parent_id"] for s in sections}
        ]
        for c in doc_evidence:
            used_chunks.add(c["chunk_id"])
        documents.append({
            "doc_id": doc.doc_id,
            "document_summary": (doc.document_summary_hits[0].text
                                 if doc.document_summary_hits else None),
            "summary_id": (doc.document_summary_hits[0].summary_id
                           if doc.document_summary_hits else None),
            "aggregate_rank": doc.aggregate_rank,
            "rrf_contributions": {k: round(v, 6) for k, v in doc.rrf_contributions.items()},
            "sections": sections,
            "rescue_evidence": orphan_evidence,
        })
    # recall safety: rescue evidence from documents outside the winner
    # set must never be dropped (HYBRID invariant)
    unassigned_rescue = [
        c for c in evidence if c["chunk_id"] not in used_chunks
    ]

    return {
        "query": query,
        "meta": {
            "mode": MODE_GRAPH,
            "plan_version": GRAPH_PLAN_VERSION,
            "pass1_plan_version": result.plan.plan_version,
            "corpus_id": corpus_id,
            "graph_bounds": {"max_seeds": 8, "max_facts": GRAPH_MAX_FACTS},
            "document_count": len(documents),
            "evidence_count": len(evidence),
            "graph_fact_count": len(graph_facts),
            "degraded": degradations(),
        },
        "documents": documents,
        "unassigned_rescue_evidence": [
            {
                "chunk_id": c["chunk_id"],
                "doc_id": c["doc_id"],
                "parent_id": c["parent_id"],
                "locator": f"chunk:{c['chunk_id']}",
                "arrival": c.get("arrival"),
                "g3_score": c.get("rerank_score"),
            }
            for c in unassigned_rescue
        ],
        "graph_relationships": [
            {
                "fact_id": f["fact_id"],
                "predicate": f["predicate"],
                "subject_id": f["subject_id"],
                "subject": f["subject"],
                "object_id": f["object_id"],
                "object": f["object"],
            }
            for f in graph_facts
        ],
        "trace": {
            "lane_sizes": result.trace["lane_sizes"],
            "graph_seed_surfaces": _selected_surfaces(query, evidence)[:8],
            "latency_ms": {
                "pass1": round(pass1_ms, 1),
                "graph": round(graph_ms, 1),
                "total": round(pass1_ms + graph_ms, 1),
            },
        },
    }

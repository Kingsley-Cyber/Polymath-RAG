"""Retrieval API: POST /retrieve — the three-lane cross-domain route.

Returns the routing TRACE (document ranking with reasons, parent hits,
child evidence, graph expansion) — the caller judges the mapping, not
just the answer. Document routing is parallel and never a recall gate:
a child hit survives even when its document scores zero.

Answer generation lives outside this endpoint (AGENTS.md: keep answer
generation outside retrieval scoring and graph policy).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from polymath_shared.db import tx
from polymath_shared.projection_contracts import (
    EMBEDDING_CONTRACT,
    qdrant_collection_name,
)
from polymath_shared.retrieval import graph_expansion, run_lanes
from polymath_shared.settings import get_settings

router = APIRouter()

HIGH_MEDIUM_PREDICATES = {
    "founded", "created", "developed", "employs", "has_role", "leads",
    "member_of", "owns", "acquired", "subsidiary_of", "uses",
    "implemented_with", "causes", "enables", "influences", "depends_on",
    "is_a", "instance_of", "part_of", "located_in", "occurred_at",
    "measured_by", "transforms_into", "derived_from",
}


class RetrieveRequest(BaseModel):
    query: str
    corpus_id: Optional[str] = None
    limit: int = 10


@router.post("/retrieve")
async def retrieve(req: RetrieveRequest) -> dict:
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    corpus_id = req.corpus_id

    with tx() as conn:
        profiles = _fetch_profiles(conn, corpus_id)
        parents = _fetch_parents(conn, corpus_id)
        children_rows = _fetch_children_rows(conn, corpus_id)
        children = [r for r in children_rows if r["tier"] == "child"]
        parent_rows = [r for r in children_rows if r["tier"] == "parent"]
        # Parent lane scores PARENT summaries.
        parents = [
            {"chunk_id": r["chunk_id"], "doc_id": r["doc_id"], "summary": r["summary"]}
            for r in parent_rows
        ]

    def fetch_profiles():
        return profiles

    def fetch_parents():
        return parents

    def fetch_children(limit):
        return children[:limit]

    def child_search(limit):
        return _qdrant_search(query, corpus_id, limit)

    result = run_lanes(
        query,
        fetch_profiles=fetch_profiles,
        fetch_parents=fetch_parents,
        fetch_children=fetch_children,
        child_search=child_search,
    )

    result.graph_facts = graph_expansion(
        _entity_surfaces(query, result),
        expand=lambda surfaces: _neo4j_expand(surfaces),
    )

    return {
        "query": query,
        "document_routing": [
            {"rank": i, "doc_id": h.id, "score": round(h.score, 4), "why": h.why}
            for i, h in enumerate(result.doc_ranking[: req.limit])
        ],
        "parent_routing": [
            {"chunk_id": h.id, "score": round(h.score, 4)}
            for h in result.parent_ranking[: req.limit]
        ],
        "selected_documents": result.selected_documents[: req.limit],
        "child_evidence": [
            {k: c[k] for k in ("chunk_id", "doc_id", "parent_id", "score") if k in c}
            for c in result.selected_children[: req.limit]
        ],
        "child_evidence_count": len(result.selected_children),
        "graph_facts": result.graph_facts,
    }


def _fetch_profiles(conn, corpus_id: Optional[str]) -> list[dict]:
    if corpus_id:
        rows = conn.execute(
            """
            SELECT doc_id, retrieval_profile FROM documents
             WHERE corpus_id = %s AND retrieval_profile IS NOT NULL
            """,
            (corpus_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT doc_id, retrieval_profile FROM documents WHERE retrieval_profile IS NOT NULL"
        ).fetchall()
    return [{"doc_id": r[0], "retrieval_profile": r[1] or {}} for r in rows]


def _fetch_parents(conn, corpus_id: Optional[str]) -> list[dict]:
    if corpus_id:
        rows = conn.execute(
            """
            SELECT c.chunk_id, c.doc_id, c.summary FROM chunks c
              JOIN documents d ON d.doc_id = c.doc_id
             WHERE c.tier = 'parent' AND d.corpus_id = %s
            """,
            (corpus_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT chunk_id, doc_id, summary FROM chunks WHERE tier = 'parent'"
        ).fetchall()
    return [{"chunk_id": r[0], "doc_id": r[1], "summary": r[2]} for r in rows]


def _fetch_children_rows(conn, corpus_id: Optional[str]) -> list[dict]:
    if corpus_id:
        rows = conn.execute(
            """
            SELECT c.chunk_id, c.doc_id, c.parent_id, c.tier, c.text, c.summary
              FROM chunks c
              JOIN documents d ON d.doc_id = c.doc_id
             WHERE d.corpus_id = %s
            """,
            (corpus_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT chunk_id, doc_id, parent_id, tier, text, summary FROM chunks"
        ).fetchall()
    return [
        {"chunk_id": r[0], "doc_id": r[1], "parent_id": r[2], "tier": r[3],
         "text": r[4], "summary": r[5]}
        for r in rows
    ]


def _qdrant_search(query: str, corpus_id: Optional[str], limit: int) -> list[dict]:
    from polymath_shared.projection_contracts import embed
    from polymath_shared.stores import qdrant_client as _qdrant_client

    client = _qdrant_client(timeout=30)
    try:
        collections = [c.name for c in client.get_collections().collections]
        targets = [
            name for name in collections
            if name.startswith("polymath_") and (
                not corpus_id or name == qdrant_collection_name(corpus_id, EMBEDDING_CONTRACT)
            )
        ]
        vector = embed(query, EMBEDDING_CONTRACT)
        out: list[dict] = []
        for collection in targets:
            hits = client.query_points(
                collection_name=collection,
                query=vector,
                limit=limit,
                with_payload=True,
            ).points
            for p in hits:
                payload = p.payload or {}
                out.append({
                    "chunk_id": payload.get("chunk_id", ""),
                    "doc_id": payload.get("doc_id", ""),
                    "parent_id": payload.get("parent_id", ""),
                    "text": payload.get("text", ""),
                    "vector_score": p.score or 0.0,
                })
        return out
    except Exception:
        return []
    finally:
        client.close()


def _entity_surfaces(query: str, result) -> list[str]:
    from polymath_shared.retrieval import tokens

    surfaces: list[str] = []
    for term in tokens(query):
        if len(term) > 3:
            surfaces.append(term)
    for child in result.selected_children[:10]:
        for term in tokens(child.get("text", "")):
            if len(term) > 5:
                surfaces.append(term)
    return list(dict.fromkeys(surfaces))[:12]


def _neo4j_expand(surfaces: list[str]) -> list[dict]:
    from polymath_shared.stores import neo4j_driver

    driver = neo4j_driver()
    try:
        with driver.session() as session:
            matched = session.run(
                """
                MATCH (e:Entity)
                WHERE any(s IN $surfaces WHERE toLower(e.surface) CONTAINS s)
                   OR any(s IN $surfaces WHERE s CONTAINS toLower(e.surface))
                RETURN e.entity_id AS entity_id, e.surface AS surface
                LIMIT 8
                """,
                surfaces=surfaces,
            ).data()
            if not matched:
                return []
            ids = [m["entity_id"] for m in matched]
            rows = session.run(
                """
                MATCH (s:Entity)-[r:REL]->(o:Entity)
                WHERE s.entity_id IN $ids AND r.predicate IN $predicates
                RETURN r.fact_id AS fact_id, r.predicate AS predicate,
                       s.surface AS subject, o.surface AS object
                LIMIT 20
                """,
                ids=ids,
                predicates=sorted(HIGH_MEDIUM_PREDICATES),
            ).data()
            return rows
    except Exception:
        return []
    finally:
        driver.close()

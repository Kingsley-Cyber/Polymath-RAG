"""Retrieval API: POST /retrieve plus R3a grounded evidence assembly.

/retrieve returns the routing TRACE (document ranking with reasons, parent
hits, child evidence, graph expansion). Document routing is parallel and
never a recall gate: a child hit survives even when its document scores zero.

/evidence-bundle runs that retrieval path, then re-resolves every selected
passage and graph fact against authoritative Postgres state. Answer
generation remains outside both endpoints.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from polymath_shared.db import tx
from polymath_shared.embedding_contracts import active_contract
from polymath_shared.projection_contracts import qdrant_collection_name
from polymath_shared.retrieval import (
    EvidenceAssemblyError,
    assemble_evidence_bundle,
    graph_expansion,
    run_lanes,
)
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

    def _hit(h) -> dict:
        return {
            "source_id": h.source_id,
            "representation_kind": h.representation_kind,
            "contract_id": h.contract_id,
            "rank": h.rank,
            "raw_score": round(h.raw_score, 4),
            "document_id": h.document_id,
            "parent_id": h.parent_id,
            "chunk_id": h.chunk_id,
            "why": h.why,
        }

    return {
        "query": query,
        # Per-lane ablation BEFORE fusion (G2 gate 2).
        "document_lane": [_hit(h) for h in result.document_ranking[: req.limit]],
        "parent_lane": [_hit(h) for h in result.parent_ranking[: req.limit]],
        "child_dense_lane": [_hit(h) for h in result.child_dense_ranking[: req.limit]],
        "child_lexical_lane": [_hit(h) for h in result.child_lexical_ranking[: req.limit]],
        # Fused view.
        "selected_documents": result.selected_documents[: req.limit],
        "child_evidence_count": len(result.selected_children),
        "child_evidence": [c for c in result.selected_children[: req.limit]],
        "graph_facts": result.graph_facts,
    }


@router.post("/evidence-bundle")
async def evidence_bundle(req: RetrieveRequest) -> dict:
    """R3a: retrieve, then assemble only source-resolvable support.

    The client supplies only the query scope. It cannot inject its own graph
    facts or evidence trace. Every selected chunk/fact is re-resolved from
    Postgres before it enters the bundle.
    """
    trace = await retrieve(req)
    child_ids = _stable_ids(trace["child_evidence"], "chunk_id")
    fact_ids = _stable_ids(trace["graph_facts"], "fact_id")

    with tx() as conn:
        passage_rows = _fetch_passage_support(conn, child_ids)
        fact_rows = _fetch_fact_support(conn, fact_ids)

    selected_by_id = {
        str(item.get("chunk_id")): item
        for item in trace["child_evidence"]
        if item.get("chunk_id")
    }
    passage_by_id = {row["chunk_id"]: row for row in passage_rows}
    grounded_passages: list[dict] = []

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
            trace["child_dense_lane"],
            trace["child_lexical_lane"],
            fallback_rank=rank,
        )
        grounded_passages.append(enriched)

    try:
        bundle = assemble_evidence_bundle(
            trace["query"],
            passages=grounded_passages,
            graph_facts=trace["graph_facts"],
            fact_support_rows=fact_rows,
        )
    except EvidenceAssemblyError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"grounding invariant failed: {exc}",
        ) from exc

    return bundle.model_dump()


def _stable_ids(items: list[dict], key: str) -> list[str]:
    return list(dict.fromkeys(str(item[key]) for item in items if item.get(key)))


def _retrieval_paths(
    chunk_id: str,
    selected: dict,
    dense_lane: list[dict],
    lexical_lane: list[dict],
    *,
    fallback_rank: int,
) -> list[dict]:
    paths: list[dict] = []
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

    if not paths:
        paths.append({
            "lane": "parent_sibling_expansion",
            "representation_kind": "child_chunk",
            "contract_id": "structural-parent-expansion-v1",
            "rank": fallback_rank,
            "raw_score": None,
            "parent_id": str(selected.get("parent_id") or ""),
        })
    return paths


def _fetch_passage_support(conn, chunk_ids: list[str]) -> list[dict]:
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
            "chunk_id": r[0], "doc_id": r[1], "source_name": r[2],
            "text": r[3], "char_start": r[4], "char_end": r[5],
        }
        for r in rows
    ]


def _fetch_fact_support(conn, fact_ids: list[str]) -> list[dict]:
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
               e.rule_id, e.rule_version, e.extractor_version, e.gliner_scores,
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
            "fact_id": r[0], "predicate": r[1],
            "subject_id": r[2], "subject": r[3],
            "object_id": r[4], "object": r[5],
            "qualifiers": r[6] or {}, "decision": r[7],
            "rule_id": r[8], "rule_version": r[9], "provenance": r[10] or {},
            "evidence_id": r[11], "doc_id": r[12], "chunk_id": r[13],
            "span_offsets": r[14] or {}, "evidence_rule_id": r[15],
            "evidence_rule_version": r[16], "extractor_version": r[17],
            "gliner_scores": r[18] or {}, "source_name": r[19],
            "text": r[20], "char_start": r[21], "char_end": r[22],
        }
        for r in rows
    ]


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
    from polymath_shared.stores import qdrant_client as _qdrant_client

    contract = active_contract()
    client = _qdrant_client(timeout=30)
    try:
        collections = [c.name for c in client.get_collections().collections]
        # Only collections of the ACTIVE contract: other contract versions
        # have different dimensions and must never be queried with this
        # contract's vectors.
        contract_suffix = f"_{contract.contract_id}"
        targets = [
            name for name in collections
            if name.startswith("polymath_")
            and name.endswith(contract_suffix)
            and (not corpus_id or name == qdrant_collection_name(corpus_id, contract.contract_id))
        ]
        if contract.embed_fn is not None:
            vector = contract.embed(query, "query")
        else:
            from polymath_shared.clients import EmbedderClient

            embedder = EmbedderClient()
            try:
                vector = embedder.embed([query], "query")["vectors"][0]
            finally:
                embedder.close()
        out: list[dict] = []
        for collection in targets:
            try:
                hits = client.query_points(
                    collection_name=collection,
                    query=vector,
                    limit=limit,
                    with_payload=True,
                ).points
            except Exception:
                continue  # one broken collection never kills the lane
            for p in hits:
                payload = p.payload or {}
                out.append({
                    "chunk_id": payload.get("chunk_id", ""),
                    "doc_id": payload.get("doc_id", ""),
                    "parent_id": payload.get("parent_id", ""),
                    "text": payload.get("text", ""),
                    "corpus_id": payload.get("corpus_id", ""),
                    "contract_id": contract.contract_id,
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

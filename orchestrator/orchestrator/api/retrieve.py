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
from polymath_shared.embedding_contracts import active_contract
from polymath_shared.projection_contracts import qdrant_collection_name
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
    mode: Optional[str] = None


@router.post("/retrieve")
async def retrieve(req: RetrieveRequest) -> dict:
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    corpus_id = req.corpus_id

    # R1C: explicit production modes. FAST maps deterministically to the
    # qualified pass1-retrieval-v1 engine; LEGACY is the frozen lane
    # route retained for regression (G1/G2 golden contracts).
    from polymath_shared.retrieval_modes import MODE_FAST, validate_mode

    mode = validate_mode(req.mode)
    if mode == MODE_FAST:
        from orchestrator.api.fast import fast_retrieve

        return fast_retrieve(query, corpus_id)

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
        expand=lambda surfaces: _neo4j_expand(
            surfaces,
            corpus_id=corpus_id,
            preferred_chunk_ids=[c["chunk_id"] for c in result.selected_children[:10]],
        ),
    )

    # G3 candidate: cross-representation reranking over the FUSED views
    # only (per-lane ablations stay untouched). Enabled via
    # POLYMATH_G3_RERANKER=1; unavailable rerankers fail loudly.
    from polymath_shared.rerank import RerankUnavailable, apply_rerank

    try:
        selected_documents, selected_children = apply_rerank(
            query, result.selected_documents, result.selected_children,
        )
    except RerankUnavailable as exc:
        raise HTTPException(status_code=502, detail={
            "error_code": "rerank_unavailable",
            "message": str(exc),
        }) from exc

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
        # Fused views (G3: reranked when the candidate is enabled).
        "selected_documents": selected_documents[: req.limit],
        "child_evidence_count": len(selected_children),
        "child_evidence": [
            c for c in selected_children[: req.limit]
        ],
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


def _surface_matches(surface: str, term: str) -> bool:
    s, t = surface.lower(), term.lower()
    return bool(t) and (t in s or s in t)


def _corpus_seed_ids(
    conn,
    surfaces: list[str],
    corpus_id: Optional[str],
    preferred_chunk_ids: list[str],
) -> list[str]:
    """Corpus-authorized seed resolution (D2).

    Seeds are entities attached to in-scope evidence — never a raw
    surface match against the unrestricted shared graph. Preference
    order: entities attached to the RETRIEVED evidence chunks first,
    then any entity evidenced in the active corpus; ties broken by
    entity_id for determinism. MENTION_ONLY entities can never seed
    (they have no graph nodes). GLOBAL identity is untouched."""
    from polymath_shared.neo4j_eligibility import entity_eligible_sql

    rows = conn.execute(
        """
        SELECT DISTINCT e.entity_id, e.normalized_surface,
               bool_or(ev.chunk_id = ANY(%s)) AS preferred
          FROM entities e
          JOIN facts f ON f.subject_id = e.entity_id OR f.object_id = e.entity_id
          JOIN evidence ev ON ev.fact_id = f.fact_id
          JOIN documents d ON d.doc_id = ev.doc_id
         WHERE (""" + ("" if corpus_id is None else "d.corpus_id = %s AND ") +
        entity_eligible_sql("e") + """)
         GROUP BY e.entity_id, e.normalized_surface
        """,
        (preferred_chunk_ids or [], *( [corpus_id] if corpus_id else [] )),
    ).fetchall()
    matched = [
        (bool(pref), eid) for eid, surf, pref in rows
        if any(_surface_matches(surf, term) for term in surfaces)
    ]
    matched.sort(key=lambda x: (not x[0], x[1]))
    return [eid for _, eid in matched[:8]]


def _authorized_fact_ids(conn, corpus_id: Optional[str]) -> Optional[set]:
    """Facts authorized for graph expansion under the active corpus.

    A fact is authorized when it is supported by evidence in the active
    corpus. Facts supported EXCLUSIVELY by another corpus are excluded
    (D2). Facts with NO evidence anywhere are INTENTIONALLY kept: an
    unresolvable reference must fail loudly in assembly (frozen R3a
    acceptance), never be silently hidden. With no corpus scope
    (cross-corpus route), every projected fact is authorized."""
    if corpus_id is None:
        return None
    rows = conn.execute(
        """
        SELECT DISTINCT ev.fact_id FROM evidence ev
          JOIN documents d ON d.doc_id = ev.doc_id
         WHERE d.corpus_id = %s
        """,
        (corpus_id,),
    ).fetchall()
    in_scope = {r[0] for r in rows}
    # Evidence-less facts stay authorized so assembly fails loudly.
    rows = conn.execute(
        """
        SELECT f.fact_id FROM facts f
         WHERE NOT EXISTS (SELECT 1 FROM evidence e WHERE e.fact_id = f.fact_id)
        """
    ).fetchall()
    return in_scope | {r[0] for r in rows}


def _neo4j_expand(
    surfaces: list[str],
    corpus_id: Optional[str] = None,
    preferred_chunk_ids: Optional[list[str]] = None,
) -> list[dict]:
    """One-hop graph expansion (production, canonical bidirectional,
    corpus-authorized).

    Two DIRECTED clauses preserve stored fact orientation by
    construction; an incoming edge only makes the EXISTING fact
    eligible, never reverses or invents a relation. HIGH_MEDIUM
    allowlist, 8-seed / 20-fact caps, dedupe by fact_id, stable
    ORDER BY fact_id. Seeds are resolved from entities attached to
    in-scope evidence (D2); facts supported exclusively by another
    corpus are never returned (D2)."""
    from polymath_shared.stores import neo4j_driver

    with tx() as conn:
        ids = _corpus_seed_ids(conn, surfaces, corpus_id, preferred_chunk_ids or [])
        authorized = _authorized_fact_ids(conn, corpus_id)

    if not ids:
        return []

    driver = neo4j_driver()
    try:
        with driver.session() as session:
            rows = session.run(
                """
                CALL () {
                    MATCH (s:Entity)-[r:REL]->(o:Entity)
                    WHERE s.entity_id IN $ids AND r.predicate IN $predicates
                    RETURN r.fact_id AS fact_id, r.predicate AS predicate,
                           s.entity_id AS subject_id, s.surface AS subject,
                           o.entity_id AS object_id, o.surface AS object
                    UNION
                    MATCH (s:Entity)-[r:REL]->(o:Entity)
                    WHERE o.entity_id IN $ids AND r.predicate IN $predicates
                    RETURN r.fact_id AS fact_id, r.predicate AS predicate,
                           s.entity_id AS subject_id, s.surface AS subject,
                           o.entity_id AS object_id, o.surface AS object
                }
                RETURN fact_id, predicate, subject_id, subject, object_id, object
                ORDER BY fact_id
                LIMIT 20
                """,
                ids=ids,
                predicates=sorted(HIGH_MEDIUM_PREDICATES),
            ).data()
            if authorized is not None:
                rows = [r for r in rows if r["fact_id"] in authorized]
            return rows
    except Exception:
        return []
    finally:
        driver.close()

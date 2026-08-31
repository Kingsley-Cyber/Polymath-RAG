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
    # LLM-DIRECT-FACTS-V1: the relation ontology (17 + RELATED_TO) as
    # stored by workers/llm_direct.py — uppercase enum ids.
    "IS_A", "PART_OF", "HAS_PROPERTY", "SAME_AS", "USES", "REQUIRES",
    "PRODUCES", "CAUSES", "REGULATES", "CORRELATES_WITH", "CONSTRAINED_BY",
    "PRECEDES", "MEASURES", "LOCATED_IN", "ALTERNATIVE_TO", "OPPOSES",
    "ACTS_ON", "RELATED_TO",
}


class RetrieveRequest(BaseModel):
    query: str
    corpus_id: Optional[str] = None
    corpus_ids: Optional[list[str]] = None
    workspace: Optional[str] = None
    all_authorized: bool = False
    limit: int = 10
    mode: Optional[str] = None


def resolve_http_scope(conn, req) -> "QueryScope":
    """QUERY-SCOPE-V1 at the route boundary: every public query route
    resolves EXACTLY ONE explicit scope before any retrieval dispatch.
    Missing scope is a typed 422, never search-everything (the legacy
    implicit-all path loaded 41,831 rows across 77 corpora — measured
    by the 2026-08-26 SMART verification)."""
    from polymath_shared.query_scope import (
        QueryScopeRequired,
        UnknownQueryScope,
        resolve_query_scope,
    )

    try:
        return resolve_query_scope(
            conn,
            corpus_id=getattr(req, "corpus_id", None),
            corpus_ids=getattr(req, "corpus_ids", None),
            workspace=getattr(req, "workspace", None),
            all_authorized=bool(getattr(req, "all_authorized", False)))
    except QueryScopeRequired:
        raise HTTPException(status_code=422, detail={
            "error_code": "QUERY_SCOPE_REQUIRED",
            "message": "explicit query scope required: supply one of "
                       "corpus_id / corpus_ids / workspace / all_authorized",
        })
    except UnknownQueryScope as exc:
        raise HTTPException(status_code=404, detail={
            "error_code": "QUERY_SCOPE_UNKNOWN", "message": str(exc),
        })
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "error_code": "QUERY_SCOPE_AMBIGUOUS", "message": str(exc),
        })


def graph_expand_or_502(
    surfaces: list[str],
    corpus_ids: list[str],
    preferred_chunk_ids: list[str],
    seed_entity_ids: list[str] | None = None,
) -> list[dict]:
    """FAILURE-TRANSPARENCY-V1: one translation point from the typed
    graph-store failure to the typed HTTP failure. GRAPH_SUCCESS with
    zero relationships stays an empty list; a backend failure is 502."""
    from polymath_shared.stores import GraphBackendUnavailable

    try:
        return _neo4j_expand(
            surfaces,
            corpus_ids=corpus_ids,
            preferred_chunk_ids=preferred_chunk_ids,
            seed_entity_ids=seed_entity_ids,
        )
    except GraphBackendUnavailable as exc:
        raise HTTPException(status_code=502, detail={
            "error_code": "graph_backend_unavailable",
            "message": str(exc),
        }) from exc


def single_corpus_or_422(scope, mode: str) -> str:
    """FAST/HYBRID/GRAPH are single-corpus engines (collection-per-
    corpus projection). A wider resolved scope fails closed — it is
    never silently narrowed or fanned out."""
    if len(scope.corpus_ids) != 1:
        raise HTTPException(status_code=422, detail={
            "error_code": "mode_requires_single_corpus",
            "message": f"mode {mode!r} retrieves over exactly one corpus; "
                       f"resolved scope has {len(scope.corpus_ids)}",
        })
    return scope.corpus_ids[0]


@router.post("/retrieve")
async def retrieve(req: RetrieveRequest) -> dict:
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is required")

    with tx() as conn:
        scope = resolve_http_scope(conn, req)

    # R1C: explicit production modes. FAST maps deterministically to the
    # qualified pass1-retrieval-v1 engine; LEGACY is the frozen lane
    # route retained for regression (G1/G2 golden contracts).
    from polymath_shared.retrieval_modes import MODE_FAST, MODE_GRAPH, MODE_HYBRID, validate_mode

    mode = validate_mode(req.mode)
    if mode == MODE_FAST:
        from orchestrator.api.fast import fast_retrieve

        return fast_retrieve(query, single_corpus_or_422(scope, mode))
    if mode == MODE_HYBRID:
        from orchestrator.api.hybrid import hybrid_fast_retrieve

        return hybrid_fast_retrieve(query, single_corpus_or_422(scope, mode))
    if mode == MODE_GRAPH:
        from orchestrator.api.graph import graph_retrieve

        return graph_retrieve(query, single_corpus_or_422(scope, mode))

    corpus_ids = list(scope.corpus_ids)
    with tx() as conn:
        profiles = _fetch_profiles(conn, corpus_ids)
        parents = _fetch_parents(conn, corpus_ids)
        children_rows = _fetch_children_rows(conn, corpus_ids)
        children = [r for r in children_rows if r["tier"] == "child"]
        # ONE-SUMMARY-AUTHORITY (audit F5): the parent lane scores the
        # compiled cards from _fetch_parents — the chunks.summary
        # override that shadowed it is gone.

    def fetch_profiles():
        return profiles

    def fetch_parents():
        return parents

    def fetch_children(limit):
        return children[:limit]

    def child_search(limit):
        return _qdrant_search(query, corpus_ids, limit)

    result = run_lanes(
        query,
        fetch_profiles=fetch_profiles,
        fetch_parents=fetch_parents,
        fetch_children=fetch_children,
        child_search=child_search,
    )

    result.graph_facts = graph_expansion(
        _entity_surfaces(query, result),
        expand=lambda surfaces: graph_expand_or_502(
            surfaces, corpus_ids,
            [c["chunk_id"] for c in result.selected_children[:10]],
        ),
    )

    # G3 candidate: cross-representation reranking over the FUSED views
    # only (per-lane ablations stay untouched). Enabled via
    # POLYMATH_G3_RERANKER=1. NEVER-ERROR-ON-A-COLD-MODEL: an
    # unreachable reranker degrades to fusion order (same candidates,
    # same recall — it only reorders) rather than failing the query.
    from polymath_shared.rerank import RerankUnavailable, apply_rerank

    from orchestrator.api.fast import _RERANK_DEGRADED

    try:
        selected_documents, selected_children = apply_rerank(
            query, result.selected_documents, result.selected_children,
        )
    except RerankUnavailable as exc:
        _RERANK_DEGRADED.set(str(exc)[:300])
        selected_documents = result.selected_documents
        selected_children = result.selected_children

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


def _fetch_profiles(conn, corpus_ids: list[str]) -> list[dict]:
    # QUERY-SCOPE-V1: helpers take a RESOLVED corpus set. There is no
    # implicit-all branch — a missing scope fails at the route boundary.
    rows = conn.execute(
        """
        SELECT doc_id, retrieval_profile FROM documents
         WHERE corpus_id = ANY(%s) AND retrieval_profile IS NOT NULL
        """,
        (list(corpus_ids),),
    ).fetchall()
    return [{"doc_id": r[0], "retrieval_profile": r[1] or {}} for r in rows]


def _fetch_parents(conn, corpus_ids: list[str]) -> list[dict]:
    """ONE-SUMMARY-AUTHORITY (audit F5, verified drift): this lane used
    to score chunks.summary while FAST routed on the compiled cards —
    two different texts for the same parent. retrieval_summaries ACTIVE
    rows are the declared authority (register 4.4.8); chunks.summary is
    the fallback for parents the compiler has not carded."""
    rows = conn.execute(
        """
        SELECT c.chunk_id, c.doc_id,
               COALESCE(rs.summary_text, c.summary) AS summary
          FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
          LEFT JOIN retrieval_summaries rs
                 ON rs.parent_id = c.chunk_id AND rs.active
                AND rs.kind = 'section_retrieval_summary'
         WHERE c.tier = 'parent' AND d.corpus_id = ANY(%s)
        """,
        (list(corpus_ids),),
    ).fetchall()
    return [{"chunk_id": r[0], "doc_id": r[1], "summary": r[2]} for r in rows]


def _fetch_children_rows(conn, corpus_ids: list[str]) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.chunk_id, c.doc_id, c.parent_id, c.tier, c.text, c.summary
          FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
         WHERE d.corpus_id = ANY(%s)
        """,
        (list(corpus_ids),),
    ).fetchall()
    return [
        {"chunk_id": r[0], "doc_id": r[1], "parent_id": r[2], "tier": r[3],
         "text": r[4], "summary": r[5]}
        for r in rows
    ]


def _qdrant_search(query: str, corpus_ids: list[str], limit: int) -> list[dict]:
    from polymath_shared.stores import qdrant_client as _qdrant_client

    contract = active_contract()
    client = _qdrant_client(timeout=30)
    try:
        collections = [c.name for c in client.get_collections().collections]
        # Only collections of the ACTIVE contract: other contract versions
        # have different dimensions and must never be queried with this
        # contract's vectors. Scope: ONLY the resolved corpora's
        # collections — never every collection on the server.
        allowed = {
            qdrant_collection_name(cid, contract.contract_id)
            for cid in corpus_ids
        }
        contract_suffix = f"_{contract.contract_id}"
        targets = [
            name for name in collections
            if name.startswith("polymath_")
            and name.endswith(contract_suffix)
            and name in allowed
        ]
        if contract.embed_fn is not None:
            vector = contract.embed(query, "query")
        else:
            from polymath_shared.clients import EmbedderClient

            from orchestrator.api.fast import _await_embedder

            embedder = EmbedderClient()
            try:
                # WAKE-ON-QUERY: give the autopilot time to start a
                # parked embedder before the call fails typed.
                _await_embedder(embedder)
                vector = embedder.embed([query], "query")["vectors"][0]
            finally:
                embedder.close()
        out: list[dict] = []
        # CHILD-LANE-KIND-FILTER (measured 2026-08-30): the §11 build put
        # entity cards, procedures, concepts and summaries into the SAME
        # collection; an unfiltered dense search let every kind compete in
        # the child lane and surfaced them as empty-chunk_id junk rows.
        # This lane is the CHILD lane: children only, scoped to the
        # resolved corpora.
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue
        child_filter = Filter(must=[
            FieldCondition(key="representation_kind",
                           match=MatchValue(value="routing_child")),
            FieldCondition(key="corpus_id",
                           match=MatchAny(any=list(corpus_ids))),
        ])
        for collection in targets:
            try:
                hits = client.query_points(
                    collection_name=collection,
                    query=vector,
                    query_filter=child_filter,
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
    corpus_ids: Optional[list[str]],
    preferred_chunk_ids: list[str],
    seed_entity_ids: Optional[list[str]] = None,
) -> list[str]:
    """Corpus-authorized seed resolution (D2).

    Seeds are entities attached to in-scope evidence — never a raw
    surface match against the unrestricted shared graph. Preference
    order: entities attached to the RETRIEVED evidence chunks first,
    then any entity evidenced in the active corpus; ties broken by
    entity_id for determinism. MENTION_ONLY entities can never seed
    (they have no graph nodes). GLOBAL identity is untouched.

    corpus_ids=None is the UNSCOPED qualification form (eval harnesses
    only); every production route resolves scope before reaching here."""
    from polymath_shared.neo4j_eligibility import entity_eligible_sql

    rows = conn.execute(
        """
        SELECT DISTINCT e.entity_id, e.normalized_surface,
               bool_or(ev.chunk_id = ANY(%s)) AS preferred
          FROM entities e
          JOIN facts f ON f.subject_id = e.entity_id OR f.object_id = e.entity_id
          JOIN evidence ev ON ev.fact_id = f.fact_id
          JOIN documents d ON d.doc_id = ev.doc_id
         WHERE (""" + ("" if corpus_ids is None else "d.corpus_id = ANY(%s) AND ") +
        entity_eligible_sql("e") + """)
         GROUP BY e.entity_id, e.normalized_surface
        """,
        (preferred_chunk_ids or [],
         *([list(corpus_ids)] if corpus_ids is not None else [])),
    ).fetchall()
    # CARD-SEEDS-V1 (audit F1, measured): token surfaces split multiword
    # entities ("Amazon S3" -> 'amazon' + dropped 's3') and junk unigrams
    # burned the 8-seed cap -> 0 facts on entity questions. Entity ids
    # resolved via routing_entity cards seed FIRST (still restricted to
    # the corpus-authorized eligible rows fetched above — the card lane
    # proposes, this authorization decides); surface matching remains the
    # fallback vocabulary.
    card_set = set(seed_entity_ids or [])
    card_seeds = sorted(eid for eid, _surf, _pref in rows if eid in card_set)
    matched = [
        (bool(pref), eid) for eid, surf, pref in rows
        if eid not in card_set
        and any(_surface_matches(surf, term) for term in surfaces)
    ]
    matched.sort(key=lambda x: (not x[0], x[1]))
    return (card_seeds + [eid for _, eid in matched])[:8]


def _authorized_fact_ids(conn, corpus_ids: Optional[list[str]]) -> Optional[set]:
    """Facts authorized for graph expansion under the resolved scope.

    A fact is authorized when it is supported by evidence in a scoped
    corpus. Facts supported EXCLUSIVELY by another corpus are excluded
    (D2). Facts with NO evidence anywhere are INTENTIONALLY kept: an
    unresolvable reference must fail loudly in assembly (frozen R3a
    acceptance), never be silently hidden. corpus_ids=None is the
    UNSCOPED qualification form (eval harnesses only)."""
    if corpus_ids is None:
        return None
    rows = conn.execute(
        """
        SELECT DISTINCT ev.fact_id FROM evidence ev
          JOIN documents d ON d.doc_id = ev.doc_id
         WHERE d.corpus_id = ANY(%s)
        """,
        (list(corpus_ids),),
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
    corpus_ids: Optional[list[str]] = None,
    seed_entity_ids: Optional[list[str]] = None,
) -> list[dict]:
    """One-hop graph expansion (production, canonical bidirectional,
    corpus-authorized).

    Two DIRECTED clauses preserve stored fact orientation by
    construction; an incoming edge only makes the EXISTING fact
    eligible, never reverses or invents a relation. HIGH_MEDIUM
    allowlist, 8-seed / 20-fact caps, dedupe by fact_id, stable
    ORDER BY fact_id. Seeds are resolved from entities attached to
    in-scope evidence (D2); facts supported exclusively by another
    corpus are never returned (D2).

    Scope: pass corpus_ids (resolved QUERY-SCOPE-V1 set) from every
    production caller; corpus_id remains for single-corpus callers and
    the eval qualification harnesses. Both None = UNSCOPED (eval only)."""
    from polymath_shared.stores import neo4j_driver

    if corpus_ids is None and corpus_id is not None:
        corpus_ids = [corpus_id]

    with tx() as conn:
        ids = _corpus_seed_ids(conn, surfaces, corpus_ids, preferred_chunk_ids or [],
                               seed_entity_ids or [])
        authorized = _authorized_fact_ids(conn, corpus_ids)

    if not ids:
        return []

    driver = neo4j_driver()
    try:
        with driver.session() as session:
            # GRAPH-LIFECYCLE-V2 (P9): authorization is applied INSIDE
            # the query, before LIMIT. It used to run in Python after
            # the limit, so stale edges consumed answer slots and were
            # then discarded — MEASURED on the live graph, 85 of 545
            # REL edges (15.6%) are unauthorized and up to 8 of the 20
            # slots in a fact_id window were garbage. That is
            # answer-bearing evidence displaced by rows nobody may see.
            auth_filter = "" if authorized is None else \
                " AND r.fact_id IN $authorized"
            rows = session.run(
                """
                CALL () {
                    MATCH (s:Entity)-[r:REL]->(o:Entity)
                    WHERE s.entity_id IN $ids AND r.predicate IN $predicates
                      """ + auth_filter + """
                    RETURN r.fact_id AS fact_id, r.predicate AS predicate,
                           s.entity_id AS subject_id, s.surface AS subject,
                           o.entity_id AS object_id, o.surface AS object
                    UNION
                    MATCH (s:Entity)-[r:REL]->(o:Entity)
                    WHERE o.entity_id IN $ids AND r.predicate IN $predicates
                      """ + auth_filter + """
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
                authorized=(None if authorized is None else sorted(authorized)),
            ).data()
            if authorized is not None:
                # belt and braces: the Cypher filter is the authority,
                # this can only ever be a no-op now.
                rows = [r for r in rows if r["fact_id"] in authorized]
            return rows
    except Exception as exc:
        # FAILURE-TRANSPARENCY-V1: a graph-store failure is typed and
        # loud — it must never masquerade as a valid zero-relationship
        # result (SMART verification REQ-014).
        from polymath_shared.stores import GraphBackendUnavailable

        raise GraphBackendUnavailable(
            f"neo4j expansion failed: {type(exc).__name__}: {exc}") from exc
    finally:
        driver.close()

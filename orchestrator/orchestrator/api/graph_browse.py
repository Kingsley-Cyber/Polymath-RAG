"""GRAPH-BROWSE-V1 — the smallest read-only graph API the V2 UI needs (F9).

Two endpoints, both READ-ONLY, both corpus-scoped, both bounded:

    GET /graph/entities?corpus_id=&q=&limit=
    GET /graph/entity/{entity_id}/relationships?corpus_id=&limit=

**Source-attested only.** FRONTEND-V2-PLAN §8: "Only source-attested relationships may
appear as canonical truth." Neo4j holds the topology (`(s:Entity)-[r:REL]->(o:Entity)`
with `predicate` + `fact_id`) but carries NO corpus and NO provenance. Attestation lives
in Postgres `evidence(fact_id, doc_id, chunk_id, span_offsets)`. A relationship is
therefore returned ONLY when it has at least one evidence row whose document belongs to
the requested corpus — a relationship nobody can point at a source for is not truth and
is not served here.

This adds no writer, no new store, and no second graph implementation: it reuses
`polymath_shared.stores.neo4j_driver` and the existing tables.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from polymath_shared.db import tx

router = APIRouter()

MAX_LIMIT = 100


@router.get("/graph/entities")
def graph_entities(
    corpus_id: str = Query(..., min_length=1),
    q: str = Query("", description="surface substring; empty = most-attested entities"),
    limit: int = Query(25, ge=1, le=MAX_LIMIT),
) -> dict:
    """Entity search within one corpus, ranked by how much source backs them.

    Sourced from `mentions`, which is the only corpus-scoped entity surface we have;
    counts are mentions and distinct documents, so the ranking is "what this corpus
    actually talks about", not graph degree.
    """
    like = f"%{q.strip()}%" if q.strip() else "%"
    with tx() as conn:
        rows = conn.execute(
            """SELECT m.normalized_surface,
                      MIN(m.surface)          AS surface,
                      MIN(m.core_type)        AS core_type,
                      COUNT(*)                AS mentions,
                      COUNT(DISTINCT m.doc_id) AS documents
                 FROM mentions m
                WHERE m.corpus_id = %s AND m.surface ILIKE %s
                GROUP BY m.normalized_surface
                ORDER BY COUNT(*) DESC
                LIMIT %s""",
            (corpus_id, like, limit)).fetchall()
    # Resolve each surface to its GRAPH id by asking the graph, never by re-deriving
    # the hash convention here. A hand-rolled slug silently broke the vector<->graph
    # join once before; the projection's own ids are the only authority.
    ids = _resolve_entity_ids([r[0] for r in rows])
    return {
        "contract": "graph-browse-v1",
        "corpus_id": corpus_id,
        "query": q,
        "entities": [
            {"normalized_surface": r[0], "surface": r[1], "core_type": r[2],
             "mentions": r[3], "documents": r[4], "entity_id": ids.get(r[0], "")}
            for r in rows
        ],
    }


@router.get("/graph/entity/{entity_id}/relationships")
def graph_entity_relationships(
    entity_id: str,
    corpus_id: str = Query(..., min_length=1),
    limit: int = Query(25, ge=1, le=MAX_LIMIT),
) -> dict:
    """Relationships touching one entity, each carrying the source that attests it.

    Unattested relationships are DROPPED, not shown greyed out: the plan's rule is that
    only source-attested relationships may appear as canonical truth, and `dropped`
    reports how many were withheld so the count is never silently wrong.
    """
    try:
        from polymath_shared.stores import neo4j_driver
        driver = neo4j_driver()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"graph backend unavailable: {exc}") from exc

    try:
        with driver.session() as session:
            raw = session.run(
                """
                CALL () {
                    MATCH (s:Entity)-[r:REL]->(o:Entity) WHERE s.entity_id = $eid
                    RETURN r.fact_id AS fact_id, r.predicate AS predicate,
                           s.entity_id AS subject_id, s.surface AS subject,
                           o.entity_id AS object_id, o.surface AS object, 'out' AS direction
                    UNION
                    MATCH (s:Entity)-[r:REL]->(o:Entity) WHERE o.entity_id = $eid
                    RETURN r.fact_id AS fact_id, r.predicate AS predicate,
                           s.entity_id AS subject_id, s.surface AS subject,
                           o.entity_id AS object_id, o.surface AS object, 'in' AS direction
                }
                RETURN fact_id, predicate, subject_id, subject, object_id, object, direction
                ORDER BY predicate, fact_id
                LIMIT $lim
                """,
                eid=entity_id, lim=limit * 4).data()
    finally:
        try:
            driver.close()
        except Exception:  # noqa: BLE001
            pass

    if not raw:
        return {"contract": "graph-browse-v1", "corpus_id": corpus_id, "entity_id": entity_id,
                "relationships": [], "dropped_unattested": 0}

    fact_ids = sorted({r["fact_id"] for r in raw if r.get("fact_id")})
    with tx() as conn:
        ev = conn.execute(
            """SELECT e.fact_id, e.doc_id, e.chunk_id, d.source_name, c.text
                 FROM evidence e
                 JOIN documents d ON d.doc_id = e.doc_id AND d.corpus_id = %s
                 LEFT JOIN chunks c ON c.chunk_id = e.chunk_id
                WHERE e.fact_id = ANY(%s)""",
            (corpus_id, fact_ids)).fetchall()

    attest: dict[str, list[dict]] = {}
    for fact_id, doc_id, chunk_id, source_name, text in ev:
        attest.setdefault(fact_id, []).append({
            "doc_id": doc_id, "chunk_id": chunk_id, "source_name": source_name,
            "text": (text or "")[:600],
        })

    out, dropped = [], 0
    for r in raw:
        sources = attest.get(r["fact_id"])
        if not sources:
            dropped += 1          # unattested in THIS corpus — withheld by design
            continue
        out.append({**r, "sources": sources[:3], "source_count": len(sources)})
        if len(out) >= limit:
            break

    return {"contract": "graph-browse-v1", "corpus_id": corpus_id, "entity_id": entity_id,
            "relationships": out, "dropped_unattested": dropped}


def _resolve_entity_ids(normalized_surfaces: list[str]) -> dict[str, str]:
    """normalized surface -> graph `entity_id`, read from the graph itself.

    `Entity.surface` in Neo4j is already the normalized (lower-cased) form, which is
    what `mentions.normalized_surface` holds, so this is an exact match — no slug
    convention is reinvented here. A graph outage degrades to empty ids (the search
    still lists what the corpus talks about) rather than failing the request.
    """
    if not normalized_surfaces:
        return {}
    try:
        from polymath_shared.stores import neo4j_driver
        driver = neo4j_driver()
    except Exception:  # noqa: BLE001
        return {}
    try:
        with driver.session() as session:
            rows = session.run(
                "MATCH (e:Entity) WHERE e.surface IN $surfaces "
                "RETURN e.surface AS surface, e.entity_id AS entity_id",
                surfaces=normalized_surfaces).data()
        return {r["surface"]: r["entity_id"] for r in rows}
    except Exception:  # noqa: BLE001
        return {}
    finally:
        try:
            driver.close()
        except Exception:  # noqa: BLE001
            pass

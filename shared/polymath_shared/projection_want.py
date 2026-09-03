"""WANT-SET-AUTHORITY-V1 (roadmap A2) — the ONE deterministic authority
for "which projection artifacts SHOULD exist".

The F6 children-only rule independently lived in THREE consumers
(verify_worker, census, tickets) and the un-synced copies wedged every
run at reconciling (measured 2026-08-31). Every consumer now calls this
module; the rule text exists exactly once.

RULES (qdrant chunk lane):
  - chunk points are CHILDREN ONLY (F6 PARENT-POINT-RETIREMENT);
  - neo4j chunk nodes are ALL tiers (unchanged semantics).
"""
from __future__ import annotations

#: The qdrant chunk-lane tier rule as a SQL fragment over alias `c`.
QDRANT_CHUNK_TIER_SQL = "c.tier = 'child'"


def chunk_tier_sql(projection: str, alias: str = "c") -> str:
    """Predicate fragment for a projection's chunk want-set ('' = all)."""
    if projection == "qdrant":
        return QDRANT_CHUNK_TIER_SQL.replace("c.", f"{alias}.")
    return ""


def desired_chunk_ids(conn, run_id: str, projection: str = "qdrant") -> list[str]:
    """The run's desired chunk-lane ids for a projection (verify's
    reconciliation want-set)."""
    tier = chunk_tier_sql(projection)
    clause = f"AND {tier}" if tier else ""
    rows = conn.execute(
        f"""
        SELECT c.chunk_id FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s {clause}
         ORDER BY c.chunk_id
        """,
        (run_id,),
    ).fetchall()
    return [r[0] for r in rows]


def missing_chunk_receipts_for_run(conn, run_id: str,
                                   projection: str) -> list[str]:
    """Census promotion gate: desired chunk ids of the run lacking an
    active receipt under the projection."""
    tier = chunk_tier_sql(projection)
    clause = f"AND {tier}" if tier else ""
    rows = conn.execute(
        f"""
        SELECT c.chunk_id FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
          JOIN runs r ON r.corpus_id = d.corpus_id
         WHERE r.run_id = %s {clause}
           AND NOT EXISTS (
               SELECT 1 FROM projection_receipts pr
                WHERE pr.projection = %s
                  AND pr.entity_kind = 'chunk'
                  AND pr.active
                  AND pr.entity_id = c.chunk_id)
        """,
        (run_id, projection),
    ).fetchall()
    return [r[0] for r in rows]


def missing_chunk_receipts_for_docs(conn, doc_ids: list[str],
                                    projection: str) -> list[str]:
    """RUN-SCOPED-RECEIPTS-V1 (2026-09-03): desired chunk ids of THESE
    documents lacking an active receipt under the projection. Note that
    `missing_chunk_receipts_for_run` joins the run's whole CORPUS (every
    document sharing the corpus) — that is the census barrier's semantics;
    a document's own downstream stages must be gated on the document."""
    if not doc_ids:
        return []
    tier = chunk_tier_sql(projection)
    clause = f"AND {tier}" if tier else ""
    rows = conn.execute(
        f"""
        SELECT c.chunk_id FROM chunks c
         WHERE c.doc_id = ANY(%s) {clause}
           AND NOT EXISTS (
               SELECT 1 FROM projection_receipts pr
                WHERE pr.projection = %s
                  AND pr.entity_kind = 'chunk'
                  AND pr.active
                  AND pr.entity_id = c.chunk_id)
        """,
        (list(doc_ids), projection),
    ).fetchall()
    return [r[0] for r in rows]


def corpora_with_missing_chunk_receipts(conn, projection: str) -> set[str]:
    """Barrier gate (BULK-RECEIPT-COMPLETENESS-V1 shape preserved): one
    set-based anti-join answering ALL corpora at once."""
    tier = chunk_tier_sql(projection)
    clause = f"AND {tier}" if tier else ""
    rows = conn.execute(
        f"""
        SELECT DISTINCT d.corpus_id
          FROM chunks c
          JOIN documents d ON d.doc_id = c.doc_id
         WHERE NOT EXISTS (
             SELECT 1 FROM projection_receipts pr
              WHERE pr.projection = %s AND pr.active
                AND pr.entity_kind = 'chunk'
                AND pr.entity_id = c.chunk_id)
           {clause}
        """,
        (projection,),
    ).fetchall()
    return {r[0] for r in rows}

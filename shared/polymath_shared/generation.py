"""GENERATION-SWAP-V1 — chunk-generation visibility during a blue/green re-ingest.

A blue/green successor run (`runs.metadata.blue_green`) converges BESIDE the
serving run. When the chunker contract changed, its intake writes a second
generation of chunk rows for the same documents (the (doc_id, chunk_index)
uniqueness is per generation since migration 0050). Until the successor is
promoted, readers must not serve that generation:

* Postgres readers append `CHUNK_VISIBLE_SQL` (a correlated NOT EXISTS over
  in-flight blue/green runs of the chunk's corpus — no parameters, safe to
  paste into any query that joins `documents d`).
* Qdrant readers add one `must_not chunk_contract_version = g` per hidden
  generation (`hidden_generations`); legacy points without the field pass.

Extraction-only successors (same chunker) share the chunk rows and hide
nothing; their facts land beside the predecessor's until the swap purges the
old generation's evidence. The FACT tier is therefore not generation-isolated
mid-swap; the chunk tiers (FAST/HYBRID/evidence resolution) are.
"""
from __future__ import annotations

#: run statuses under which a blue/green successor is still "in flight"
IN_FLIGHT_STATUSES = ("intake", "reconciling", "degraded")

#: SQL fragment. `{c}` = chunks alias, `{d}` = documents alias (must be joined).
CHUNK_VISIBLE_SQL = (
    "NOT EXISTS (SELECT 1 FROM runs hr "
    "WHERE hr.corpus_id = {d}.corpus_id "
    "AND hr.status IN ('intake','reconciling','degraded') "
    "AND hr.metadata->'blue_green'->>'generation' IS NOT NULL "
    "AND hr.metadata->'blue_green'->>'generation' = {c}.chunk_contract_version "
    "AND hr.metadata->'blue_green'->>'generation' "
    "    IS DISTINCT FROM hr.metadata->'blue_green'->>'predecessor_generation')"
)


def chunk_visible_sql(chunks_alias: str = "c", documents_alias: str = "d") -> str:
    return CHUNK_VISIBLE_SQL.format(c=chunks_alias, d=documents_alias)


def hidden_generations(conn, corpus_id: str) -> list[str]:
    """Chunk generations being built by in-flight blue/green successors of
    this corpus that differ from the generation they replace."""
    rows = conn.execute(
        """SELECT DISTINCT metadata->'blue_green'->>'generation'
             FROM runs
            WHERE corpus_id = %s
              AND status = ANY(%s)
              AND metadata->'blue_green'->>'generation' IS NOT NULL
              AND metadata->'blue_green'->>'generation'
                  IS DISTINCT FROM metadata->'blue_green'->>'predecessor_generation'""",
        (corpus_id, list(IN_FLIGHT_STATUSES))).fetchall()
    return sorted(r[0] for r in rows if r[0])


def is_blue_green_run(conn, run_id: str) -> bool:
    row = conn.execute(
        "SELECT metadata->'blue_green' IS NOT NULL FROM runs WHERE run_id = %s",
        (run_id,)).fetchone()
    return bool(row and row[0])

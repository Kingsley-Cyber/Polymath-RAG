"""One-off sweep of derived objects that outlived their Postgres rows.

The pre-blue/green re-ingest path (P6, 2026-09-03) purged chunk rows per
document while Neo4j kept the Chunk/Evidence nodes projected from them and
`concept_artifacts` kept `supporting_chunks` pointing at purged ids
(`test_no_derived_node_outlives_its_postgres_row`,
`test_truncated_concepts_still_hydrate_full_text`). GENERATION-SWAP-V1
sweeps what IT purges; this script clears the backlog with the same
semantics, from Postgres truth, never by hand:

  * Neo4j `Chunk` nodes whose `chunk_id` has no `chunks` row and
    `Evidence` nodes whose `evidence_id` has no `evidence` row → DETACH DELETE
  * `concept_artifacts` / `procedure_artifacts` whose every supporting chunk
    is gone → RE-GROUND to the document's current child chunks (that is the
    persister's own semantics: `supporting_chunks`/`source_chunk_ids` are the
    document's chunk ids at compile time); DELETE only when the document has
    no chunks at all. Runs pinned to an older era cannot be re-armed (the
    era fence refuses the lease); re-grounding is the only repair short of a
    blue/green re-ingest.

    python scripts/sweep_orphan_derivatives.py            # dry run (counts)
    python scripts/sweep_orphan_derivatives.py --execute
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for p in (ROOT / "shared", ROOT / "control"):
    sys.path.insert(0, str(p))

import psycopg  # noqa: E402

from polymath_shared.settings import get_settings  # noqa: E402
from polymath_shared.stores import neo4j_driver  # noqa: E402

_BATCH = 1000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="apply (default: dry run)")
    args = ap.parse_args()
    with psycopg.connect(get_settings().postgres.dsn, connect_timeout=5) as conn:
        live_chunks = {r[0] for r in conn.execute("SELECT chunk_id FROM chunks").fetchall()}
        live_evidence = {r[0] for r in conn.execute("SELECT evidence_id FROM evidence").fetchall()}
        with neo4j_driver() as driver, driver.session() as session:
            graph_chunks = {r["i"] for r in session.run("MATCH (n:Chunk) RETURN n.chunk_id AS i") if r["i"]}
            graph_evidence = {r["i"] for r in session.run("MATCH (n:Evidence) RETURN n.evidence_id AS i") if r["i"]}
            orphan_chunks = sorted(graph_chunks - live_chunks)
            orphan_evidence = sorted(graph_evidence - live_evidence)
            print(f"neo4j orphan Chunk nodes: {len(orphan_chunks)}  orphan Evidence nodes: {len(orphan_evidence)}")
            if args.execute:
                deleted = 0
                for ids, label, key in ((orphan_chunks, "Chunk", "chunk_id"),
                                        (orphan_evidence, "Evidence", "evidence_id")):
                    for i in range(0, len(ids), _BATCH):
                        res = session.run(
                            f"MATCH (n:{label}) WHERE n.{key} IN $ids DETACH DELETE n RETURN count(*) AS n",
                            ids=ids[i:i + _BATCH]).single()
                        deleted += int(res["n"]) if res else 0
                print(f"  deleted {deleted} nodes")
        stale = {}
        for table, col in (("concept_artifacts", "supporting_chunks"), ("procedure_artifacts", "source_chunk_ids")):
            stale[table] = conn.execute(
                f"""SELECT count(*) FROM {table} a
                     WHERE COALESCE(array_length(a.{col}, 1), 0) > 0
                       AND NOT EXISTS (SELECT 1 FROM chunks c WHERE c.chunk_id = ANY(a.{col}))"""
            ).fetchone()[0]
        print(f"ungrounded derived artifacts: {stale}")
        if args.execute:
            for table, col in (("concept_artifacts", "supporting_chunks"), ("procedure_artifacts", "source_chunk_ids")):
                regrounded = conn.execute(
                    f"""UPDATE {table} a
                           SET {col} = sub.ids
                          FROM (SELECT c.doc_id, array_agg(c.chunk_id ORDER BY c.chunk_index) AS ids
                                  FROM chunks c WHERE c.tier = 'child' GROUP BY c.doc_id) sub
                         WHERE sub.doc_id = a.document_id
                           AND COALESCE(array_length(a.{col}, 1), 0) > 0
                           AND NOT EXISTS (SELECT 1 FROM chunks c WHERE c.chunk_id = ANY(a.{col}))"""
                ).rowcount
                deleted = conn.execute(
                    f"""DELETE FROM {table} a
                         WHERE COALESCE(array_length(a.{col}, 1), 0) > 0
                           AND NOT EXISTS (SELECT 1 FROM chunks c WHERE c.chunk_id = ANY(a.{col}))"""
                ).rowcount
                print(f"  {table}: re-grounded {regrounded}, deleted (document has no chunks) {deleted}")
            conn.commit()
        else:
            conn.rollback()
            print("dry run — nothing changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

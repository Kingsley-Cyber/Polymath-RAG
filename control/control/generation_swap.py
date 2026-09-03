"""GENERATION-SWAP-V1 — retire the predecessor of a blue/green successor.

Called by `scheduler.apply_promotions` in the promotion transaction, right
after the successor became `query_ready`. Postgres work is atomic with the
promotion (a failure rolls the tick back and the successor stays hidden and
`reconciling`); the store sweeps (Neo4j Chunk/Evidence nodes, Qdrant chunk
points) are best-effort and logged — the verify stage's want-set sweep is
the backstop for Qdrant, the graph lifecycle invariant test for Neo4j.
"""
from __future__ import annotations

import json
import logging

from psycopg import Connection

log = logging.getLogger("control.generation_swap")

_BATCH = 1000


def swap(conn: Connection, run_id: str, corpus_id: str) -> dict | None:
    """Return None when `run_id` is not a blue/green successor."""
    row = conn.execute(
        "SELECT metadata::text FROM runs WHERE run_id = %s", (run_id,)).fetchone()
    if row is None:
        return None
    metadata = json.loads(row[0] or "{}")
    bg = metadata.get("blue_green")
    if not bg or bg.get("swapped_at"):
        return None
    old_run_id = bg.get("supersedes")
    generation = bg.get("generation")

    # 1. retire the predecessor and its open tickets — evidence preserved
    conn.execute(
        """UPDATE runs SET status='superseded', superseded_by_run_id=%s,
                           updated_at=now()
            WHERE run_id=%s AND status <> 'superseded'""", (run_id, old_run_id))
    conn.execute(
        """UPDATE stage_tickets SET status='superseded', updated_at=now()
            WHERE run_id=%s AND status NOT IN ('done','superseded')""",
        (old_run_id,))

    # 2. purge the old generation's chunk rows for every document the
    #    successor re-chunked (documents that now carry the new generation)
    purged: list[str] = []
    evidence_ids: list[str] = []
    if generation:
        evidence_ids = [r[0] for r in conn.execute(
            """SELECT e.evidence_id FROM evidence e
                 JOIN chunks c ON c.chunk_id = e.chunk_id
                 JOIN documents d ON d.doc_id = c.doc_id
                WHERE d.corpus_id = %s
                  AND c.chunk_contract_version IS DISTINCT FROM %s
                  AND EXISTS (SELECT 1 FROM chunks n WHERE n.doc_id = c.doc_id
                                 AND n.chunk_contract_version = %s)""",
            (corpus_id, generation, generation)).fetchall()]
        purged = [r[0] for r in conn.execute(
            """DELETE FROM chunks c USING documents d
                WHERE d.doc_id = c.doc_id AND d.corpus_id = %s
                  AND c.chunk_contract_version IS DISTINCT FROM %s
                  AND EXISTS (SELECT 1 FROM chunks n WHERE n.doc_id = c.doc_id
                                 AND n.chunk_contract_version = %s)
                RETURNING c.chunk_id""",
            (corpus_id, generation, generation)).fetchall()]

    # 3. derived artifacts whose every supporting chunk is gone
    concepts = conn.execute(
        """DELETE FROM concept_artifacts ca
            WHERE ca.corpus_id = %s
              AND COALESCE(array_length(ca.supporting_chunks, 1), 0) > 0
              AND NOT EXISTS (SELECT 1 FROM chunks c
                               WHERE c.chunk_id = ANY(ca.supporting_chunks))""",
        (corpus_id,)).rowcount if purged else 0
    procedures = conn.execute(
        """DELETE FROM procedure_artifacts pa
            WHERE pa.corpus_id = %s
              AND COALESCE(array_length(pa.source_chunk_ids, 1), 0) > 0
              AND NOT EXISTS (SELECT 1 FROM chunks c
                               WHERE c.chunk_id = ANY(pa.source_chunk_ids))""",
        (corpus_id,)).rowcount if purged else 0

    # 4. stamp the swap on the successor (history, and the idempotency guard)
    conn.execute(
        """UPDATE runs SET metadata = jsonb_set(metadata, '{blue_green,swapped_at}',
                                                to_jsonb(now()::text)),
                           updated_at = now()
            WHERE run_id = %s""", (run_id,))

    report = {"predecessor": old_run_id, "generation": generation,
              "purged_chunks": len(purged), "purged_evidence": len(evidence_ids),
              "purged_concepts": concepts, "purged_procedures": procedures}
    report.update(_sweep_stores(corpus_id, purged, evidence_ids))
    log.info("blue/green swap: %s", json.dumps(report), extra={
        "run_id": run_id, "stage": "promotion", "error_code": None})
    return report


def _sweep_stores(corpus_id: str, chunk_ids: list[str],
                  evidence_ids: list[str]) -> dict:
    """Best-effort: derived store objects of purged rows. Never raises."""
    out = {"neo4j_deleted": None, "qdrant_deleted": None}
    if not chunk_ids and not evidence_ids:
        return out
    try:
        from polymath_shared.stores import neo4j_driver
        deleted = 0
        with neo4j_driver() as driver, driver.session() as session:
            for i in range(0, len(chunk_ids), _BATCH):
                res = session.run(
                    "MATCH (c:Chunk) WHERE c.chunk_id IN $ids "
                    "DETACH DELETE c RETURN count(*) AS n",
                    ids=chunk_ids[i:i + _BATCH]).single()
                deleted += int(res["n"]) if res else 0
            for i in range(0, len(evidence_ids), _BATCH):
                res = session.run(
                    "MATCH (e:Evidence) WHERE e.evidence_id IN $ids "
                    "DETACH DELETE e RETURN count(*) AS n",
                    ids=evidence_ids[i:i + _BATCH]).single()
                deleted += int(res["n"]) if res else 0
        out["neo4j_deleted"] = deleted
    except Exception as exc:  # noqa: BLE001 — sweep is best-effort
        log.warning("blue/green neo4j sweep skipped: %s", str(exc)[:200],
                    extra={"error_code": "GENERATION_SWAP_NEO4J_SWEEP"})
    if chunk_ids:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import (FieldCondition, Filter,
                                              FilterSelector, MatchAny)
            from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT
            from polymath_shared.projection_contracts import qdrant_collection_name
            from polymath_shared.settings import get_settings
            collection = qdrant_collection_name(corpus_id, NEURAL_EMBED_CONTRACT.contract_id)
            client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
            try:
                if client.collection_exists(collection):
                    before = client.count(collection_name=collection, exact=True).count
                    for i in range(0, len(chunk_ids), _BATCH):
                        client.delete(
                            collection_name=collection,
                            points_selector=FilterSelector(filter=Filter(must=[
                                FieldCondition(key="chunk_id",
                                               match=MatchAny(any=chunk_ids[i:i + _BATCH]))])))
                    after = client.count(collection_name=collection, exact=True).count
                    out["qdrant_deleted"] = int(before - after)
            finally:
                client.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("blue/green qdrant sweep skipped: %s", str(exc)[:200],
                        extra={"error_code": "GENERATION_SWAP_QDRANT_SWEEP"})
    return out

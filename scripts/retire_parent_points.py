"""PARENT-POINT-RETIREMENT one-off (audit F6).

The chunk lane now projects CHILDREN only (project_qdrant_worker +
verify_worker filter tier='child'). Points already projected for
tier='parent' chunks hold ACTIVE receipts, so the verify sweep will
never classify them as orphans — this script retires them explicitly:

  1. supersede their qdrant receipts (history survives in attempts);
  2. delete their points from each corpus collection.

Order matters: receipts first, in the same spirit as receipts-are-the-
commit-point — a crash after (1) leaves store points with no active
receipt, which the NEXT verify sweep deletes as true orphans (desired
excludes parents now). Re-runnable; prints per-corpus counts.
"""
from __future__ import annotations

from qdrant_client import QdrantClient

from polymath_shared.db import tx
from polymath_shared.embedding_contracts import NEURAL_EMBED_CONTRACT
from polymath_shared.projection_contracts import (
    qdrant_collection_name,
    qdrant_point_uuid,
)
from polymath_shared.receipts import supersede_projection_claims
from polymath_shared.settings import get_settings


def main() -> None:
    with tx() as conn:
        rows = conn.execute(
            """
            SELECT d.corpus_id, c.chunk_id
              FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
             WHERE c.tier = 'parent'
               AND EXISTS (SELECT 1 FROM projection_receipts pr
                            WHERE pr.projection = 'qdrant'
                              AND pr.entity_kind = 'chunk'
                              AND pr.entity_id = c.chunk_id
                              AND pr.active)
            """).fetchall()
    by_corpus: dict[str, list[str]] = {}
    for corpus_id, chunk_id in rows:
        by_corpus.setdefault(corpus_id, []).append(chunk_id)
    if not by_corpus:
        print("nothing to retire: no active parent-chunk qdrant receipts")
        return

    client = QdrantClient(url=get_settings().stores.qdrant_url, timeout=60)
    try:
        for corpus_id, chunk_ids in sorted(by_corpus.items()):
            with tx() as conn:
                supersede_projection_claims(
                    conn, projection="qdrant", entity_ids=chunk_ids)
            collection = qdrant_collection_name(
                corpus_id, NEURAL_EMBED_CONTRACT.contract_id)
            point_ids = [qdrant_point_uuid(cid) for cid in chunk_ids]
            try:
                client.delete(collection_name=collection,
                              points_selector=point_ids)
                print(f"{corpus_id}: retired {len(chunk_ids)} parent points "
                      f"from {collection}")
            except Exception as exc:
                # receipts already superseded -> next verify sweep
                # finishes the deletion as true orphans
                print(f"{corpus_id}: receipts superseded; point delete "
                      f"deferred to verify sweep ({type(exc).__name__}: {exc})")
    finally:
        client.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""PROJECTION-ORPHAN-PURGE-V1: remove derived state whose document is gone.

MEASURED 2026-08-30 on cysa-study-v1: 3,576 of 15,735 Qdrant routing
points (23%) and 2,780 `retrieval_summaries` rows belonged to 14
documents no longer in `documents` for that corpus (the non-cyber
backfills moved out under the 2026-08-29 owner decision). Any query
whose routing hit landed on a ghost failed the whole answer with
`UnresolvedDocumentError` — the assembler is right to refuse a document
it cannot resolve; the projection was wrong to still offer it.

What counts as an orphan (per corpus):
  * Qdrant points in the corpus collection whose payload `doc_id` is not
    a `documents` row OF THAT CORPUS (moved or deleted documents both
    qualify — a moved document is re-projected under its new corpus).
  * `retrieval_summaries`, `mentions`, `parent_summaries` (by parent chunk),
    `document_summaries` rows whose document no longer exists anywhere.

Idempotent. Dry-run by default; `--apply` deletes and prints counts.

    .venv/bin/python scripts/purge_orphan_projections.py
    .venv/bin/python scripts/purge_orphan_projections.py --apply [--corpus <id>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

from polymath_shared.settings import get_settings  # noqa: E402


def _collections_for(client, corpus_id: str) -> list[str]:
    import hashlib
    prefix = f"polymath_{hashlib.sha256(corpus_id.encode()).hexdigest()[:12]}_"
    return [c.name for c in client.get_collections().collections
            if c.name.startswith(prefix)]


def orphan_points(client, collection: str, live_doc_ids: set[str]) -> list[str]:
    ids: list[str] = []
    nxt = None
    while True:
        pts, nxt = client.scroll(collection_name=collection, limit=1000, offset=nxt,
                                 with_payload=["doc_id"], with_vectors=False)
        ids.extend(str(p.id) for p in pts if p.payload.get("doc_id") not in live_doc_ids)
        if nxt is None:
            break
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="delete (default: report only)")
    ap.add_argument("--corpus", default=None, help="limit to one corpus_id")
    args = ap.parse_args()

    from qdrant_client import QdrantClient
    settings = get_settings()
    client = QdrantClient(url=settings.stores.qdrant_url, timeout=60)
    report: dict = {"apply": args.apply, "corpora": {}, "postgres": {}}
    with psycopg.connect(settings.postgres.dsn, connect_timeout=5) as conn:
        corpora = [r[0] for r in conn.execute(
            "SELECT corpus_id FROM corpora" + (" WHERE corpus_id=%s" if args.corpus else ""),
            (args.corpus,) if args.corpus else ()).fetchall()]
        for corpus_id in corpora:
            live = {r[0] for r in conn.execute(
                "SELECT doc_id FROM documents WHERE corpus_id=%s", (corpus_id,)).fetchall()}
            per: dict = {}
            for coll in _collections_for(client, corpus_id):
                ids = orphan_points(client, coll, live)
                per[coll] = len(ids)
                if args.apply and ids:
                    for i in range(0, len(ids), 512):
                        client.delete(collection_name=coll, points_selector=ids[i:i + 512])
            report["corpora"][corpus_id] = per

        # Postgres derived rows whose document no longer exists ANYWHERE
        # (a moved document keeps its rows under the new corpus).
        targets = {
            "retrieval_summaries": "DELETE FROM retrieval_summaries rs WHERE NOT EXISTS "
                                   "(SELECT 1 FROM documents d WHERE d.doc_id = rs.doc_id)",
            "document_summaries": "DELETE FROM document_summaries x WHERE NOT EXISTS "
                                  "(SELECT 1 FROM documents d WHERE d.doc_id = x.document_id)",
            "mentions": "DELETE FROM mentions m WHERE NOT EXISTS "
                        "(SELECT 1 FROM documents d WHERE d.doc_id = m.doc_id)",
            "parent_summaries": "DELETE FROM parent_summaries p WHERE NOT EXISTS "
                                "(SELECT 1 FROM chunks c WHERE c.chunk_id = p.parent_id)",
        }
        for table, sql in targets.items():
            count_sql = "SELECT count(*) " + sql[sql.index("FROM"):]
            n = conn.execute(count_sql).fetchone()[0]
            report["postgres"][table] = n
            if args.apply and n:
                conn.execute(sql)
        if args.apply:
            conn.commit()
    client.close()
    import json
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

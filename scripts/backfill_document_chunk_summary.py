"""DOCUMENT-CHUNK-SUMMARY-V1 backfill (execution authority follow-up to §20A).

Populates document_chunk_summary (migration 0058) for existing documents whose
chunks were inserted before this migration — a ONE-TIME bounded read against
`chunks` (the ongoing write path never queries it again: intake_worker.py computes
the summary from the same in-memory rows it is about to insert).

Bounded, resumable, idempotent: keyset-paginated over `documents.doc_id`, batched,
commits per batch. Re-running after completion touches zero rows (only documents
missing from document_chunk_summary are selected).

Usage:
    .venv/bin/python scripts/backfill_document_chunk_summary.py [--batch-size N] [--dry-run]

Owner: governance. Reads: documents, chunks (chunks read-only). Writes:
document_chunk_summary only. Verifier: scripts/verify_document_chunk_summary_parity.py.
"""
from __future__ import annotations

import argparse
import os
import sys

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from polymath_shared.document_chunk_summary import compute_chunk_summary  # noqa: E402


def backfill(conn: psycopg.Connection, *, batch_size: int = 200, dry_run: bool = False) -> dict:
    total = {"processed": 0, "updated": 0, "errors": 0}
    last_seen = ""
    while True:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT d.doc_id, d.corpus_id FROM documents d "
                "LEFT JOIN document_chunk_summary s ON s.doc_id = d.doc_id "
                "WHERE s.doc_id IS NULL AND d.doc_id > %s "
                "ORDER BY d.doc_id LIMIT %s",
                (last_seen, batch_size),
            )
            docs = cur.fetchall()
        if not docs:
            break
        last_seen = docs[-1][0]
        doc_ids = [d[0] for d in docs]
        with conn.cursor() as cur:
            cur.execute(
                "SELECT doc_id, tier, region_role FROM chunks WHERE doc_id = ANY(%s)",
                (doc_ids,),
            )
            rows = cur.fetchall()
        by_doc: dict[str, dict[str, list]] = {d: {"children": [], "parents": []} for d in doc_ids}
        for doc_id, tier, region_role in rows:
            bucket = by_doc.get(doc_id)
            if bucket is None:
                continue
            (bucket["children"] if tier == "child" else bucket["parents"]).append(
                {"region_role": region_role})
        for doc_id, corpus_id in docs:
            total["processed"] += 1
            try:
                summary = compute_chunk_summary(by_doc[doc_id]["children"], by_doc[doc_id]["parents"])
            except Exception as exc:  # noqa: BLE001 — stop on ambiguity, never invent a value
                total["errors"] += 1
                print(f"ERROR doc_id={doc_id}: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            if not dry_run:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO document_chunk_summary
                               (doc_id, corpus_id, child_count, parent_count, map_eligible_count, updated_at)
                           VALUES (%s, %s, %s, %s, %s, now())
                           ON CONFLICT (doc_id) DO UPDATE
                              SET corpus_id = EXCLUDED.corpus_id,
                                  child_count = EXCLUDED.child_count,
                                  parent_count = EXCLUDED.parent_count,
                                  map_eligible_count = EXCLUDED.map_eligible_count,
                                  updated_at = now()""",
                        (doc_id, corpus_id, summary["child_count"], summary["parent_count"],
                         summary["map_eligible_count"]),
                    )
            total["updated"] += 1
        if not dry_run:
            conn.commit()
        else:
            conn.rollback()
        print(f"batch done: processed={total['processed']} updated={total['updated']} "
              f"errors={total['errors']}", flush=True)
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true", help="compute and report, write nothing")
    args = ap.parse_args()

    dsn = os.environ["POLYMATH_PG_DSN"]
    conn = psycopg.connect(dsn)
    try:
        result = backfill(conn, batch_size=args.batch_size, dry_run=args.dry_run)
    finally:
        conn.close()
    print(f"DONE: {result}")
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

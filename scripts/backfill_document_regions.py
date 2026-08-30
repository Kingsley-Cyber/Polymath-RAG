#!/usr/bin/env python
"""DOCUMENT-REGION-V1 backfill: classify already-ingested chunks.

NO RE-INGEST REQUIRED (proved in
eval/v5/PRODUCTION-REALITY-AND-DOCUMENT-REGION-FINAL.md §Phase A):
classification reads only `chunks.text`, which is durable and
immutable. Nothing is re-chunked, re-embedded, or re-extracted; no
FACT / PROCEDURE / CONCEPT artifact is regenerated, because none of
their contracts depend on document role.

Idempotent: re-running reclassifies from the same immutable text and
writes the same roles. Dry-run by default.

    python scripts/backfill_document_regions.py --corpus cysa-study-v1
    python scripts/backfill_document_regions.py --corpus cysa-study-v1 --apply
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.document_region import (  # noqa: E402
    CONTRACT,
    classify_region,
    is_noisy,
)

BATCH = 500


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="write roles (default: dry run)")
    args = ap.parse_args()

    with tx() as conn:
        rows = conn.execute(
            """SELECT c.chunk_id, c.text
                 FROM chunks c JOIN documents d ON d.doc_id = c.doc_id
                WHERE d.corpus_id = %s AND c.tier = 'child'
                ORDER BY c.chunk_id""",
            (args.corpus,)).fetchall()

    counts: collections.Counter = collections.Counter()
    updates: list[tuple] = []
    for chunk_id, text in rows:
        role, reason = classify_region(text)
        counts[role] += 1
        updates.append((role, reason, CONTRACT, chunk_id))

    total = len(rows)
    demoted = sum(n for r, n in counts.items() if is_noisy(r))
    print(f"corpus            : {args.corpus}")
    print(f"children           : {total}")
    for role, n in counts.most_common():
        flag = "DEMOTED" if is_noisy(role) else "retrievable"
        pct = (100.0 * n / total) if total else 0.0
        print(f"  {role:<14} {n:>6}  {pct:5.1f}%  {flag}")
    print(f"total demoted      : {demoted} "
          f"({(100.0 * demoted / total) if total else 0:.1f}%)")

    if not args.apply:
        print("\nDRY RUN — pass --apply to write")
        return 0

    written = 0
    with tx() as conn:
        for i in range(0, len(updates), BATCH):
            part = updates[i:i + BATCH]
            conn.execute(
                """UPDATE chunks AS c
                      SET region_role = v.role,
                          region_reason = v.reason,
                          region_contract = v.contract
                     FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[])
                          AS v(role, reason, contract, chunk_id)
                    WHERE c.chunk_id = v.chunk_id""",
                ([u[0] for u in part], [u[1] for u in part],
                 [u[2] for u in part], [u[3] for u in part]))
            written += len(part)
    print(f"\nwrote region_role for {written} chunks (contract {CONTRACT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

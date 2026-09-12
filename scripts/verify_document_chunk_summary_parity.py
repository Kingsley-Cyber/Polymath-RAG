"""DOCUMENT-CHUNK-SUMMARY-V1 shadow parity (execution authority follow-up to §20A).

Compares the OLD live COUNT(*) derivation (child/parent/map-eligible counts
straight from `chunks`) against the NEW `document_chunk_summary` table for every
document — the pre-cutover gate: 100% of eligible documents checked, 0 mismatches.

Read-only. Prints a summary and per-corpus breakdown; exits 1 on any mismatch.

Owner: governance. Reads: documents, chunks, document_chunk_summary. Writes: none.
Verifier for scripts/backfill_document_chunk_summary.py.
"""
from __future__ import annotations

import os
import sys

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from polymath_shared.document_region import NOISY_ROLES  # noqa: E402


def main() -> int:
    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"])
    c = conn.cursor()
    c.execute("""
        SELECT d.doc_id, d.corpus_id,
               COALESCE((SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.doc_id AND c.tier='child'), 0),
               COALESCE((SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.doc_id AND c.tier='parent'), 0),
               COALESCE((SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.doc_id AND c.tier='parent'
                         AND COALESCE(c.region_role,'') <> ALL(%s)), 0),
               s.child_count, s.parent_count, s.map_eligible_count
        FROM documents d
        LEFT JOIN document_chunk_summary s ON s.doc_id = d.doc_id
    """, (list(NOISY_ROLES),))
    rows = c.fetchall()
    conn.close()

    mismatches = []
    per_corpus: dict[str, dict] = {}
    for (doc_id, corpus_id, old_child, old_parent, old_eligible,
         new_child, new_parent, new_eligible) in rows:
        pairs = [("child_count", old_child, new_child), ("parent_count", old_parent, new_parent),
                 ("map_eligible_count", old_eligible, new_eligible)]
        row_ok = True
        for field, old, new in pairs:
            if old != new:
                mismatches.append((doc_id, corpus_id, field, old, new))
                row_ok = False
        d = per_corpus.setdefault(corpus_id, {"docs": 0, "mismatched_docs": 0, "missing_summary": 0})
        d["docs"] += 1
        if new_child is None:
            d["missing_summary"] += 1
        if not row_ok:
            d["mismatched_docs"] += 1

    print(f"documents checked: {len(rows)}")
    print(f"mismatches:        {len(mismatches)}")
    print()
    print("per-corpus:")
    for corpus_id in sorted(per_corpus):
        d = per_corpus[corpus_id]
        flag = "PASS" if d["mismatched_docs"] == 0 and d["missing_summary"] == 0 else "FAIL"
        print(f"  {corpus_id:20s} docs={d['docs']:4d} mismatched={d['mismatched_docs']:4d} "
              f"missing_summary={d['missing_summary']:4d} [{flag}]")
    if mismatches or any(d["missing_summary"] for d in per_corpus.values()):
        print()
        print("MISMATCHES (first 20):")
        for m in mismatches[:20]:
            print(" ", m)
        return 1
    print()
    print("PARITY: 100% match, 0 mismatches — safe to cut over.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

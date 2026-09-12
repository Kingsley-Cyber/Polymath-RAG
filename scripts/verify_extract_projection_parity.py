"""EXTRACT-OPERATIONAL-PROJECTION-V1 shadow parity (execution authority §20A phase F).

Compares the OLD JSONB-derived values (payload->'llm_extraction'->'stats') against
the NEW narrow columns (migration 0057) for every stage='extract' artifact — the
pre-cutover gate: 100% of eligible rows checked, 0 mismatches, 0 unexplained NULLs.

Read-only. Prints a summary and per-corpus breakdown (rag-canary / ecom-meta-v1 /
cinema where present); exits 1 if any mismatch is found.

Owner: governance. Reads: artifacts, runs. Writes: none. Verifier for
scripts/backfill_extract_projection.py.
"""
from __future__ import annotations

import os
import sys

import psycopg


def main() -> int:
    conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"])
    c = conn.cursor()
    c.execute("""
        SELECT a.artifact_id, r.corpus_id,
               jsonb_exists(a.payload, 'llm_extraction') AS old_present,
               (a.payload->'llm_extraction'->'stats'->>'calls')::int AS old_calls,
               (a.payload->'llm_extraction'->'stats'->>'entities')::int AS old_entities,
               (a.payload->'llm_extraction'->'stats'->>'relations')::int AS old_relations,
               (a.payload->'llm_extraction'->'stats'->>'neighborhoods_sent')::int AS old_sent,
               (a.payload->'llm_extraction'->'stats'->>'neighborhoods_unaccounted')::int AS old_unacc,
               (a.payload->'llm_extraction'->'stats'->>'neighborhoods_dropped')::int AS old_dropped,
               a.extract_stats_present, a.extract_llm_calls, a.extract_entity_count,
               a.extract_relation_count, a.extract_neighborhoods_sent,
               a.extract_neighborhoods_unaccounted, a.extract_neighborhoods_dropped
        FROM artifacts a JOIN runs r ON r.run_id = a.run_id
        WHERE a.stage = 'extract'
    """)
    rows = c.fetchall()
    conn.close()

    mismatches = []
    per_corpus: dict[str, dict] = {}
    for row in rows:
        (artifact_id, corpus_id, old_present, old_calls, old_entities, old_relations,
         old_sent, old_unacc, old_dropped, new_present, new_calls, new_entities,
         new_relations, new_sent, new_unacc, new_dropped) = row
        pair = [
            ("present", old_present, new_present), ("calls", old_calls, new_calls),
            ("entities", old_entities, new_entities), ("relations", old_relations, new_relations),
            ("neighborhoods_sent", old_sent, new_sent),
            ("neighborhoods_unaccounted", old_unacc, new_unacc),
            ("neighborhoods_dropped", old_dropped, new_dropped),
        ]
        row_ok = True
        for field, old, new in pair:
            if old != new:
                mismatches.append((artifact_id, corpus_id, field, old, new))
                row_ok = False
        d = per_corpus.setdefault(corpus_id, {"rows": 0, "mismatched_rows": 0})
        d["rows"] += 1
        if not row_ok:
            d["mismatched_rows"] += 1

    print(f"eligible rows checked: {len(rows)}")
    print(f"semantic mismatches:   {len(mismatches)}")
    print()
    print("per-corpus:")
    for corpus_id in sorted(per_corpus):
        d = per_corpus[corpus_id]
        flag = "PASS" if d["mismatched_rows"] == 0 else "FAIL"
        print(f"  {corpus_id:20s} rows={d['rows']:4d} mismatched={d['mismatched_rows']:4d} [{flag}]")
    if mismatches:
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

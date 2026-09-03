#!/usr/bin/env python3
"""Backfill documents.frontmatter (migration 0051) from each document's first
chunk: the transcript exporter and the book materializer both write a
`--- key: value ---` head. Dry run by default.

    python scripts/backfill_frontmatter.py --corpus mark-builds-brands-v1
    python scripts/backfill_frontmatter.py --corpus mark-builds-brands-v1 --execute
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for p in (ROOT / "shared", ROOT / "orchestrator"):
    sys.path.insert(0, str(p))

import psycopg  # noqa: E402

from orchestrator.api.evidence_rows import parse_frontmatter  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=None, help="corpus_id (default: every document without frontmatter)")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    with psycopg.connect(get_settings().postgres.dsn, connect_timeout=5) as conn:
        where = "d.frontmatter IS NULL" + (" AND d.corpus_id = %s" if a.corpus else "")
        args = (a.corpus,) if a.corpus else ()
        rows = conn.execute(
            f"""SELECT DISTINCT ON (d.doc_id) d.doc_id, d.source_name, c.text
                  FROM documents d JOIN chunks c ON c.doc_id = d.doc_id AND c.tier = 'child'
                 WHERE {where} ORDER BY d.doc_id, c.chunk_index""", args).fetchall()
        stamped = 0
        for doc_id, source_name, text in rows:
            fm = parse_frontmatter(text or "")
            if not fm:
                continue
            stamped += 1
            print(f"{'STAMP' if a.execute else 'DRY  '} {doc_id[:16]} {source_name[-48:]!r} -> {json.dumps(fm)[:120]}")
            if a.execute:
                conn.execute("UPDATE documents SET frontmatter = %s::jsonb WHERE doc_id = %s", (json.dumps(fm), doc_id))
        if a.execute:
            conn.commit()
        print(f"documents scanned {len(rows)}, with frontmatter {stamped}, {'stamped' if a.execute else 'dry run'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

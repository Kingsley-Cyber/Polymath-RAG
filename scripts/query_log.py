"""QUERY-RECEIPTS-V1 operator view — what was asked, how long it took, was it
answered. Reads `query_receipts` (every /chat, /ask, /retrieve writes one row).

    .venv/bin/python scripts/query_log.py                      # last 24 h, all corpora
    .venv/bin/python scripts/query_log.py --corpus <id> --limit 50 --since-h 6
    .venv/bin/python scripts/query_log.py --kind chat --json

Exit 0 always (a report, not a gate); prints per-(kind, mode) count / p50 /
p95 / max / abstained / errors / avg citations, then the recent rows.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

from polymath_shared.query_receipts import query_summary, recent_queries  # noqa: E402
from polymath_shared.settings import get_settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus")
    ap.add_argument("--kind", choices=("chat", "ask", "retrieve"))
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--since-h", type=float, default=24.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    with psycopg.connect(get_settings().postgres.dsn, autocommit=True) as conn:
        summary = query_summary(conn, corpus_id=a.corpus, kind=a.kind, since_h=a.since_h)
        rows = recent_queries(conn, corpus_id=a.corpus, kind=a.kind, limit=a.limit, since_h=a.since_h)
    if a.json:
        print(json.dumps({"summary": summary, "queries": rows}, indent=1, default=str))
        return 0
    scope = f"corpus={a.corpus}" if a.corpus else "all corpora"
    print(f"query receipts — last {a.since_h:g} h, {scope}" + (f", kind={a.kind}" if a.kind else ""))
    if not summary:
        print("  (no queries served in the window)")
        return 0
    print(f"  {'kind':9}{'mode':8}{'n':>5}{'p50ms':>8}{'p95ms':>8}{'maxms':>8}{'abst':>6}{'err':>5}{'cites':>7}")
    for r in summary:
        print(f"  {r['kind']:9}{r['mode']:8}{r['n']:>5}{r['p50_ms'] or 0:>8.0f}{r['p95_ms'] or 0:>8.0f}"
              f"{r['max_ms'] or 0:>8}{r['abstained']:>6}{r['errors']:>5}"
              f"{(r['avg_citations'] if r['avg_citations'] is not None else 0):>7.1f}")
    print(f"  recent ({len(rows)}):")
    for r in rows:
        tail = f" err={r['error'][:80]}" if r.get("error") else ""
        print(f"  {r['received_at'][:19]} {r['kind']:8} {(r['mode'] or '-'):7} {r['wall_ms']:>7}ms "
              f"{r['status']:9} cites={r['citations'] if r['citations'] is not None else '-':<3} "
              f"{','.join(r['corpus_ids'] or [])[:28]:28} {r['question_head'][:60]!r}{tail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

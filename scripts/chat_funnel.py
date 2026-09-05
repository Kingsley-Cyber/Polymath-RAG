#!/usr/bin/env python
"""RETRIEVAL-FUNNEL-V1 reader (plan §3.9): print where candidates died for one
chat receipt.

  chat_funnel.py --last [--kind chat_stream]      newest receipt
  chat_funnel.py <query_id>                      one receipt
  chat_funnel.py <query_id> --chunk <chunk_id>   rank at every stage + death
  chat_funnel.py --last --top 100                 top-N ids per stage
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query_id", nargs="?")
    ap.add_argument("--last", action="store_true")
    ap.add_argument("--kind", default=None)
    ap.add_argument("--chunk", default=None)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    import psycopg
    from polymath_shared.funnel import STAGES, rank_at, where_did_it_die
    dsn = os.environ.get("POLYMATH_PG_DSN") or os.environ.get("POLYMATH_TEST_DSN")
    if not dsn:
        print("POLYMATH_PG_DSN not set", file=sys.stderr); return 2
    with psycopg.connect(dsn) as c:
        if a.last or not a.query_id:
            row = c.execute("""SELECT query_id, kind, received_at::text, question_head, wall_ms, meta FROM query_receipts
                               WHERE meta ? 'funnel' AND (%s::text IS NULL OR kind=%s) ORDER BY received_at DESC LIMIT 1""",
                            (a.kind, a.kind)).fetchone()
        else:
            row = c.execute("SELECT query_id, kind, received_at::text, question_head, wall_ms, meta FROM query_receipts WHERE query_id=%s",
                            (a.query_id,)).fetchone()
    if not row:
        print("no receipt with a funnel"); return 1
    qid, kind, at, q, wall, meta = row
    fun = (meta or {}).get("funnel") or {}
    if a.json:
        print(json.dumps({"query_id": qid, "kind": kind, "received_at": at, "question": q, "wall_ms": wall, "funnel": fun}, indent=1)); return 0
    print(f"{qid}  {kind}  {at}  {wall} ms\n  Q: {q}\n  plan: {fun.get('plan_version')}  phase_ms: {meta.get('phase_ms')}")
    print("  stage          count   top ids")
    for st in STAGES:
        ids = (fun.get("stages") or {}).get(st) or []
        print(f"  {st:14s} {fun.get('counts', {}).get(st, 0):5d}   {' '.join(i[-12:] for i in ids[:a.top])}")
    print("  lanes:", fun.get("lane_counts"), " multi-lane candidates:", fun.get("multi_lane"))
    if a.chunk:
        print(f"\n  chunk {a.chunk[-16:]}: {where_did_it_die(fun, a.chunk)}")
        for k, v in rank_at(fun, a.chunk).items():
            print(f"    {k:26s} {v}")
    else:
        deaths: dict[str, int] = {}
        for cid in (fun.get("stages") or {}).get("retrieved") or []:
            d = where_did_it_die(fun, cid); deaths[d] = deaths.get(d, 0) + 1
        print("  deaths among retrieved:", dict(sorted(deaths.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

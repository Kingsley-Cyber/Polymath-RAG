#!/usr/bin/env python3
"""TRUE-CORPUS-DELETE-V1 (2026-11-20): delete one library everywhere and show the disk space it gave back.

Owner: "I SHOULD BE ABLE TO TRULY DELETE A CORPUS AND IT DOES WHAT ITS SUPPOSE TO DO ON MY MACHINE AND GIVES ME STORAGE."

    python scripts/delete_corpus.py <corpus_id> --confirm <corpus_id> [--no-reclaim] [--api http://127.0.0.1:7200]

It calls the fleet's own delete (`DELETE /corpora/{id}`: Postgres rows, the library's Qdrant collections and its points in
the shared ones, its Neo4j chunks) with `reclaim=true`, which compacts the emptied Postgres tables (VACUUM FULL; it skips a
table the disk has no room to copy). It measures the store folders and the free disk before and after.
IRREVERSIBLE: there is no undo. Neo4j keeps its files at the same size and reuses the freed space for new data.
"""
from __future__ import annotations

import argparse
import http.client
import json
import pathlib
import shutil
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
STORES = ("postgres", "qdrant", "neo4j")


def folder_bytes(path: pathlib.Path) -> int:
    """Disk use of a folder (du -sk), 0 when it does not exist."""
    if not path.exists():
        return 0
    out = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True, check=False).stdout.split()
    return int(out[0]) * 1024 if out else 0


def snapshot() -> dict:
    return {**{s: folder_bytes(ROOT / "stores" / s) for s in STORES}, "free": shutil.disk_usage(ROOT).free}


def gb(n: int) -> str:
    return f"{n / 1024 ** 3:6.2f} GB"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("corpus_id")
    ap.add_argument("--confirm", required=True, help="type the corpus_id again")
    ap.add_argument("--no-reclaim", action="store_true", help="delete only; do not compact Postgres")
    ap.add_argument("--api", default="http://127.0.0.1:7200")
    args = ap.parse_args(argv)
    if args.confirm != args.corpus_id:
        print("refused: --confirm must equal the corpus_id", file=sys.stderr)
        return 2
    api = urllib.parse.urlsplit(args.api)
    if api.scheme not in ("http", "https") or not api.hostname:
        print("refused: --api must be an http(s) URL", file=sys.stderr)
        return 2
    before = snapshot()
    query = urllib.parse.urlencode({"confirm": args.confirm, "reclaim": str(not args.no_reclaim).lower()})
    conn_cls = http.client.HTTPSConnection if api.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(api.hostname, api.port, timeout=6 * 3600)   # compaction of a large table takes minutes
    try:
        conn.request("DELETE", f"{api.path.rstrip('/')}/corpora/{urllib.parse.quote(args.corpus_id)}?{query}")
        resp = conn.getresponse()
        body = resp.read()
    finally:
        conn.close()
    if resp.status != 200:
        print(f"delete failed: HTTP {resp.status} {body.decode(errors='replace')[:400]}", file=sys.stderr)
        return 1
    out = json.loads(body)
    after = snapshot()
    removed = out.get("removed", {})
    print(f"deleted {out.get('deleted')!r}")
    print(f"  rows removed: {sum(v for v in removed.values() if isinstance(v, int)):,} in "
          f"{sum(1 for v in removed.values() if isinstance(v, int) and v)} tables")
    for key in ("qdrant_collections", "qdrant_shared_points", "neo4j_chunks", "neo4j_rels",
                "tables_not_deleted", "qdrant_error", "neo4j_error"):
        if key in removed:
            print(f"  {key}: {removed[key]}")
    for row in (out.get("reclaim") or {}).get("tables", []):
        if row["status"] == "skipped":
            print(f"  NOT compacted {row['table']}: {row['reason']}")
    print(f"{'store':10s} {'before':>10s} {'after':>10s} {'freed':>10s}")
    for s in STORES:
        print(f"{s:10s} {gb(before[s])} {gb(after[s])} {gb(before[s] - after[s])}")
    print(f"{'free disk':10s} {gb(before['free'])} {gb(after['free'])} {gb(after['free'] - before['free'])}")
    return 0 if not removed.get("tables_not_deleted") else 1


if __name__ == "__main__":
    sys.exit(main())

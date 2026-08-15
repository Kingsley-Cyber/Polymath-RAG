"""D4 measurement: capture per-candidate signals from the frozen
retrieval + G3 pipeline for the frozen D4 development set.

Read-only. Records, per query/candidate: text_kind, doc_id, chunk_id,
dense score, lexical score, rerank score, pre/post rank. No retrieval
change happens while this evidence is collected.

Usage: .venv/bin/python eval/d4/measure.py --out /tmp/d4/measure.json
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

import psycopg  # noqa: E402

QUERIES = Path(__file__).resolve().parent / "queries.json"
API = "http://127.0.0.1:7200"
CORPUS = "i2-qualification-corpus"


def retrieve(query: str) -> dict:
    req = urllib.request.Request(
        API + "/retrieve",
        data=json.dumps({"query": query, "corpus_id": CORPUS, "limit": 50}).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def main() -> int:
    frozen = json.loads(QUERIES.read_text())
    records = []
    for entry in frozen["queries"]:
        r = retrieve(entry["query"])
        by_chunk: dict[str, dict] = {}
        for lane, kind in (("child_dense_lane", "dense"), ("child_lexical_lane", "lexical")):
            for i, h in enumerate(r.get(lane) or []):
                cid = h.get("chunk_id") or ""
                slot = by_chunk.setdefault(cid, {
                    "chunk_id": cid, "doc_id": h.get("document_id"),
                    "dense_score": None, "lexical_score": None,
                    "dense_rank": None, "lexical_rank": None,
                    "rerank_score": None, "post_rerank_rank": None,
                })
                slot[f"{kind}_score"] = round(h.get("raw_score"), 6) if h.get("raw_score") is not None else None
                slot[f"{kind}_rank"] = i
        for i, c in enumerate(r.get("child_evidence") or []):
            slot = by_chunk.setdefault(c.get("chunk_id") or "", {
                "chunk_id": c.get("chunk_id"), "doc_id": c.get("doc_id"),
                "dense_score": None, "lexical_score": None,
                "dense_rank": None, "lexical_rank": None,
                "rerank_score": None, "post_rerank_rank": None,
            })
            slot["rerank_score"] = c.get("rerank_score")
            slot["post_rerank_rank"] = i
            slot["doc_id"] = slot.get("doc_id") or c.get("doc_id")
        for cid, slot in sorted(by_chunk.items()):
            slot["text_kind"] = "child_chunk"
            records.append({
                "query_id": entry["query_id"],
                "kind": entry["kind"],
                **slot,
            })
        # document summaries (document_lane) and section summaries (parent_lane)
        for i, d in enumerate(r.get("document_lane") or []):
            records.append({
                "query_id": entry["query_id"], "kind": entry["kind"],
                "text_kind": "document_summary",
                "chunk_id": None, "doc_id": d.get("document_id"),
                "dense_score": None, "lexical_score": d.get("raw_score"),
                "dense_rank": None, "lexical_rank": None,
                "rerank_score": d.get("rerank_score"),
                "post_rerank_rank": d.get("rank"),
            })
        for i, p in enumerate(r.get("parent_lane") or []):
            records.append({
                "query_id": entry["query_id"], "kind": entry["kind"],
                "text_kind": "section_summary",
                "chunk_id": p.get("source_id"), "doc_id": p.get("document_id"),
                "dense_score": None, "lexical_score": p.get("raw_score"),
                "dense_rank": None, "lexical_rank": None,
                "rerank_score": p.get("rerank_score"),
                "post_rerank_rank": p.get("rank"),
            })
        print(f"{entry['query_id']}: {len(by_chunk)} children + "
              f"{len(r.get('document_lane') or [])} docs + {len(r.get('parent_lane') or [])} parents")

    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else Path("/tmp/d4/measure.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"queries_sha256": None, "records": records}, indent=2))
    print(f"wrote {len(records)} records to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

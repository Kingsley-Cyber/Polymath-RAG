#!/usr/bin/env python3
"""FAST_HYBRID evidence producer (release_gates.gate_text_retrieval).

Live probes against the orchestrator, scored deterministically:
  fast_ok      every FAST probe: HTTP 200, meta.mode == FAST, >= MIN_HITS hits,
               and the top hit comes from the corpus the query was scoped to
  hybrid_ok    the same for HYBRID
  isolation_ok across EVERY probe (including cross-topic and nonce probes),
               no returned hit belongs to a document outside the scoped corpus
               (hits carry doc_id only; corpus membership is resolved in
               Postgres, never trusted from the response)
Writes eval/v5/release_evidence/retrieval_fast_hybrid.json with each probe's
wall time, hit count, in/foreign-corpus counts and top document.

    .venv/bin/python eval/v5/retrieval/record_fast_hybrid_evidence.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

import psycopg

DSN = os.environ.get("POLYMATH_PG_DSN", "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
ORCH = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200").rstrip("/")
OUT = pathlib.Path(__file__).resolve().parents[1] / "release_evidence" / "retrieval_fast_hybrid.json"
MIN_HITS = 3

# (corpus, topical question). Each corpus is also probed with the OTHER
# corpus's question and with a nonce — those must not leak foreign documents.
TOPICAL = [
    ("ecom-meta-v1", "What are the seven elements of the StoryBrand framework?"),
    ("cysa-study-v1", "How does a vulnerability scan differ from a penetration test?"),
]
NONCE = "What is the capital of the moon colony Zorblax?"


def retrieve(query: str, corpus: str, mode: str) -> tuple[int, float, dict]:
    body = json.dumps({"query": query, "corpus_id": corpus, "mode": mode, "limit": 8}).encode()
    req = urllib.request.Request(ORCH + "/retrieve", data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "record-fast-hybrid-evidence/1.0"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, (time.perf_counter() - t0) * 1000, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, (time.perf_counter() - t0) * 1000, json.loads(e.read() or b"{}")


def hits_of(out: dict) -> list[dict]:
    for k in ("evidence", "hits", "selected_children", "child_dense_lane"):
        v = out.get(k)
        if isinstance(v, list):
            return [h for h in v if isinstance(h, dict)]
    return []


def main() -> int:
    conn = psycopg.connect(DSN, autocommit=True)
    doc_corpus: dict[str, str] = dict(conn.execute("SELECT doc_id, corpus_id FROM documents").fetchall())
    probes = []
    for corpus, question in TOPICAL:
        others = [q for c, q in TOPICAL if c != corpus]
        for label, q in [("topical", question)] + [("cross_topic", o) for o in others] + [("nonce", NONCE)]:
            for mode in ("FAST", "HYBRID"):
                code, ms, out = retrieve(q, corpus, mode)
                hits = hits_of(out)
                owners = [doc_corpus.get(h.get("doc_id") or "", "?") for h in hits]
                foreign = sum(1 for o in owners if o != corpus)
                top_in = bool(owners) and owners[0] == corpus
                probes.append({
                    "corpus": corpus, "kind": label, "mode": mode, "question": q, "http": code,
                    "wall_ms": round(ms), "echo_mode": (out.get("meta") or {}).get("mode") if isinstance(out, dict) else None,
                    "hits": len(hits), "in_corpus": len(hits) - foreign, "foreign": foreign,
                    "top_doc": (hits[0].get("source_name") if hits else None), "top_in_corpus": top_in,
                    "answered": code == 200 and len(hits) >= MIN_HITS and top_in and
                                ((out.get("meta") or {}).get("mode") == mode),
                })
                p = probes[-1]
                print(f"{corpus:14} {label:11} {mode:6} HTTP {code} {p['wall_ms']:>5} ms hits={p['hits']:<2} "
                      f"foreign={foreign} top={p['top_doc']}")
    topical = [p for p in probes if p["kind"] == "topical"]
    fast_ok = all(p["answered"] for p in topical if p["mode"] == "FAST")
    hybrid_ok = all(p["answered"] for p in topical if p["mode"] == "HYBRID")
    isolation_ok = all(p["foreign"] == 0 and p["http"] == 200 for p in probes)
    ev = {"fast_ok": fast_ok, "hybrid_ok": hybrid_ok, "isolation_ok": isolation_ok,
          "min_hits": MIN_HITS, "probes": probes,
          "p50_ms": sorted(p["wall_ms"] for p in probes)[len(probes) // 2],
          "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
          "producer": "eval/v5/retrieval/record_fast_hybrid_evidence.py"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ev, indent=1))
    print(f"fast_ok={fast_ok} hybrid_ok={hybrid_ok} isolation_ok={isolation_ok} p50={ev['p50_ms']} ms -> {OUT}")
    return 0 if (fast_ok and hybrid_ok and isolation_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())

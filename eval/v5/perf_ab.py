#!/usr/bin/env python3
"""PHASE B8 — same-EPUB A/B harness.

snapshot: capture the corpus's COMPLETE semantic identity (state hash, L1
ledger hash, counts, per-run extract perf artifact) to a file.
compare: two snapshots must be semantically IDENTICAL (hashes byte-equal);
only the perf numbers may differ. The optimized run reuses the SAME corpus
id after a wipe so every content-addressed id (incl. entc_) is comparable.
"""
import argparse, json, os, sys
sys.path[:0] = ["shared", "workers"]

import psycopg

DSN = os.environ.get("POLYMATH_PG_DSN",
                     "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")


def snapshot(corpus: str) -> dict:
    from polymath_shared.raw_evidence import ledger_hash
    from workers.reprocess_worker import semantic_state_hash

    with psycopg.connect(DSN) as c:
        docs = [r[0] for r in c.execute(
            "SELECT doc_id FROM documents WHERE corpus_id=%s ORDER BY 1", (corpus,)).fetchall()]
        perf = [r[0] for r in c.execute(
            """SELECT a.payload->'perf' FROM artifacts a JOIN runs r ON r.run_id=a.run_id
                WHERE r.corpus_id=%s AND a.stage='extract'
                  AND a.payload ? 'perf' ORDER BY a.created_at DESC""", (corpus,)).fetchall()]
        counts = {t: c.execute(
            f"SELECT COUNT(*) FROM {t} WHERE doc_id = ANY(%s)", (docs,)).fetchone()[0]
            for t in ("mentions", "raw_entity_proposals", "span_hypotheses",
                      "sentence_slices", "relation_candidates")}
        counts["facts"] = c.execute(
            """SELECT COUNT(DISTINCT f.fact_id) FROM facts f
                 JOIN evidence ev ON ev.fact_id=f.fact_id
                WHERE ev.doc_id = ANY(%s)""", (docs,)).fetchone()[0]
        return {"corpus": corpus, "docs": len(docs),
                "semantic_state_hash": semantic_state_hash(c, corpus),
                "l1_ledger": ledger_hash(c, docs),
                "counts": counts,
                "extract_perf": perf[0] if perf else None}


SEMANTIC_KEYS = ("semantic_state_hash", "l1_ledger", "counts")


def compare(a: dict, b: dict) -> dict:
    deltas = {k: (a[k], b[k]) for k in SEMANTIC_KEYS if a[k] != b[k]}
    pa, pb = a.get("extract_perf") or {}, b.get("extract_perf") or {}
    speed = {k: {"baseline": pa.get(k), "optimized": pb.get(k)}
             for k in sorted(set(pa) | set(pb))}
    return {"semantically_identical": not deltas, "semantic_deltas": deltas,
            "perf": speed,
            "speedup_total": (round(pa.get("total_s", 0) / pb["total_s"], 2)
                              if pb.get("total_s") else None)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("snapshot"); s1.add_argument("--corpus", required=True)
    s1.add_argument("--out", required=True)
    s2 = sub.add_parser("compare"); s2.add_argument("a"); s2.add_argument("b")
    args = ap.parse_args()
    if args.cmd == "snapshot":
        snap = snapshot(args.corpus)
        json.dump(snap, open(args.out, "w"), indent=1)
        print(json.dumps({k: snap[k] for k in ("corpus", "docs", "counts")}, indent=1))
        print("state:", snap["semantic_state_hash"][:24])
    else:
        r = compare(json.load(open(args.a)), json.load(open(args.b)))
        print(json.dumps(r, indent=1))
        sys.exit(0 if r["semantically_identical"] else 1)

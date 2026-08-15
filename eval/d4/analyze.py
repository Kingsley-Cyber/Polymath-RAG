"""D4 signal analysis: which frozen signal separates SUPPORTED from
UNSUPPORTED text candidates across the frozen development set.

Read-only analysis over /tmp/d4/measure.json + gold labels.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

measure = json.load(open("/tmp/d4/measure.json"))
gold_map = json.load(open("/tmp/d4/gold.json"))["gold"]

def key(r):
    if r["text_kind"] == "document_summary":
        return f"{r['query_id']}::__doc__:{doc_source(r)}"
    return f"{r['query_id']}::{r['chunk_id']}"

def doc_source(r):
    import psycopg
    c = psycopg.connect("postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
    try:
        row = c.execute("SELECT source_name FROM documents WHERE doc_id=%s", (r["doc_id"],)).fetchone()
        return row[0] if row else ""
    finally:
        c.close()

records = measure["records"]
print(f"{len(records)} records")

per_q = defaultdict(lambda: {"S": 0, "U": 0})
for r in records:
    k = key(r)
    label = gold_map.get(k, "UNSUPPORTED")
    per_q[r["query_id"]][label[0]] += 1
print("\nper query gold distribution (S=supported, U=unsupported):")
for qid in sorted(per_q):
    print(f"  {qid:24} S={per_q[qid]['S']:3} U={per_q[qid]['U']:3}")

# signal distributions by label
def dist(signal):
    buckets = {"SUPPORTED": [], "UNSUPPORTED": []}
    for r in records:
        k = key(r)
        v = r.get(signal)
        if v is None:
            continue
        label = gold_map.get(k, "UNSUPPORTED")
        buckets[label].append(v)
    return buckets

for signal in ("dense_score", "lexical_score", "rerank_score"):
    b = dist(signal)
    s = sorted(b["SUPPORTED"]); u = sorted(b["UNSUPPORTED"])
    if not s or not u:
        print(f"\n{signal}: S={len(s)} U={len(u)} (incomplete)")
        continue
    def q(p, xs): return xs[min(len(xs)-1, int(len(xs)*p))]
    print(f"\n{signal}: S n={len(s)} p50={q(0.5,s):.4f} min={s[0]:.4f} max={s[-1]:.4f}")
    print(f"          U n={len(u)} p50={q(0.5,u):.4f} p90={q(0.9,u):.4f} p95={q(0.95,u):.4f} max={u[-1]:.4f}")
    # best separation threshold: max U value below which all S lie
    sep_ok = s[0] > u[-1]
    print(f"          full separation: {sep_ok} (S_min={s[0]:.4f} vs U_max={u[-1]:.4f})")
    # achievable precision@1 operating points
    for t in sorted({round(x, 2) for x in s + u}):
        tp = sum(1 for x in s if x >= t); fp = sum(1 for x in u if x >= t)
        fn = len(s) - tp; tn = len(u) - fp
        if fp == 0 and tp > 0:
            print(f"          zero-FP point: t>={t}: TP={tp}/{len(s)} FN={fn} FP=0")
            break
    # lowest-FP top region stats
    u_sorted = sorted(u, reverse=True)
    print(f"          top-5 U scores: {[round(x,4) for x in u_sorted[:5]]}")

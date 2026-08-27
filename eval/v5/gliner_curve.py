#!/usr/bin/env python3
"""PHASE B2 — provider throughput curve + output-equivalence verification.

Same texts, same labels, same threshold, through the LIVE sidecar:
  per-call /infer (production-before)  vs  /infer_batch at 1/8/16/32/64/128.
Equivalence is exact-set equality of (text,start,end,label,score) per chunk;
any divergence disqualifies that batch mode outright.
"""
import json, os, statistics as st, sys, time
sys.path[:0] = ["shared"]
import httpx, psycopg

DSN = os.environ.get("POLYMATH_PG_DSN",
                     "postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
BASE = "http://127.0.0.1:8740"
LABELS = ["Person", "Organization", "Location", "Product", "Technology",
          "Concept", "Method", "Event", "Document", "Process", "Measurement",
          "TimeReference", "Library", "Framework", "API", "Vulnerability",
          "AttackTechnique", "Model", "Dataset", "ProgrammingLanguage"]
N_TEXTS = 128


def norm(rows):
    return sorted((r["text"], int(r["start"]), int(r["end"]), r["label"],
                   round(float(r["score"]), 6)) for r in rows)


def main() -> int:
    with psycopg.connect(DSN) as c:
        texts = [r[0] for r in c.execute(
            """SELECT c.text FROM chunks c JOIN documents d ON d.doc_id=c.doc_id
                WHERE d.corpus_id='perf-baseline-v1' AND c.tier='child'
                ORDER BY c.chunk_index LIMIT %s""", (N_TEXTS,)).fetchall()]
    print(f"{len(texts)} real chunks; labels={len(LABELS)}")
    cl = httpx.Client(base_url=BASE, timeout=300)
    print("sidecar batch mode:", cl.post("/infer_batch", json={
        "task": "entity", "texts": texts[:2], "labels": LABELS,
        "threshold": 0.5}).json()["mode"])

    # reference: per-call /infer (the pre-optimization transport)
    t0 = time.perf_counter(); ref = []
    for t in texts:
        r = cl.post("/infer", json={"task": "entity", "text": t,
                                    "labels": LABELS, "threshold": 0.5})
        ref.append(r.json()["spans"])
    per_call_s = time.perf_counter() - t0
    print(f"per-call /infer      : {per_call_s:6.1f}s "
          f"({len(texts)/per_call_s:5.2f} chunks/s)")

    results = {"per_call_s": round(per_call_s, 1)}
    for batch in (1, 8, 16, 32, 64, 128):
        t0 = time.perf_counter(); got = []
        for i in range(0, len(texts), batch):
            r = cl.post("/infer_batch", json={
                "task": "entity", "texts": texts[i:i+batch],
                "labels": LABELS, "threshold": 0.5})
            got.extend(r.json()["results"])
        dt = time.perf_counter() - t0
        eq = all(norm(a) == norm(b) for a, b in zip(ref, got))
        print(f"/infer_batch b={batch:<4}: {dt:6.1f}s "
              f"({len(texts)/dt:5.2f} chunks/s)  EQUIVALENT={eq}")
        results[f"batch_{batch}"] = {"s": round(dt, 1), "equivalent": eq}
    json.dump(results, open("eval/v5/gliner_curve_results.json", "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""B4 — MPS contention: GLiNER latency alone vs under co-resident GPU load.

All sidecars share the one Apple-silicon GPU (MPS). This measures how
much entity-pass throughput degrades when the embedder and reranker are
actively working, using real chunk texts and the production batch size.
Read-only: no DB writes, no semantic surface.
"""
import json
import statistics
import sys
import threading
import time

import httpx
import psycopg

GLINER = "http://127.0.0.1:8740"
EMBED = "http://127.0.0.1:8742"
RERANK = "http://127.0.0.1:8743"
LABELS = ["person", "organization", "location", "product", "concept",
          "process", "artifact", "event", "condition", "measurement",
          "system", "method", "material", "document", "role",
          "technology", "substance", "structure", "phenomenon", "activity"]


def chunks(n=64):
    c = psycopg.connect("postgresql://polymath:polymath-dev@127.0.0.1:5432/polymath")
    rows = c.execute(
        """SELECT text FROM chunks WHERE tier='child'
           AND doc_id=(SELECT doc_id FROM documents WHERE corpus_id='perf-baseline-v1')
           ORDER BY chunk_index LIMIT %s""", (n,)).fetchall()
    return [r[0] for r in rows]


def gliner_pass(texts, client):
    t0 = time.monotonic()
    for i in range(0, len(texts), 32):
        r = client.post(f"{GLINER}/infer_batch", json={
            "texts": texts[i:i+32], "labels": LABELS, "threshold": 0.5,
            "mode": "entity"}, timeout=300)
        r.raise_for_status()
    return time.monotonic() - t0


def load_embed(stop, texts, errors):
    with httpx.Client() as cl:
        while not stop.is_set():
            try:
                cl.post(f"{EMBED}/infer", json={"texts": texts[:32]}, timeout=120)
            except Exception as e:
                errors.append(f"embed:{e}"); return


def load_rerank(stop, texts, errors):
    with httpx.Client() as cl:
        while not stop.is_set():
            try:
                cl.post(f"{RERANK}/rerank", json={
                    "query": "how does incident response work",
                    "documents": texts[:24]}, timeout=120)
            except Exception as e:
                errors.append(f"rerank:{e}"); return


def measure(texts, background):
    errors = []
    stop = threading.Event()
    threads = [threading.Thread(target=fn, args=(stop, texts, errors), daemon=True)
               for fn in background]
    for t in threads:
        t.start()
    time.sleep(3)  # let load reach steady state
    samples = []
    with httpx.Client() as cl:
        for _ in range(3):
            samples.append(gliner_pass(texts, cl))
    stop.set()
    for t in threads:
        t.join(timeout=130)
    return {"runs_s": [round(s, 2) for s in samples],
            "median_s": round(statistics.median(samples), 2),
            "chunks_per_s": round(len(texts) / statistics.median(samples), 2),
            "load_errors": errors}


def main():
    texts = chunks()
    out = {"chunks": len(texts), "batch": 32}
    out["gliner_alone"] = measure(texts, [])
    out["gliner_plus_embed"] = measure(texts, [load_embed])
    out["gliner_plus_embed_plus_rerank"] = measure(texts, [load_embed, load_rerank])
    base = out["gliner_alone"]["median_s"]
    for k in ("gliner_plus_embed", "gliner_plus_embed_plus_rerank"):
        out[k]["slowdown_x"] = round(out[k]["median_s"] / base, 2)
    json.dump(out, sys.stdout, indent=1)
    with open("eval/v5/mps_contention_results.json", "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()

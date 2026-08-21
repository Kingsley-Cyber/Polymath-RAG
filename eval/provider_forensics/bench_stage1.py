#!/usr/bin/env python3
"""ENTITY-PROVIDER-FORENSICS-V1 — stage 1: one model, all chunks.

Deliberately dependency-free beyond the model package so the same file runs
in both venvs. Identical inputs, labels, threshold, backend (PyTorch/MPS),
in-process inference for both arms.
"""
import argparse, json, pathlib, statistics as st, sys, time

THRESHOLD = 0.5
WARMUP, REPS = 2, 5
PIN = {"id": "urchade/gliner_medium-v2.1",
       "revision": "40ec419335d09393f298636f471328b722c6da9e"}
G2 = "fastino/gliner2-base-v1"


def load(model_name):
    t0 = time.perf_counter()
    if model_name == "medium":
        from gliner import GLiNER
        cache = pathlib.Path.home() / ".cache" / "polymath" / "gliner"
        m = GLiNER.from_pretrained(PIN["id"], revision=PIN["revision"],
                                   cache_dir=str(cache)).to("mps")
        def predict(text, labels):
            return [{"text": r["text"], "start": int(r["start"]), "end": int(r["end"]),
                     "label": r["label"], "score": float(r["score"])}
                    for r in m.predict_entities(text, labels, threshold=THRESHOLD)]
    else:
        from gliner2 import GLiNER2
        m = GLiNER2.from_pretrained(G2)
        try: m = m.to("mps")
        except Exception: pass
        def predict(text, labels):
            out = m.extract_entities(text, labels, threshold=THRESHOLD,
                                     include_confidence=True, include_spans=True)
            spans = []
            for label, items in (out.get("entities") or {}).items():
                for it in items:
                    spans.append({"text": it.get("text", ""),
                                  "start": int(it.get("start", -1)),
                                  "end": int(it.get("end", -1)),
                                  "label": str(label), "score": float(it.get("confidence", 1.0))})
            return spans
    return predict, round((time.perf_counter() - t0) * 1000, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["medium", "gliner2"])
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    data = json.loads(pathlib.Path(a.inputs).read_text())
    predict, load_ms = load(a.model)
    result = {"model": a.model, "threshold": THRESHOLD, "load_ms": load_ms, "docs": {}}
    for doc in data["docs"]:
        lat, spans_by_chunk = [], {}
        for ch in doc["chunks"]:
            for _ in range(WARMUP):
                predict(ch["text"], doc["labels"])
            times, out = [], None
            for _ in range(REPS):
                t0 = time.perf_counter()
                out = predict(ch["text"], doc["labels"])
                times.append((time.perf_counter() - t0) * 1000)
            lat.append(st.median(times))
            spans_by_chunk[ch["chunk_id"]] = out
        result["docs"][doc["name"]] = {
            "chunk_ms_median": round(st.median(lat), 1),
            "chunk_ms_all": [round(x, 1) for x in lat],
            "proposals": sum(len(v) for v in spans_by_chunk.values()),
            "spans": spans_by_chunk,
        }
    pathlib.Path(a.out).write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"model": a.model, "load_ms": load_ms,
                      "per_doc": {k: {"ms": v["chunk_ms_median"], "n": v["proposals"]}
                                  for k, v in result["docs"].items()}}, indent=1))


if __name__ == "__main__":
    main()

"""GLINER-SPEED-V1 benchmark — one arm per invocation (see PLAN.md).

In-process inference: no HTTP, so the measurement isolates model latency
rather than sidecar serialization. Mirrors the sidecar's call exactly —
same load params, same predict_entities signature, same threshold.

Usage:
  .venv/bin/python eval/gliner_speed_v1/bench.py --arm A --model medium --labels identity
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

HERE = ROOT / "eval" / "gliner_speed_v1"
DOCS = ["01_northvale_health.md", "05_corval_logistics.md"]
THRESHOLD = 0.5
WARMUP = 3
REPS = 10
PIN = {"id": "urchade/gliner_medium-v2.1",
       "revision": "40ec419335d09393f298636f471328b722c6da9e"}


def slices_for(doc: str) -> list[str]:
    from workers.summarizer import split_sentences
    text = (ROOT / "eval/i4/corpus" / doc).read_text()
    return [s for s in split_sentences(text) if s.strip()]


def load_medium():
    from gliner import GLiNER
    # Same cache the sidecar uses — reuses the already-pinned weights and
    # keeps 1.5GB of model data out of the repository tree.
    cache = Path.home() / ".cache" / "polymath" / "gliner"
    t0 = time.perf_counter()
    m = GLiNER.from_pretrained(PIN["id"], revision=PIN["revision"],
                               cache_dir=str(cache))
    m = m.to("mps")
    return m, round((time.perf_counter() - t0) * 1000, 1)


GLINER2_REPO = "fastino/gliner2-base-v1"  # no MLX build exists; MPS keeps
                                          # the backend identical to arms A/B


def load_gliner2():
    from gliner2 import GLiNER2
    t0 = time.perf_counter()
    m = GLiNER2.from_pretrained(GLINER2_REPO)
    try:
        m = m.to("mps")
    except Exception:
        pass
    return m, round((time.perf_counter() - t0) * 1000, 1)


def predict_medium(model, text, labels):
    return [{"text": r["text"], "start": int(r["start"]), "end": int(r["end"]),
             "label": r["label"].split(":", 1)[0].strip(), "score": float(r["score"])}
            for r in model.predict_entities(text, labels, threshold=THRESHOLD)]


def predict_gliner2(model, text, labels):
    out = model.extract_entities(text, labels, threshold=THRESHOLD,
                                 include_confidence=True, include_spans=True)
    spans = []
    for label, items in (out.get("entities") or {}).items():
        for it in items:
            spans.append({"text": it.get("text", ""),
                          "start": int(it.get("start", -1)),
                          "end": int(it.get("end", -1)),
                          "label": str(label).split(":", 1)[0].strip(),
                          "score": float(it.get("confidence", 1.0))})
    return spans


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--model", required=True, choices=["medium", "gliner2"])
    ap.add_argument("--labels", required=True, choices=["identity", "descriptive"])
    a = ap.parse_args()

    L = json.loads((HERE / "LABELS.json").read_text())
    labels = L["identity"] if a.labels == "identity" else list(L["descriptive"].values())
    assert len(labels) == 12, "label count must be held at 12"

    if a.model == "medium":
        model, load_ms = load_medium()
        predict = predict_medium
    else:
        model, load_ms = load_gliner2()
        predict = predict_gliner2

    result = {"arm": a.arm, "model": a.model, "labels": a.labels,
              "label_count": len(labels), "threshold": THRESHOLD,
              "model_load_ms": load_ms, "warmup": WARMUP, "reps": REPS,
              "documents": {}}

    for doc in DOCS:
        sl = slices_for(doc)
        for _ in range(WARMUP):                       # discarded
            for s in sl:
                predict(model, s, labels)
        per_slice, per_doc = [], []
        spans = None
        for _ in range(REPS):
            d0 = time.perf_counter()
            out = []
            for s in sl:
                t0 = time.perf_counter()
                r = predict(model, s, labels)
                per_slice.append((time.perf_counter() - t0) * 1000)
                out.extend(r)
            per_doc.append((time.perf_counter() - d0) * 1000)
            spans = out                                # last rep's output
        result["documents"][doc] = {
            "slices": len(sl),
            "chars": sum(len(s) for s in sl),
            "slice_ms": {"median": round(st.median(per_slice), 2),
                         "p95": round(sorted(per_slice)[int(len(per_slice) * .95) - 1], 2),
                         "min": round(min(per_slice), 2)},
            "doc_ms": {"median": round(st.median(per_doc), 2),
                       "p95": round(sorted(per_doc)[int(len(per_doc) * .95) - 1], 2),
                       "min": round(min(per_doc), 2)},
            "chars_per_sec": round(sum(len(s) for s in sl) / (st.median(per_doc) / 1000), 1),
            "entity_count": len(spans),
            "entities": sorted(spans, key=lambda x: (x["label"], x["text"])),
        }

    out = HERE / "arms"
    out.mkdir(exist_ok=True)
    (out / f"{a.arm}.json").write_text(json.dumps(result, indent=1))
    print(f"ARM {a.arm}: model={a.model} labels={a.labels} load={load_ms}ms")
    for doc, d in result["documents"].items():
        print(f"  {doc:<28} {d['slices']}sl  slice_med={d['slice_ms']['median']}ms "
              f"p95={d['slice_ms']['p95']}ms  doc_med={d['doc_ms']['median']}ms  "
              f"{d['chars_per_sec']}c/s  entities={d['entity_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

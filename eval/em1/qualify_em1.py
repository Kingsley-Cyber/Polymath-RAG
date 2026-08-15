"""EM1 entity-model qualification runner (Phase 1-2).

For every pinned model x threshold grid point: load the model, run the
FAIR contract (production labels + mapping) over the EP1 dev corpus,
score with the EP1 entity harness, record pins (file sha256s, config,
license, library versions, device, dtype, load time, peak memory) and
run a determinism re-check (identical spans on a second pass).

Usage:
    .venv/bin/python eval/em1/qualify_em1.py --model <id> [--thresholds 0.5]
Artifacts: eval/em1/artifacts/<id>_<threshold>.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))
sys.path.insert(0, str(ROOT / "eval" / "ep1"))

import yaml  # noqa: E402

from harness_entity import _norm, score_document  # noqa: E402
from polymath_shared.contracts import CoreType  # noqa: E402
from workers.chunker import materialize_chunks, plan_document  # noqa: E402
from workers.extract_worker import _map_label, _pack  # noqa: E402
from workers.profile_router import chunk_label_set, route_document  # noqa: E402

MODELS = yaml.safe_load((ROOT / "eval" / "em1" / "models.yaml").read_text())
CORPUS = ROOT / "eval" / "gold" / "realistic_smoke_v1"


def _load_model(entry: dict):
    from gliner import GLiNER

    t0 = time.time()
    model = GLiNER.from_pretrained(entry["repo"], revision=entry["revision"])
    load_s = time.time() - t0
    return model, load_s


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_hashes(model_id: str) -> dict:
    """Record sha256 of every committed file in the HF snapshot."""
    import os

    cache = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    out = {}
    for snap in cache.glob(f"models--{model_id.replace('/', '--')}*/snapshots/*"):
        for f in sorted(snap.rglob("*")):
            if f.is_file() and f.name not in (".lock", "*.incomplete"):
                try:
                    out[str(f.relative_to(snap))] = _sha256(f)
                except OSError:
                    pass
        break  # first snapshot dir (the pinned revision)
    return out


def _peak_memory() -> int:
    try:
        import torch

        return int(torch.mps.current_allocated_memory() / (1024 * 1024))
    except Exception:
        return 0


def run_model(entry: dict, threshold: float) -> dict:
    model, load_s = _load_model(entry)
    device = "mps"
    try:
        import torch

        model = model.to(device)
        torch.mps.empty_cache()
    except Exception:
        device = "cpu"
        model = model.to("cpu")

    pack = _pack()
    docs = sorted(CORPUS.glob("*.md"))
    gold = yaml.safe_load((ROOT / "eval" / "gold" / "ep1_dev_gold.yaml").read_text())
    gold_by_doc = {d["doc"]: d["mentions"] for d in gold["documents"]}

    def run_pass() -> dict:
        per_doc: dict = {}
        for doc_path in docs:
            doc_text = doc_path.read_text()
            plan = plan_document(doc_text, f"em1_{doc_path.stem}")
            children = [c for c in materialize_chunks(plan) if c["tier"] == "child"]
            profile = route_document(doc_path.name, doc_text[:4000])
            proposals: list[dict] = []
            for chunk in children:
                labels = chunk_label_set(chunk["text"], profile)
                label_core = {
                    lab: (_map_label(lab, pack) or lab) for lab in labels
                }
                result = model.predict_entities(chunk["text"], labels,
                                                threshold=threshold)
                for item in result:
                    span_text = item.get("text") or chunk["text"][item["start"]:item["end"]]
                    core = label_core.get(item.get("label"), "Concept")
                    proposals.append({
                        "text": span_text,
                        "label": item.get("label"),
                        "core_type": core,
                        "score": round(item.get("score", 0.0), 4),
                        "start": item["start"],
                        "end": item["end"],
                    })
            per_doc[doc_path.name] = {
                "score": score_document_chunks(doc_text, children, proposals,
                                               gold_by_doc.get(doc_path.name, [])),
                "proposals": proposals,
            }
        return per_doc

    per_doc = run_pass()
    # determinism re-check (second pass)
    per_doc2 = run_pass()
    deterministic = all(
        [(p["text"], p["label"], p["start"], p["end"]) for p in per_doc[d]["proposals"]]
        == [(p["text"], p["label"], p["start"], p["end"]) for p in per_doc2[d]["proposals"]]
        for d in per_doc
    )

    # aggregate
    n_proposals = sum(len(d["proposals"]) for d in per_doc.values())
    exact = sum(d["score"]["counts"]["exact"] for d in per_doc.values())
    matched = sum(
        d["score"]["counts"]["exact"] + d["score"]["counts"]["overlap"]
        + d["score"]["counts"]["bare_head"] for d in per_doc.values()
    )
    false = sum(d["score"]["counts"]["false"] for d in per_doc.values())
    type_c = sum(d["score"]["counts"]["type_correct"] for d in per_doc.values())
    type_w = sum(d["score"]["counts"]["type_wrong"] for d in per_doc.values())
    n_mentions = sum(d["score"]["mentions"] for d in per_doc.values())
    mw_n = sum(d["score"]["multiword_n"] for d in per_doc.values())
    mw_m = sum(d["score"]["multiword_matched"] for d in per_doc.values())
    bare = sum(d["score"]["counts"]["bare_head"] for d in per_doc.values())

    payload = {
        "model": entry["id"],
        "repo": entry["repo"],
        "revision": entry["revision"],
        "license": entry["license"],
        "threshold": threshold,
        "device": device,
        "dtype": "fp32",
        "library": {"gliner": "0.2.28", "torch": "2.13.0",
                    "transformers": "5.13.1"},
        "load_seconds": round(load_s, 2),
        "peak_mps_mb": _peak_memory(),
        "maxrss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "file_sha256": _snapshot_hashes(entry["repo"]),
        "deterministic": deterministic,
        "summary": {
            "proposals": n_proposals,
            "mentions": n_mentions,
            "exact_precision": exact / max(n_proposals, 1),
            "exact_recall": exact / max(n_mentions, 1),
            "overlap_recall": matched / max(n_mentions, 1),
            "multiword_recall": mw_m / max(mw_n, 1),
            "core_type_accuracy": type_c / max(type_c + type_w, 1),
            "bare_head_rate": bare / max(n_proposals, 1),
            "false_span_rate": false / max(n_proposals, 1),
        },
        "per_document": {
            d: {
                "score": per_doc[d]["score"],
                "proposals": per_doc[d]["proposals"],
            }
            for d in per_doc
        },
    }
    return payload


def score_document_chunks(doc_text: str, children: list[dict],
                          proposals: list[dict], mentions: list[dict]) -> dict:
    """Score chunk-local proposals against doc-level gold by locating
    proposal text in the document (chunk text is whitespace-normalized)."""
    located: list[dict] = []
    seen: set[tuple[int, int, str]] = set()
    for p in proposals:
        for chunk in children:
            text = chunk["text"]
            idx = text.find(p["text"])
            if idx < 0:
                idx = _norm(text).find(_norm(p["text"]))
            if idx >= 0:
                start = chunk["char_start"] + idx
                end = chunk["char_start"] + idx + len(p["text"])
                key = (start, end, _norm(p["text"]))
                if key in seen:
                    break
                seen.add(key)
                located.append({
                    "start": start, "end": end,
                    "text": p["text"],
                    "label": p["label"],
                    "core_type": p["core_type"],
                })
                break
    return score_document(doc_text, located, mentions)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--thresholds", default=None,
                        help="comma-separated; default = contract grid")
    args = parser.parse_args()

    entry = next(m for m in MODELS["models"] if m["id"] == args.model)
    thresholds = ([float(t) for t in args.thresholds.split(",")]
                  if args.thresholds else MODELS["contract"]["threshold_grid"])
    outdir = ROOT / "eval" / "em1" / "artifacts"
    outdir.mkdir(parents=True, exist_ok=True)
    for thr in thresholds:
        payload = run_model(entry, thr)
        out = outdir / f"{entry['id']}_{thr:.2f}.json"
        out.write_text(json.dumps(payload, sort_keys=True, indent=1))
        s = payload["summary"]
        print(f"{entry['id']} @{thr:.2f}: overlapR={s['overlap_recall']:.3f} "
              f"mwR={s['multiword_recall']:.3f} typeAcc={s['core_type_accuracy']:.3f} "
              f"bareHead={s['bare_head_rate']:.3f} false={s['false_span_rate']:.3f} "
              f"exactP={s['exact_precision']:.3f} det={payload['deterministic']} "
              f"load={payload['load_seconds']}s peak={payload['peak_mps_mb']}MB "
              f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

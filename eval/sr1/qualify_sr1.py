"""SR1 measurement: bounded deterministic span repair over the EM1
clean direct-API baseline (gliner_medium-v2.1 @ 40ec4193).

Arms:
  SR1-A  = raw proposals + bounded-span-repair-v1 (deterministic only)
  SR1-B  = SR1-A + local GLiNER consistency check on repaired spans
           (same model, same labels — the inference contract is
           unchanged; only the boundary is re-scored)

Measures the EP1/EM1 entity metrics plus a repair confusion report
(RAW -> REPAIRED, correct/incorrect/no-op counts).

Usage:
    .venv/bin/python eval/sr1/qualify_sr1.py --arm SR1-A --threshold 0.45
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))
sys.path.insert(0, str(ROOT / "eval" / "ep1"))
sys.path.insert(0, str(ROOT / "eval" / "em1"))

import yaml  # noqa: E402

from harness_entity import _norm, score_document  # noqa: E402
from polymath_shared.span_repair import REPAIR_VERSION, repair_span  # noqa: E402
from qualify_em1 import CORPUS, _load_model  # noqa: E402
from workers.chunker import materialize_chunks, plan_document  # noqa: E402
from workers.extract_worker import _map_label, _pack  # noqa: E402
from workers.profile_router import chunk_label_set, route_document  # noqa: E402

GOLD = yaml.safe_load((ROOT / "eval" / "gold" / "ep1_dev_gold.yaml").read_text())


def _locate(text: str, span_text: str, window: str, base: int) -> int | None:
    idx = window.find(span_text)
    if idx < 0:
        idx = _norm(window).find(_norm(span_text))
    return (base + idx) if idx >= 0 else None


def run(threshold: float, arm: str) -> dict:
    entry = next(m for m in yaml.safe_load(
        (ROOT / "eval" / "em1" / "models.yaml").read_text())["models"]
        if m["id"] == "baseline-medium")
    model, load_s = _load_model(entry)
    import torch

    model = model.to("mps")
    torch.mps.empty_cache()
    pack = _pack()

    docs = sorted(CORPUS.glob("*.md"))
    gold_by_doc = {d["doc"]: d["mentions"] for d in GOLD["documents"]}

    repair_report = {"total": 0, "repaired": 0, "no_op": 0, "correct": 0,
                     "incorrect": 0, "confusion": []}

    def run_pass():
        per_doc = {}
        for doc_path in docs:
            doc_text = doc_path.read_text()
            plan = plan_document(doc_text, f"sr1_{doc_path.stem}")
            children = [c for c in materialize_chunks(plan) if c["tier"] == "child"]
            profile = route_document(doc_path.name, doc_text[:4000])
            proposals = []
            for chunk in children:
                labels = chunk_label_set(chunk["text"], profile)
                label_core = {lab: (_map_label(lab, pack) or lab) for lab in labels}
                result = model.predict_entities(chunk["text"], labels,
                                                threshold=threshold)
                for item in result:
                    raw_text = chunk["text"][item["start"]:item["end"]]
                    r = repair_span(chunk["text"], item["start"], item["end"],
                                    allow_right=(arm == "SR1-B"))
                    if arm == "SR1-B" and r.changed:
                        # local consistency check: same model, same labels
                        scored = model.predict_entities(
                            r.repaired_text, [item.get("label")], threshold=0.0)
                        best = max((s.get("score", 0.0) for s in scored), default=0.0)
                        if best + 0.05 < item.get("score", 0.0):
                            r = repair_span(chunk["text"], item["start"], item["end"],
                                            allow_right=(arm == "SR1-B"))
                            r.rule = "rejected-by-local-score"
                            r.changed = False
                    base = chunk["char_start"]
                    if r.changed:
                        loc = _locate(doc_text, r.repaired_text,
                                      doc_text[base:base + len(chunk["text"])], base)
                        proposals.append({
                            "text": r.repaired_text, "label": item.get("label"),
                            "core_type": label_core.get(item.get("label"), "Concept"),
                            "loc": loc, "repaired": True,
                        })
                    else:
                        loc = _locate(doc_text, raw_text,
                                      doc_text[base:base + len(chunk["text"])], base)
                        proposals.append({
                            "text": raw_text, "label": item.get("label"),
                            "core_type": label_core.get(item.get("label"), "Concept"),
                            "loc": loc, "repaired": False,
                        })
            located = []
            seen = set()
            for p in proposals:
                if p["loc"] is None:
                    continue
                key = (p["loc"], _norm(p["text"]))
                if key in seen:
                    continue
                seen.add(key)
                located.append({
                    "start": p["loc"], "end": p["loc"] + len(p["text"]),
                    "text": p["text"], "label": p["label"],
                    "core_type": p["core_type"],
                })
            per_doc[doc_path.name] = {
                "score": score_document(doc_text, located,
                                        gold_by_doc.get(doc_path.name, [])),
                "proposals": located,
            }
        return per_doc

    per_doc = run_pass()
    per_doc2 = run_pass()
    deterministic = all(
        [(p["text"], p["start"], p["end"]) for p in per_doc[d]["proposals"]]
        == [(p["text"], p["start"], p["end"]) for p in per_doc2[d]["proposals"]]
        for d in per_doc
    )

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

    # repair confusion: per repaired proposal, RAW vs REPAIRED + gold match
    raw_proposals = []
    for doc_path in docs:
        doc_text = doc_path.read_text()
        plan = plan_document(doc_text, f"sr1_{doc_path.stem}")
        children = [c for c in materialize_chunks(plan) if c["tier"] == "child"]
        profile = route_document(doc_path.name, doc_text[:4000])
        for chunk in children:
            labels = chunk_label_set(chunk["text"], profile)
            result = model.predict_entities(chunk["text"], labels,
                                            threshold=threshold)
            for item in result:
                raw_text = chunk["text"][item["start"]:item["end"]]
                r = repair_span(chunk["text"], item["start"], item["end"],
                                allow_right=(arm == "SR1-B"))
                if r.changed:
                    raw_proposals.append({
                        "doc": doc_path.name,
                        "raw": raw_text,
                        "repaired": r.repaired_text,
                        "rule": r.rule,
                        "label": item.get("label"),
                    })

    gold_surfaces = set()
    for d in GOLD["documents"]:
        for m in d["mentions"]:
            gold_surfaces.add(_norm(m["surface"]))
    repair_report["total"] = n_proposals
    repair_report["repaired"] = len(raw_proposals)
    for rp in raw_proposals:
        repair_report["confusion"].append(rp)
        if _norm(rp["repaired"]) in gold_surfaces:
            repair_report["correct"] += 1
        else:
            repair_report["incorrect"] += 1

    return {
        "arm": arm,
        "repair_version": REPAIR_VERSION,
        "threshold": threshold,
        "deterministic": deterministic,
        "load_seconds": round(load_s, 2),
        "summary": {
            "proposals": n_proposals,
            "mentions": n_mentions,
            "exact_precision": exact / max(n_proposals, 1),
            "exact_recall": exact / max(n_mentions, 1),
            "overlap_recall": matched / max(n_mentions, 1),
            "multiword_recall": mw_m / max(mw_n, 1),
            "core_type_accuracy": type_c / max(type_c + type_w, 1),
            "bare_head_rate": sum(d["score"]["counts"]["bare_head"] for d in per_doc.values()) / max(n_proposals, 1),
            "false_span_rate": false / max(n_proposals, 1),
        },
        "repair_report": repair_report,
        "per_document": {
            d: per_doc[d]["score"] for d in per_doc
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=["SR1-A", "SR1-B"], default="SR1-A")
    parser.add_argument("--threshold", type=float, default=0.45)
    args = parser.parse_args()
    payload = run(args.threshold, args.arm)
    outdir = ROOT / "eval" / "sr1" / "artifacts"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{args.arm}_{args.threshold:.2f}.json"
    out.write_text(json.dumps(payload, sort_keys=True, indent=1))
    s = payload["summary"]
    print(f"{args.arm} @{args.threshold:.2f}: overlapR={s['overlap_recall']:.3f} "
          f"mwR={s['multiword_recall']:.3f} typeAcc={s['core_type_accuracy']:.3f} "
          f"bareHead={s['bare_head_rate']:.3f} false={s['false_span_rate']:.3f} "
          f"exactP={s['exact_precision']:.3f} det={payload['deterministic']}")
    print(f"repairs: {payload['repair_report']['repaired']} "
          f"(correct={payload['repair_report']['correct']} "
          f"incorrect={payload['repair_report']['incorrect']})")
    print(f"artifact: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

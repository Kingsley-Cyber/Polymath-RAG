"""E2/C1.1 entity-admission qualification (experiment-only).

Scores the candidate admission policy against the frozen gold, then
re-runs the downstream G4 checkpoint with an admission-filtered graph
(disposable projection simulation: MENTION_ONLY surfaces are excluded
from the seed/entity population; GLOBAL + SCOPED survive; SCOPED =
corpus-local identity for this single-corpus fixture).

Usage:
    .venv/bin/python eval/admission/qualify_admission.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))
# PHASE 0 (D1): import PRODUCTION admission, never the local fork.
# `eval/admission/entity_admission.py` is a frozen v1.1 snapshot kept for
# historical reproduction only; importing it meant this harness never
# tested the code that actually ships.
from polymath_shared.entity_admission import POLICY_VERSION, decide  # noqa: E402

HERE = ROOT / "eval" / "admission"
ARTIFACTS = HERE / "artifacts"


def main() -> int:
    # PHASE 0 (D2): admission_gold.json is the v1 (44-item) set using the
    # umbrella label "SCOPED". The policy split SCOPED into
    # CORPUS_SCOPED/DOCUMENT_SCOPED at v1.1 (identity contract v2) and the
    # harness was never repointed, so every scoped item scored as wrong
    # (0.773). GOLD is selectable; the default matches the live policy.
    gold_name = os.environ.get("POLYMATH_ADMISSION_GOLD", "admission_gold_v1.1.json")
    gold_path = HERE / gold_name
    gold_doc = json.loads(gold_path.read_text())
    gold = gold_doc["items"]
    gold_labels = sorted({i["label"] for i in gold})
    policy_labels = {"GLOBAL", "CORPUS_SCOPED", "DOCUMENT_SCOPED", "MENTION_ONLY"}
    unknown = [l for l in gold_labels if l not in policy_labels]
    if unknown:
        raise SystemExit(
            f"gold {gold_name} uses label(s) {unknown} that the {POLICY_VERSION} "
            f"policy cannot emit (it emits {sorted(policy_labels)}). "
            f"This gold predates the current contract - pick a matching gold "
            f"or re-author it. Refusing to report a misleading accuracy."
        )

    # ---- local scoring: baseline (all GLOBAL) vs candidate ----
    per_class = Counter(i["label"] for i in gold)
    rows = []
    for item in gold:
        d = decide(item["surface"], item["core_type"], 0.5)
        rows.append({
            "surface": item["surface"],
            "gold": item["label"],
            "candidate": d.reference_class,
            "reasons": list(d.reasons),
            "correct": d.reference_class == item["label"],
        })
    correct = sum(1 for r in rows if r["correct"])
    class_stats = {}
    for cls in ("GLOBAL", "SCOPED", "MENTION_ONLY"):
        gold_cls = [r for r in rows if r["gold"] == cls]
        cand_cls = [r for r in rows if r["candidate"] == cls]
        tp = sum(1 for r in gold_cls if r["candidate"] == cls)
        fn = len(gold_cls) - tp
        fp = sum(1 for r in cand_cls if r["gold"] != cls)
        class_stats[cls] = {
            "gold": len(gold_cls),
            "precision": tp / max(len(cand_cls), 1),
            "recall": tp / max(len(gold_cls), 1),
            "false_negatives": [r["surface"] for r in gold_cls if r["candidate"] != cls][:10],
            "false_positives": [r["surface"] for r in cand_cls if r["gold"] != cls][:10],
        }
    errors = [r for r in rows if not r["correct"]]

    # ---- downstream: admission-filtered G4 graph ----
    # MENTION_ONLY surfaces lose global graph identity: simulate by
    # excluding them from the seed/entity population of the G4 corpus.
    g4_spec = json.loads((ROOT / "eval" / "g4" / "corpus_spec_v1.1.json").read_text())
    surfaces = []
    for h in g4_spec["hubs"] + g4_spec["noise_inserts"]:
        surfaces.append(h["surface"])
    for n in g4_spec["named_query_entities"]:
        surfaces.append(n["surface"])
    for i in range(12):
        for j in range(22):
            surfaces.append(f"component {i}x{j}")

    admission = {s: decide(s, "Technology", 0.5).reference_class for s in surfaces}
    dropped = {s: c for s, c in admission.items() if c == "MENTION_ONLY"}
    kept = {s: c for s, c in admission.items() if c != "MENTION_ONLY"}

    queries = json.loads((ROOT / "eval" / "g4" / "frozen_queries.json").read_text())["queries"]
    hub_q = [q for q in queries if "hub" in q["class"]]
    generic_q = [q for q in queries if "adversarial" in q["class"]]

    downstream = {
        "generic_surfaces_dropped": sorted(dropped),
        "kept_surfaces": sorted(kept),
        "hub_queries": [q["id"] for q in hub_q],
        "generic_queries": [q["id"] for q in generic_q],
        "expected_effect": {
            "generic_hub_suppression": "the system/the model/the platform/database -> MENTION_ONLY (no global node)",
            "specific_hub_survival": "multiword SCOPED hubs (the vector index, the retrieval pipeline, the worker pool) remain",
            "named_entities_survival": "metric recorder/corpus layer/verification loop/attention model remain SCOPED",
            "bidirectional_safety": "no generic mega-node remains for q09/q10 to expand",
        },
    }

    payload = {
        "policy_version": POLICY_VERSION,
        "gold_items": len(gold),
        "gold_class_distribution": dict(per_class),
        "baseline": {"description": "current behavior: every accepted span is globally entity-eligible",
                     "global_entities_created": len(gold)},
        "candidate": {
            "accuracy": correct / len(rows),
            "gold_file": gold_name,
            "gold_version": gold_doc.get("version"),
            "policy_version": POLICY_VERSION,
            "per_class": class_stats,
            "errors": errors,
        },
        "downstream_g4_projection": downstream,
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    # PHASE 0 (D3): committed artifacts are evidence. Writing requires an
    # explicit opt-in; otherwise the run reports to stdout only.
    out = ARTIFACTS / "admission_metrics.json"
    if os.environ.get("POLYMATH_WRITE_ARTIFACTS") == "1":
        out.write_text(json.dumps(payload, indent=1, sort_keys=True))
        print(json.dumps({"artifact_written": str(out)}))
    else:
        print(json.dumps({
            "artifact_write": "SKIPPED (set POLYMATH_WRITE_ARTIFACTS=1 to persist)",
            "would_write": str(out)}))

    print(json.dumps({
        "accuracy": payload["candidate"]["accuracy"],
        "per_class": {
            cls: {k: v for k, v in class_stats[cls].items() if k != "false_positives"}
            for cls in ("GLOBAL", "SCOPED", "MENTION_ONLY")
        },
        "errors": errors,
    }, indent=1))
    print(json.dumps(downstream, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

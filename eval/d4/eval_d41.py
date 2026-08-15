"""D4.1 candidate answer-support model evaluation (qualification only).

For each candidate model: deterministic repeated inference over the
frozen (query, passage) pair set; records entailment/neutral/
contradiction class probabilities per pair + latency. No production
wiring; no retrieval change.

Usage: .venv/bin/python eval/d4/eval_d41.py --model <hf_id> --runs 2
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from sentence_transformers import CrossEncoder  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=32)
    args = ap.parse_args()

    pairs_path = ROOT / "eval" / "d4" / "artifacts" / "d41_pairs.jsonl"
    pairs = [json.loads(l) for l in pairs_path.read_text().splitlines()]

    print(f"loading {args.model} ...", flush=True)
    t0 = time.time()
    from torch.nn import functional as F
    model = CrossEncoder(args.model, device="mps")
    num_labels = model.model.config.num_labels
    if num_labels == 1:
        model.default_activation_fn = None  # raw logit; score it separately
    else:
        model.default_activation_fn = F.softmax
    model.model.eval()
    print(f"loaded in {time.time()-t0:.1f}s (num_labels={num_labels})", flush=True)

    inputs = [(p["query"], p["passage"]) for p in pairs]
    runs = []
    for run in range(args.runs):
        t_start = time.time()
        probs = model.predict(
            inputs, batch_size=args.batch_size, show_progress_bar=False,
        )
        elapsed = time.time() - t_start
        rows = []
        for p, pr in zip(pairs, probs):
            if num_labels == 1:
                rows.append({
                    "query_id": p["query_id"], "text_kind": p["text_kind"],
                    "chunk_id": p["chunk_id"], "doc_id": p["doc_id"],
                    "gold_label": p["gold_label"],
                    "support_score": round(float(pr), 6),
                    "entail_prob": None, "contra_prob": None, "neutral_prob": None,
                })
            else:
                labels = model.model.config.id2label
                idx = {name.lower(): i for i, name in labels.items()}
                ent_i = next((i for name, i in idx.items() if name == "entailment"), None)
                con_i = next((i for name, i in idx.items() if "contra" in name), None)
                neu_i = next((i for name, i in idx.items() if "neutral" in name), None)
                rows.append({
                    "query_id": p["query_id"], "text_kind": p["text_kind"],
                    "chunk_id": p["chunk_id"], "doc_id": p["doc_id"],
                    "gold_label": p["gold_label"],
                    "support_score": round(float(pr[ent_i]), 6) if ent_i is not None else None,
                    "entail_prob": round(float(pr[ent_i]), 6) if ent_i is not None else None,
                    "contra_prob": round(float(pr[con_i]), 6) if con_i is not None else None,
                    "neutral_prob": round(float(pr[neu_i]), 6) if neu_i is not None else None,
                })
        runs.append(rows)
        print(f"run {run}: {elapsed:.1f}s ({len(pairs)/elapsed:.1f} pairs/s)", flush=True)

    identical = all(
        runs[0][i]["entail_prob"] == runs[1][i]["entail_prob"]
        for i in range(len(runs[0]))
    ) if len(runs) > 1 else None
    print(f"deterministic: {identical}")

    out = ROOT / "eval" / "d4" / "artifacts" / f"d41_{args.model.split('/')[-1]}.json"
    out.write_text(json.dumps({"model": args.model, "label_order": model.model.config.id2label,
                               "deterministic": identical, "runs": runs}, indent=1))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

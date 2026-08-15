"""G4.1: bidirectional-hop1 + G3 reranker downstream qualification.

Answers the one deferred G4 question: does the production-default
reranker suppress graph-added noise (especially q09's 17 generic-hub
edges) while retaining the useful hub evidence that outgoing-only
traversal misses?

Configs over the FROZEN G4 12-query set:
  A = outgoing hop1 (production traversal) + reranker
  B = bidirectional hop1 (measurement-only candidate) + reranker
Same HIGH_MEDIUM allowlist, same 8-seed/20-fact caps, hop2 rejected.
Final SELECTED evidence = top-k (k=10) by rerank score over the
candidate union — the metric is downstream evidence quality, not raw
graph precision.

Usage:
    .venv/bin/python eval/g4/qualify_g41.py
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "workers"))

from polymath_shared.clients import RerankerClient  # noqa: E402
from polymath_shared.retrieval import tokens  # noqa: E402

from eval.g4.qualify_g4 import _bidir_expand, _neo4j_expand_facts  # noqa: E402

G4 = ROOT / "eval" / "g4"
ARTIFACTS = G4 / "artifacts"
TOP_K = 10
REPEATS = 2


def _fact_text(f: dict) -> str:
    return f"{f.get('subject', '')} {f.get('predicate', '')} {f.get('object', '')}"


def _classify(f: dict, q: dict) -> str:
    surfaces = {f.get("subject", ""), f.get("object", "")}
    rel = set(q.get("relevant_surfaces", []))
    noise = set(q.get("noise_surfaces", []))
    if any(s in rel or any(r.split()[-1] in s for r in rel) for s in surfaces):
        return "relevant"
    return "irrelevant"


def main() -> int:
    queries = json.loads((G4 / "frozen_queries.json").read_text())["queries"]
    client = RerankerClient()
    per_query = []
    q09 = {}
    agg = Counter()

    for q in queries:
        surfaces = [t for t in tokens(q["text"]) if len(t) > 3][:12]
        row = {"id": q["id"], "class": q["class"]}

        results = {}
        for cfg in ("A", "B"):
            timings = []
            selected_sets = []
            for _ in range(REPEATS):
                t0 = time.perf_counter()
                facts = (_neo4j_expand_facts(surfaces) if cfg == "A"
                         else _bidir_expand(surfaces))
                unique = {f["fact_id"]: f for f in facts}
                raw = list(unique.values())
                if raw:
                    resp = client.rerank(q["text"], [_fact_text(f) for f in raw])
                    order = resp["order"][:TOP_K]
                    selected = [raw[i] for i in order]
                else:
                    selected = []
                selected_sets.append({f["fact_id"]: f for f in selected})
                timings.append(time.perf_counter() - t0)
            raw_cls = Counter(_classify(f, q) for f in raw)
            sel = selected_sets[0]
            sel_cls = Counter(_classify(f, q) for f in sel.values())
            results[cfg] = {
                "raw": dict(raw_cls),
                "selected": dict(sel_cls),
                "selected_ids": set(sel.keys()),
                "latency_p50": round(statistics.median(timings), 4),
                "deterministic": selected_sets[0] == selected_sets[1],
            }
            row[f"{cfg}_raw_useful"] = raw_cls.get("relevant", 0)
            row[f"{cfg}_raw_noise"] = raw_cls.get("irrelevant", 0)
            row[f"{cfg}_selected_useful"] = sel_cls.get("relevant", 0)
            row[f"{cfg}_selected_noise"] = sel_cls.get("irrelevant", 0)
            row[f"{cfg}_latency_p50"] = results[cfg]["latency_p50"]
            row[f"{cfg}_deterministic"] = results[cfg]["deterministic"]

        # retention: useful facts A selected that B also selects
        a_raw = {f["fact_id"]: f for f in _neo4j_expand_facts(surfaces)}
        a_useful_sel = {fid for fid in results["A"]["selected_ids"]
                        if _classify(a_raw[fid], q) == "relevant"}
        b_sel = results["B"]["selected_ids"]
        row["retained_useful_A_in_B"] = len(a_useful_sel & b_sel)
        row["A_useful_selected"] = len(a_useful_sel)
        row["hub_class"] = q["class"]

        agg["A_raw_useful"] += row["A_raw_useful"]
        agg["A_raw_noise"] += row["A_raw_noise"]
        agg["B_raw_useful"] += row["B_raw_useful"]
        agg["B_raw_noise"] += row["B_raw_noise"]
        agg["A_sel_useful"] += row["A_selected_useful"]
        agg["A_sel_noise"] += row["A_selected_noise"]
        agg["B_sel_useful"] += row["B_selected_useful"]
        agg["B_sel_noise"] += row["B_selected_noise"]
        if q["id"] == "q09":
            q09 = {
                "A_raw_noise": row["A_raw_noise"], "A_selected_noise": row["A_selected_noise"],
                "B_raw_noise": row["B_raw_noise"], "B_selected_noise": row["B_selected_noise"],
            }
        per_query.append(row)
        print(f"{q['id']} {q['class'][:24]:24} "
              f"A: raw {row['A_raw_useful']}u/{row['A_raw_noise']}n sel {row['A_selected_useful']}u/{row['A_selected_noise']}n | "
              f"B: raw {row['B_raw_useful']}u/{row['B_raw_noise']}n sel {row['B_selected_useful']}u/{row['B_selected_noise']}n | "
              f"retain {row['retained_useful_A_in_B']}/{row['A_useful_selected']}")

    hub_queries = [r for r in per_query if "hub" in r["class"] and "adversarial" not in r["class"]]
    hub_a = sum(r["A_selected_useful"] for r in hub_queries)
    hub_b = sum(r["B_selected_useful"] for r in hub_queries)

    payload = {
        "configs": {
            "A": "outgoing hop1 + reranker (production traversal)",
            "B": "bidirectional hop1 + reranker (candidate)",
        },
        "top_k": TOP_K,
        "query_set_sha256": hashlib.sha256((G4 / "frozen_queries.json").read_bytes()).hexdigest(),
        "aggregate": dict(agg),
        "hub_queries": [r["id"] for r in hub_queries],
        "hub_selected_useful_A": hub_a,
        "hub_selected_useful_B": hub_b,
        "q09": q09,
        "per_query": per_query,
        "verdict_criteria": {
            "hub_centered_useful_B_gt_A": hub_b > hub_a,
            "final_topk_useful_B_ge_A": agg["B_sel_useful"] >= agg["A_sel_useful"],
            "q09_noise_materially_reduced": q09.get("B_selected_noise", 99)
            < q09.get("B_raw_noise", 0),
            "all_useful_A_retained_in_B": all(
                r["retained_useful_A_in_B"] == r["A_useful_selected"] for r in per_query),
            "deterministic": all(r["A_deterministic"] and r["B_deterministic"] for r in per_query),
            "cap_bounded": all(r["B_raw_useful"] + r["B_raw_noise"] <= 20 for r in per_query),
        },
    }
    (ARTIFACTS / "g41_metrics.json").write_text(
        json.dumps(payload, indent=1, sort_keys=True, default=str))
    print(json.dumps({k: payload[k] for k in
                      ("aggregate", "hub_selected_useful_A", "hub_selected_useful_B",
                       "q09", "verdict_criteria")}, indent=1))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

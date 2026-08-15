"""R2A candidate runner: frozen set x ablations x reproducibility.

Usage:
  .venv/bin/python eval/r2a/run.py --base-url http://127.0.0.1:8100/v1 \
      --model <served-name> --candidate A|B [--runs 2]

Ablations over the frozen set:
  summary context: children-only / +doc-summaries / +doc+section
  hierarchy: flat vs hierarchical
  graph: HYBRID packet vs GRAPH packet (fact corpus)
Scored by deterministic gates + frozen gold judgments.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "orchestrator"))
sys.path.insert(0, str(ROOT / "eval" / "r2a"))

from harness import Provider, build_packet, parse_response, prompt_hash, score  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()

    frozen = json.loads((ROOT / "eval" / "r2a" / "queries.json").read_text())
    provider = Provider(args.base_url, args.model)
    rows = []

    def run_query(gold, packet_kwargs):
        packet, meta = build_packet(gold["query"], gold["corpus"],
                                    mode=gold["mode"], **packet_kwargs)
        t0 = time.time()
        resp = provider.generate(packet)
        parsed = parse_response(resp["text"])
        sc = score(gold, parsed, meta["ids"])
        sc["latency_ms"] = resp["latency_ms"]
        sc["input_tokens"] = resp.get("usage", {}).get("prompt_tokens")
        sc["output_tokens"] = resp.get("usage", {}).get("completion_tokens")
        return sc, parsed, meta

    for run in range(args.runs):
        for gold in frozen["queries"]:
            kwargs = {}
            if gold["corpus"] == "r2a-fact-corpus":
                kwargs["include_graph"] = (gold["mode"] == "GRAPH")
            # baseline configuration: hierarchical + summaries
            sc, parsed, meta = run_query(gold, {
                "hierarchy": "hierarchical",
                "include_doc_summaries": True,
                "include_section_summaries": True,
                **kwargs,
            })
            sc["run"] = run
            sc["packet_variant"] = "base"
            rows.append(sc)

    # ablations on the TEXT corpus (supported + unsupported controls)
    for gold in frozen["queries"]:
        if gold["corpus"] != "r2a-text-corpus":
            continue
        for variant, pk in (
            ("children_only", {"hierarchy": "hierarchical",
                               "include_doc_summaries": False,
                               "include_section_summaries": False}),
            ("plus_doc_summaries", {"hierarchy": "hierarchical",
                                    "include_doc_summaries": True,
                                    "include_section_summaries": False}),
            ("flat", {"hierarchy": "flat",
                      "include_doc_summaries": True,
                      "include_section_summaries": True}),
        ):
            sc, _, _ = run_query(gold, pk)
            sc["run"] = 0
            sc["packet_variant"] = variant
            rows.append(sc)

    # graph ablation: HYBRID packet (no graph) for the fact corpus
    for gold in frozen["queries"]:
        if gold["corpus"] != "r2a-fact-corpus":
            continue
        sc, _, _ = run_query(gold, {
            "hierarchy": "hierarchical",
            "include_doc_summaries": True,
            "include_section_summaries": True,
            "include_graph": False,
        })
        sc["run"] = 0
        sc["packet_variant"] = "no_graph"
        rows.append(sc)

    # aggregation
    def agg(pred, rows_sel):
        sel = [r for r in rows_sel]
        if not sel:
            return {}
        total = len(sel)
        return {
            "n": total,
            "answerable_accuracy": round(
                sum(1 for r in sel if r.get("answerable_match")) / total, 3),
            "unsupported_abstained": round(
                sum(1 for r in sel if r.get("abstained_when_required")) /
                max(1, sum(1 for g in frozen["queries"]
                           if not g["answerable"] and g["query_id"] in
                           {x["query_id"] for x in sel})), 3),
            "answered_when_unsupported": sum(
                1 for r in sel if r.get("answered_when_unsupported")),
            "invalid_citations": sum(len(r.get("invalid_citations", [])) for r in sel),
            "invalid_graph_ids": sum(len(r.get("invalid_graph_ids", [])) for r in sel),
            "summary_only_citations": sum(
                len(r.get("summary_only_citations", [])) for r in sel),
            "topic_coverage": round(
                sum(r.get("required_topics_hit", 0) for r in sel) /
                max(1, sum(r.get("required_topics_total", 0) for r in sel)), 3),
            "forbidden_hits": sum(len(r.get("forbidden_hit", [])) for r in sel),
            "parse_errors": sum(1 for r in sel if r.get("parse_error")),
            "latency_p50_ms": round(sorted(r["latency_ms"] for r in sel)[len(sel) // 2], 1),
        }

    base = [r for r in rows if r["packet_variant"] == "base"]
    by_query_id = {g["query_id"]: g for g in frozen["queries"]}
    groups = {}
    for r in rows:
        gold = by_query_id[r["query_id"]]
        key = (gold["category"], r["packet_variant"])
        groups.setdefault(key, []).append(r)

    summary = {
        "candidate": args.candidate,
        "prompt_contract": "synthesis-prompt-v1",
        "prompt_hash": prompt_hash()[:16],
        "response_contract": "synthesis-response-v1",
        "base": agg(None, base),
        "by_category": {
            f"{cat}/{variant}": agg(None, sel)
            for (cat, variant), sel in sorted(groups.items())
        },
    }
    out_path = ROOT / "eval" / "r2a" / f"result_{args.candidate}.json"
    out_path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, default=str))
    print(json.dumps(summary, indent=1))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

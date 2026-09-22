#!/usr/bin/env python
"""GNN-RETRIEVAL-V1 — ONE frozen query set across the five modes + the causal controls, retrieval-level metrics (plan §20–§23).

    set -a; . ./.env; set +a
    .venv/bin/python scripts/gnn_route_qualify.py --corpus cinema --fixtures L,B \\
        --out docs/wiki/experiments/gnn-route/cinema/qualify-2026-09-22.json

Reuses the existing frozen fixtures (`eval/fixtures/chat_*.json`, `gold_chunk_ids`; gold PARENT ids are read from the live `chunks` table,
never guessed), the exact live functions (`chat_retrieve_mode` for FAST / HYBRID / GRAPH / WILDCARD / GNN; the SAME `_rerank_children`
judge for the fixed-budget arms) and the engine's own receipts (`funnel_union`, the reranked evidence order).

Per query, per mode: gold_in_union · gold_after_rerank (gold inside the judged evidence list) · Recall@K (K = the mode's evidence rows) ·
MRR (first gold in the reranked order) · selected_gold · candidate / unique counts · latency.  GNN additionally: GNN_UNIQUE_GOLD (gold the
GNN route found AND the HYBRID baseline union did not).  TEST A (recall ceiling): HYBRID union vs HYBRID ∪ GNN-route children (the additive
lane).  TEST B (fixed budget, K = 24): A = the HYBRID fusion prefix 24 · B = 18 HYBRID + 6 GNN-real · C = 18 + 6 no-graph · D = 18 + 6
shuffled — the SAME reranker and the SAME selected-evidence budget judge each arm.  Real must beat BOTH controls to claim topology (§21).
Read-only; nothing is written but the report. No LLM synthesis (retrieval only, as the plan demands).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("shared", "orchestrator"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

FIXTURES = {"L": ROOT / "eval/fixtures/chat_lexical_L.json", "B": ROOT / "eval/fixtures/chat_baseline_B.json", "M": ROOT / "eval/fixtures/chat_multi_M.json"}
MODES = ("FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN")
CONTROLS = ("nograph", "shuffled")
K_FIXED, K_GNN_SHARE = 24, 6


def _questions(path: Path, corpus_id: str):
    d = json.loads(path.read_text())
    items = d.get("questions") if isinstance(d, dict) else d
    return [q for q in (items or []) if q.get("corpus_id") == corpus_id]


def _gold(q: dict) -> set[str]:
    g = set(q.get("gold_chunk_ids") or [])
    if q.get("gold_chunk_id"):
        g.add(q["gold_chunk_id"])
    return g


def _gold_parents(chunk_ids: set[str]) -> dict[str, str]:
    import psycopg
    if not chunk_ids:
        return {}
    with psycopg.connect(os.environ["POLYMATH_PG_DSN"]) as conn, conn.cursor() as cur:
        cur.execute("SELECT chunk_id, parent_id FROM chunks WHERE chunk_id = ANY(%s)", (sorted(chunk_ids),))
        return {c: p for c, p in cur.fetchall()}


def _pct(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(round((len(xs) - 1) * p)))], 1) if xs else None


def _metrics(gold: set[str], union: list[str], evidence_order: list[str], selected: list[str]) -> dict:
    ranks = [i + 1 for i, c in enumerate(evidence_order) if c in gold]
    return {"gold_in_union": bool(gold & set(union)), "gold_after_rerank": bool(gold & set(evidence_order)), "recall_at_k": round(len(gold & set(evidence_order)) / max(1, len(gold)), 3),
            "mrr": round(1.0 / ranks[0], 3) if ranks else 0.0, "selected_gold": bool(gold & set(selected)), "candidates": len(union), "unique_candidates": len(set(union)), "k": len(evidence_order)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--fixtures", default="L,B")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--family", default="", help="GNN family (default gnn_route.DEFAULT_FAMILY); e.g. m1-smooth or m2-hsage")
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    os.environ.setdefault("POLYMATH_CHAT_RERANK_DEADLINE_S", "4")
    from orchestrator.api.chat_retrieval import chat_retrieve_mode, chat_retrieve_v2, default_budget
    from orchestrator.api.fast import _rerank_children
    from polymath_shared import gnn_route as gr

    family = a.family or gr.DEFAULT_FAMILY
    modes = [m.strip().upper() for m in a.modes.split(",") if m.strip()]
    report = {"contract": "gnn-route-qualify-v1", "corpus": a.corpus, "family": family, "fixtures": {}, "modes": modes, "k_fixed": K_FIXED, "k_gnn_share": K_GNN_SHARE, "rows": []}

    def run(mode: str, q: dict, **kw) -> tuple[dict, float]:
        t0 = time.perf_counter()
        res = chat_retrieve_mode(mode, q["question"], a.corpus, exact_terms=tuple(q.get("exact_terms") or ()), **kw)
        return res, (time.perf_counter() - t0) * 1000

    def views(res: dict) -> tuple[list[str], list[str], list[str]]:
        trace = res.get("trace") or {}
        union = [str(x) for x in (trace.get("funnel_union") or [])]
        order = [str(r.get("chunk_id")) for r in (res.get("evidence") or [])]
        return union, order, order[: int(default_budget().synthesis_max)]

    for key in [f.strip() for f in a.fixtures.split(",") if f.strip()]:
        qs = _questions(FIXTURES[key], a.corpus)
        if a.limit:
            qs = qs[: a.limit]
        gold_parent_map = _gold_parents({c for q in qs for c in _gold(q)})
        for qi, q in enumerate(qs):
            gold = _gold(q)
            row = {"fixture": key, "query_id": q.get("id") or f"{key}{qi:02d}", "query": q["question"][:160], "gold_chunk_ids": sorted(gold),
                   "gold_parent_ids": sorted({gold_parent_map.get(c) for c in gold if gold_parent_map.get(c)}), "modes": {}, "controls": {}, "test_a": {}, "test_b": {}}
            per: dict[str, dict] = {}
            for mode in modes:
                try:
                    kw = {"budget": replace(default_budget(), gnn_family=family)} if mode == "GNN" else {}
                    res, ms = run(mode, q, **kw)
                    union, order, selected = views(res)
                    m = {**_metrics(gold, union, order, selected), "latency_ms": round(ms, 1), "degraded": (res.get("meta") or {}).get("degraded") or []}
                    if mode == "GNN":
                        g = (res.get("meta") or {}).get("gnn") or {}
                        m["gnn"] = {k: g.get(k) for k in ("collection", "gnn_contract", "graph_snapshot_id", "model_digest", "parent_k", "hydrated_children", "unique_children", "elapsed_ms", "code")}
                        m["route_parents"] = [p["parent_id"] for p in (g.get("parents") or [])]
                        m["gold_parent_nominated"] = bool(set(m["route_parents"]) & set(row["gold_parent_ids"]))
                    per[mode] = {"union": union, "order": order, "selected": selected, "evidence": res.get("evidence") or [], "metrics": m}
                    row["modes"][mode] = m
                except Exception as exc:  # noqa: BLE001 — a failed mode is recorded as such, never as another mode's result
                    row["modes"][mode] = {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
            base = per.get("HYBRID")
            gnn = per.get("GNN")
            if base and gnn:
                base_gold, gnn_gold = gold & set(base["union"]), gold & set(gnn["union"])
                row["gnn_unique_gold"] = bool(gnn_gold and not base_gold)
                row["overlap_with_hybrid"] = round(len(set(gnn["union"]) & set(base["union"])) / max(1, len(set(gnn["union"]))), 3)
            # controls: the GNN route alone with the no-graph and shuffled collections
            for variant in CONTROLS:
                try:
                    res, ms = run("GNN", q, budget=replace(default_budget(), gnn_family=family, gnn_variant=variant))
                    union, order, selected = views(res)
                    per[f"GNN:{variant}"] = {"union": union, "order": order, "evidence": res.get("evidence") or []}
                    row["controls"][variant] = {**_metrics(gold, union, order, selected), "latency_ms": round(ms, 1), "degraded": (res.get("meta") or {}).get("degraded") or []}
                except Exception as exc:  # noqa: BLE001
                    row["controls"][variant] = {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
            # TEST A — recall ceiling: HYBRID ∪ the additive GNN lane (lane I unioned LAST on a HYBRID turn)
            if base:
                try:
                    res, ms = run("HYBRID", q, budget=replace(default_budget(), gnn_enabled=True, gnn_family=family))
                    union, order, selected = views(res)
                    row["test_a"] = {"baseline_gold_in_union": bool(gold & set(base["union"])), "plus_gnn_gold_in_union": bool(gold & set(union)),
                                     "baseline_union": len(base["union"]), "plus_gnn_union": len(union), "gnn_lane": len((res.get("trace") or {}).get("funnel_lanes", {}).get("gnn_route") or []),
                                     "gained_gold": bool((gold & set(union)) - (gold & set(base["union"]))), "latency_ms": round(ms, 1)}
                except Exception as exc:  # noqa: BLE001
                    row["test_a"] = {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
            # TEST B — fixed budget K = 24, the SAME judge, the SAME selected budget
            if base and gnn:
                by_id = {}
                for src in [base] + [per[k] for k in per if k.startswith("GNN")]:
                    for r in src["evidence"]:
                        by_id.setdefault(str(r.get("chunk_id")), r)
                sel_n = int(default_budget().synthesis_max)
                arms = {"A_hybrid_24": base["union"][:K_FIXED]}
                arms["B_hybrid18_gnn6"] = base["union"][: K_FIXED - K_GNN_SHARE] + [c for c in gnn["union"] if c not in base["union"][: K_FIXED - K_GNN_SHARE]][:K_GNN_SHARE]
                for variant, label in (("nograph", "C_hybrid18_nograph6"), ("shuffled", "D_hybrid18_shuffled6")):
                    ctl = per.get(f"GNN:{variant}")
                    if ctl:
                        arms[label] = base["union"][: K_FIXED - K_GNN_SHARE] + [c for c in ctl["union"] if c not in base["union"][: K_FIXED - K_GNN_SHARE]][:K_GNN_SHARE]
                for label, ids in arms.items():
                    rows = [dict(by_id[c]) for c in ids if c in by_id]
                    missing = len(ids) - len(rows)
                    try:
                        judged = _rerank_children(q["question"], rows)
                        order = [str(r.get("chunk_id")) for r in judged]
                        row["test_b"][label] = {**_metrics(gold, ids, order, order[:sel_n]), "unhydrated": missing}
                    except Exception as exc:  # noqa: BLE001
                        row["test_b"][label] = {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
            report["rows"].append(row)
            print(f"[{key}{qi:02d}] " + " ".join(f"{m}:{'G' if row['modes'].get(m, {}).get('gold_after_rerank') else ('u' if row['modes'].get(m, {}).get('gold_in_union') else '-')}" for m in modes)
                  + (f" unique={'Y' if row.get('gnn_unique_gold') else 'n'}" if "gnn_unique_gold" in row else ""), flush=True)

    # ── aggregates
    rows = report["rows"]
    n = max(1, len(rows))

    def agg(get):
        vals = [get(r) for r in rows]
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / max(1, len(vals)), 3) if vals else None

    summary = {"n": len(rows), "per_mode": {}, "controls": {}, "test_a": {}, "test_b": {}}
    for mode in modes:
        ms = [r["modes"][mode] for r in rows if mode in r["modes"] and "error" not in r["modes"][mode]]
        if ms:
            summary["per_mode"][mode] = {"n": len(ms), "gold_in_union": round(sum(m["gold_in_union"] for m in ms) / len(ms), 3), "gold_after_rerank": round(sum(m["gold_after_rerank"] for m in ms) / len(ms), 3),
                                         "recall_at_k": round(sum(m["recall_at_k"] for m in ms) / len(ms), 3), "mrr": round(sum(m["mrr"] for m in ms) / len(ms), 3),
                                         "selected_gold": round(sum(m["selected_gold"] for m in ms) / len(ms), 3), "candidates_mean": round(sum(m["candidates"] for m in ms) / len(ms), 1),
                                         "unique_candidates_mean": round(sum(m["unique_candidates"] for m in ms) / len(ms), 1),
                                         "latency_p50_ms": _pct([m["latency_ms"] for m in ms], 0.5), "latency_p95_ms": _pct([m["latency_ms"] for m in ms], 0.95),
                                         "errors": sum(1 for r in rows if "error" in r["modes"].get(mode, {}))}
    for variant in CONTROLS:
        cs = [r["controls"][variant] for r in rows if variant in r["controls"] and "error" not in r["controls"][variant]]
        if cs:
            summary["controls"][variant] = {"n": len(cs), "gold_in_union": round(sum(c["gold_in_union"] for c in cs) / len(cs), 3), "gold_after_rerank": round(sum(c["gold_after_rerank"] for c in cs) / len(cs), 3),
                                            "mrr": round(sum(c["mrr"] for c in cs) / len(cs), 3), "selected_gold": round(sum(c["selected_gold"] for c in cs) / len(cs), 3)}
    uq = [r for r in rows if "gnn_unique_gold" in r]
    summary["gnn_unique_gold_count"] = sum(1 for r in uq if r["gnn_unique_gold"])
    summary["gnn_unique_gold_rate"] = round(summary["gnn_unique_gold_count"] / max(1, len(uq)), 3)
    summary["gnn_overlap_with_hybrid_mean"] = agg(lambda r: r.get("overlap_with_hybrid"))
    summary["gnn_gold_parent_nominated_rate"] = agg(lambda r: (r["modes"].get("GNN") or {}).get("gold_parent_nominated"))
    ta = [r["test_a"] for r in rows if r.get("test_a") and "error" not in r["test_a"]]
    if ta:
        summary["test_a"] = {"n": len(ta), "baseline_gold_in_union": round(sum(t["baseline_gold_in_union"] for t in ta) / len(ta), 3), "plus_gnn_gold_in_union": round(sum(t["plus_gnn_gold_in_union"] for t in ta) / len(ta), 3),
                             "queries_gaining_gold": sum(1 for t in ta if t["gained_gold"]), "baseline_union_mean": round(sum(t["baseline_union"] for t in ta) / len(ta), 1), "plus_gnn_union_mean": round(sum(t["plus_gnn_union"] for t in ta) / len(ta), 1)}
    for label in ("A_hybrid_24", "B_hybrid18_gnn6", "C_hybrid18_nograph6", "D_hybrid18_shuffled6"):
        tb = [r["test_b"][label] for r in rows if label in r.get("test_b", {}) and "error" not in r["test_b"][label]]
        if tb:
            summary["test_b"][label] = {"n": len(tb), "gold_in_union": round(sum(t["gold_in_union"] for t in tb) / len(tb), 3), "gold_after_rerank": round(sum(t["gold_after_rerank"] for t in tb) / len(tb), 3),
                                        "mrr": round(sum(t["mrr"] for t in tb) / len(tb), 3), "selected_gold": round(sum(t["selected_gold"] for t in tb) / len(tb), 3)}
    real, ng, sh = (summary["per_mode"].get("GNN") or {}), summary["controls"].get("nograph") or {}, summary["controls"].get("shuffled") or {}
    if real and ng and sh:
        summary["causal"] = {"delta_real_minus_nograph_gold_after_rerank": round(real["gold_after_rerank"] - ng["gold_after_rerank"], 3),
                             "delta_real_minus_shuffled_gold_after_rerank": round(real["gold_after_rerank"] - sh["gold_after_rerank"], 3),
                             "delta_real_minus_nograph_mrr": round(real["mrr"] - ng["mrr"], 3), "delta_real_minus_shuffled_mrr": round(real["mrr"] - sh["mrr"], 3),
                             "topology_supported": bool(real["gold_after_rerank"] > ng["gold_after_rerank"] and real["gold_after_rerank"] > sh["gold_after_rerank"])}
    tb = summary["test_b"]
    if "B_hybrid18_gnn6" in tb and "A_hybrid_24" in tb:
        summary["fixed_budget_delta_gnn_minus_baseline_selected_gold"] = round(tb["B_hybrid18_gnn6"]["selected_gold"] - tb["A_hybrid_24"]["selected_gold"], 3)
    report["summary"] = summary
    print(json.dumps(summary, indent=1, sort_keys=True))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, indent=1, sort_keys=True, default=str), encoding="utf-8")
        print(f"[gnn-route-qualify] wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

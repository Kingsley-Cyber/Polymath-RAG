"""RETRIEVAL-PATHWAYS-5Q analysis ($0): reads results.json (written by run_5q.py) and reports, per turn, what the compiler
planned, what routed (scout / profile expansion / bridges), what each retrieval lane contributed at every funnel stage down
to the cited evidence, per-probe survival, latent seats and labels, and the WILDCARD sweep; then compares each HYBRID /
WILDCARD pair on the same question. Writes summary.json next to this file."""
from __future__ import annotations

import json
import pathlib
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
LANES = ("hierarchical", "global_dense_child", "global_sparse_child", "latent_rescue", "dualread", "resolution_lift",
         "seealso_fanout", "graph_dest", "gnn_route")


def _durations(pm: dict) -> dict:
    """phase_ms holds CUMULATIVE marks; turn them into per-phase durations."""
    order = [k for k in ("scope", "compile", "compile_joined", "retrieve", "assemble", "carry", "generate") if k in pm]
    out, prev = {}, 0.0
    for k in order:
        out[k] = round(pm[k] - prev, 1)
        prev = pm[k]
    out["total"] = pm.get("total")
    return out


def summarize(t: dict) -> dict:
    rec = t.get("receipt") or {}
    m = rec.get("meta") or {}
    cp = m.get("chat_plan") or {}
    comp = cp.get("compiler") or {}
    f = m.get("funnel") or {}
    stages = f.get("stages") or {}
    arrivals = f.get("arrivals") or {}
    sel, cited = set(stages.get("selected") or []), set(stages.get("cited") or [])
    lane_final = {ln: sum(1 for c in sel if ln in (arrivals.get(c) or [])) for ln in LANES}
    lane_cited = {ln: sum(1 for c in cited if ln in (arrivals.get(c) or [])) for ln in LANES}
    queries = cp.get("queries") or []
    retrieval = (t.get("stream") or {}).get("retrieval") or {}
    legend = retrieval.get("legend") or m.get("legend") or []
    cited_docs = sorted({e.get("doc_id") for e in legend if e.get("chunk_id") in cited and e.get("doc_id")})
    final_docs = sorted({e.get("doc_id") for e in legend if e.get("doc_id")})
    crumbs = [e.get("breadcrumb") for e in legend if e.get("chunk_id") in cited][:12]
    answer = (((t.get("stream") or {}).get("answer") or {}).get("result") or {}).get("answer") or ""
    wc_lane = retrieval.get("wildcard") or []
    return {
        "turn": t["turn"], "mode": t["mode"], "question": t["question"], "wall_s": t["wall_s"],
        "errors": (t.get("stream") or {}).get("errors"),
        "receipt": {"status": rec.get("status"), "verdict": rec.get("verdict"), "citations": rec.get("citations"),
                    "evidence": rec.get("evidence"), "source_docs": len(rec.get("source_docs") or [])},
        "phase_s": _durations(m.get("phase_ms") or {}),
        "compiler": {"lane": comp.get("lane"), "model": comp.get("model"), "attempt": comp.get("attempt"),
                     "fallback": comp.get("fallback"), "first_failure": comp.get("first_failure"),
                     "wall_ms": comp.get("wall_ms"), "compile_ms": comp.get("compile_ms"),
                     "reasoning_sent": (comp.get("reasoning") or {}).get("top_level"),
                     "task_type": cp.get("task_type"), "retrieval_required": cp.get("retrieval_required")},
        "plan": {"n": len(queries), "by_origin": dict(Counter(q.get("origin") or "USER" for q in queries)),
                 "queries": [(q.get("id"), q.get("origin"), q.get("type"), (q.get("query") or "")[:70],
                              q.get("derived_from")) for q in queries]},
        "routing": {"scout": comp.get("scout"), "profile_expansion": comp.get("profile_expansion"),
                    "bridge_expansion": comp.get("bridge_expansion"),
                    "corpus_explore": comp.get("corpus_explore_firing")},
        "funnel": {"counts": f.get("counts"), "lane_counts": f.get("lane_counts"), "multi_lane": f.get("multi_lane"),
                   "lane_in_final": lane_final, "lane_in_cited": lane_cited},
        "probes": {k: (m.get("retrieval_trace") or {}).get(k) for k in ("aspects", "aspect_final", "aspect_best",
                                                                         "weak_aspects", "weak_reasons", "timed_out")},
        "lane_ms": (m.get("trace_ms") or {}).get("lanes"), "stage_ms": (m.get("trace_ms") or {}).get("stages"),
        "latent_selection": m.get("latent_selection"), "prompt": m.get("prompt"),
        "wildcard": m.get("wildcard"), "wildcard_bridges": [
            {k: (b.get(k) if not isinstance(b.get(k), str) else b.get(k)[:160]) for k in
             ("bridge", "insight", "text", "query", "role", "doc_id", "source", "via") if b.get(k)}
            for b in wc_lane[:6] if isinstance(b, dict)],
        "generation": m.get("generation"), "degraded": m.get("degraded"),
        "final_docs": final_docs, "cited_docs": cited_docs, "cited_breadcrumbs": crumbs, "answer_head": answer[:900],
    }


def main() -> int:
    turns = json.loads((HERE / "results.json").read_text())
    rows = [summarize(t) for t in turns]
    pairs = []
    by_q: dict = {}
    for r in rows:
        by_q.setdefault(r["question"], {})[r["mode"]] = r
    for q, modes in by_q.items():
        if "HYBRID" in modes and "WILDCARD" in modes:
            h, w = set(modes["HYBRID"]["cited_docs"]), set(modes["WILDCARD"]["cited_docs"])
            hf, wf = set(modes["HYBRID"]["final_docs"]), set(modes["WILDCARD"]["final_docs"])
            pairs.append({"question": q, "cited_overlap": sorted(h & w), "wildcard_only_cited": sorted(w - h),
                          "hybrid_only_cited": sorted(h - w), "final_jaccard": round(len(hf & wf) / max(1, len(hf | wf)), 3)})
    (HERE / "summary.json").write_text(json.dumps({"turns": rows, "pairs": pairs}, indent=1, default=str))
    for r in rows:
        print(f"\n=== turn {r['turn']} {r['mode']} ({r['wall_s']}s) — {r['question']}")
        print("  receipt:", r["receipt"], "| phases(s):", r["phase_s"])
        print("  compiler:", {k: r["compiler"][k] for k in ("lane", "attempt", "fallback", "wall_ms", "reasoning_sent")})
        print("  compile_ms:", r["compiler"]["compile_ms"])
        print("  plan:", r["plan"]["by_origin"])
        for q in r["plan"]["queries"]:
            print("     ", q)
        rt = r["routing"]
        print("  scout:", {k: (rt["scout"] or {}).get(k) for k in ("n_injected", "nominations", "ms")},
              "| profile_exp:", rt["profile_expansion"],
              "| bridges:", {k: (rt["bridge_expansion"] or {}).get(k) for k in ("attempted", "generated", "admitted", "latency_ms", "route")})
        print("  funnel counts:", r["funnel"]["counts"])
        print("  lane_counts:", r["funnel"]["lane_counts"])
        print("  lane→final:", {k: v for k, v in r["funnel"]["lane_in_final"].items() if v},
              "| lane→cited:", {k: v for k, v in r["funnel"]["lane_in_cited"].items() if v})
        print("  probes final:", r["probes"]["aspect_final"], "| weak:", r["probes"]["weak_aspects"], r["probes"]["weak_reasons"])
        print("  lane_ms:", r["lane_ms"])
        print("  latent:", r["latent_selection"], "| prompt:", r["prompt"])
        if r["wildcard"]:
            print("  wildcard:", r["wildcard"])
            for b in r["wildcard_bridges"]:
                print("     bridge:", b)
        print("  generation:", r["generation"], "| degraded:", r["degraded"])
        print("  cited:", r["cited_breadcrumbs"])
    print("\n=== HYBRID vs WILDCARD pairs")
    for p in pairs:
        print(json.dumps(p, default=str)[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""SEEALSO-BLEND-V1 replay ($0 — no LLM call; register 11.475). The five stored questions of RETRIEVAL-PATHWAYS-5Q, replayed
through the candidate engine against the live stores + local embedder / reranker, three ways:
  base    — the deployed chat config before any SEE ALSO change (skeleton routes, the judge in WILDCARD, the probe gate)
  blend50 — base + POLYMATH_CHAT_SEEALSO_BLEND=1 (the question's documents' see-also lines, blended 50/50 with the question)
  blend70 — the same with the question weighted 0.7 (POLYMATH_CHAT_SEEALSO_BLEND_ALPHA=0.7)
Each question runs in its own stored mode and in GRAPH. Run from the branch worktree with its PYTHONPATH and the main .env
loaded. Writes replay.json next to this file."""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = HERE.parent / "retrieval-pathways-2026-09-23" / "results.json"
_spec = importlib.util.spec_from_file_location("skeleton_replay", HERE.parent / "skeleton-routing-2026-09-23" / "replay.py")
SK = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SK)
CONFIGS = {"base": ("0", ""), "blend50": ("1", "0.5"), "blend70": ("1", "0.7")}


def _once(mode: str, question: str, cp: dict, cfg: str) -> dict:
    flag, alpha = CONFIGS[cfg]
    os.environ.update({"POLYMATH_CHAT_SKELETON_ROUTES": "1", "POLYMATH_CHAT_CONTEXTUAL_JUDGE": "wildcard",
                       "POLYMATH_CHAT_SKELETON_PROBES": "0", "POLYMATH_CHAT_PROBE_GATE": "1",
                       "POLYMATH_CHAT_SEEALSO_BLEND": flag})
    os.environ.pop("POLYMATH_CHAT_SEEALSO_HOP", None)
    if alpha:
        os.environ["POLYMATH_CHAT_SEEALSO_BLEND_ALPHA"] = alpha
    else:
        os.environ.pop("POLYMATH_CHAT_SEEALSO_BLEND_ALPHA", None)
    from orchestrator.api import chat_retrieval as _cr
    from orchestrator.api.chat_retrieval import chat_retrieve_mode, default_budget, intent_policy_enabled
    from polymath_shared.probe_gate import gate_probes
    from polymath_shared.query_intent import apply_intent_policy, policy_for
    from polymath_shared.skeleton_routes import apply_skeleton_routes
    plan = SK._plan(cp)
    ip = bool(intent_policy_enabled() and plan.intent)
    budget = apply_intent_policy(plan.intent, default_budget()) if ip else default_budget()
    budget = apply_skeleton_routes(budget, mode=mode, plan=plan)
    gated_out = set()
    if getattr(budget, "probe_gate_floor", 0.0) > 0:
        gated_out, _ = gate_probes((cp.get("resolved_request") or question).strip(),
                                   [(q.id, q.origin, q.query) for q in plan.queries if q.type != "PRIMARY"],
                                   _cr._rerank_children, floor=budget.probe_gate_floor)
    t0 = time.perf_counter()
    out = chat_retrieve_mode(
        "HYBRID" if mode == "WILDCARD" else mode, cp.get("retrieval_query") or question, "cinema",
        graph_useful=True if mode == "GRAPH" else bool(plan.graph_useful),
        graph_assist=(policy_for(plan.intent).graph if ip else "off"), keep_latent=False, budget=budget,
        exact_terms=plan.exact_terms,
        subqueries=tuple((q.id, q.type, q.query, q.weight, q.origin, q.derived_from) for q in plan.queries
                         if q.type != "PRIMARY" and q.id not in gated_out),
        latent_bridge_ids=tuple(q.id for q in plan.queries if q.origin in ("BRIDGE", "CORPUS_EXPLORE") and q.id not in gated_out))
    wall = round((time.perf_counter() - t0) * 1000, 1)
    ev = out.get("evidence") or []
    fan = (out.get("trace") or {}).get("seealso_fanout") or {}
    return {"wall_ms": wall, "alpha": budget.seealso_blend_alpha, "blend_on": bool(budget.seealso_blend_enabled),
            "final_chunks": [r.get("chunk_id") for r in ev],
            "direct_final": sum(1 for r in ev if "q0" in (r.get("query_ids") or [])),
            "lane_g_final": [r.get("chunk_id") for r in ev if "SEEALSO_FANOUT" in (r.get("arrivals") or [])],
            "lane_g_only_final": [r.get("chunk_id") for r in ev if (r.get("arrivals") or []) == ["SEEALSO_FANOUT"]],
            "rows": {r.get("chunk_id"): {"source": r.get("source_name"), "arrivals": r.get("arrivals"),
                                         "text": (r.get("text") or "")[:220]} for r in ev},
            "fanout": {k: fan.get(k) for k in ("enabled", "candidates", "blends", "blend_candidates", "lane_ms", "degraded")}}


def main() -> int:
    turns = json.loads(RESULTS.read_text())
    runs, seen = [], set()
    for t in turns:
        cp = ((t.get("receipt") or {}).get("meta") or {}).get("chat_plan") or {}
        for mode in dict.fromkeys((t["mode"], "GRAPH")):
            if (t["question"], mode) not in seen:
                seen.add((t["question"], mode))
                runs.append((t["turn"], mode, t["question"], cp))
    out = []
    for turn, mode, q, cp in runs:
        rec = {"turn": turn, "mode": mode, "question": q}
        for cfg in CONFIGS:
            try:
                rec[cfg] = _once(mode, q, cp, cfg)
            except Exception as exc:  # noqa: BLE001 — a failed replay is a finding
                rec[cfg] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        base = rec["base"]
        for cfg in ("blend50", "blend70"):
            b = rec[cfg]
            if "error" in base or "error" in b:
                continue
            rec[f"delta_{cfg}"] = {"new": [c for c in b["final_chunks"] if c not in base["final_chunks"]],
                                   "displaced": [c for c in base["final_chunks"] if c not in b["final_chunks"]],
                                   "direct": (base["direct_final"], b["direct_final"]),
                                   "g_only_new": [c for c in b["lane_g_only_final"] if c not in base["final_chunks"]],
                                   "wall_delta_ms": round(b["wall_ms"] - base["wall_ms"], 1)}
        out.append(rec)
        line = [f"turn {turn} {mode:8s}"]
        for cfg in ("blend50", "blend70"):
            d = rec.get(f"delta_{cfg}") or {}
            line.append(f"{cfg}: new={len(d.get('new') or [])} out={len(d.get('displaced') or [])} "
                        f"g_only_new={len(d.get('g_only_new') or [])} direct={d.get('direct')} "
                        f"blends={len((rec[cfg].get('fanout') or {}).get('blends') or [])} wallΔ={d.get('wall_delta_ms')}")
        print(" | ".join(line), f"err={base.get('error')}", flush=True)
    (HERE / "replay.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

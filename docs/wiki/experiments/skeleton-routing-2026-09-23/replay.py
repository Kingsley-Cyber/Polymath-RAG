"""SKELETON-ROUTING-V1 replay ($0 — no LLM call): re-run today's five stored plans (RETRIEVAL-PATHWAYS-5Q) through the
candidate engine against the live stores + local embedder / reranker, three ways:
  off   — today's behaviour (flags off)
  paths — POLYMATH_CHAT_SKELETON_ROUTES=1 (doors by plan + mode, path ids, route seats)
  judge — paths + POLYMATH_CHAT_CONTEXTUAL_JUDGE=1 (path-aware cross-encoder, no LLM)
  deployed — the live V1 config: paths + the judge in WILDCARD only (POLYMATH_CHAT_CONTEXTUAL_JUDGE=wildcard)
  probes   — deployed + POLYMATH_CHAT_SKELETON_PROBES=1 (V1.1: each planned probe drives the skeleton door)
WILDCARD turns replay the CORE retrieval with WILDCARD's door budget (the sweep's LLM finish is not called).
Writes replay.json next to this file (REPLAY_OUT renames it; REPLAY_RESULTS picks the stored turns, REPLAY_CONFIGS the
configs). Run from the branch worktree with its PYTHONPATH and the main .env loaded."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
from types import SimpleNamespace

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = pathlib.Path(os.environ.get("REPLAY_RESULTS") or (HERE.parent / "retrieval-pathways-2026-09-23" / "results.json"))
SKELETON = ("LATENT_RESCUE", "SHADOW_DUALREAD", "SEEALSO_FANOUT", "GRAPH_DEST")


def _plan(cp: dict):
    qs = [SimpleNamespace(id=q.get("id"), type=q.get("type"), query=q.get("query"), weight=q.get("weight") or 1.0,
                          origin=q.get("origin") or "USER", derived_from=q.get("derived_from") or "")
          for q in (cp.get("queries") or [])]
    return SimpleNamespace(queries=qs, intent=cp.get("intent"), exact_terms=tuple(cp.get("exact_terms") or ()),
                           graph_useful=cp.get("graph_useful"))


def _run(mode: str, question: str, cp: dict, config: str) -> dict:
    os.environ["POLYMATH_CHAT_SKELETON_ROUTES"] = "1" if config in ("paths", "judge", "deployed", "probes") else "0"
    os.environ["POLYMATH_CHAT_CONTEXTUAL_JUDGE"] = {"judge": "1", "deployed": "wildcard", "probes": "wildcard"}.get(config, "0")
    os.environ["POLYMATH_CHAT_SKELETON_PROBES"] = "1" if config == "probes" else "0"
    from orchestrator.api.chat_retrieval import (
        chat_retrieve_mode,
        default_budget,
        intent_policy_enabled,
    )
    from polymath_shared.query_intent import apply_intent_policy, policy_for
    from polymath_shared.skeleton_routes import apply_skeleton_routes
    plan = _plan(cp)
    ip = bool(intent_policy_enabled() and plan.intent)
    budget = apply_intent_policy(plan.intent, default_budget()) if ip else default_budget()
    budget = apply_skeleton_routes(budget, mode=mode, plan=plan)
    graph_useful = bool(plan.graph_useful) if plan.graph_useful is not None else True
    if config != "off" and mode == "GRAPH":
        graph_useful = True
    core_mode = "HYBRID" if mode == "WILDCARD" else mode           # the sweep's LLM finish stays out of a $0 replay
    t0 = time.perf_counter()
    fast = chat_retrieve_mode(
        core_mode, cp.get("retrieval_query") or question, "cinema", graph_useful=graph_useful,
        graph_assist=(policy_for(plan.intent).graph if ip else "off"), keep_latent=False, budget=budget,
        exact_terms=plan.exact_terms,
        subqueries=tuple((q.id, q.type, q.query, q.weight, q.origin, q.derived_from) for q in plan.queries if q.type != "PRIMARY"),
        latent_bridge_ids=tuple(q.id for q in plan.queries if q.origin in ("BRIDGE", "CORPUS_EXPLORE")))
    wall = round((time.perf_counter() - t0) * 1000, 1)
    ev = fast.get("evidence") or []
    tr = fast.get("trace") or {}
    lanes_final = {}
    for r in ev:
        for a in (r.get("arrivals") or []):
            lanes_final[a] = lanes_final.get(a, 0) + 1
    indirect_ids = {q.id for q in plan.queries if q.origin in ("PROFILE", "BRIDGE", "CORPUS_EXPLORE")}
    probe_ids = {q.id for q in plan.queries if q.type != "PRIMARY"}
    return {"mode": mode, "config": config, "wall_ms": wall, "final": len(ev),
            "final_chunks": [r.get("chunk_id") for r in ev], "final_docs": sorted({r.get("doc_id") for r in ev}),
            "lanes_final": lanes_final,
            "skeleton_final": sum(1 for r in ev if set(r.get("arrivals") or []) & set(SKELETON)),
            "skeleton_only_final": sum(1 for r in ev if (r.get("arrivals") or []) and set(r.get("arrivals")) <= set(SKELETON)),
            "indirect_final": sum(1 for r in ev if set(r.get("query_ids") or []) & indirect_ids),
            "direct_final": sum(1 for r in ev if "q0" in (r.get("query_ids") or [])),
            "route_aspects": {k: v.get("lanes") for k, v in (tr.get("aspects") or {}).items() if str(k).startswith("rt:")},
            "aspect_prefix": tr.get("aspect_prefix"), "contextual": tr.get("contextual"),
            "probe_routes": tr.get("probe_routes"),
            "probe_route_final": sum(1 for r in ev if "rt:probe" in (r.get("query_ids") or [])),
            "aspect_final": {k: v for k, v in (tr.get("aspect_final") or {}).items() if k in probe_ids or str(k).startswith("rt:")},
            "final_rows": [{"chunk_id": r.get("chunk_id"), "doc_id": r.get("doc_id"), "source_name": r.get("source_name"),
                            "query_ids": r.get("query_ids"), "arrivals": r.get("arrivals"), "g3": r.get("g3_score"),
                            "text": (r.get("text") or "")[:160]} for r in ev],
            "lane_sizes": {k: tr.get("lane_sizes", {}).get(k) for k in ("latent_rescue", "dualread", "seealso_fanout", "graph_dest",
                                                                         "probe_routes")},
            "timings_ms": tr.get("timings_ms"), "rerank_prefix": tr.get("rerank_prefix"),
            "degraded": [d.get("component") for d in (fast.get("meta") or {}).get("degraded") or []]}


def main() -> int:
    turns = json.loads(RESULTS.read_text())
    out = []
    for t in turns:
        cp = ((t.get("receipt") or {}).get("meta") or {}).get("chat_plan") or {}
        for config in (os.environ.get("REPLAY_CONFIGS") or "off,paths,judge").split(","):
            try:
                r = _run(t["mode"], t["question"], cp, config)
            except Exception as exc:  # noqa: BLE001 — a failed replay is a finding
                r = {"mode": t["mode"], "config": config, "error": f"{type(exc).__name__}: {exc}"[:300]}
            r["turn"] = t["turn"]
            out.append(r)
            print(f"turn {t['turn']} {t['mode']:8s} {config:5s} wall={r.get('wall_ms')}ms final={r.get('final')} "
                  f"skeleton={r.get('skeleton_final')} skel_only={r.get('skeleton_only_final')} indirect={r.get('indirect_final')} "
                  f"direct={r.get('direct_final')} probe_final={r.get('probe_route_final')} "
                  f"docs={len(r.get('final_docs') or [])} ctx={r.get('contextual')} err={r.get('error')}", flush=True)
    (HERE / (os.environ.get("REPLAY_OUT") or "replay.json")).write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""SEEALSO-HOP-V1 replay ($0 — no LLM call; register 11.472). The five stored questions of RETRIEVAL-PATHWAYS-5Q, replayed
through the candidate engine against the live stores + local embedder / reranker, two ways:
  live — today's deployed chat config (skeleton routes, the judge in WILDCARD only, the probe gate)
  hop  — live + POLYMATH_CHAT_SEEALSO_HOP=1 (the one-hop SEE ALSO door inside lane G, GRAPH / WILDCARD)
Every question runs in GRAPH; the two WILDCARD questions also run in WILDCARD (core retrieval with WILDCARD's door budget).
Run from the branch worktree with its PYTHONPATH and the main .env loaded. Writes replay.json next to this file."""
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


def _once(mode: str, question: str, cp: dict, hop: bool) -> dict:
    os.environ["POLYMATH_CHAT_SKELETON_ROUTES"] = "1"
    os.environ["POLYMATH_CHAT_CONTEXTUAL_JUDGE"] = "wildcard"
    os.environ["POLYMATH_CHAT_SKELETON_PROBES"] = "0"
    os.environ["POLYMATH_CHAT_PROBE_GATE"] = "1"
    os.environ["POLYMATH_CHAT_SEEALSO_HOP"] = "1" if hop else "0"
    from orchestrator.api.chat_retrieval import chat_retrieve_mode, default_budget, intent_policy_enabled
    from polymath_shared.probe_gate import gate_probes
    from polymath_shared.query_intent import apply_intent_policy, policy_for
    from polymath_shared.skeleton_routes import apply_skeleton_routes
    from orchestrator.api import chat_retrieval as _cr
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
        "HYBRID" if mode == "WILDCARD" else mode, cp.get("retrieval_query") or question, "cinema", graph_useful=True,
        graph_assist=(policy_for(plan.intent).graph if ip else "off"), keep_latent=False, budget=budget,
        exact_terms=plan.exact_terms,
        subqueries=tuple((q.id, q.type, q.query, q.weight, q.origin, q.derived_from) for q in plan.queries
                         if q.type != "PRIMARY" and q.id not in gated_out),
        latent_bridge_ids=tuple(q.id for q in plan.queries if q.origin in ("BRIDGE", "CORPUS_EXPLORE") and q.id not in gated_out))
    wall = round((time.perf_counter() - t0) * 1000, 1)
    ev = out.get("evidence") or []
    fan = (out.get("trace") or {}).get("seealso_fanout") or {}
    return {"wall_ms": wall, "hop_on": bool(budget.seealso_hop_enabled),
            "final_chunks": [r.get("chunk_id") for r in ev],
            "final_docs": sorted({r.get("doc_id") for r in ev}),
            "direct_final": sum(1 for r in ev if "q0" in (r.get("query_ids") or [])),
            "lane_g_final": [r.get("chunk_id") for r in ev if "SEEALSO_FANOUT" in (r.get("arrivals") or [])],
            "rows": {r.get("chunk_id"): {"doc": r.get("doc_id"), "source": r.get("source_name"),
                                         "arrivals": r.get("arrivals"), "text": (r.get("text") or "")[:220]} for r in ev},
            "fanout": {k: fan.get(k) for k in ("enabled", "candidates", "hops", "hop_candidates", "lane_ms", "degraded")}}


def main() -> int:
    turns = json.loads(RESULTS.read_text())
    runs, seen = [], set()
    for t in turns:
        cp = ((t.get("receipt") or {}).get("meta") or {}).get("chat_plan") or {}
        for mode in ("GRAPH",) + (("WILDCARD",) if t["mode"] == "WILDCARD" else ()):
            key = (t["question"], mode)
            if key in seen:
                continue
            seen.add(key)
            runs.append((t["turn"], mode, t["question"], cp))
    out = []
    for turn, mode, q, cp in runs:
        rec = {"turn": turn, "mode": mode, "question": q}
        for cfg, hop in (("live", False), ("hop", True)):
            try:
                rec[cfg] = _once(mode, q, cp, hop)
            except Exception as exc:  # noqa: BLE001 — a failed replay is a finding
                rec[cfg] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        a, b = rec["live"], rec["hop"]
        if "error" not in a and "error" not in b:
            new = [c for c in b["final_chunks"] if c not in a["final_chunks"]]
            gone = [c for c in a["final_chunks"] if c not in b["final_chunks"]]
            rec["delta"] = {"new_in_final": new, "displaced": gone,
                            "new_docs": [d for d in b["final_docs"] if d not in a["final_docs"]],
                            "direct_live": a["direct_final"], "direct_hop": b["direct_final"],
                            "wall_delta_ms": round(b["wall_ms"] - a["wall_ms"], 1),
                            "hops": (b["fanout"] or {}).get("hops"), "hop_candidates": (b["fanout"] or {}).get("hop_candidates")}
        out.append(rec)
        d = rec.get("delta") or {}
        print(f"turn {turn} {mode:8s} final {len((a or {}).get('final_chunks') or [])}->{len((b or {}).get('final_chunks') or [])} "
              f"new={len(d.get('new_in_final') or [])} displaced={len(d.get('displaced') or [])} "
              f"direct {d.get('direct_live')}->{d.get('direct_hop')} hop_cands={d.get('hop_candidates')} "
              f"hops={len(d.get('hops') or [])} wall_delta={d.get('wall_delta_ms')}ms "
              f"err={a.get('error') or b.get('error')}", flush=True)
    (HERE / "replay.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

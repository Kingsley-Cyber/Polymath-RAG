"""Replay the owner's three 2026-09-22 chat plans (frozen in query_receipts) through the in-process retrieval
engine of whichever tree is on PYTHONPATH — retrieval + reranker + the WLK2C bridge pass only, NO LLM call.

usage: PYTHONPATH=<tree>/shared:<tree>/orchestrator:<tree>/workers python replay_owner_plans.py <label> <configs> <out.jsonl>
configs: comma list of MODE:cap   e.g. FAST:0,HYBRID:3,HYBRID:10   (cap 0 = the tree's default budget)
"""
import json
import os
import sys
import time
import types
from dataclasses import replace

import psycopg

from orchestrator.api import chat_retrieval as cr
from orchestrator.api import ui
from polymath_shared.query_intent import apply_intent_policy, policy_for

LABEL, CONFIGS, OUT = sys.argv[1], sys.argv[2].split(","), sys.argv[3]
QIDS = ["q_be4b06b788b540b9acb5a4d0", "q_7eab052201dd4d31bdf29ad1", "q_bdd1abd51e414e3e926fde17"]

conn = psycopg.connect(os.environ["POLYMATH_PG_DSN"])
plans = {}
with conn.cursor() as c:
    for qid in QIDS:
        c.execute("select meta->'chat_plan' from query_receipts where query_id=%s", (qid,))
        plans[qid] = c.fetchone()[0]
conn.close()


def plan_obj(cp):
    qs = [types.SimpleNamespace(**{**q, "origin": q.get("origin", "")}) for q in cp["queries"]]
    return types.SimpleNamespace(intent=cp.get("intent"), queries=qs, exact_terms=cp.get("exact_terms") or [],
                                 must_answer=cp.get("must_answer") or [], graph_useful=bool(cp.get("graph_useful")),
                                 task_type=cp.get("task_type"), response_type=cp.get("response_type"),
                                 resolved_request=cp.get("resolved_request"), retrieval_query=cp.get("retrieval_query"),
                                 evidence_policy=cp.get("evidence_policy"), antecedent=None)


with open(OUT, "a") as fh:
    for qid in QIDS:
        cp = plans[qid]
        plan = plan_obj(cp)
        for cfg in CONFIGS:
            mode, cap = cfg.split(":")
            cap = int(cap)
            budget = apply_intent_policy(cp["intent"], cr.default_budget())
            if cap:
                budget = replace(budget, max_subqueries=cap)
            pol = policy_for(cp["intent"])
            subs = tuple((q["id"], q["type"], q["query"], q["weight"], q.get("origin", "")) for q in cp["queries"] if q["type"] != "PRIMARY")
            bridge_ids = tuple(q["id"] for q in cp["queries"] if q.get("origin", "") in ui.LATENT_ORIGINS)
            q0 = cp["retrieval_query"]
            t0 = time.perf_counter()
            out = cr.chat_retrieve_mode("VECTOR" if mode == "FAST" else mode, q0, "cinema",
                                        graph_useful=bool(cp.get("graph_useful")), graph_assist=pol.graph if pol else "off",
                                        budget=budget, exact_terms=tuple(cp.get("exact_terms") or ()),
                                        subqueries=subs, latent_bridge_ids=bridge_ids)
            wall = round((time.perf_counter() - t0) * 1000)
            pool = out.get("latent_pool") or []
            t1 = time.perf_counter()
            rec = ui._apply_latent_selection(out, plan, q0)
            sel_ms = round((time.perf_counter() - t1) * 1000)
            meta, trace = out.get("meta") or {}, out.get("trace") or {}
            ev = out.get("evidence") or []
            searched = sorted({q for e in ev for q in (e.get("query_ids") or [])})
            aspects = meta.get("aspects") or trace.get("aspects") or {}
            lat = trace.get("latency_ms") or meta.get("latency_ms") or {}
            row = {
                "tree": LABEL, "plan": qid[:12], "mode": mode, "cap": cap or budget.max_subqueries, "wall_ms": wall,
                "retrieval_total_ms": lat.get("total") if isinstance(lat, dict) else lat, "rerank_ms": (lat or {}).get("rerank") if isinstance(lat, dict) else None,
                "lane_sizes": {k: v for k, v in (meta.get("lane_sizes") or {}).items() if v},
                "aspects": sorted(aspects.keys()) if isinstance(aspects, dict) else aspects,
                "degraded": [d.get("component") if isinstance(d, dict) else d for d in (meta.get("degraded") or [])],
                "pool": len(pool), "pool_bridge": sum(1 for p in pool if set(p.get("query_ids") or []) & set(bridge_ids)),
                "bridge_pass": (None if rec is None else {k: rec.get(k) for k in ("admitted", "n_admitted", "latent_admitted", "graded", "n_graded", "roles", "admitted_ids") if k in rec}),
                "bridge_pass_keys": None if rec is None else sorted(rec.keys())[:20], "bridge_pass_ms": sel_ms,
                "final_n": len(ev), "final_from_subquery": sum(1 for e in ev if any(q != "q0" for q in (e.get("query_ids") or []))),
                "final_from_bridge": sum(1 for e in ev if set(e.get("query_ids") or []) & set(bridge_ids)),
                "final_q0_only": sum(1 for e in ev if set(e.get("query_ids") or []) <= {"q0"}),
                "final_query_ids": searched,
            }
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(json.dumps({k: row[k] for k in ("tree", "plan", "mode", "cap", "wall_ms", "retrieval_total_ms", "pool", "pool_bridge", "final_n", "final_from_bridge", "degraded")}), flush=True)

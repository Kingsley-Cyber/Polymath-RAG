"""K1 replay ($0 — no model call; register 11.485): the knowledge-role scope on the real retrieval pipeline.

For the three stored RETRIEVAL-PATHWAYS-5Q questions, each in FAST / HYBRID / GRAPH / WILDCARD, the chat retrieval runs
twice in-process against the live stores + local embedder / reranker: without a scope, and with the reference-only scope
Trail sends. A recorder wraps the Qdrant client class and keeps the filter of EVERY search / count that reaches Qdrant;
the profile scout and Corpus Explore (the compiler's context) are run the same way. It checks:
  1. under the reference-only scope, every content search carries `must_not knowledge_role == implementation`;
  2. without a scope, no search carries it (today's behaviour);
  3. the evidence is identical (no implementation material exists yet, so the scope must change nothing today);
  4. the time the clause costs.
Run from the K1 worktree with its PYTHONPATH and the main .env loaded. Writes replay.json next to this file."""
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
MODES = ("FAST", "HYBRID", "GRAPH", "WILDCARD")
CALLS: list[dict] = []


def _record(kind: str, flt) -> None:
    from polymath_shared.code.scope import REFERENCE_ONLY
    role = REFERENCE_ONLY.qdrant_must_not()[0]
    CALLS.append({"kind": kind, "filtered": flt is not None,
                  "role_clause": bool(flt is not None and role in list(getattr(flt, "must_not", None) or []))})


def _install_recorder() -> None:
    from qdrant_client import QdrantClient
    q0, s0, c0 = QdrantClient.query_points, QdrantClient.search, QdrantClient.count

    def query_points(self, *a, **kw):
        pre = kw.get("prefetch")
        if pre:
            for p in (pre if isinstance(pre, list) else [pre]):
                _record("query_points.prefetch", getattr(p, "filter", None))
        else:
            _record("query_points", kw.get("query_filter"))
        return q0(self, *a, **kw)

    def search(self, *a, **kw):
        _record("search", kw.get("query_filter"))
        return s0(self, *a, **kw)

    def count(self, *a, **kw):
        _record("count", kw.get("count_filter"))
        return c0(self, *a, **kw)

    QdrantClient.query_points, QdrantClient.search, QdrantClient.count = query_points, search, count


def _once(q: dict, mode: str, scope) -> dict:
    from orchestrator.api import chat_retrieval as _cr
    from orchestrator.api.chat_retrieval import chat_retrieve_mode, default_budget, intent_policy_enabled
    from polymath_shared.code.scope import scope_kwargs
    from polymath_shared.probe_gate import gate_probes
    from polymath_shared.query_intent import apply_intent_policy, policy_for
    from polymath_shared.skeleton_routes import apply_skeleton_routes
    cp, question = q["cp"], q["question"]
    plan = SK._plan(cp)
    ip = bool(intent_policy_enabled() and plan.intent)
    budget = apply_intent_policy(plan.intent, default_budget()) if ip else default_budget()
    budget = apply_skeleton_routes(budget, mode=mode, plan=plan)
    gated_out = set()
    if getattr(budget, "probe_gate_floor", 0.0) > 0:
        gated_out, _ = gate_probes((cp.get("resolved_request") or question).strip(),
                                   [(p.id, p.origin, p.query) for p in plan.queries if p.type != "PRIMARY"],
                                   _cr._rerank_children, floor=budget.probe_gate_floor)
    CALLS.clear()
    t0 = time.perf_counter()
    out = chat_retrieve_mode(
        mode, cp.get("retrieval_query") or question, "cinema",
        graph_useful=True if mode == "GRAPH" else bool(plan.graph_useful),
        graph_assist=(policy_for(plan.intent).graph if ip else "off"), keep_latent=False, budget=budget,
        exact_terms=plan.exact_terms,
        subqueries=tuple((p.id, p.type, p.query, p.weight, p.origin, p.derived_from) for p in plan.queries
                         if p.type != "PRIMARY" and p.id not in gated_out),
        latent_bridge_ids=tuple(p.id for p in plan.queries if p.origin in ("BRIDGE", "CORPUS_EXPLORE") and p.id not in gated_out),
        **scope_kwargs(scope))
    wall = round((time.perf_counter() - t0) * 1000, 1)
    calls = list(CALLS)
    return {"wall_ms": wall, "evidence": [r.get("chunk_id") for r in (out.get("evidence") or [])],
            "graph_facts": [f.get("fact_id") for f in (out.get("graph_relationships") or [])],
            "searches": len(calls), "with_role_clause": sum(1 for c in calls if c["role_clause"]),
            "unfiltered": [c["kind"] for c in calls if not c["filtered"]],
            "without_role_clause": sorted({c["kind"] for c in calls if c["filtered"] and not c["role_clause"]})}


def _scout(question: str, scope) -> dict:
    from orchestrator.api import ui
    from polymath_shared.code.scope import scope_kwargs
    CALLS.clear()
    ui._profile_scout(question, ["cinema"], **scope_kwargs(scope))
    calls = list(CALLS)
    return {"searches": len(calls), "with_role_clause": sum(1 for c in calls if c["role_clause"])}


def main() -> int:
    from polymath_shared.code.scope import REFERENCE_ONLY
    os.environ.update({"POLYMATH_CHAT_SKELETON_ROUTES": "1", "POLYMATH_CHAT_CONTEXTUAL_JUDGE": "wildcard",
                       "POLYMATH_CHAT_SKELETON_PROBES": "0", "POLYMATH_CHAT_PROBE_GATE": "1", "POLYMATH_CHAT_SEEALSO_BLEND": "1",
                       "POLYMATH_CHAT_DOC_STEER": "1", "POLYMATH_GRAPH_FACT_RANK": "1", "POLYMATH_PROFILE_SCOUT": "1"})
    _install_recorder()
    seen, qs = set(), []
    for t in json.loads(RESULTS.read_text()):
        if t["question"] not in seen:
            seen.add(t["question"])
            qs.append({"question": t["question"], "cp": ((t.get("receipt") or {}).get("meta") or {}).get("chat_plan") or {}})
    out = []
    for q in qs:
        for mode in MODES:
            _once(q, mode, None)                                      # warm-up
            rec = {"question": q["question"], "mode": mode, "none": _once(q, mode, None), "reference": _once(q, mode, REFERENCE_ONLY)}
            n, r = rec["none"], rec["reference"]
            rec["checks"] = {"reference_all_searches_scoped": r["with_role_clause"] == r["searches"] - len(r["unfiltered"]) and not r["without_role_clause"],
                             "none_never_scoped": n["with_role_clause"] == 0,
                             "same_evidence": n["evidence"] == r["evidence"], "same_graph_facts": n["graph_facts"] == r["graph_facts"]}
            out.append(rec)
            print(mode, q["question"][:40], rec["checks"], "searches", r["searches"], "unfiltered", r["unfiltered"],
                  "wall", n["wall_ms"], "→", r["wall_ms"], flush=True)
        sc = {"question": q["question"], "scout_none": _scout(q["question"], None), "scout_reference": _scout(q["question"], REFERENCE_ONLY)}
        out.append(sc)
        print("scout", q["question"][:40], sc["scout_none"], sc["scout_reference"], flush=True)
    (HERE / "replay.json").write_text(json.dumps(out, indent=1, default=str))
    ok = all(all(r["checks"].values()) for r in out if "checks" in r) and all(
        r["scout_reference"]["with_role_clause"] == r["scout_reference"]["searches"] and r["scout_none"]["with_role_clause"] == 0
        for r in out if "scout_reference" in r)
    print("ALL CHECKS PASS" if ok else "A CHECK FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""D1 replay ($0 — no LLM call; gap D-01): GRAPH questions re-run through the chat's GRAPH retrieval against the live stores
+ local embedder / reranker, with the hop-1 fact order off (the legacy first 20 by `fact_id`) and on
(`POLYMATH_GRAPH_FACT_RANK=1`: evidence on the page → specific predicate → seed rank → `fact_id`, cards best-first).

Questions: the three stored RETRIEVAL-PATHWAYS-5Q questions (their saved plans) + the five most recent distinct GRAPH
questions in `query_receipts` that carry a saved plan (read-only). Per run it records the 20 facts, how many are BACKED
(their proving chunk is in the turn's evidence, so the answer can cite them), how many use the last-resort predicate
(RELATED_TO), the seeds, the ranked pool sizes and the graph time. The flag also reorders the facts lane H (the graph
destination lane) expands from the entity cards, so the evidence can change: each run records its evidence rows (lanes,
cross-encoder score, text) and a second OFF pass ("off2") measures the run-to-run noise.
Run from the D1 worktree with its PYTHONPATH and the main .env loaded. Writes replay.json next to this file."""
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
RECENT = 5
POOL: list[int] = []


def _key(question: str) -> str:
    # near-duplicates ("a prompt for a image" / "a prompt for an image") count once: first six content words
    words = [w for w in "".join(ch.lower() if ch.isalpha() else " " for ch in question).split() if w not in ("a", "an", "the")]
    return " ".join(words[:6])


def _questions() -> list[dict]:
    out, seen = [], set()
    for t in json.loads(RESULTS.read_text()):
        if t["question"] not in seen:
            seen.add(t["question"])
            out.append({"source": f"stored turn {t['turn']}", "question": t["question"], "corpus_id": "cinema",
                        "cp": ((t.get("receipt") or {}).get("meta") or {}).get("chat_plan") or {}})
    import psycopg
    with psycopg.connect(os.environ["POLYMATH_PG_DSN"]) as conn:
        rows = conn.execute(
            """SELECT DISTINCT ON (question_sha256) question_sha256, received_at, question_head, corpus_ids,
                      meta->'chat_plan'
                 FROM query_receipts
                WHERE mode = 'GRAPH' AND kind = 'chat_stream' AND status = 'ok' AND meta ? 'chat_plan'
                ORDER BY question_sha256, received_at DESC""").fetchall()
    heads = {_key(q["question"]) for q in out}
    for _sha, at, head, corpora, cp in sorted(rows, key=lambda r: r[1], reverse=True):
        if len(out) >= 3 + RECENT:
            break
        if not head or _key(head) in heads or not corpora or len(corpora) != 1:
            continue
        heads.add(_key(head))
        out.append({"source": f"receipt {at:%Y-%m-%d}", "question": head, "corpus_id": corpora[0], "cp": cp or {}})
    return out


def _once(q: dict, ranked: bool) -> dict:
    os.environ.update({"POLYMATH_CHAT_SKELETON_ROUTES": "1", "POLYMATH_CHAT_CONTEXTUAL_JUDGE": "wildcard",
                       "POLYMATH_CHAT_SKELETON_PROBES": "0", "POLYMATH_CHAT_PROBE_GATE": "1",
                       "POLYMATH_CHAT_SEEALSO_BLEND": "1", "POLYMATH_GRAPH_FACT_RANK": "1" if ranked else "0"})
    from orchestrator.api import chat_retrieval as _cr
    from orchestrator.api.chat_retrieval import chat_retrieve_mode, default_budget, intent_policy_enabled
    from polymath_shared.probe_gate import gate_probes
    from polymath_shared.query_intent import apply_intent_policy, policy_for
    from polymath_shared.skeleton_routes import apply_skeleton_routes
    cp, question = q["cp"], q["question"]
    plan = SK._plan(cp)
    ip = bool(intent_policy_enabled() and plan.intent)
    budget = apply_intent_policy(plan.intent, default_budget()) if ip else default_budget()
    budget = apply_skeleton_routes(budget, mode="GRAPH", plan=plan)
    gated_out = set()
    if getattr(budget, "probe_gate_floor", 0.0) > 0:
        gated_out, _ = gate_probes((cp.get("resolved_request") or question).strip(),
                                   [(p.id, p.origin, p.query) for p in plan.queries if p.type != "PRIMARY"],
                                   _cr._rerank_children, floor=budget.probe_gate_floor)
    POOL.clear()
    t0 = time.perf_counter()
    out = chat_retrieve_mode(
        "GRAPH", cp.get("retrieval_query") or question, q["corpus_id"], graph_useful=True,
        graph_assist=(policy_for(plan.intent).graph if ip else "off"), keep_latent=False, budget=budget,
        exact_terms=plan.exact_terms,
        subqueries=tuple((p.id, p.type, p.query, p.weight, p.origin, p.derived_from) for p in plan.queries
                         if p.type != "PRIMARY" and p.id not in gated_out),
        latent_bridge_ids=tuple(p.id for p in plan.queries if p.origin in ("BRIDGE", "CORPUS_EXPLORE") and p.id not in gated_out))
    wall = round((time.perf_counter() - t0) * 1000, 1)
    ev = out.get("evidence") or []
    ev_ids = [r.get("chunk_id") for r in ev]
    facts = out.get("graph_relationships") or []
    meta, trace = out.get("meta") or {}, out.get("trace") or {}
    return {"wall_ms": wall, "graph_ms": (trace.get("latency_ms") or {}).get("graph"), "evidence": ev_ids,
            "fact_order": (meta.get("graph_bounds") or {}).get("fact_order"), "degraded": meta.get("graph_degraded"),
            "seeds": {"cards": trace.get("graph_seed_cards"), "surfaces": trace.get("graph_seed_surfaces")},
            "pools": list(POOL),          # one per ranked expansion: lane H first when it ran, the answer's facts last
            "rows": {r.get("chunk_id"): {"source": r.get("source_name"), "arrivals": r.get("arrivals"),
                                         "query_ids": r.get("query_ids"), "rerank": r.get("rerank_score"),
                                         "text": (r.get("text") or "")[:220]} for r in ev},
            "direct": sum(1 for r in ev if "q0" in (r.get("query_ids") or [])),
            "backed": sum(1 for f in facts if f.get("chunk_id") in set(ev_ids)),
            "related_to": sum(1 for f in facts if f.get("predicate") == "RELATED_TO"),
            "facts": [{"fact_id": f.get("fact_id"), "predicate": f.get("predicate"), "subject": f.get("subject"),
                       "object": f.get("object"), "backed": f.get("chunk_id") in set(ev_ids)} for f in facts]}


def main() -> int:
    from orchestrator.api import retrieve as retrieve_mod
    orig = retrieve_mod.rank_graph_facts

    def rank(rows, seed_ids, selected):
        POOL.append(len(rows))
        return orig(rows, seed_ids, selected)

    retrieve_mod.rank_graph_facts = rank
    out = []
    for q in _questions():
        rec = {"source": q["source"], "question": q["question"], "corpus_id": q["corpus_id"]}
        for name, ranked in (("off", False), ("on", True), ("off2", False)):
            try:
                rec[name] = _once(q, ranked)
            except Exception as exc:  # noqa: BLE001 — a failed replay is a finding
                rec[name] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        off, on, off2 = rec["off"], rec["on"], rec["off2"]
        if not any("error" in r for r in (off, on, off2)):
            rec["same_evidence"] = {"off_vs_on": off["evidence"] == on["evidence"],
                                    "off_vs_off2": off["evidence"] == off2["evidence"]}
            rec["summary"] = {"facts": (len(off["facts"]), len(on["facts"])), "backed": (off["backed"], on["backed"]),
                              "related_to": (off["related_to"], on["related_to"]), "pools": on["pools"],
                              "direct": (off["direct"], on["direct"], off2["direct"]),
                              "graph_ms": (off["graph_ms"], on["graph_ms"])}
        out.append(rec)
        print(rec["source"], "|", q["question"][:60], "|", rec.get("summary"), "same_evidence=", rec.get("same_evidence"),
              "err=", off.get("error") or on.get("error"), flush=True)
    (HERE / "replay.json").write_text(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

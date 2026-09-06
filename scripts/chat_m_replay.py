#!/usr/bin/env python3
"""CHAT-M-REPLAY-V1 — in-process replay of fixture M with FROZEN compiled plans.

Why: the live M gate (scripts/chat_baseline.py --fixture eval/fixtures/chat_multi_M.json) re-compiles every
question through the LLM compiler lane, so two runs never see the same typed queries and a selection change
cannot be isolated from compiler noise. This harness replays the plans recorded in the query receipts
(eval/fixtures/chat_multi_M_plans.json, CHAT-M-REPLAY-PLANS-V1) straight into `chat_retrieve_v2` — the exact
engine call the chat path makes — so a before/after pair differs only in the code under test.

Arms (interleaved per question so both see the same GPU contention):
  single  PRIMARY only                 (= POLYMATH_CHAT_RETRIEVAL v2-single)
  multi   PRIMARY + typed subqueries   (= v2, P1.b decomposition + aspect seats)
  AB      lanes A+B only (VECTOR composition), PRIMARY only          (P1.d / P1.e)
  ABC     lanes A+B+C (HYBRID composition), PRIMARY only

Scoring is scripts/chat_baseline.aspect_stats — the same strict (gold / own document) and system-honest
(judge-accepted evidence shown, or explicitly flagged) readings as the recorded gate. The pre-R1 reading
("legacy": the PRIMARY is never flagged) is computed from the same run, so the R1 flag change is measured
with zero retrieval noise. Per-stage latency (embed / lanes / rerank_select / total) and the MPS OOM events
the sidecar logs record inside each turn's window are receipted per arm.

Usage:
  set -a; . ./.env; set +a
  .venv/bin/python scripts/chat_m_replay.py --tag r1-M [--limit 10] [--arms single,multi]
Writes docs/wiki/experiments/chat-m-replay-<tag>.json + .md. No receipts are written (the route owns those).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("", "shared", "orchestrator", "scripts"):
    p = str(ROOT / sub) if sub else str(ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

FIXTURES = {  # kind → (questions, frozen plans)
    "M": (ROOT / "eval" / "fixtures" / "chat_multi_M.json", ROOT / "eval" / "fixtures" / "chat_multi_M_plans.json"),
    "B": (ROOT / "eval" / "fixtures" / "chat_baseline_B.json", ROOT / "eval" / "fixtures" / "chat_baseline_B_plans.json"),
    "L": (ROOT / "eval" / "fixtures" / "chat_lexical_L.json", ROOT / "eval" / "fixtures" / "chat_lexical_L_plans.json"),
}
OUT_DIR = ROOT / "docs" / "wiki" / "experiments"
FLEET_LOGS = Path("/private/tmp/polymath_fleet")
_TS = re.compile(r'"timestamp":"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?)')


def _med(xs):
    xs = [float(x) for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 1) if xs else None


def _p90(xs):
    xs = sorted(float(x) for x in xs if isinstance(x, (int, float)))
    if not xs:
        return None
    return round(xs[min(len(xs) - 1, int(round(0.9 * (len(xs) - 1))))], 1)


def _oom_events(t0: float, t1: float) -> dict:
    """OOM lines the MLX sidecars logged between t0 and t1 (epoch seconds, UTC log stamps)."""
    out = {}
    lo = dt.datetime.fromtimestamp(t0, dt.timezone.utc).replace(tzinfo=None)
    hi = dt.datetime.fromtimestamp(t1, dt.timezone.utc).replace(tzinfo=None)
    for name in ("sidecar_embedder", "sidecar_reranker"):
        path = FLEET_LOGS / f"{name}.log"
        n = 0
        if path.exists():
            with path.open("rb") as fh:
                fh.seek(max(0, path.stat().st_size - 4_000_000))
                for raw in fh.read().decode("utf-8", "ignore").splitlines():
                    if "oom" not in raw.lower():
                        continue
                    m = _TS.search(raw)
                    if not m:
                        continue
                    try:
                        ts = dt.datetime.fromisoformat(m.group(1))
                    except ValueError:
                        continue
                    if lo <= ts <= hi:
                        n += 1
        out[name] = n
    return out


def _legacy_reading(ans: dict, weak_reasons: dict) -> dict:
    """Pre-R1 semantics: the PRIMARY (q0) was never flagged `below_floor`."""
    ret = dict(ans["retrieval"])
    weak = [q for q in (ret.get("weak_aspects") or []) if not (q == "q0" and weak_reasons.get("q0") == "below_floor")]
    ret["weak_aspects"] = weak
    return {"retrieval": ret}


def _gold_stats(q: dict, trace: dict) -> dict:
    """Fixture B / L: where the gold chunk died or was seated (same definitions as chat_baseline)."""
    golds = set(q.get("gold_chunk_ids") or ([q["gold_chunk_id"]] if q.get("gold_chunk_id") else []))
    union = trace.get("funnel_union") or []; pre = trace.get("pre_g3_order") or []; final = trace.get("final") or []
    rank = next((i + 1 for i, cid in enumerate(final) if cid in golds), None)
    comp = trace.get("composition") or {}
    return {"gold_in_union": any(g in union for g in golds), "gold_in_pre_rerank": any(g in pre for g in golds),
            "gold_union_rank": next((i + 1 for i, cid in enumerate(union) if cid in golds), None),
            "gold_selected_rank": rank, "hit10": bool(rank and rank <= 10), "rr": (1.0 / rank if rank else 0.0),
            "doc_share_top": comp.get("doc_share_top"), "docs_within_gap": comp.get("docs_within_gap"), "dominance": comp.get("dominance"),
            "dominance_avoidable": comp.get("dominance_avoidable")}


def run(args) -> int:
    import os
    if args.rerank_max:
        os.environ["POLYMATH_CHAT_RERANK_MAX"] = str(args.rerank_max)       # default_budget() reads it per call
    from orchestrator.api.chat_retrieval import chat_retrieve_v2   # the chat path's engine call
    from chat_baseline import aspect_stats                          # the recorded gate's scorer

    kind = args.fixture.upper()
    fixture_path, plans_path = FIXTURES[kind]
    fx = json.loads(fixture_path.read_text())
    items = fx["items"] if isinstance(fx, dict) and "items" in fx else fx["questions"]
    plans = {p["idx"]: p for p in json.loads(Path(args.plans or plans_path).read_text())["plans"]}
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    idxs = [i for i in range(len(items)) if i in plans]
    idxs = idxs[: args.limit] if args.limit else idxs
    rows: list[dict] = []
    t_run0 = time.time()
    for i in idxs:
        q = items[i]; plan = plans[i]
        query = plan.get("retrieval_query") or plan["queries"][0]["query"]
        exact = tuple(plan.get("exact_terms") or ())
        subs = tuple((s["id"], s["type"], s["query"], s.get("weight", 1.0)) for s in plan["queries"] if s.get("type") != "PRIMARY")
        for arm in (arms if i % 2 == 0 else list(reversed(arms))):   # alternate the arm order per question (no order bias)
            t0 = time.time()
            lanes = {"AB": ("HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD"), "ABC": ("HIERARCHICAL_ROUTE", "GLOBAL_DENSE_CHILD", "GLOBAL_SPARSE_CHILD")}.get(arm)
            kw = {"lanes": lanes} if lanes else {}
            try:
                fast = chat_retrieve_v2(query, q["corpus_id"], exact_terms=exact, subqueries=(subs if arm == "multi" else ()), **kw)
                err = None
            except Exception as exc:  # noqa: BLE001 — recorded, never hides a turn
                fast, err = None, f"{type(exc).__name__}: {str(exc)[:200]}"
            t1 = time.time()
            row = {"idx": i, "arm": arm, "corpus_id": q["corpus_id"], "question": q["question"][:90], "error": err,
                   "wall_ms": round((t1 - t0) * 1000, 1), "oom": _oom_events(t0, t1), "compiled_queries": 1 if arm == "single" else 1 + len(subs)}
            if fast is not None:
                meta, trace = fast.get("meta") or {}, fast.get("trace") or {}
                ans = {"retrieval": {"aspects": meta.get("aspects") or {}, "weak_aspects": meta.get("weak_aspects") or [],
                                     "legend": [], "final_detail": meta.get("final_detail") or []}}
                rec = {"meta": {"funnel": {"stages": {"selected": trace.get("final") or [], "union": trace.get("funnel_union") or []}}}}
                st = aspect_stats(q, ans, rec) if kind == "M" else {}
                st_legacy = aspect_stats(q, _legacy_reading(ans, meta.get("weak_reasons") or {}), rec) if kind == "M" else {}
                if kind != "M":
                    row.update(_gold_stats(q, trace))
                row.update({"latency_ms": trace.get("latency_ms") or {}, "degraded_components": [d.get("component") for d in (meta.get("degraded") or [])],
                            "lanes_used": meta.get("lanes"), "weak_aspects": meta.get("weak_aspects"),
                            "weak_reasons": meta.get("weak_reasons"), "aspect_best": meta.get("aspect_best"),
                            "rerank_prefix": trace.get("rerank_prefix"), "candidates": meta.get("candidates"),
                            "evidence_count": meta.get("evidence_count"), "degraded": meta.get("degraded"),
                            "dims": st.get("dims", 0), "dims_ok": st.get("dims_ok", 0), "dims_system_ok": st.get("dims_system_ok", 0),
                            "dims_flagged": st.get("dims_flagged", 0), "dims_silent": st.get("dims_silent", 0),
                            "dims_covered_gold": st.get("dims_covered_gold", 0), "dims_covered": st.get("dims_covered", 0),
                            "dims_in_union": st.get("dims_in_union", 0),
                            "legacy_dims_ok": st_legacy.get("dims_ok", 0), "legacy_dims_system_ok": st_legacy.get("dims_system_ok", 0),
                            "aspects": st.get("aspects")})
            rows.append(row)
            if kind == "M":
                print(f"[{i:02d}] {arm:6s} {row['wall_ms']/1000:6.2f}s  ok={row.get('dims_ok')}/{row.get('dims')} sys={row.get('dims_system_ok')} "
                      f"weak={row.get('weak_aspects')} oom={row['oom']} {('ERR ' + err) if err else ''}", flush=True)
            else:
                print(f"[{i:02d}] {arm:6s} {row['wall_ms']/1000:6.2f}s  union={row.get('gold_in_union')} pre={row.get('gold_in_pre_rerank')} "
                      f"rank={row.get('gold_selected_rank')} urank={row.get('gold_union_rank')} prefix={row.get('rerank_prefix')} oom={row['oom']} {('ERR ' + err) if err else ''}", flush=True)
    t_run1 = time.time()

    summary = {"tag": args.tag, "fixture": kind, "rerank_max_override": args.rerank_max, "n_questions": len(idxs), "arms": arms,
               "plans": str(Path(args.plans or plans_path).relative_to(ROOT)),
               "run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "run_wall_s": round(t_run1 - t_run0, 1),
               "oom_during_run": _oom_events(t_run0, t_run1), "per_arm": {}}
    for arm in arms:
        ar = [r for r in rows if r["arm"] == arm and not r.get("error")]
        dims = sum(r["dims"] for r in ar) or 1
        lat = [r.get("latency_ms") or {} for r in ar]
        keys = sorted({k for l in lat for k in l})
        gold = {}
        if kind != "M":
            in_union = [r for r in ar if r.get("gold_in_union")]
            gold = {"gold_in_union": round(len(in_union) / max(1, len(ar)), 3),
                    "gold_in_pre_rerank": round(sum(1 for r in ar if r.get("gold_in_pre_rerank")) / max(1, len(ar)), 3),
                    "hit@10_selected": round(sum(1 for r in ar if r.get("hit10")) / max(1, len(ar)), 3),
                    "mrr_selected": round(sum(r.get("rr") or 0.0 for r in ar) / max(1, len(ar)), 3),
                    "survival_selected_given_union": round(sum(1 for r in in_union if r.get("gold_selected_rank")) / max(1, len(in_union)), 3),
                    "unseated_in_union": [{"idx": r["idx"], "union_rank": r.get("gold_union_rank"), "pre_rerank": r.get("gold_in_pre_rerank")} for r in in_union if not r.get("gold_selected_rank")],
                    "dominance_violations": sum(1 for r in ar if r.get("dominance")),
                    "dominance_avoidable_violations": sum(1 for r in ar if r.get("dominance_avoidable")),
                    "dominance_eligible_turns": sum(1 for r in ar if (r.get("docs_within_gap") or 0) >= 3)}
        summary["per_arm"][arm] = {
            **gold,
            "n": len(ar), "errors": sum(1 for r in rows if r["arm"] == arm and r.get("error")),
            "dims": sum(r.get("dims", 0) for r in ar),
            "dims_ok_strict": sum(r.get("dims_ok", 0) for r in ar), "strict_rate": round(sum(r.get("dims_ok", 0) for r in ar) / dims, 3),
            "dims_system_ok": sum(r.get("dims_system_ok", 0) for r in ar), "system_rate": round(sum(r.get("dims_system_ok", 0) for r in ar) / dims, 3),
            "legacy_strict_rate": round(sum(r.get("legacy_dims_ok", 0) for r in ar) / dims, 3),
            "legacy_system_rate": round(sum(r.get("legacy_dims_system_ok", 0) for r in ar) / dims, 3),
            "dims_flagged": sum(r.get("dims_flagged", 0) for r in ar), "dims_silent": sum(r.get("dims_silent", 0) for r in ar),
            "dims_covered_gold": sum(r.get("dims_covered_gold", 0) for r in ar), "dims_covered": sum(r.get("dims_covered", 0) for r in ar),
            "dims_in_union": sum(r.get("dims_in_union", 0) for r in ar),
            "primary_flagged_below_floor": sum(1 for r in ar if (r.get("weak_reasons") or {}).get("q0") == "below_floor"),
            "wall_p50_s": round((_med([r["wall_ms"] for r in ar]) or 0) / 1000, 2), "wall_p90_s": round((_p90([r["wall_ms"] for r in ar]) or 0) / 1000, 2),
            "latency_ms_p50": {k: _med([l.get(k) for l in lat]) for k in keys},
            "rerank_prefix_p50": _med([r.get("rerank_prefix") for r in ar]),
            "degraded_turns": sum(1 for r in ar if r.get("degraded_components")),
            "degraded_components": sorted({c for r in ar for c in (r.get("degraded_components") or [])}),
            "latency_ms_p90": {k: _p90([l.get(k) for l in lat]) for k in keys if k in ("embed", "rerank_select", "total", "lanes", "union", "compose")},
            "oom_embedder": sum(r["oom"]["sidecar_embedder"] for r in ar), "oom_reranker": sum(r["oom"]["sidecar_reranker"] for r in ar),
            # clean-turn subset: turns during which neither sidecar logged an OOM split — the closest thing to an
            # uncontended interactive measurement without pausing any service
            "clean_turns": sum(1 for r in ar if not any(r["oom"].values())),
            "clean_wall_p50_s": round((_med([r["wall_ms"] for r in ar if not any(r["oom"].values())]) or 0) / 1000, 2),
            "clean_rerank_p50_ms": _med([(r.get("latency_ms") or {}).get("rerank_select") for r in ar if not any(r["oom"].values())]),
            "clean_embed_p50_ms": _med([(r.get("latency_ms") or {}).get("embed") for r in ar if not any(r["oom"].values())]),
            "clean_total_p50_ms": _med([(r.get("latency_ms") or {}).get("total") for r in ar if not any(r["oom"].values())]),
            "silent": [{"idx": r["idx"], "term": a["term"], "naming": a["queries_naming"], "in_union": a["in_union"]}
                       for r in ar for a in (r.get("aspects") or []) if a.get("silent")],
            "not_system_ok": [{"idx": r["idx"], "term": a["term"], "naming": a["queries_naming"]}
                              for r in ar for a in (r.get("aspects") or []) if not a.get("system_ok")],
        }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"chat-m-replay-{args.tag}.json").write_text(json.dumps({"summary": summary, "results": rows}, indent=1, default=str))
    md = [f"---\ntitle: \"CHAT-M-REPLAY {args.tag}: fixture M replayed in-process with frozen plans\"\nowner: governance\n"
          f"last_reviewed: {dt.date.today().isoformat()}\nlast_touched: {dt.date.today().isoformat()}\nstatus: measured\n---\n",
          f"# CHAT-M-REPLAY {args.tag}", "", f"run {summary['run_utc']} · fixture {kind} · {len(idxs)} questions · arms {', '.join(arms)} · plans `{summary['plans']}` "
          f"· rerank_max override {args.rerank_max} · OOM during run {summary['oom_during_run']}", ""]
    if kind != "M":
        md += ["| arm | n | gold in union | gold in prefix | hit@10 | MRR | survival given union | unseated | dominance viol / eligible | wall p50 s | clean turns | clean wall p50 s | rerank p50 ms | clean rerank p50 ms | prefix p50 | OOM emb/rr |", "|---|" + "---|" * 15]
        for arm, s_ in summary["per_arm"].items():
            L = s_["latency_ms_p50"]
            md.append(f"| {arm} | {s_['n']} | {s_['gold_in_union']} | {s_['gold_in_pre_rerank']} | {s_['hit@10_selected']} | {s_['mrr_selected']} | {s_['survival_selected_given_union']} | "
                      f"{len(s_['unseated_in_union'])} | {s_['dominance_violations']} / {s_['dominance_eligible_turns']} | {s_['wall_p50_s']} | {s_['clean_turns']} | {s_['clean_wall_p50_s']} | "
                      f"{L.get('rerank_select')} | {s_['clean_rerank_p50_ms']} | {s_['rerank_prefix_p50']} | {s_['oom_embedder']}/{s_['oom_reranker']} |")
        md += ["", "Unseated golds that were in the union:", ""] + [f"- {arm}: {s_['unseated_in_union'] or 'none'}" for arm, s_ in summary["per_arm"].items()]
    md += ["", "| arm | n | strict | system-honest | legacy strict | legacy system | flagged | silent | gold covered | in union | "
          "primary flagged | wall p50 s | wall p90 s | embed p50 ms | rerank p50 ms | total p50 ms | prefix p50 | OOM emb/rr | clean turns | clean wall p50 s | clean rerank p50 ms |", "|---|" + "---|" * 20]
    for arm, s in summary["per_arm"].items():
        L = s["latency_ms_p50"]
        md.append(f"| {arm} | {s['n']} | {s['strict_rate']} ({s['dims_ok_strict']}/{s['dims']}) | {s['system_rate']} ({s['dims_system_ok']}/{s['dims']}) | "
                  f"{s['legacy_strict_rate']} | {s['legacy_system_rate']} | {s['dims_flagged']} | {s['dims_silent']} | {s['dims_covered_gold']} | {s['dims_in_union']} | "
                  f"{s['primary_flagged_below_floor']} | {s['wall_p50_s']} | {s['wall_p90_s']} | {L.get('embed')} | {L.get('rerank_select')} | {L.get('total')} | "
                  f"{s['rerank_prefix_p50']} | {s['oom_embedder']}/{s['oom_reranker']} | {s['clean_turns']} | {s['clean_wall_p50_s']} | {s['clean_rerank_p50_ms']} |")
    md += ["", "Residual (not system-honest OK):", ""] + [f"- {arm}: {s['not_system_ok'] or 'none'}" for arm, s in summary["per_arm"].items()]
    md += ["", "Strict misses (silent):", ""] + [f"- {arm}: {s['silent'] or 'none'}" for arm, s in summary["per_arm"].items()]
    (OUT_DIR / f"chat-m-replay-{args.tag}.md").write_text("\n".join(md) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_arm"}, indent=1))
    for arm, s in summary["per_arm"].items():
        print(arm, json.dumps({k: v for k, v in s.items() if k not in ("silent", "not_system_ok", "latency_ms_p50")}))
        print("  latency p50:", s["latency_ms_p50"])
        print("  not system-honest:", s["not_system_ok"])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", default="replay")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--arms", default="single,multi")
    ap.add_argument("--fixture", default="M", help="M (two-aspect, coverage) | B (baseline, gold rank) | L (lexical identifiers)")
    ap.add_argument("--plans", default=None, help="frozen plans file (default: the fixture's *_plans.json)")
    ap.add_argument("--rerank-max", type=int, default=None, help="override CandidateBudget.rerank_max for this run (POLYMATH_CHAT_RERANK_MAX)")
    return run(ap.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())

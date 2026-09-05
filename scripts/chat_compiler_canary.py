#!/usr/bin/env python
"""CHAT-INTENT-PLAN-V1 canary + P0.b gate tool (CHAT-QUERY-COMPILER-PLAN §4, §6).

Runs the compiler in-process through the `chat_compiler` stage pin on
  * the conversation fixtures in eval/fixtures/chat_conversations/*.json
    (each declares expectations: task_type, retrieval_required, ...), and
  * the baseline set B questions (eval/fixtures/chat_baseline_B.json),
and reports: fallback rate, task-verb preservation, expectation matches,
wall-time p50/p90 per call, lanes used. Writes
docs/wiki/experiments/chat-compiler-<tag>.{json,md}.

Gate (P0.b): fallback < 5 % on B; task verb preserved on 100 % of fixtures;
p50 compile ≤ 2.5 s. Readiness canary: every fixture yields a valid plan.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("shared", "orchestrator"):
    sys.path.insert(0, str(ROOT / sub))
FIX_DIR = ROOT / "eval" / "fixtures" / "chat_conversations"
B_FILE = ROOT / "eval" / "fixtures" / "chat_baseline_B.json"
OUT_DIR = ROOT / "docs" / "wiki" / "experiments"


def _check(fx: dict, plan) -> list[str]:
    from polymath_shared.chat_plan import task_classes
    exp = fx.get("expected") or fx.get("expected_after_compiler") or {}
    fails: list[str] = []
    allowed = exp.get("task_type_in") or ([exp["task_type"]] if exp.get("task_type") else [])
    if allowed and plan.task_type not in allowed:
        fails.append(f"task_type {plan.task_type} not in {allowed}")
    if "retrieval_required" in exp and plan.retrieval_required != exp["retrieval_required"]:
        fails.append(f"retrieval_required {plan.retrieval_required} != {exp['retrieval_required']}")
    if exp.get("response_type") and plan.response_type != exp["response_type"]:
        fails.append(f"response_type {plan.response_type} != {exp['response_type']}")
    for needle in exp.get("resolved_contains") or []:
        if needle.lower() not in plan.resolved_request.lower():
            fails.append(f"resolved lacks {needle!r}")
    for term in exp.get("exact_terms_include") or []:
        if term not in plan.exact_terms:
            fails.append(f"exact_terms lacks {term!r}")
    if exp.get("task_class") and exp["task_class"] not in task_classes(plan.resolved_request):
        fails.append(f"task class {exp['task_class']} not preserved")
    orig = task_classes(fx["message"])
    if orig and not (orig & task_classes(plan.resolved_request)) and plan.task_type != "CONTINUE_PRIOR_ARTIFACT":
        fails.append("task verb dropped")
    if plan.fallback:
        fails.append(f"fallback:{plan.compiler.get('reason')}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="shadow")
    ap.add_argument("--skip-b", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    from orchestrator.api.ui import _compile_chat_plan
    from polymath_shared.chat_plan import plan_receipt, task_classes
    rows = []
    print("== fixtures ==", flush=True)
    for p in sorted(FIX_DIR.glob("*.json")):
        fx = json.loads(p.read_text())
        t0 = time.perf_counter()
        plan = _compile_chat_plan(fx["message"], fx.get("history") or [], [fx.get("corpus_id")], session_key=p.stem)
        wall = (time.perf_counter() - t0) * 1000
        fails = _check(fx, plan)
        rows.append({"set": "fixture", "name": p.stem, "wall_ms": round(wall, 1), "fallback": plan.fallback,
                     "lane": plan.compiler.get("lane"), "task_type": plan.task_type, "retrieval_required": plan.retrieval_required,
                     "resolved_request": plan.resolved_request, "queries": [q.query for q in plan.queries],
                     "exact_terms": plan.exact_terms, "fails": fails})
        print(f"  {p.stem:24s} {plan.task_type:24s} rr={str(plan.retrieval_required):5s} {wall:6.0f}ms lane={plan.compiler.get('lane')} {'OK' if not fails else 'FAIL ' + '; '.join(fails)}", flush=True)
        if plan.queries:
            print("      queries:", [q.query for q in plan.queries][:4], "| exact:", plan.exact_terms[:6], flush=True)
    if not a.skip_b:
        print("== baseline B ==", flush=True)
        B = json.loads(B_FILE.read_text())["questions"][: a.limit or None]
        for q in B:
            t0 = time.perf_counter()
            plan = _compile_chat_plan(q["question"], [], [q["corpus_id"]], session_key=q["gold_chunk_id"])
            wall = (time.perf_counter() - t0) * 1000
            orig = task_classes(q["question"])
            kept = (not orig) or bool(orig & task_classes(plan.resolved_request))
            rows.append({"set": "B", "name": q["question"][:60], "wall_ms": round(wall, 1), "fallback": plan.fallback,
                         "lane": plan.compiler.get("lane"), "task_type": plan.task_type, "retrieval_required": plan.retrieval_required,
                         "resolved_request": plan.resolved_request, "queries": [x.query for x in plan.queries],
                         "exact_terms": plan.exact_terms, "fails": ([] if kept else ["task verb dropped"]) + ([f"fallback:{plan.compiler.get('reason')}"] if plan.fallback else [])})
            print(f"  {q['corpus_id'][:6]} {plan.task_type:20s} rr={str(plan.retrieval_required):5s} {wall:6.0f}ms {'OK' if not rows[-1]['fails'] else 'FAIL ' + '; '.join(rows[-1]['fails'])} | {q['question'][:50]}", flush=True)
    fixtures = [r for r in rows if r["set"] == "fixture"]; b = [r for r in rows if r["set"] == "B"]
    walls = [r["wall_ms"] for r in rows]
    summary = {
        "tag": a.tag, "n_fixtures": len(fixtures), "n_B": len(b),
        "fixture_pass": sum(1 for r in fixtures if not r["fails"]),
        "fixture_task_verb_kept": sum(1 for r in fixtures if "task verb dropped" not in r["fails"]),
        "B_fallback_rate": round(sum(1 for r in b if r["fallback"]) / max(1, len(b)), 3),
        "B_task_verb_kept_rate": round(sum(1 for r in b if "task verb dropped" not in r["fails"]) / max(1, len(b)), 3),
        "B_retrieval_required_rate": round(sum(1 for r in b if r["retrieval_required"]) / max(1, len(b)), 3),
        "wall_p50_ms": round(statistics.median(walls), 1) if walls else None,
        "wall_p90_ms": round(sorted(walls)[int(len(walls) * 0.9) - 1], 1) if len(walls) >= 10 else None,
        "lanes": sorted({r["lane"] for r in rows if r["lane"]}),
        "fallback_reasons": sorted({r["fails"][-1] for r in rows if r["fallback"]}),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"chat-compiler-{a.tag}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    import datetime as _dt
    today = _dt.date.today().isoformat()
    md = ["---", f"title: \"Chat compiler canary — {a.tag}\"", "owner: governance", f"last_reviewed: {today}", f"last_touched: {today}",
          "status: measured", "---", "", f"# Chat compiler canary — {a.tag}", "", "| metric | value |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in summary.items() if k != "tag"]
    md += ["", "| set | name | task_type | retrieval | wall ms | lane | result |", "|---|---|---|---|---|---|---|"]
    md += [f"| {r['set']} | {r['name']} | {r['task_type']} | {r['retrieval_required']} | {r['wall_ms']} | {r['lane']} | {'OK' if not r['fails'] else '; '.join(r['fails'])} |" for r in rows]
    (OUT_DIR / f"chat-compiler-{a.tag}.md").write_text("\n".join(md) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

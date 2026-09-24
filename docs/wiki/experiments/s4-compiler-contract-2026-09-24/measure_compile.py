"""S4 compile measurement: v1 (today — the plan call, then the separate bridge call) against v2 (the grounded-learning
contract — one call writes the plan and the bridges, the old bridge admission decides). Compiler only: no retrieval, no
answer, no chat turn. Runs `ui._compile_chat_plan` in-process from the S4 worktree (its PYTHONPATH + the main .env, so
the live Scout, profile expansion and bridge flags apply), v1 then v2 per question with the same session key, REPS times.

Per run: the compile wall and each step (scout / matches / lanes = the plan call / profile_expansion / bridges), the
plan call's own wall, fallback + reason, the lane that answered, bridges proposed / admitted, and the v2 fields.
LIVE SPEND: compiler-lane calls only (v1 also makes its bridge call). Writes measure.json (S4_OUT renames) next to this file."""
from __future__ import annotations

import json
import os
import pathlib
import statistics
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPS = int(os.environ.get("S4_REPS", "2"))
QUESTIONS = [
    "What do my books say about making an animated character's movement feel weighty?",
    "How do editors and directors build suspense without dialogue?",
    "How do lighting and color choices change how an audience reads a scene?",
    "What does the book say about nonsquare pixels?",
    "How do the rhythm of film editing and the timing of music relate?",
    "What is the 180-degree rule in filming a scene?",
    "make a character's suppressed grief visible while they try hard to hide it",
    "why does camera angle sell a staged hit",
    ("What do the cinema documents say about how a camera crew keeps equipment working through a shooting day, and what "
     "goes wrong in hand-offs?"),
    "What is the Facial Action Coding System and what does it measure?",
]


def _one(ui, q: str, contract: bool, key: str) -> dict:
    os.environ["POLYMATH_CHAT_COMPILER_CONTRACT"] = "1" if contract else "0"
    t0 = time.perf_counter()
    try:
        plan = ui._compile_chat_plan(q, [], ["cinema"], session_key=key)
    except Exception as exc:  # noqa: BLE001 — _compile_chat_plan never raises; a raise here is a finding
        return {"error": f"{type(exc).__name__}: {exc}"[:300], "wall_ms": round((time.perf_counter() - t0) * 1000, 1)}
    c = plan.compiler or {}
    bx = c.get("bridge_expansion") or {}
    queries = [{"id": x.id, "type": x.type, "origin": x.origin, "query": x.query,
                "expected_contribution": x.expected_contribution, "evidence_requirement": x.evidence_requirement}
               for x in plan.queries]
    return {"wall_ms": round((time.perf_counter() - t0) * 1000, 1), "compile_ms": c.get("compile_ms"),
            "llm_wall_ms": c.get("wall_ms"), "model": c.get("model"), "fallback": bool(plan.fallback),
            "reason": c.get("reason"), "task_type": plan.task_type, "retrieval_required": plan.retrieval_required,
            "contract": plan.contract, "learning_need": plan.retrieval_goal if contract else None,
            "inquiry": plan.inquiry, "synthesis_targets": plan.synthesis_targets, "contract_diag": c.get("contract"),
            "bridge_expansion": {k: bx.get(k) for k in ("merged", "attempted", "generated", "admitted", "rejected",
                                                        "dropped_covered", "fallback_reason", "latency_ms")},
            "queries": queries}


def _med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 1) if xs else None


def _p90(xs):
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    return round(xs[min(len(xs) - 1, int(0.9 * len(xs)))], 1) if xs else None


def summarize(runs: list) -> dict:
    out = {}
    for variant in ("v1", "v2"):
        rs = [r for r in runs if r["variant"] == variant and "error" not in r["result"]]
        res = [r["result"] for r in rs]

        def step(name, res=res):
            return [(x.get("compile_ms") or {}).get(name) for x in res]
        user_qs = [q for x in res if not x["fallback"] for q in x["queries"] if q["origin"] == "USER"]
        out[variant] = {
            "runs": len(res), "errors": sum(1 for r in runs if r["variant"] == variant and "error" in r["result"]),
            "fallback_rate": round(sum(x["fallback"] for x in res) / len(res), 3) if res else None,
            "fallback_reasons": sorted({x["reason"] for x in res if x["fallback"]}),
            "compile_total_ms": {"median": _med(step("total")), "p90": _p90(step("total"))},
            "plan_call_ms": {"median": _med(step("lanes")), "p90": _p90(step("lanes"))},
            "bridges_step_ms": {"median": _med(step("bridges")), "p90": _p90(step("bridges"))},
            "scout_ms": _med(step("scout")), "matches_ms": _med(step("matches")),
            "bridges_admitted_per_turn": _med([x["bridge_expansion"].get("admitted") for x in res]),
            "turns_with_bridges": sum(1 for x in res if (x["bridge_expansion"].get("admitted") or 0) > 0),
            "retrieval_required_rate": round(sum(bool(x["retrieval_required"]) for x in res) / len(res), 3) if res else None,
            "learning_need_rate": (round(sum(bool(x["learning_need"]) for x in res if not x["fallback"])
                                         / max(1, sum(not x["fallback"] for x in res)), 3) if variant == "v2" else None),
            "user_queries_with_purpose": (round(sum(bool(q["expected_contribution"]) for q in user_qs) / max(1, len(user_qs)), 3)
                                          if variant == "v2" else None),
            "synthesis_targets_per_turn": _med([len(x["synthesis_targets"]) for x in res]) if variant == "v2" else None,
            "inquiry_dims_per_turn": _med([len(x["inquiry"]) for x in res]) if variant == "v2" else None,
        }
    return out


def main() -> int:
    from orchestrator.api import ui
    os.environ.setdefault("POLYMATH_REASONING_RECEIPT", str(HERE / "reasoning_receipt.jsonl"))
    runs = []
    for rep in range(REPS):
        for i, q in enumerate(QUESTIONS):
            key = f"s4-measure-{i}-{rep}"
            for variant in ("v1", "v2"):
                r = _one(ui, q, variant == "v2", key)
                runs.append({"rep": rep, "q": i, "question": q, "variant": variant, "result": r})
                cm = r.get("compile_ms") or {}
                print(f"[rep {rep} q{i} {variant}] total={cm.get('total')} plan={cm.get('lanes')} bridges={cm.get('bridges')} "
                      f"fallback={r.get('fallback')} reason={r.get('reason')} admitted={(r.get('bridge_expansion') or {}).get('admitted')}",
                      flush=True)
    summary = summarize(runs)
    out = HERE / os.environ.get("S4_OUT", "measure.json")
    out.write_text(json.dumps({"reps": REPS, "questions": QUESTIONS, "summary": summary, "runs": runs}, indent=1, default=str))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""CORPUS-EXPLORE-FIRING-V1 CE8 — firing ATTRIBUTION (live, staged budget).

CE7 measured that Corpus Explore fired 14/18 but could not say why the rest did not: every closed gate
returned silently. This runner reads the per-turn `corpus_explore_firing` receipt (exactly ONE cause code per
non-firing request) and builds a cause table: cause -> count -> queries.

STAGED BUDGET (owner rule): no up-front matrix. Each invocation runs ONE named batch of <= 8 live
executions and APPENDS it to the artifact; a batch is only added while the diagnosis is unresolved, and its
`question` (what this batch answers) is recorded with it. The runner refuses to pass 24 total executions
without `--owner-approved` (ask the owner first).

"fired" here is the STRICT product meaning: the explorer added >=1 CORPUS_EXPLORE subquery to a plan whose
retrieval ran. CE7's looser "activated" (n_activations > 0) is reported alongside so the two are comparable.

Live calls use `/chat/stream` with the deterministic template synthesizer (no synthesis LLM): activation is
computed at plan-compile time and is mode-independent, so FAST is used throughout.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "shared"))

from polymath_shared.corpus_explore_firing import summarize  # noqa: E402

BASE = "http://127.0.0.1:7200"
ASK_LINE = 24

#: query bank. `kind`: target = on-target (should fire) · negative = should stay quiet.
#: `seen` = came from CE7 (Phase A reuses them to reproduce the baseline misses); fresh = unseen until Phase C.
BANK = {
    # CE7 queries (the two baseline misses + firing controls + negatives)
    "suppressed_grief": ("target", "make a character's suppressed grief visible while they try hard to hide it"),
    "physical_weight_f2": ("target", "the movement should feel grounded and forceful rather than weightless and flashy"),
    "physical_weight_f0": ("target", "make a fight feel like the blows land with real weight and consequence"),
    "nonverbal_authority_f0": ("target", "a character commands a room the moment she enters, without saying a word"),
    "insincere_expression_f0": ("target", "make a character's smile read as fake and forced to the audience"),
    "ordinary_unease_f0": ("target", "make an ordinary hallway feel quietly menacing without turning it into a horror set"),
    "neg_birthday": ("negative", "design a bright, joyful children's birthday party montage full of balloons and cake"),
    "neg_cooking": ("negative", "create an upbeat step-by-step cooking tutorial for a simple pasta dish"),
    "neg_vacation": ("negative", "write a lighthearted scene of friends cheerfully planning a summer beach vacation"),
    # FRESH on-target queries — NOT used in Phase A; self-authored, no book/domain names (anti-overfitting).
    "fresh_loneliness_crowd": ("target", "show that a character feels completely alone even though the room is full of people"),
    "fresh_power_shift": ("target", "let the audience feel the balance of power tip from one person to the other mid-conversation"),
    "fresh_time_pressure": ("target", "make the audience feel time running out without ever showing a clock"),
    "fresh_unreliable_memory": ("target", "signal that what we are watching is a memory that cannot be fully trusted"),
    "fresh_exhaustion": ("target", "convey bone-deep exhaustion in a character through how they move and hold themselves"),
    "fresh_hidden_threat": ("target", "make a polite, friendly conversation feel like a veiled threat"),
    "fresh_neg_weather": ("negative", "write a cheerful weather forecast for a sunny spring weekend"),
    "fresh_neg_shopping": ("negative", "list the groceries needed for a week of simple family dinners"),
}


def probe(question: str, *, corpus_explorer: bool = True, timeout: int = 240) -> dict:
    body = json.dumps({"message": question, "corpus_id": "cinema", "mode": "FAST",
                       "synthesizer": "deterministic-template-v3",
                       "corpus_explorer": corpus_explorer}).encode()
    req = urllib.request.Request(f"{BASE}/chat/stream", data=body,
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    ans, cur, err, compile_phase = {}, None, None, {}
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").rstrip("\n")
                if line.startswith("event:"):
                    cur = line[6:].strip()
                elif line.startswith("data:"):
                    try:
                        data = json.loads(line[5:].strip())
                    except Exception:  # noqa: BLE001
                        data = None
                    if cur == "answer" and isinstance(data, dict):
                        ans = data
                    elif cur == "error":
                        err = line[5:].strip()[:300]
                    elif cur == "phase" and isinstance(data, dict) and data.get("stage") == "compile":
                        compile_phase = data
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {str(exc)[:160]}"
    retrieval = ans.get("retrieval") or {}
    plan = retrieval.get("chat_plan") or {}
    comp = plan.get("compiler") or {}
    firing = comp.get("corpus_explore_firing") or retrieval.get("corpus_explore_firing") or {}
    act = comp.get("corpus_activation") or {}
    exp = comp.get("corpus_explore_expansion") or {}
    ce_queries = [q for q in (plan.get("queries") or []) if (q.get("origin") == "CORPUS_EXPLORE")]
    evidence = retrieval.get("legend") or retrieval.get("used_evidence") or []
    return {
        "q": question, "err": err, "latency_s": round(time.time() - t0, 1),
        "answer_event": bool(ans), "firing": firing,
        "fired": bool(firing.get("fired")), "cause": firing.get("cause"), "detail": firing.get("detail"),
        "activated": bool(act.get("n_activations")), "n_activations": act.get("n_activations", 0),
        "concept_ids": [a.get("concept_id") for a in (act.get("activations") or [])],
        "provenance_complete": all((a.get("source_document_ids") or []) for a in (act.get("activations") or [])),
        "n_ce_subqueries": len(ce_queries), "ce_subquery_ids": [q.get("id") for q in ce_queries],
        "expansion": {k: exp.get(k) for k in ("attempted", "added", "eligible", "reason", "fallback_reason",
                                               "json_status", "generate_error", "generated", "admitted",
                                               "latency_ms")},
        "plan": {"intent": plan.get("intent"), "task_type": plan.get("task_type"),
                 "retrieval_required": plan.get("retrieval_required"),
                 "retrieval_skipped": plan.get("retrieval_skipped"),
                 "fallback": comp.get("fallback"), "fallback_reason": comp.get("reason"),
                 "model": comp.get("model"), "wall_ms": comp.get("wall_ms"),
                 "attempts": comp.get("attempts"), "n_queries": len(plan.get("queries") or [])},
        "compile_phase": {k: compile_phase.get(k) for k in ("fallback", "task_type", "wall_ms", "queries")},
        "evidence_ids": sorted({str(e.get("chunk_id")) for e in evidence if isinstance(e, dict) and e.get("chunk_id")}),
    }


def cause_table(runs: list[dict]) -> dict:
    """cause -> {count, queries}. Targets and negatives are tabulated separately."""
    out: dict = {}
    for kind in ("target", "negative"):
        rows = [r for r in runs if r["kind"] == kind]
        table: dict = {}
        for r in rows:
            if not r["fired"]:
                c = r.get("cause") or "NO_RECEIPT"
                e = table.setdefault(c, {"count": 0, "queries": {}, "details": {}})
                e["count"] += 1
                e["queries"][r["key"]] = e["queries"].get(r["key"], 0) + 1
                d = str(r.get("detail"))
                e["details"][d] = e["details"].get(d, 0) + 1
        fired = sum(1 for r in rows if r["fired"])
        out[kind] = {"n": len(rows), "fired": fired,
                     "firing_rate": (round(fired / len(rows), 3) if rows else None),
                     "activated": sum(1 for r in rows if r["activated"]),
                     "causes": dict(sorted(table.items(), key=lambda kv: (-kv[1]["count"], kv[0])))}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", required=True, help="cumulative JSON artifact (created if missing)")
    ap.add_argument("--batch", required=True, help="batch label, e.g. A1")
    ap.add_argument("--question", required=True, help="the question THIS batch answers (recorded)")
    ap.add_argument("--run", action="append", default=[], metavar="KEY[:N]",
                    help="bank key, optionally repeated N times (order preserved)")
    ap.add_argument("--flag-off", action="store_true", help="send corpus_explorer=false (pre-feature path)")
    ap.add_argument("--owner-approved", action="store_true", help="owner approved passing the 24-run line")
    args = ap.parse_args()

    path = pathlib.Path(args.artifact)
    art = json.loads(path.read_text()) if path.exists() else {
        "contract": "corpus-explore-ce8-firing-attribution-v1", "corpus": "cinema", "mode": "FAST",
        "fired_definition": "explorer added >=1 CORPUS_EXPLORE subquery to a plan whose retrieval ran",
        "batches": []}
    order: list[str] = []
    for spec in args.run:
        key, _, n = spec.partition(":")
        if key not in BANK:
            print(f"unknown bank key: {key}", file=sys.stderr)
            return 2
        order.extend([key] * int(n or 1))
    if not order or len(order) > 8:
        print("a batch is 1..8 live executions", file=sys.stderr)
        return 2
    done = sum(len(b["runs"]) for b in art["batches"])
    if done + len(order) > ASK_LINE and not args.owner_approved:
        print(f"REFUSED: {done} done + {len(order)} would pass the {ASK_LINE}-run ask line. Ask the owner.",
              file=sys.stderr)
        return 3

    runs = []
    for i, key in enumerate(order):
        kind, q = BANK[key]
        r = probe(q, corpus_explorer=not args.flag_off)
        r.update({"key": key, "kind": kind, "seq": done + i + 1, "flag_off": bool(args.flag_off)})
        runs.append(r)
        print(f"[{r['seq']:02d} {key:26s}] fired={r['fired']!s:5} cause={r['cause']} detail={r['detail']} "
              f"act={r['n_activations']} ce_sq={r['n_ce_subqueries']} intent={r['plan']['intent']} "
              f"fallback={r['plan']['fallback']} {r['latency_s']}s err={r['err']}", flush=True)
    art["batches"].append({"batch": args.batch, "question": args.question, "flag_off": bool(args.flag_off),
                           "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "runs": runs})
    on = [r for b in art["batches"] if not b.get("flag_off") for r in b["runs"]]
    art["n_live_executions"] = sum(len(b["runs"]) for b in art["batches"])
    art["cause_table"] = cause_table(on)
    art["receipt_summary"] = summarize([r["firing"] for r in on if r["firing"]])
    art["no_receipt"] = [r["key"] for r in on if not r["firing"]]
    path.write_text(json.dumps(art, indent=1))
    print(f"\nTOTAL live executions: {art['n_live_executions']}")
    print(json.dumps(art["cause_table"], indent=1))
    print(f"ARTIFACT {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

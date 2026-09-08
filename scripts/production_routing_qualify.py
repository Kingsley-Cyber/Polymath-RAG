#!/usr/bin/env python
"""PRODUCTION-ROUTING-QUALIFY-V1 — the intent-aware stack, qualified for non-regression.

FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 "production routing qualification": with the intent
policy ON, the whole routing stack (intent → budget → the additive lanes: dual-read /
profile-atom / resolution-lift, micro-latent, intent breadth) must NOT regress the frozen
gold. Everything is additive + unioned last, so `gold_in_union` can only stay or rise — this
proves it empirically over the frozen L (exact identifiers) + B (grounded QA) fixtures.

For each query it computes the intent (`classify_intent`), builds the intent budget
(`apply_intent_policy`), and calls the exact live function (`chat_retrieve_v2`) over the live
Qdrant — policy OFF (default budget) vs ON — comparing `gold_in_union`. Read-only. Exit
non-zero if ANY gold present with the policy off is lost with it on (a real regression).

    .venv/bin/python scripts/production_routing_qualify.py --corpus cinema \
        --out docs/wiki/experiments/production-routing-qualify-2026-09-08.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "shared", ROOT / "orchestrator", ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

FIXTURES = {"L": ROOT / "eval" / "fixtures" / "chat_lexical_L.json",
            "B": ROOT / "eval" / "fixtures" / "chat_baseline_B.json"}


def _questions(path: Path, corpus_id: str):
    d = json.loads(path.read_text())
    items = d.get("questions") if isinstance(d, dict) else d
    return [q for q in (items or []) if q.get("corpus_id") == corpus_id]


def _gold(q: dict) -> set[str]:
    g = set(q.get("gold_chunk_ids") or [])
    if q.get("gold_chunk_id"):
        g.add(q["gold_chunk_id"])
    return g


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--fixtures", default="L,B")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    os.environ.setdefault("POLYMATH_CHAT_RERANK_DEADLINE_S", "2")
    from orchestrator.api.chat_retrieval import chat_retrieve_v2, default_budget
    from polymath_shared.query_intent import apply_intent_policy, classify_intent

    def union(q, budget):
        res = chat_retrieve_v2(q["question"], args.corpus, exact_terms=tuple(q.get("exact_terms") or ()), budget=budget)
        return set((res.get("trace") or {}).get("funnel_union") or [])

    report = {"corpus": args.corpus, "fixtures": {}, "regressions": []}
    ok = True
    for key in [f.strip() for f in args.fixtures.split(",") if f.strip()]:
        qs = _questions(FIXTURES[key], args.corpus)
        if args.limit:
            qs = qs[: args.limit]
        off_hits = on_hits = 0
        rows = []
        for q in qs:
            gold = _gold(q)
            intent = classify_intent(q["question"], exact_terms=tuple(q.get("exact_terms") or ()))
            off_u = union(q, default_budget())
            on_u = union(q, apply_intent_policy(intent, default_budget()))
            gio_off, gio_on = bool(gold & off_u), bool(gold & on_u)
            off_hits += int(gio_off)
            on_hits += int(gio_on)
            regressed = gio_off and not gio_on
            if regressed:
                ok = False
                report["regressions"].append({"fixture": key, "intent": intent, "q": q["question"][:80]})
            rows.append({"intent": intent, "gold_in_union_off": gio_off, "gold_in_union_on": gio_on,
                         "union_off": len(off_u), "union_on": len(on_u), "regressed": regressed})
        n = len(qs) or 1
        report["fixtures"][key] = {"n": len(qs), "gold_in_union_off": round(off_hits / n, 3),
                                   "gold_in_union_on": round(on_hits / n, 3),
                                   "no_regression": on_hits >= off_hits and not any(r["regressed"] for r in rows),
                                   "rows": rows}
        print(f"[{key}] n={len(qs)} gold_in_union off={off_hits}/{len(qs)} on={on_hits}/{len(qs)} "
              f"regressions={sum(1 for r in rows if r['regressed'])}")

    report["passed"] = ok
    print(f"\n[production-routing-qualify] {'PASS' if ok else 'FAIL'} — intent-aware stack non-regressive: {ok}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"[production-routing-qualify] wrote {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

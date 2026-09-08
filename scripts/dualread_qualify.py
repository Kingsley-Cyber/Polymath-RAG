#!/usr/bin/env python
"""DUALREAD-QUALIFY-V1 — the S9 flag-on qualification (RETRIEVAL-MIGRATION §17).

The S9 gate is "frozen evaluation non-regression + exact-lookup control passes". The
flag-OFF non-regression is proven byte-identically by `scripts/chat_regression.py --check`
(lane E empty ⇒ union unchanged). This script proves the flag-ON half IN-PROCESS, calling
the exact function the live path calls (`chat_retrieve_v2`) over the live Qdrant, with
`POLYMATH_CHAT_DUALREAD_ENABLED` OFF then ON, and asserting:

  * EXACT-LOOKUP CONTROL — on the L fixture (identifiers in ≤2 child chunks), the gold
    chunk stays in the union with dual-read ON: `gold_in_union_on >= gold_in_union_off`
    for EVERY question (the additive union unions lane E LAST, so it can only add — this
    confirms it empirically and would catch any accidental removal).
  * GROUNDED NON-REGRESSION — same property on the B fixture (grounded QA).
  * CONTRIBUTION — how many turns lane E actually fed (the mapped-cohort docs).

No HTTP backend needed (only Qdrant + the embedder). Read-only. Exit non-zero if ANY
gold chunk present with the flag off drops out with it on (a real regression).

    .venv/bin/python scripts/dualread_qualify.py --corpus cinema \
        --out docs/wiki/experiments/dualread-qualify-2026-09-07.json
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

FIXTURES = {
    "L": ROOT / "eval" / "fixtures" / "chat_lexical_L.json",
    "B": ROOT / "eval" / "fixtures" / "chat_baseline_B.json",
}


def _questions(fixture_path: Path, corpus_id: str) -> list[dict]:
    d = json.loads(fixture_path.read_text())
    items = d.get("questions") if isinstance(d, dict) else d
    return [q for q in (items or []) if q.get("corpus_id") == corpus_id]


def _gold_ids(q: dict) -> set[str]:
    g = set(q.get("gold_chunk_ids") or [])
    if q.get("gold_chunk_id"):
        g.add(q["gold_chunk_id"])
    return g


def _run(chat_retrieve_v2, q: dict, corpus_id: str) -> dict:
    exact = tuple(q.get("exact_terms") or ())
    res = chat_retrieve_v2(q["question"], corpus_id, exact_terms=exact)
    tr = res.get("trace") or {}
    return {"union": set(tr.get("funnel_union") or []),
            "dualread_size": (tr.get("lane_sizes") or {}).get("dualread", 0),
            "resolved_parents": (tr.get("dualread") or {}).get("resolved_parents", 0)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--fixtures", default="L,B")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    # keep the reranker from stalling the in-process call if its sidecar is down — the union
    # (what we measure) is computed BEFORE the judge, so a short judge deadline is harmless.
    os.environ.setdefault("POLYMATH_CHAT_RERANK_DEADLINE_S", "2")
    from orchestrator.api.chat_retrieval import chat_retrieve_v2  # noqa: E402

    def with_flag(on: bool):
        if on:
            os.environ["POLYMATH_CHAT_DUALREAD_ENABLED"] = "1"
        else:
            os.environ.pop("POLYMATH_CHAT_DUALREAD_ENABLED", None)

    report = {"corpus": args.corpus, "fixtures": {}, "regressions": []}
    overall_ok = True
    for key in [f.strip() for f in args.fixtures.split(",") if f.strip()]:
        qs = _questions(FIXTURES[key], args.corpus)
        if args.limit:
            qs = qs[: args.limit]
        rows, off_hits, on_hits, contributed, both = [], 0, 0, 0, 0
        for q in qs:
            gold = _gold_ids(q)
            with_flag(False)
            off = _run(chat_retrieve_v2, q, args.corpus)
            with_flag(True)
            on = _run(chat_retrieve_v2, q, args.corpus)
            gio_off = bool(gold & off["union"])
            gio_on = bool(gold & on["union"])
            off_hits += int(gio_off)
            on_hits += int(gio_on)
            contributed += int(on["dualread_size"] > 0)
            regressed = gio_off and not gio_on          # gold present OFF, lost ON = real regression
            if regressed:
                overall_ok = False
                report["regressions"].append({"fixture": key, "question": q["question"][:80],
                                              "gold": sorted(gold)})
            rows.append({"q": q["question"][:70], "term": q.get("term"),
                         "gold_in_union_off": gio_off, "gold_in_union_on": gio_on,
                         "dualread_children": on["dualread_size"], "resolved_parents": on["resolved_parents"],
                         "regressed": regressed})
            both += int(gio_off and gio_on)
        n = len(qs) or 1
        report["fixtures"][key] = {
            "n": len(qs),
            "gold_in_union_off": round(off_hits / n, 3),
            "gold_in_union_on": round(on_hits / n, 3),
            "no_regression": on_hits >= off_hits and not any(r["regressed"] for r in rows),
            "turns_dualread_contributed": contributed,
            "rows": rows,
        }
        with_flag(False)
        print(f"[{key}] n={len(qs)} gold_in_union off={off_hits}/{len(qs)} on={on_hits}/{len(qs)} "
              f"dualread_contributed={contributed} regressions={sum(1 for r in rows if r['regressed'])}")

    report["passed"] = overall_ok
    print(f"\n[dualread-qualify] {'PASS' if overall_ok else 'FAIL'} — exact-lookup control preserved: {overall_ok}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"[dualread-qualify] wrote {args.out}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

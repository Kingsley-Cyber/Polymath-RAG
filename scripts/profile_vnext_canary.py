#!/usr/bin/env python
"""PROFILE-VNEXT-CANARY-V1 — the S5 fingerprint-budget quality/cost/latency canary.

RETRIEVAL-MIGRATION-DEPENDENCY-V1 §18 / DOCUMENT-SEMANTIC-INDEX-V1 slice S5: benchmark
the adaptive `DocumentFingerprint` at 500 / 1000 / 1500 / 2000 tokens on a SMALL
controlled real-document cohort and pick the smallest budget whose profile quality has
plateaued and shows no late-structure (first-400) bias.

This SPENDS provider quota (owner-authorized controlled canary): one `groq/compound`
profile call per (doc, budget) through the EXISTING isolated `doc_profile` pool
(`workers.doc_profile_worker._pool_complete`) — no second scheduler, no new provider
path. Paced sequentially so it does not oversubscribe the shared account budget.

    .venv/bin/python scripts/profile_vnext_canary.py --preflight            # 1 call
    .venv/bin/python scripts/profile_vnext_canary.py --corpus cinema --docs 5

Records evidence JSON under docs/wiki/experiments/ and prints a per-budget summary.
Read-only against Postgres; makes NO change to fleet config, schema, or the live
profile stage. Reuses `fingerprint` (deterministic) + `profile_prompt_vnext` + the
pool; the compiler switch is S8 (this canary counts raw items, it does not persist).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "shared", ROOT / "workers"):
    sys.path.insert(0, str(_p))

from polymath_shared.db import tx  # noqa: E402
from polymath_shared.document_profile import fingerprint as FP  # noqa: E402
from polymath_shared.document_profile import profile_prompt_vnext as PP  # noqa: E402

DEFAULT_BUDGETS = (500, 1000, 1500, 2000)
_WORD_RE = re.compile(r"[a-z][a-z0-9'\-]{2,}")
_STOP = FP._ps.STOP_TERMS  # reuse the skeleton stop list


def _load_cohort(corpus_id: str, n: int) -> list[tuple[dict, list[dict]]]:
    with tx() as conn:
        docs = conn.execute(
            "SELECT doc_id, corpus_id, source_name, media_type, frontmatter, content_hash "
            "FROM documents WHERE corpus_id=%s ORDER BY source_name LIMIT %s", (corpus_id, n)).fetchall()
        out = []
        for d in docs:
            parents = [
                {"chunk_index": r[0], "char_start": r[1], "char_end": r[2], "heading_path": r[3],
                 "text": r[4], "region_role": r[5]}
                for r in conn.execute(
                    "SELECT chunk_index, char_start, char_end, heading_path, text, region_role FROM chunks "
                    "WHERE doc_id=%s AND tier='parent' ORDER BY chunk_index", (d[0],)).fetchall()]
            out.append(({"doc_id": d[0], "corpus_id": d[1], "source_name": d[2], "media_type": d[3],
                         "frontmatter": d[4] or {}, "content_hash": d[5]}, parents))
        return out


def _parse_items(raw: str) -> dict[str, list[str]]:
    """Light label parse (the S8 compiler owns the real one): label -> list of items,
    splitting a single labelled line's value on ',' / ';' so 'TERM: a, b, c' counts 3."""
    items: dict[str, list[str]] = {}
    for line in (raw or "").splitlines():
        if ":" not in line:
            continue
        label, _, val = line.partition(":")
        label = label.strip()
        if not label or label == "END" or " " in label:
            continue
        vals = [v.strip() for v in re.split(r"[;,]", val) if v.strip()]
        items.setdefault(label, []).extend(vals)
    return items


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD_RE.findall((text or "").lower()) if t not in _STOP}


def _late_structure_ratio(items: dict[str, list[str]], parents: list[dict]) -> float | None:
    """Fraction of profile routing terms (SEARCH/Q/TOPIC/TERM) whose content tokens
    appear in the document's SECOND half (by source order), among terms that appear in
    EITHER half. ~0.5 is balanced full-document coverage; near 0 is first-400 bias."""
    body = [p for p in parents if str(p.get("text") or "").strip()]
    body.sort(key=lambda r: (r.get("chunk_index") is None, r.get("chunk_index") or 0, r.get("char_start") or 0))
    if len(body) < 4:
        return None
    mid = len(body) // 2
    first = _tokens(" ".join(str(p["text"]) for p in body[:mid]))
    second = _tokens(" ".join(str(p["text"]) for p in body[mid:]))
    terms: list[str] = []
    for lab in ("SEARCH", "Q", "TOPIC", "TERM"):
        terms.extend(items.get(lab, []))
    in_first = in_second = 0
    for term in terms:
        tt = _tokens(term)
        if not tt:
            continue
        f, s = bool(tt & first), bool(tt & second)
        if s:
            in_second += 1
        if f or s:
            # counts toward the denominator
            pass
        if f and not s:
            in_first += 1
    denom = in_first + in_second
    return round(in_second / denom, 3) if denom else None


def _run_one(doc: dict, parents: list[dict], budget: int) -> dict:
    import workers.doc_profile_worker as W
    fp = FP.build_fingerprint(doc, parents, budget_tokens=budget)
    system, user = PP.build_vnext_profile_prompt(fp)
    in_tok = FP.est_tokens(system) + FP.est_tokens(user)
    t0 = time.time()
    raw, err, rec = W._pool_complete(system, user, 2400, run_key=f"s5-canary-{doc['doc_id'][:8]}-{budget}")
    wall = round(time.time() - t0, 2)
    items = _parse_items(raw) if raw else {}
    field_labels = sorted(items)
    total_items = sum(len(v) for v in items.values())
    return {
        "doc": doc["source_name"], "budget": budget, "parents": len(parents),
        "fingerprint_used": fp.used_total, "coverage_samples": fp.sources["coverage_samples"],
        "input_tokens": in_tok, "output_chars": len(raw or ""), "latency_s": wall,
        "lane": rec.get("lane"), "model": rec.get("model"), "error": err,
        "fields_present": len(field_labels), "field_labels": field_labels, "total_items": total_items,
        "research_tags_present": sum(1 for t in FP.RESEARCH_INDEX_TAGS if t in items),
        "late_structure_ratio": _late_structure_ratio(items, parents),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="cinema")
    ap.add_argument("--docs", type=int, default=5)
    ap.add_argument("--budgets", default=",".join(map(str, DEFAULT_BUDGETS)))
    ap.add_argument("--preflight", action="store_true", help="one (doc, budget=1000) call only")
    ap.add_argument("--pace-s", type=float, default=1.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    budgets = [1000] if args.preflight else [int(b) for b in args.budgets.split(",")]
    cohort = _load_cohort(args.corpus, 1 if args.preflight else args.docs)
    if not cohort:
        print(f"no docs in corpus {args.corpus}", file=sys.stderr)
        return 1
    rows: list[dict] = []
    for doc, parents in cohort:
        for b in budgets:
            r = _run_one(doc, parents, b)
            rows.append(r)
            print(f"  b={b:<4} {r['doc'][:38]:38} in≈{r['input_tokens']:<5} {r['latency_s']:>5}s "
                  f"fields={r['fields_present']} tags={r['research_tags_present']} "
                  f"items={r['total_items']} late={r['late_structure_ratio']} err={r['error']}")
            time.sleep(args.pace_s)

    # per-budget aggregate
    def _mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 3) if xs else None
    summary = {}
    for b in budgets:
        br = [r for r in rows if r["budget"] == b]
        ok = [r for r in br if not r["error"]]
        summary[b] = {
            "n": len(br), "ok": len(ok), "errors": len(br) - len(ok),
            "mean_input_tokens": _mean([r["input_tokens"] for r in br]),
            "mean_latency_s": _mean([r["latency_s"] for r in ok]),
            "mean_items": _mean([r["total_items"] for r in ok]),
            "mean_fields": _mean([r["fields_present"] for r in ok]),
            "mean_research_tags": _mean([r["research_tags_present"] for r in ok]),
            "mean_late_structure": _mean([r["late_structure_ratio"] for r in ok]),
        }
    print("\n=== per-budget summary ===")
    print(f"  {'budget':>6} {'ok/n':>6} {'in_tok':>7} {'lat_s':>6} {'items':>6} {'fields':>7} {'tags':>5} {'late':>6}")
    for b in budgets:
        s = summary[b]
        print(f"  {b:>6} {str(s['ok'])+'/'+str(s['n']):>6} {str(s['mean_input_tokens']):>7} "
              f"{str(s['mean_latency_s']):>6} {str(s['mean_items']):>6} {str(s['mean_fields']):>7} "
              f"{str(s['mean_research_tags']):>5} {str(s['mean_late_structure']):>6}")

    payload = {"contract": "profile-vnext-canary-v1", "corpus": args.corpus,
               "cohort": [d["source_name"] for d, _ in cohort], "budgets": budgets,
               "rows": rows, "summary": summary}
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2))
        print(f"\nevidence -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

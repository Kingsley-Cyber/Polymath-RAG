#!/usr/bin/env python3
"""JUDGE-FAST-PATH-V1 benchmark: the production judge (fp32, untruncated 4000-char surfaces) against fp16 and/or
256-token truncation on REAL (query, candidate) pairs — the frozen fixture-B plans' retrieval queries and the fusion
prefix (first 24 union ids) recorded by the acceptance modes replay, texts read from Postgres exactly as the chat path
sends them (client cap 4000 chars).

Configs are `<dtype>:<max_length>` and run interleaved per question (rotating order) so every config sees the same
GPU contention; each pass is ONE forward pass over the question's pairs under an interactive Metal lease, inside
torch.inference_mode. Reported per config: pass ms p50/p90, ms per pair, non-finite scores, and agreement with the
reference config (the first one): Spearman rho, Kendall tau, top-1 / top-5 / top-8 overlap.

Usage (repo root, .env sourced):
  .venv/bin/python scripts/rerank_judge_bench.py --tag judge-bench --questions 10 \
      --configs fp32:8192,fp32:256,fp16:8192,fp16:256
Writes docs/wiki/experiments/rerank-judge-bench-<tag>.{json,md}. Read-only against the stores; no sidecar involved.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
OUT_DIR = ROOT / "docs" / "wiki" / "experiments"
CLIENT_SURFACE_CHARS = 4000       # polymath_shared.rerank.RERANK_MAX_SURFACE_CHARS


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: -xs[i])
    r = [0.0] * len(xs)
    for pos, i in enumerate(order):
        r[i] = float(pos)
    return r


def spearman(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return 1.0
    ra, rb = _ranks(a), _ranks(b)
    d2 = sum((x - y) ** 2 for x, y in zip(ra, rb))
    return round(1 - 6 * d2 / (n * (n * n - 1)), 4)


def kendall(a: list[float], b: list[float]) -> float:
    n = len(a)
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = (a[i] - a[j]) * (b[i] - b[j])
            if s > 0:
                conc += 1
            elif s < 0:
                disc += 1
    tot = conc + disc
    return round((conc - disc) / tot, 4) if tot else 1.0


def topk_overlap(a: list[float], b: list[float], k: int) -> float:
    ta = set(sorted(range(len(a)), key=lambda i: -a[i])[:k]); tb = set(sorted(range(len(b)), key=lambda i: -b[i])[:k])
    return round(len(ta & tb) / max(1, min(k, len(a))), 3)


def _med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 1) if xs else None


def _p90(xs):
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    return round(xs[min(len(xs) - 1, int(round(0.9 * (len(xs) - 1))))], 1) if xs else None


def load_pairs(n_questions: int, prefix: int) -> list[dict]:
    import psycopg
    plans = json.loads((ROOT / "eval/fixtures/chat_baseline_B_plans.json").read_text())["plans"]
    modes = json.loads((ROOT / "docs/wiki/experiments/chat-m-replay-final-B-modes.json").read_text())["results"]
    hybrid = {r["idx"]: r for r in modes if r["arm"] == "HYBRID" and not r.get("error") and r.get("union_ids")}
    dsn = os.environ.get("POLYMATH_PG_DSN") or os.environ.get("POLYMATH_TEST_DSN")
    if not dsn:
        sys.exit("POLYMATH_PG_DSN not set — source .env")
    out = []
    with psycopg.connect(dsn) as conn:
        for plan in plans:
            idx = int(plan["idx"])
            if idx not in hybrid or len(out) >= n_questions:
                continue
            ids = hybrid[idx]["union_ids"][:prefix]
            rows = conn.execute("SELECT chunk_id, text FROM chunks WHERE chunk_id = ANY(%s)", (ids,)).fetchall()
            text = {cid: (t or "")[:CLIENT_SURFACE_CHARS] for cid, t in rows}
            docs = [text[c] for c in ids if c in text]
            if len(docs) < prefix // 2:
                continue
            out.append({"idx": idx, "query": plan.get("retrieval_query") or plan["question"], "docs": docs,
                        "doc_chars": [len(d) for d in docs]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", default="judge-bench")
    ap.add_argument("--questions", type=int, default=10)
    ap.add_argument("--prefix", type=int, default=24, help="pairs per question (the chat judge prefix)")
    ap.add_argument("--configs", default="fp32:8192,fp32:256,fp16:8192,fp16:256", help="<dtype>:<max_length>,…; the first is the reference")
    ap.add_argument("--repeats", type=int, default=1, help="passes per question per config (timing only)")
    a = ap.parse_args()
    import torch
    from sentence_transformers import CrossEncoder
    from polymath_shared.metal import device_lease

    configs = [(c.split(":")[0].strip().lower(), int(c.split(":")[1])) for c in a.configs.split(",") if c.strip()]
    dtypes = sorted({d for d, _ in configs})
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    manifest = ROOT / "sidecars/reranker/manifest.toml"
    import tomllib
    m = tomllib.loads(manifest.read_text())["identity"]["model"]
    cache = Path.home() / ".cache" / "polymath" / "reranker"
    models = {}
    for d in dtypes:
        kw = {"torch_dtype": {"fp16": torch.float16, "bf16": torch.bfloat16}[d]} if d != "fp32" else None
        t0 = time.perf_counter()
        ce = CrossEncoder(m["id"], revision=m["revision"], cache_folder=str(cache), max_length=8192, model_kwargs=kw)
        ce.model.to(device)
        if kw:
            ce.model.to(kw["torch_dtype"])
        ce.model.eval()
        models[d] = ce
        print(f"loaded {d} in {time.perf_counter() - t0:.1f}s", flush=True)
    questions = load_pairs(a.questions, a.prefix)
    print(f"{len(questions)} questions × {a.prefix} pairs; device {device}; configs {configs}", flush=True)

    def run(cfg, q) -> tuple[list[float], float]:
        d, ml = cfg
        ce = models[d]
        ce.max_length = ml                                  # sentence-transformers truncates every pair to this many tokens
        pairs = [[q["query"], doc] for doc in q["docs"]]
        with device_lease("interactive", what="judge-bench"):
            t0 = time.perf_counter()
            with torch.inference_mode():
                sc = ce.predict(pairs, batch_size=len(pairs), show_progress_bar=False)
            if device == "mps":
                torch.mps.synchronize()
            ms = (time.perf_counter() - t0) * 1000
        return [float(x) for x in sc], round(ms, 1)

    results = {f"{d}:{ml}": {"pass_ms": [], "nonfinite": 0, "spearman": [], "kendall": [], "top1": [], "top5": [], "top8": []} for d, ml in configs}
    per_q = []
    for qi, q in enumerate(questions):
        order = configs[qi % len(configs):] + configs[:qi % len(configs)]      # rotate the arm order per question
        scores = {}
        for cfg in order:
            for _ in range(a.repeats):
                sc, ms = run(cfg, q)
                results[f"{cfg[0]}:{cfg[1]}"]["pass_ms"].append(ms)
            scores[cfg] = sc
            results[f"{cfg[0]}:{cfg[1]}"]["nonfinite"] += sum(1 for x in sc if not math.isfinite(x))
        ref = scores[configs[0]]
        row = {"idx": q["idx"], "pairs": len(q["docs"]), "doc_chars_p50": _med(q["doc_chars"])}
        for cfg in configs:
            key = f"{cfg[0]}:{cfg[1]}"; sc = scores[cfg]
            clean = [(x, y) for x, y in zip(ref, sc) if math.isfinite(x) and math.isfinite(y)]
            rx, ry = [x for x, _ in clean], [y for _, y in clean]
            stats = {"spearman": spearman(rx, ry), "kendall": kendall(rx, ry), "top1": topk_overlap(rx, ry, 1), "top5": topk_overlap(rx, ry, 5), "top8": topk_overlap(rx, ry, 8)}
            for k, v in stats.items():
                results[key][k].append(v)
            row[key] = {"ms": results[key]["pass_ms"][-1], **stats}
        per_q.append(row)
        print(f"[{q['idx']:02d}] " + "  ".join(f"{k}: {row[k]['ms']:.0f}ms ρ{row[k]['spearman']} top8 {row[k]['top8']}" for k in results), flush=True)

    summary = {"tag": a.tag, "run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "device": device, "model": m["id"],
               "questions": len(questions), "pairs_per_question": a.prefix, "reference": f"{configs[0][0]}:{configs[0][1]}", "per_config": {}}
    for key, r in results.items():
        n_pairs = a.prefix
        summary["per_config"][key] = {"pass_ms_p50": _med(r["pass_ms"]), "pass_ms_p90": _p90(r["pass_ms"]), "ms_per_pair_p50": round((_med(r["pass_ms"]) or 0) / n_pairs, 1),
                                      "nonfinite": r["nonfinite"], "spearman_mean": round(statistics.mean(r["spearman"]), 4) if r["spearman"] else None,
                                      "spearman_min": min(r["spearman"]) if r["spearman"] else None, "kendall_mean": round(statistics.mean(r["kendall"]), 4) if r["kendall"] else None,
                                      "top1_agreement": round(statistics.mean(r["top1"]), 3) if r["top1"] else None, "top5_overlap": round(statistics.mean(r["top5"]), 3) if r["top5"] else None,
                                      "top8_overlap": round(statistics.mean(r["top8"]), 3) if r["top8"] else None}
    ref_ms = summary["per_config"][summary["reference"]]["pass_ms_p50"] or 1
    for key in summary["per_config"]:
        summary["per_config"][key]["speedup_vs_reference"] = round(ref_ms / (summary["per_config"][key]["pass_ms_p50"] or 1), 2)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"rerank-judge-bench-{a.tag}.json").write_text(json.dumps({"summary": summary, "per_question": per_q}, indent=1))
    today = dt.date.today().isoformat()
    md = [f"---\ntitle: \"RERANK-JUDGE-BENCH {a.tag}: fp32 vs fp16 vs 256-token truncation on real judge pairs\"\nowner: governance\nlast_reviewed: {today}\nlast_touched: {today}\nstatus: measured\n---\n",
          f"# RERANK-JUDGE-BENCH {a.tag}", "", f"run {summary['run_utc']} · {m['id']} on {device} · {len(questions)} fixture-B questions × {a.prefix} real pairs (fusion prefix of the acceptance modes replay, texts from Postgres, client cap 4000 chars) · configs interleaved per question · reference = {summary['reference']}", "",
          "| config | pass p50 ms | pass p90 ms | ms / pair | speed-up vs reference | non-finite | Spearman mean / min | Kendall | top-1 | top-5 overlap | top-8 overlap |", "|---|" + "---|" * 10]
    for key, r in summary["per_config"].items():
        md.append(f"| {key} | {r['pass_ms_p50']} | {r['pass_ms_p90']} | {r['ms_per_pair_p50']} | {r['speedup_vs_reference']}× | {r['nonfinite']} | {r['spearman_mean']} / {r['spearman_min']} | {r['kendall_mean']} | {r['top1_agreement']} | {r['top5_overlap']} | {r['top8_overlap']} |")
    md += ["", "Per question (ms · Spearman · top-8 overlap vs reference):", ""] + [f"- q{row['idx']:02d} ({row['pairs']} pairs, doc p50 {row['doc_chars_p50']} chars): " + "; ".join(f"{k} {row[k]['ms']:.0f} ms ρ {row[k]['spearman']} top8 {row[k]['top8']}" for k in results) for row in per_q]
    (OUT_DIR / f"rerank-judge-bench-{a.tag}.md").write_text("\n".join(md) + "\n")
    print(json.dumps(summary["per_config"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

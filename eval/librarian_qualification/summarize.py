#!/usr/bin/env python3
"""Summarize a librarian qualification artifact against the mission acceptance floors (§14/§28).

Primary retrieval metric is SUCCESS@K (gold_hit): did the top-K reranked documents include at
least one gold document? — the correct metric when a query's gold is a set of ACCEPTABLE
authoritative sources (any one suffices). COVERAGE (fraction of listed gold docs retrieved) is a
secondary signal for multi-source questions. MRR is the rank of the first gold document.
Unsupported queries must NOT fabricate evidence.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
from collections import defaultdict


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def summarize(art: dict) -> dict:
    results = art["results"]
    modes = art["modes"]
    supported = [r for r in results if not r["unsupported"]]
    unsupported = [r for r in results if r["unsupported"]]
    out = {"corpus": art["corpus"], "modes": modes, "n_queries": len(results),
           "n_supported": len(supported), "n_unsupported": len(unsupported),
           "wall_s": art.get("wall_s"), "per_mode": {}, "per_category": {}, "flags": []}

    # single-target = exactly ONE acceptable gold doc (the case the MRR floor is written for)
    single = [r for r in supported if len(r.get("gold_doc_ids") or []) == 1]
    multi = [r for r in supported if len(r.get("gold_doc_ids") or []) > 1]
    for m in modes:
        hits = [r["per_mode"][m]["gold_hit"] for r in supported if m in r["per_mode"]]
        mrrs = [r["per_mode"][m]["mrr"] for r in supported if m in r["per_mode"]]
        covs = [r["per_mode"][m]["recall_at_k"] for r in supported if m in r["per_mode"]]
        precs = [r["per_mode"][m]["precision_at_k"] for r in supported if m in r["per_mode"]]
        lats = [r["per_mode"][m]["latency_s"] for r in results if m in r["per_mode"]]
        errs = [r["per_mode"][m]["error"] for r in results if m in r["per_mode"] and r["per_mode"][m]["error"]]
        # unsupported: fabricated evidence?
        halluc = [r["per_mode"][m]["hallucinated_evidence"] for r in unsupported if m in r["per_mode"]]
        declined = [r["per_mode"][m]["insufficient_declared"] for r in unsupported if m in r["per_mode"]]
        prov_complete = [(r["per_mode"][m].get("subquery_provenance") or {}).get("provenance_complete")
                         for r in results if m in r["per_mode"]]
        q0_pres = [(r["per_mode"][m].get("subquery_provenance") or {}).get("q0_preserved")
                   for r in results if m in r["per_mode"]]
        scout_on = [bool((r["per_mode"][m].get("scout") or {}).get("enabled")) for r in results if m in r["per_mode"]]
        yields = [(r["per_mode"][m].get("profile_yield") or {}).get("profile_expansion_evidence_yield")
                  for r in results if m in r["per_mode"] and r["per_mode"][m].get("profile_yield")]
        yield_pos = [1.0 if (y and y > 0) else 0.0 for y in yields]
        st_mrr = [r["per_mode"][m]["mrr"] for r in single if m in r["per_mode"]]
        mu_cov = [r["per_mode"][m]["recall_at_k"] for r in multi if m in r["per_mode"]]
        mu_hit = [1.0 if r["per_mode"][m]["gold_hit"] else 0.0 for r in multi if m in r["per_mode"]]
        out["per_mode"][m] = {
            "success_at_10": mean([1.0 if h else 0.0 for h in hits]),
            "mrr": mean(mrrs), "coverage_mean": mean(covs), "precision_mean": mean(precs),
            "single_target_mrr": mean(st_mrr), "single_target_n": len(st_mrr),
            "multi_source_success_at_10": mean(mu_hit), "multi_source_coverage": mean(mu_cov),
            "latency_p50": round(statistics.median(lats), 2) if lats else None,
            "latency_max": round(max(lats), 2) if lats else None,
            "errors": len(errs),
            "unsupported_hallucination_rate": mean([1.0 if h else 0.0 for h in halluc]),
            "unsupported_declined_rate": mean([1.0 if d else 0.0 for d in declined]),
            "provenance_complete_rate": mean([1.0 if p else 0.0 for p in prov_complete]),
            "q0_preserved_rate": mean([1.0 if p else 0.0 for p in q0_pres]),
            "scout_enabled_rate": mean([1.0 if s else 0.0 for s in scout_on]),
            "profile_expansion_queries": len(yields),
            "profile_yield_gt0_rate": mean(yield_pos),
            "profile_yield_mean": mean([y for y in yields if y is not None]),
        }

    # per-category success (for "no major class < 0.80")
    cat = defaultdict(list)
    for r in supported:
        for m in modes:
            if m in r["per_mode"]:
                cat[r["category"]].append(1.0 if r["per_mode"][m]["gold_hit"] else 0.0)
    for c, xs in sorted(cat.items()):
        out["per_category"][c] = {"success_at_10": mean(xs), "n": len(xs)}

    # sensitivity pairs: do paired queries differ in retrieval as intended?
    pairs = art.get("sensitivity_pairs") or []
    byid = {r["id"]: r for r in results}
    sens = []
    for pr in pairs:
        if len(pr) == 2 and pr[0] in byid and pr[1] in byid:
            a, b = byid[pr[0]], byid[pr[1]]
            for m in modes:
                if m in a["per_mode"] and m in b["per_mode"]:
                    da = set(a["per_mode"][m]["ranked_docs"][:10])
                    db = set(b["per_mode"][m]["ranked_docs"][:10])
                    jac = round(len(da & db) / len(da | db), 3) if (da | db) else None
                    sens.append({"pair": pr, "mode": m, "jaccard_top10": jac,
                                 "a_gold_hit": a["per_mode"][m]["gold_hit"],
                                 "b_gold_hit": b["per_mode"][m]["gold_hit"]})
    out["sensitivity"] = sens

    # mission floors
    for m in modes:
        pm = out["per_mode"][m]
        if pm["success_at_10"] is not None and pm["success_at_10"] < 0.90:
            out["flags"].append(f"{m}: success@10 {pm['success_at_10']} < 0.90")
        if pm["single_target_mrr"] is not None and pm["single_target_mrr"] < 0.80:
            out["flags"].append(f"{m}: single-target MRR {pm['single_target_mrr']} < 0.80 (n={pm['single_target_n']})")
        if pm["unsupported_hallucination_rate"]:
            out["flags"].append(f"{m}: unsupported hallucination rate {pm['unsupported_hallucination_rate']} != 0")
        if pm["errors"]:
            out["flags"].append(f"{m}: {pm['errors']} runtime errors")
        if pm["q0_preserved_rate"] not in (None, 1.0):
            out["flags"].append(f"{m}: q0_preserved_rate {pm['q0_preserved_rate']} != 1.0")
    for c, d in out["per_category"].items():
        if d["success_at_10"] is not None and d["success_at_10"] < 0.80 and c != "unsupported":
            out["flags"].append(f"category {c}: success@10 {d['success_at_10']} < 0.80 (n={d['n']})")

    # failing queries (per mode) for the repair loop
    fails = []
    for r in supported:
        for m in modes:
            d = r["per_mode"].get(m)
            if d and not d["gold_hit"]:
                fails.append({"id": r["id"], "mode": m, "category": r["category"],
                              "gold": [g[:12] for g in r["gold_doc_ids"]],
                              "ranked": [x[:12] for x in d["ranked_docs"][:8]],
                              "error": d["error"]})
    out["gold_misses"] = fails
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("artifact", nargs="?", default="")
    a = ap.parse_args()
    d = pathlib.Path("eval/librarian_qualification/results")
    art_path = pathlib.Path(a.artifact) if a.artifact else sorted(d.glob("qualification-*.json"))[-1]
    art = json.loads(art_path.read_text())
    s = summarize(art)
    print(f"# QUALIFICATION SUMMARY — {art_path.name}")
    print(f"queries={s['n_queries']} supported={s['n_supported']} unsupported={s['n_unsupported']} wall={s['wall_s']}s")
    for m, pm in s["per_mode"].items():
        print(f"\n[{m}] success@10={pm['success_at_10']} single_target_MRR={pm['single_target_mrr']}(n={pm['single_target_n']}) "
              f"multi_source_success@10={pm['multi_source_success_at_10']} coverage={pm['coverage_mean']} "
              f"prec={pm['precision_mean']} lat_p50={pm['latency_p50']}s errors={pm['errors']}")
        print(f"     unsupported: halluc={pm['unsupported_hallucination_rate']} declined={pm['unsupported_declined_rate']} "
              f"| provenance_complete={pm['provenance_complete_rate']} q0_preserved={pm['q0_preserved_rate']} scout={pm['scout_enabled_rate']}")
        print(f"     P11 yield: expansion_queries={pm['profile_expansion_queries']} yield>0_rate={pm['profile_yield_gt0_rate']} yield_mean={pm['profile_yield_mean']}")
    print("\n## per-category success@10")
    for c, d in s["per_category"].items():
        mark = "  " if (d["success_at_10"] or 0) >= 0.80 else "!!"
        print(f"  {mark} {c:22s} {d['success_at_10']} (n={d['n']})")
    print(f"\n## FLAGS ({len(s['flags'])})")
    for f in s["flags"]:
        print("  ! " + f)
    print(f"\n## gold misses ({len(s['gold_misses'])}) — repair candidates")
    for f in s["gold_misses"][:25]:
        print(f"  - {f['id']}/{f['mode']} [{f['category']}] gold={f['gold']} ranked={f['ranked'][:5]} err={f['error']}")
    outp = art_path.with_suffix(".summary.json")
    outp.write_text(json.dumps(s, indent=1))
    print(f"\nSUMMARY {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""LATENT-QUERY-FUSION-V2 · LEVEL-3 differential-QUALITY analysis (OFFLINE — no retrieval calls).

Reads the already-captured fixed-upstream artifacts and, for every V1_ONLY / V2_ONLY candidate, derives
lane-winner / top-N status, origin, C5 seat, CA4 grade, final-evidence membership, and q0/DIRECT status.
Then reports per query + aggregate the UTILITY-level differential (not composition churn).

Caveat (stated in the output): the captured `downstream` was computed on V2's evidence, so it is
meaningful for V2_ONLY candidates; V1_ONLY displacement is assessed by LINEAGE (was a lane-winner /
DIRECT dropped), not by a counterfactual V1 downstream (which would need a new retrieval — forbidden).
"""
import json, pathlib

ROOT = pathlib.Path("/Users/king/Documents/polymath-rebuild/polymath-v4/eval/wildcard_latent_knowledge")
DIRECT_ORIGINS = {"USER"}   # q0/subquery USER lanes; PRIMARY q0 role is captured as origin USER


def winner(rec):      # lane winner = local_rank 0 in ANY lane
    return any(l["local_rank"] == 0 for l in rec.get("lineage", []))

def topn(rec, n=5):
    return any(l["local_rank"] < n for l in rec.get("lineage", []))

def origins(rec):
    return sorted({l["origin"] for l in rec.get("lineage", [])})

def is_q0_direct(rec):   # a DIRECT/q0 candidate = origin USER on the primary q0 query id
    return any(l["origin"] == "USER" and str(l["query_id"]) == "q0" for l in rec.get("lineage", []))

def useful(rec):        # V2-only downstream utility: reached final OR seated OR graded
    d = rec.get("downstream") or {}
    return bool(d.get("in_final_evidence") or d.get("latent_seat") or d.get("ca4_support"))


def analyze(path):
    d = json.loads(path.read_text())
    per, agg = {}, {"n": 0, "v2_better": 0, "v1_better": 0, "equivalent": 0, "churn_no_utility": 0,
                    "v2_only_winners_preserved": 0, "v1_only_winners_displaced": 0,
                    "v2_only_useful": 0, "v2_only_useful_winners": 0,
                    "v1_only_direct_displaced": 0, "v2_only_seated": 0}
    for qid, c in d["cases"].items():
        if "error" in c:
            per[qid] = {"verdict": "AMBIGUOUS"}; continue
        v2o, v1o = c["v2_only"], c["v1_only"]
        v2_win = [r for r in v2o if winner(r)]
        v1_win = [r for r in v1o if winner(r)]
        v2_useful = [r for r in v2o if useful(r)]
        v2_useful_win = [r for r in v2_useful if winner(r)]
        v2_seated = [r for r in v2o if (r.get("downstream") or {}).get("latent_seat")]
        v1_direct = [r for r in v1o if is_q0_direct(r)]
        v2_direct = [r for r in v2o if is_q0_direct(r)]
        # per-query classification (utility-first)
        if c["identical_cap_set"]:
            verdict = "equivalent"
        elif v2_useful and not v1_win:
            verdict = "V2 better"                         # V2 admitted useful evidence, dropped no lane-winner
        elif v1_win and not v2_useful:
            verdict = "V1 better"                         # V2 dropped lane-winner(s), admitted nothing useful
        elif v2_useful and v1_win:
            verdict = "mixed"
        else:
            verdict = "composition changed, no utility difference"
        per[qid] = {
            "verdict": verdict,
            "n_v2_only": len(v2o), "n_v1_only": len(v1o),
            "v2_only_lane_winners": len(v2_win), "v1_only_lane_winners": len(v1_win),
            "v2_only_useful": len(v2_useful), "v2_only_useful_winners": len(v2_useful_win),
            "v2_only_seated_C5": len(v2_seated),
            "v1_only_direct_q0_displaced": len(v1_direct), "v2_only_direct_q0": len(v2_direct),
            "v2_useful_docs": sorted({r["doc"] for r in v2_useful}),
            "v2_useful_origins": sorted({o for r in v2_useful for o in origins(r)}),
        }
        agg["n"] += 1
        agg["v2_only_winners_preserved"] += len(v2_win)
        agg["v1_only_winners_displaced"] += len(v1_win)
        agg["v2_only_useful"] += len(v2_useful)
        agg["v2_only_useful_winners"] += len(v2_useful_win)
        agg["v1_only_direct_displaced"] += len(v1_direct)
        agg["v2_only_seated"] += len(v2_seated)
        agg[{"V2 better": "v2_better", "V1 better": "v1_better", "equivalent": "equivalent",
             "composition changed, no utility difference": "churn_no_utility", "mixed": "churn_no_utility"}[verdict]] += 1
    return {"mode": d.get("mode") or path.stem, "aggregate": agg, "per_query": per}


def main():
    out = {}
    for name, f in (("HYBRID", "CAUSAL-REPLAY-HYBRID-2026-09-19.json"),
                    ("WILDCARD", "CAUSAL-REPLAY-WILDCARD-2026-09-19.json")):
        r = analyze(ROOT / f)
        out[name] = r
        a = r["aggregate"]
        print(f"=== {name} (n={a['n']}) ===")
        print(f"  lane-winner survival:  V2 preserved (V2-only winners) = {a['v2_only_winners_preserved']}   "
              f"V1-only winners displaced = {a['v1_only_winners_displaced']}")
        print(f"  V2-only USEFUL evidence (final/seat/grade) = {a['v2_only_useful']}  "
              f"(of which lane-winners = {a['v2_only_useful_winners']})")
        print(f"  V2-only C5-seated latent = {a['v2_only_seated']}   "
              f"V1-only DIRECT/q0 displaced = {a['v1_only_direct_displaced']}")
        print(f"  per-query verdicts: V2 better={a['v2_better']} V1 better={a['v1_better']} "
              f"equivalent={a['equivalent']} churn/no-utility={a['churn_no_utility']}")
        for qid, p in r["per_query"].items():
            print(f"    {qid:22s} {p['verdict']:34s} v2useful={p.get('v2_only_useful')} "
                  f"v2win={p.get('v2_only_lane_winners')} v1win={p.get('v1_only_lane_winners')} "
                  f"seatC5={p.get('v2_only_seated_C5')} v1_direct_drop={p.get('v1_only_direct_q0_displaced')} "
                  f"docs={p.get('v2_useful_docs')}")
        print()
    pathlib.Path("/private/tmp/claude-501/-Applications/385b6f7d-af85-41ab-a699-5724b2af5173/scratchpad/f4_diffquality.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

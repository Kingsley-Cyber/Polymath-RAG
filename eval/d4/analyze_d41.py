"""D4.1 analysis: does the candidate support signal separate SUPPORTS from
TOPIC_ONLY / IRRELEVANT / CONTRADICTS on the frozen pair set?

Precision-first operating points over the entailment probability,
per-class rejection rates, query-level controls, by-text_kind quality,
and determinism.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

MODELS = ["d41_nli-deberta-v3-xsmall.json", "d41_nli-deberta-v3-base.json"]

QUERY_GROUPS = {
    "metacognition_controls": ["q1_direct_lexical", "q2_paraphrased", "q3_cross_section",
                               "q4_terminology_mismatch", "q5_summary_level",
                               "q6_child_text", "q7_graph_independent"],
    "offtopic_controls": ["u1_capital", "u2_medical", "u3_sports", "u4_product"],
    "same_domain_controls": ["u5_same_domain", "u6_keyword_trap"],
    "contradiction_controls": ["c1_contradiction", "c2_contradiction", "c3_contradiction"],
}


def analyze(path: Path) -> dict:
    data = json.loads(path.read_text())
    rows = data["runs"][0]

    def score_of(r):
        if r.get("support_score") is not None:
            return r["support_score"]
        return r.get("entail_prob") or 0.0

    def metrics(t: float) -> dict:
        tp = fp = fn = 0
        topic_rej = topic_tot = 0
        irre_rej = irre_tot = 0
        contra_rej = contra_tot = 0
        qid_decisions = {}
        for r in rows:
            sup = score_of(r) >= t
            g = r["gold_label"]
            qid_decisions.setdefault(r["query_id"], {"any_support": False,
                                                     "gold": {"SUPPORTS": 0, "TOPIC_ONLY": 0,
                                                              "IRRELEVANT": 0, "CONTRADICTS": 0}})
            qid_decisions[r["query_id"]]["gold"][g] += 1
            if sup:
                qid_decisions[r["query_id"]]["any_support"] = True
            if g == "SUPPORTS":
                if sup:
                    tp += 1
                else:
                    fn += 1
            else:
                if sup:
                    fp += 1
                if g == "TOPIC_ONLY":
                    topic_tot += 1
                    topic_rej += 0 if sup else 1
                elif g == "IRRELEVANT":
                    irre_tot += 1
                    irre_rej += 0 if sup else 1
                elif g == "CONTRADICTS":
                    contra_tot += 1
                    contra_rej += 0 if sup else 1
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        return {
            "t": t, "precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4), "false_supports": fp, "missed_supports": fn,
            "topic_only_rejection": round(topic_rej / topic_tot, 4) if topic_tot else None,
            "irrelevant_rejection": round(irre_rej / irre_tot, 4) if irre_tot else None,
            "contradiction_rejection": round(contra_rej / contra_tot, 4) if contra_tot else None,
            "qid": qid_decisions,
        }

    # score distribution
    by_gold = {"SUPPORTS": [], "TOPIC_ONLY": [], "IRRELEVANT": [], "CONTRADICTS": []}
    for r in rows:
        by_gold[r["gold_label"]].append(score_of(r))
    dist = {k: {"n": len(v), "p50": round(sorted(v)[len(v)//2], 3),
                "p90": round(sorted(v)[int(len(v)*0.9)], 3),
                "max": round(max(v), 3)} if v else None
            for k, v in by_gold.items()}

    # operating points
    points = []
    for t in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99):
        points.append(metrics(t))
    # highest-recall point with precision >= 0.95 and zero false supports
    precision_first = None
    for t in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99):
        m = metrics(t)
        if m["false_supports"] == 0:
            precision_first = m
        else:
            break
    # highest-recall point with precision >= 0.95
    best_95 = None
    for m in points:
        if m["precision"] >= 0.95:
            best_95 = m

    # by text_kind at best zero-FP threshold
    by_kind = {}
    if precision_first:
        t = precision_first["t"]
        for r in rows:
            k = r["text_kind"]
            g = r["gold_label"]
            sup = (r["entail_prob"] or 0.0) >= t
            by_kind.setdefault(k, {"S_tot": 0, "S_hit": 0, "N_tot": 0, "N_fp": 0})
            if g == "SUPPORTS":
                by_kind[k]["S_tot"] += 1
                by_kind[k]["S_hit"] += 1 if sup else 0
            else:
                by_kind[k]["N_tot"] += 1
                by_kind[k]["N_fp"] += 1 if sup else 0

    # query-level controls
    controls = {}
    for name, qids in QUERY_GROUPS.items():
        covered = 0
        abstained = 0
        for qid in qids:
            d = metrics(precision_first["t"])["qid"][qid] if precision_first else None
            if d is None:
                continue
            if d["any_support"]:
                covered += 1
            else:
                abstained += 1
        controls[name] = {"covered": covered, "abstained": abstained, "total": len(qids)}

    return {
        "model": data["model"],
        "deterministic": data["deterministic"],
        "distributions": dist,
        "operating_points": points,
        "precision_first_zero_fp": precision_first,
        "best_precision95": best_95,
        "by_text_kind": by_kind,
        "controls": controls,
    }


def main() -> int:
    out = {}
    for name in MODELS:
        a = analyze(ROOT / "eval" / "d4" / "artifacts" / name)
        out[a["model"]] = a
        print(f"=== {a['model']} deterministic={a['deterministic']}")
        print("  distributions:", json.dumps(a["distributions"]))
        for p in a["operating_points"]:
            print(f"  t={p['t']:.2f} P={p['precision']} R={p['recall']} F1={p['f1']} "
                  f"FP={p['false_supports']} FN={p['missed_supports']} "
                  f"topic_rej={p['topic_only_rejection']} irre_rej={p['irrelevant_rejection']} "
                  f"contra_rej={p['contradiction_rejection']}")
        pf = a["precision_first_zero_fp"]
        if pf:
            print(f"  zero-FP point: t={pf['t']} P={pf['precision']} R={pf['recall']} FN={pf['missed_supports']}")
        else:
            print("  zero-FP point: none")
        print("  controls:", json.dumps(a["controls"]))
        print("  by_text_kind:", json.dumps(a["by_text_kind"]))
    outpath = ROOT / "eval" / "d4" / "artifacts" / "d41_analysis.json"
    outpath.write_text(json.dumps(out, indent=1))
    print("wrote", outpath)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

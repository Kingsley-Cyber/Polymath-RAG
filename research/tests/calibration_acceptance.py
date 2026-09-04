#!/usr/bin/env python3
"""docs/25 §8 — the calibration run must prove SEMANTIC behaviour, not execution.

    python3 tests/calibration_acceptance.py --state run.json [--seed-communities r/x,r/y]

Exit 1 when any criterion fails. Thresholds are read from policies.yaml
(lived_world / provenance / calibration) and printed with every verdict so a
pass is a receipt, never a feeling. Criteria (owner, 2026-09-04):
  1. substantial concepts anchored OUTSIDE the seed population
  2. independent voices behind every kept concept
  3. cited corpus contribution across the shelf (cited rows, not returned docs)
  4. at least one field-originated product absent from corpus nouns
  5. at least one mechanism-only corpus contribution
  6. at least one hypothesis killed or reframed by field evidence
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

import graph as graphmod  # noqa: E402
import provenance as _prov  # noqa: E402
import utilization as _util  # noqa: E402

DEFAULTS = {"min_concepts_outside_seed": 2, "min_share_outside_seed": 0.5, "min_independent_voices": 3,
            "min_cited_share_of_shelf": 0.5, "min_field_originated": 1, "min_mechanism_only": 1, "min_killed_or_reframed": 1}


def _norm(c):
    return re.sub(r"^r/", "", str(c or "").strip().lower())


def evaluate(state: dict, policies: dict, seed_communities: set | None = None) -> dict:
    d = state["data"]
    cal = {**DEFAULTS, **(policies.get("calibration") or {})}
    prov = d.get("provenance") or [r for r in (_prov.lineage(c, state, policies) for c in d.get("product_concepts") or [])]
    kept = [r for r in prov if r.get("verdict") != (policies.get("provenance") or {}).get("echo_verdict", "CORPUS_ECHO_UNGROUNDED")]
    leads = {l["id"]: l for l in _all_leads(state)}
    seed = {_norm(x) for x in (seed_communities or set())}
    seed |= {_norm(l.get("community_key") or l.get("name")) for l in leads.values() if l.get("seed_population")}
    seed |= {_norm(c) for c in d.get("communities") or []}
    outside = [r for r in kept if r.get("communities") and not (set(map(_norm, r["communities"])) <= seed)]
    voices_ok = [r for r in kept if int(r.get("independent_voices") or 0) >= int(cal["min_independent_voices"])]
    cc = _prov.corpus_contribution(state)
    killed = 0
    contra_gaps = {o.get("gap_id") for o in d.get("observations") or [] if o.get("contradicts")}
    for h in d.get("hypotheses") or []:
        gaps = {g["id"] for g in d.get("gaps") or [] if g.get("hypothesis_id") == h.get("id")}
        if h.get("status") == "REJECTED" and gaps & contra_gaps:
            killed += 1
        elif h.get("status") == "CHALLENGED" and any(e.get("verdict") == "REVISE" and e.get("hypothesis_id") == h.get("id")
                                                   for e in d.get("evaluations") or []):
            killed += 1
    checks = {
        "concepts_outside_seed": {"value": len(outside), "of": len(kept), "pass": len(outside) >= int(cal["min_concepts_outside_seed"])
                                  and len(outside) >= cal["min_share_outside_seed"] * max(1, len(kept))},
        "independent_voices_per_concept": {"value": f"{len(voices_ok)}/{len(kept)}", "pass": bool(kept) and len(voices_ok) == len(kept)},
        "cited_share_of_shelf": {"value": cc["cited_share_of_shelf"], "pass": cc["cited_share_of_shelf"] >= float(cal["min_cited_share_of_shelf"])},
        "field_originated_products": {"value": sum(1 for r in kept if r.get("field_originated")), "pass": sum(1 for r in kept if r.get("field_originated")) >= int(cal["min_field_originated"])},
        "mechanism_only_corpus_contributions": {"value": cc["mechanism_only_contributions"], "pass": cc["mechanism_only_contributions"] >= int(cal["min_mechanism_only"])},
        "hypotheses_killed_or_reframed_by_field": {"value": killed, "pass": killed >= int(cal["min_killed_or_reframed"])},
    }
    return {"run_id": state.get("run_id"), "verdict": state.get("verdict"), "thresholds": cal, "seed_communities": sorted(seed),
            "checks": checks, "pass": all(c["pass"] for c in checks.values()), "lived_world": _util.compute(state).get("lived_world")}


def _all_leads(state):
    d = state["data"]
    return [l for l in (d.get("population_leads") or []) + (d.get("community_leads") or []) if isinstance(l, dict)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", required=True); ap.add_argument("--seed-communities", default="")
    a = ap.parse_args()
    state = json.load(open(a.state, encoding="utf-8"))
    rep = evaluate(state, graphmod.load_policies(), {x for x in a.seed_communities.split(",") if x.strip()})
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

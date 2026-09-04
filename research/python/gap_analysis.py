#!/usr/bin/env python3
"""DEMAND_GAP_ANALYSIS — a shared analytical operator, NOT a research mode
(docs/17 §7-9). Compares what people want/do/struggle with against what the
current market provides, and classifies the mismatch into typed gaps.

Deterministic projection: every gap it emits is derived from receipts already
in the run (divergence patterns, whitespace states, reframes, observations,
supply signals) — θ proposed those upstream; this operator only classifies.
An "unmet need" is only ONE gap type: demand can be served badly, generically,
for the wrong segment, with the wrong identity, or through the wrong channel.

Wired as `python.demand_gap_analysis` inside MARKET_DISCOVERY; other modes
run it post-terminal:  gap_analysis.py --state run.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import stable_id

GAP_TYPES = ["UNMET_NEED", "UNDERSERVED_NEED", "SEGMENT_GAP", "POSITIONING_GAP",
             "CURATION_GAP", "EXPERIENCE_GAP", "VALUE_GAP", "IDENTITY_GAP",
             "CHANNEL_GAP", "TECHNOLOGY_GAP"]

_WHITESPACE_TO_GAP = {
    "PRODUCT_WHITESPACE": "UNDERSERVED_NEED",
    "MECHANISM_WHITESPACE": "UNMET_NEED",
    "CURATION_WHITESPACE": "CURATION_GAP",
    "SUBNICHE_WHITESPACE": "SEGMENT_GAP",
    "STYLE_WHITESPACE": "IDENTITY_GAP",
    "CONTEXT_WHITESPACE": "SEGMENT_GAP",
    "VALUE_WHITESPACE": "VALUE_GAP",
}


def _add(gaps: list, seen: set, scope: str, gtype: str, basis: str, refs: list) -> None:
    gid = stable_id("dgap", scope, gtype, basis[:40])
    if gid in seen:
        return
    seen.add(gid)
    gaps.append({"id": gid, "scope_id": scope, "gap_type": gtype,
                 "basis": basis[:220], "evidence_refs": sorted(set(refs))[:8],
                 "state": "PROPOSED"})


def analyze(state: dict, policies: dict) -> list[dict]:
    d = state["data"]
    gaps: list[dict] = []
    seen: set = set()
    # channel disagreement → demand-side gap signals
    for div in d.get("signal_divergences") or []:
        sc = div.get("scope_id") or "?"
        for pat in div.get("patterns") or []:
            if pat == "PRE_CATEGORY":
                _add(gaps, seen, sc, "UNMET_NEED",
                     "workaround density high while searches frame problems, not products",
                     [div.get("id") or ""])
            elif pat == "COMMUNITY_COMMERCE_GAP":
                _add(gaps, seen, sc, "CHANNEL_GAP",
                     "active community with weak commerce reach", [div.get("id") or ""])
            elif pat == "MATURE_COMMODITY":
                _add(gaps, seen, sc, "POSITIONING_GAP",
                     "saturated generic supply — segmentation/positioning is the lever",
                     [div.get("id") or ""])
            elif pat == "EARLY_EMERGENCE":
                _add(gaps, seen, sc, "UNDERSERVED_NEED",
                     "community ahead of both search and supply", [div.get("id") or ""])
    # surviving whitespace → typed gaps (evidence already survived L4)
    for wh in d.get("whitespace_hypotheses") or []:
        if wh.get("state") in ("SUPPORTED", "REFINED", "PROPOSED"):
            gtype = _WHITESPACE_TO_GAP.get(wh.get("type") or "", None)
            if gtype:
                _add(gaps, seen, wh.get("market_scope_id") or "?", gtype,
                     wh.get("observed_mismatch") or "", wh.get("supporting_signals") or [])
    # product-anchored reframes → positioning gaps on the incumbent framing
    for rr in d.get("market_reframes") or []:
        if rr.get("user_frame_state") in ("WEAKENED", "CONTRADICTED"):
            _add(gaps, seen, rr.get("evidence_supported_frame") or "?",
                 "POSITIONING_GAP",
                 f"incumbent frame '{rr.get('initial_user_frame')}' misfits the actual community",
                 rr.get("evidence_refs") or [])
    # experience-gap signal: workaround evidence against an existing product
    for o in d.get("observations") or []:
        roles = set(o.get("evidence_roles") or [])
        if "WORKAROUND_EVIDENCE" in roles and "PRODUCT_COMPLAINT" in roles:
            _add(gaps, seen, o.get("scope_id") or o.get("bridge_id") or "?",
                 "EXPERIENCE_GAP",
                 "users modify/work around an existing product", [o.get("id") or ""])
    return gaps


def demand_gap_analysis(state: dict, policies: dict) -> str:
    gaps = analyze(state, policies)
    existing = {g.get("id") for g in state["data"].get("demand_gaps") or []}
    state["data"].setdefault("demand_gaps", []).extend(
        g for g in gaps if g["id"] not in existing)
    kinds = sorted({g["gap_type"] for g in state["data"]["demand_gaps"]})
    return (f"demand gap analysis: {len(state['data']['demand_gaps'])} typed gaps "
            f"({', '.join(kinds) or 'none'}) — unmet need is only one kind of gap")


def main():
    import graph as graphmod
    import models
    p = argparse.ArgumentParser(prog="gap_analysis")
    p.add_argument("--state", required=True)
    args = p.parse_args()
    state = models.load_state(args.state)
    note = demand_gap_analysis(state, graphmod.load_policies())
    models.save_state(state, args.state)
    print(json.dumps({"ok": True, "note": note,
                      "gaps": state["data"].get("demand_gaps") or []}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

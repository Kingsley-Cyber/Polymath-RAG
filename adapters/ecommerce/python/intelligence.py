#!/usr/bin/env python3
"""Commercial Intelligence layer (docs/11) — shared by OPPORTUNITY_RESEARCH
and NICHE_LOADOUT. The research graph discovers truth; this layer turns that
truth into market/product/style/positioning/ad intelligence WITHOUT
re-reasoning the facts.

Hard boundaries:
  - runs strictly downstream of canonical state (usually post-terminal);
  - θ GENERATES angles/claims/briefs, φ (this module) ADMITS them: lineage
    must resolve, authority is computed (never trusted), duplicates and
    generic angles die, the surviving angles are selected as a SET;
  - admission may add intelligence objects only — it can never touch
    hypotheses, observations, verdicts or any research state
    (research verdict != marketing quality);
  - a qualified product is still qualified if this layer never runs.

  intelligence.py packet --state run.json [--out packet.json]
      sanitized generation inputs + the prompt contract for θ
  intelligence.py admit  --state run.json --file out.json
      validate / grade / dedupe / select, then merge + mirror to Work Graph
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import memory
import models

INTEL_KEYS = ["market_analysis", "style_intelligence", "market_angles",
              "product_angles", "style_angles", "collection_angles",
              "ad_angles", "creative_briefs", "storefront_strategies",
              "analysis_chains"]
ANGLE_KEYS = ["market_angles", "product_angles", "style_angles",
              "collection_angles", "ad_angles"]
_ANGLE_TYPE_BY_KEY = {"market_angles": "MARKET", "product_angles": "PRODUCT",
                      "style_angles": "STYLE", "collection_angles": "COLLECTION",
                      "ad_angles": "AD"}


def _pol(policies: dict) -> dict:
    return policies.get("commercial_intelligence") or {}


# ------------------------------------------------------------------ lineage --
def resolvable_ids(state: dict) -> set[str]:
    ids = set()
    for v in state["data"].values():
        if isinstance(v, list):
            ids |= {x["id"] for x in v if isinstance(x, dict) and x.get("id")}
    return ids


def _evidence_state(refs: list, known: set, pol: dict) -> str:
    n = len([r for r in refs or [] if r in known])
    if n >= int(pol.get("grounded_min_refs", 2)):
        return "GROUNDED"
    return "PARTIAL" if n == 1 else "SPECULATIVE"


# --------------------------------------------------------------- genericness --
_word = re.compile(r"[a-z']+")


def genericness(thesis: str, pol: dict) -> float:
    lex = [str(w).lower() for w in pol.get("genericness_lexicon") or []]
    toks = _word.findall((thesis or "").lower())
    if not toks:
        return 1.0
    text = " ".join(toks)
    hits = sum(1 for w in lex if (" " in w and w in text)) \
        + sum(1 for t in toks if t in lex)
    return round(min(1.0, hits / len(toks)), 3)


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(_word.findall(a.lower())), set(_word.findall(b.lower()))
    return len(ta & tb) / max(1, len(ta | tb))


# ------------------------------------------------------------ angle admission --
def admit_angles(angles: list[dict], key: str, state: dict, policies: dict
                 ) -> tuple[list[dict], list[str], list[dict]]:
    """φ admission: schema, resolving lineage, computed evidence_state,
    genericness, dedupe. Returns (admitted, errors, receipts)."""
    pol = _pol(policies)
    known = resolvable_ids(state)
    errors, receipts, seen_theses, out = [], [], [], []
    for i, a in enumerate(angles or []):
        errs = models.validate(a, "angle")
        if a.get("angle_type") != _ANGLE_TYPE_BY_KEY[key]:
            errs.append(f"angle_type must be {_ANGLE_TYPE_BY_KEY[key]} under {key}")
        bogus = [r for r in a.get("evidence_refs") or [] if r not in known]
        if bogus:
            errs.append(f"evidence_refs do not resolve to canonical objects: {bogus}")
        if errs:
            errors += [f"{key}[{i}]: {e}" for e in errs]
            continue
        a = dict(a)
        # authority is COMPUTED — θ's own confidence claims are overwritten
        claimed = a.get("evidence_state")
        a["evidence_state"] = _evidence_state(a["evidence_refs"], known, pol)
        if claimed and claimed != a["evidence_state"]:
            receipts.append({"id": a["id"], "check": "AUTHORITY_RECOMPUTED",
                             "claimed": claimed, "computed": a["evidence_state"]})
        a["genericness"] = genericness(a["thesis"], pol)
        dup = next((t for t in seen_theses
                    if _jaccard(a["thesis"], t) >= float(pol.get("dedupe_jaccard", 0.6))), None)
        if dup is not None:
            a["disposition"] = "REJECT"
            receipts.append({"id": a["id"], "check": "DUPLICATE_ANGLE", "of": dup})
        elif a["genericness"] >= float(pol.get("genericness_reject", 0.34)):
            a["disposition"] = "REJECT"
            receipts.append({"id": a["id"], "check": "GENERIC_ANGLE",
                             "genericness": a["genericness"]})
        elif a["evidence_state"] == "SPECULATIVE":
            a["disposition"] = "HOLD"
        else:
            a["disposition"] = "ADVANCE"
            seen_theses.append(a["thesis"])
        out.append(a)
    return out, errors, receipts


def select_angle_portfolio(angles: list[dict], policies: dict,
                           state: dict | None = None) -> dict:
    """Angles are a SET, not a top-N list: 'helps runners' four times is one
    angle. Greedy marginal gain over hook-type coverage minus redundancy.
    The user's report_angle_count preference caps size within schema bounds."""
    pol = dict(_pol(policies).get("angle_portfolio") or {})
    if state is not None:
        import settings as _settings
        pol["size_max"] = int(_settings.effective(state, "report_angle_count",
                                                  pol.get("size_max", 8)))
    pool = [a for a in angles if a.get("disposition") == "ADVANCE"]
    w_cov = float(pol.get("hook_coverage_weight", 1.0))
    w_red = float(pol.get("redundancy_penalty", 0.8))

    def value(sel):
        cov = len({a.get("hook_type") or a["angle_type"] for a in sel})
        red = sum(_jaccard(x["thesis"], y["thesis"])
                  for i, x in enumerate(sel) for y in sel[i + 1:])
        return w_cov * cov - w_red * red

    selected: list[dict] = []
    while pool and len(selected) < int(pol.get("size_max", 8)):
        base = value(selected)
        best, gain = None, None
        for a in pool:
            gv = value(selected + [a]) - base
            if gain is None or gv > gain:
                best, gain = a, gv
        if gain is not None and gain <= 0 and len(selected) >= int(pol.get("size_min", 3)):
            break
        selected.append(best)
        pool.remove(best)
    return {"selected": [a["id"] for a in selected],
            "covered_hooks": sorted({a.get("hook_type") or a["angle_type"] for a in selected}),
            "size": len(selected)}


# --------------------------------------------------- claims / chains / briefs --
def admit_claims(claims: list[dict], state: dict, policies: dict
                 ) -> tuple[list[dict], list[str], list[dict]]:
    """OBSERVED must cite resolving evidence; otherwise it is downgraded to
    INFERRED with a receipt — three authority levels never render as one
    equally-factual paragraph."""
    known = resolvable_ids(state)
    out, errors, receipts = [], [], []
    for i, c in enumerate(claims or []):
        errs = models.validate(c, "analysis_claim")
        bogus = [r for r in c.get("evidence_refs") or [] if r not in known]
        if bogus:
            errs.append(f"evidence_refs do not resolve: {bogus}")
        if errs:
            errors += [f"market_analysis[{i}]: {e}" for e in errs]
            continue
        c = dict(c)
        if c["classification"] == "OBSERVED" and not c.get("evidence_refs"):
            c["classification"] = "INFERRED"
            receipts.append({"id": c["id"], "check": "OBSERVED_DOWNGRADED",
                             "reason": "no evidence refs"})
        out.append(c)
    return out, errors, receipts


def admit_chains(chains: list[dict], state: dict, policies: dict
                 ) -> tuple[list[dict], list[str]]:
    known = resolvable_ids(state)
    links = _pol(policies).get("chain_links") or []
    out, errors = [], []
    for i, ch in enumerate(chains or []):
        errs = models.validate(ch, "analysis_chain")
        errs += [f"missing link {ln!r}" for ln in links if not ch.get(ln)]
        bogus = [r for r in ch.get("evidence") or [] if r not in known]
        if bogus:
            errs.append(f"evidence does not resolve: {bogus}")
        if errs:
            errors += [f"analysis_chains[{i}]: {e}" for e in errs]
        else:
            out.append(ch)
    return out, errors


def admit_briefs(briefs: list[dict], admitted_angles: list[dict], state: dict,
                 policies: dict) -> tuple[list[dict], list[str]]:
    known = resolvable_ids(state)
    advanced = {a["id"] for a in admitted_angles if a.get("disposition") == "ADVANCE"}
    out, errors = [], []
    for i, b in enumerate(briefs or []):
        errs = models.validate(b, "ad_creative_brief")
        if b.get("angle_id") not in advanced:
            errs.append(f"angle_id {b.get('angle_id')!r} is not an ADVANCE angle — "
                        "briefs compile only from admitted angles")
        bogus = [r for r in b.get("evidence_refs") or [] if r not in known]
        if bogus:
            errs.append(f"evidence_refs do not resolve: {bogus}")
        if errs:
            errors += [f"creative_briefs[{i}]: {e}" for e in errs]
        else:
            out.append(b)
    return out, errors


def admit_storefront(strategies: list[dict], state: dict) -> tuple[list[dict], list[str]]:
    known = resolvable_ids(state)
    out, errors = [], []
    for i, s in enumerate(strategies or []):
        errs = models.validate(s, "storefront_strategy")
        if errs:
            errors += [f"storefront_strategies[{i}]: {e}" for e in errs]
            continue
        s = dict(s)
        s["authority"] = ("EVIDENCE_GROUNDED_ANALYSIS"
                          if [r for r in s.get("evidence_refs") or [] if r in known]
                          else "CREATIVE_RECOMMENDATION")
        out.append(s)
    return out, errors


def admit_style(style: dict | list, state: dict) -> tuple[list[dict], list[str]]:
    """StyleIntelligence rows: observed entries REQUIRE evidence; inferred
    entries are creative recommendations — the authority split the report
    must be able to draw."""
    known = resolvable_ids(state)
    rows = style if isinstance(style, list) else [style] if style else []
    out, errors = [], []
    for i, s in enumerate(rows):
        if not isinstance(s, dict) or not s.get("id"):
            errors.append(f"style_intelligence[{i}]: id required")
            continue
        s = dict(s)
        kind = str(s.get("kind", "observed")).lower()
        refs = [r for r in s.get("evidence_refs") or [] if r in known]
        if kind == "observed" and not refs:
            errors.append(f"style_intelligence[{i}] ({s['id']}): observed style "
                          "signals require resolving evidence_refs — otherwise "
                          "mark kind=inferred")
            continue
        s["authority"] = "OBSERVED" if kind == "observed" else "CREATIVE_RECOMMENDATION"
        out.append(s)
    return out, errors


# ------------------------------------------------------------------- packet --
def build_packet(state: dict) -> dict:
    """Sanitized generation inputs: canonical receipts, no persuasive
    narrative, plus the output contract θ must fill."""
    d = state["data"]
    return {
        "run_id": state["run_id"],
        "verdict": state.get("verdict"),
        "signal": d.get("signal"),
        "scope": d.get("scope_request") or None,
        "world_model": d.get("world_model") or None,
        "bridges": [{"id": h.get("id"), "path": h.get("path"),
                     "target_mechanism": h.get("target_mechanism"),
                     "status": h.get("status"), "invariant": h.get("invariant")}
                    for h in d.get("hypotheses") or []],
        "observations": [{"id": o.get("id"), "quote_ref": o.get("quote_ref"),
                          "source": o.get("source"), "community": o.get("community"),
                          "evidence_roles": o.get("evidence_roles"),
                          "freshness": o.get("freshness")}
                         for o in d.get("observations") or []],
        "lived_situations": d.get("lived_situations") or [],
        "mechanisms": [{"id": m.get("id"), "name": m.get("name"),
                        "status": m.get("status")} for m in d.get("mechanisms") or []],
        "products": [{"id": p.get("id"), "product_name": p.get("product_name") or p.get("name"),
                      "status": p.get("status"), "mechanism": p.get("mechanism")}
                     for p in (d.get("leads") or d.get("loadout")
                               or d.get("product_candidates") or [])],
        "satisfaction": state.get("satisfaction"),
        "challenges": d.get("challenges") or [],
        "prompt_file": "prompts/commercial_intelligence.md",
        "output_contract": {k: "list" for k in INTEL_KEYS},
        "law": ("Every angle/claim/chain must cite evidence_refs that exist in this "
                "packet. Creative claims may never exceed the evidence. New facts "
                "are prohibited — this layer projects, it does not research."),
    }


# -------------------------------------------------------------------- admit --
def admit(state: dict, payload: dict, policies: dict) -> dict:
    illegal = [k for k in payload if k not in INTEL_KEYS]
    if illegal:
        return {"ok": False,
                "error": f"intelligence layer cannot mutate research state: {illegal}",
                "allowed": INTEL_KEYS}
    all_errors, all_receipts, admitted_angles = [], [], []
    staged: dict[str, list] = {}
    for key in ANGLE_KEYS:
        if key in payload:
            adm, errs, recs = admit_angles(payload[key], key, state, policies)
            staged[key] = adm
            all_errors += errs
            all_receipts += recs
            admitted_angles += adm
    if "market_analysis" in payload:
        adm, errs, recs = admit_claims(payload["market_analysis"], state, policies)
        staged["market_analysis"] = adm
        all_errors += errs
        all_receipts += recs
    if "analysis_chains" in payload:
        adm, errs = admit_chains(payload["analysis_chains"], state, policies)
        staged["analysis_chains"] = adm
        all_errors += errs
    if "creative_briefs" in payload:
        adm, errs = admit_briefs(payload["creative_briefs"], admitted_angles,
                                 state, policies)
        staged["creative_briefs"] = adm
        all_errors += errs
    if "storefront_strategies" in payload:
        adm, errs = admit_storefront(payload["storefront_strategies"], state)
        staged["storefront_strategies"] = adm
        all_errors += errs
    if "style_intelligence" in payload:
        adm, errs = admit_style(payload["style_intelligence"], state)
        staged["style_intelligence"] = adm
        all_errors += errs
    if all_errors:
        return {"ok": False, "schema_errors": all_errors[:20]}

    for key, items in staged.items():
        state["data"].setdefault(key, [])
        existing = {x.get("id") for x in state["data"][key] if isinstance(x, dict)}
        state["data"][key].extend(x for x in items if x.get("id") not in existing)
    portfolio = select_angle_portfolio(
        [a for k in ANGLE_KEYS for a in state["data"].get(k) or []], policies, state)
    state["angle_portfolio"] = portfolio
    return {"ok": True,
            "admitted": {k: len(v) for k, v in staged.items()},
            "receipts": all_receipts,
            "angle_portfolio": portfolio}


# ---------------------------------------------------------------------- cli --
def main():
    import graph as graphmod
    p = argparse.ArgumentParser(prog="intelligence")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("packet", "admit"):
        sp = sub.add_parser(name)
        sp.add_argument("--state", required=True)
        if name == "packet":
            sp.add_argument("--out")
        else:
            sp.add_argument("--file", required=True)
    args = p.parse_args()
    state = models.load_state(args.state)
    if args.cmd == "packet":
        packet = build_packet(state)
        text = json.dumps(packet, indent=1, ensure_ascii=False)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
            print(json.dumps({"ok": True, "packet": args.out,
                              "prompt_file": packet["prompt_file"]}))
        else:
            print(text)
        return 0
    with open(args.file, encoding="utf-8") as f:
        payload = json.load(f)
    verdict_before = (state.get("verdict"), state["status"])
    result = admit(state, payload, graphmod.load_policies())
    if not result.get("ok"):
        print(json.dumps(result, indent=1, ensure_ascii=False))
        return 1
    assert (state.get("verdict"), state["status"]) == verdict_before, \
        "intelligence admission altered the research verdict — refusing"
    models.save_state(state, args.state)
    memory.sync_work_nodes(state["run_id"], state)
    memory.record_event(state["run_id"], "INTELLIGENCE_ADMITTED",
                        {"admitted": result["admitted"],
                         "policy_hash": memory.config_hashes()["policy_hash"],
                         "receipts": result["receipts"][:20]})
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

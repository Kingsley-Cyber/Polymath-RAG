"""MARKET_DISCOVERY math (docs/12, docs/14): deterministic routing utilities.

None of these numbers is a success probability. M(s) means "worth digging
into", SignalDivergence means "the channels disagree — that disagreement is
itself information", and every formula result ships as a receipt (formula id,
inputs, weights, total, config hash) — never a bare score (docs/14 §42).
"""
from __future__ import annotations

import hashlib
import json
import re

_word = re.compile(r"[a-z0-9']+")


def _cfg_hash(weights: dict) -> str:
    return hashlib.sha256(json.dumps(weights, sort_keys=True).encode()).hexdigest()[:12]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ------------------------------------------------- market frontier utility --
def market_frontier_utility(scope: dict, policies: dict) -> dict:
    """M(s) over decomposed 0..1 features supplied WITH the scope (θ estimates
    them, each traceable to lane signals; φ only combines). Returns a receipt."""
    pol = policies["market_discovery"]["frontier"]
    w = pol["weights"]
    feats = scope.get("features") or {}
    inputs = {k: float(feats.get(k, 0)) for k in w}
    total = sum(w[k] * inputs[k] for k in w)
    pos_mass = sum(v for v in w.values() if v > 0)
    score = _clamp01(total / pos_mass)
    if score >= pol["explore_threshold"]:
        disp = "EXPLORE"
    elif score >= pol["maybe_threshold"]:
        disp = "MAYBE"
    else:
        disp = "PRUNE"
    return {"formula": "market_frontier_v1", "scope_id": scope.get("id"),
            "inputs": inputs, "weights": dict(w), "total": round(score, 3),
            "disposition": disp, "config_hash": _cfg_hash(w)}


def _scope_tokens(scope: dict) -> set:
    parts = [scope.get("market") or "", scope.get("niche") or "",
             scope.get("subniche") or ""]
    dims = scope.get("dimensions") or {}
    parts += [str(v) for v in dims.values() if v]
    return set(_word.findall(" ".join(parts).lower()))


def _similarity(a: dict, b: dict) -> float:
    ta, tb = _scope_tokens(a), _scope_tokens(b)
    return len(ta & tb) / max(1, len(ta | tb))


def diversity_select(scopes: list[dict], receipts: list[dict], policies: dict,
                     sim_fn=None) -> list[str]:
    """Greedy M'(s) = M(s) - λ·max Sim(s, selected): controlled exploration,
    so the retained set is not four names for the same audience."""
    pol = policies["market_discovery"]["frontier"]
    lam = float(pol.get("diversity_lambda", 0.5))
    kmax = int(pol.get("retain_max", 8))
    sim = sim_fn or _similarity
    by_id = {s["id"]: s for s in scopes if s.get("id")}
    pool = [r for r in receipts if r["disposition"] != "PRUNE" and r["scope_id"] in by_id]
    selected: list[str] = []
    while pool and len(selected) < kmax:
        best, best_adj = None, None
        for r in pool:
            penalty = max((sim(by_id[r["scope_id"]], by_id[sid]) for sid in selected),
                          default=0.0)
            adj = r["total"] - lam * penalty
            if best_adj is None or adj > best_adj:
                best, best_adj = r, adj
        if best_adj is not None and best_adj <= 0 and len(selected) >= int(pol.get("retain_min", 3)):
            break
        selected.append(best["scope_id"])
        pool.remove(best)
    return selected


# ----------------------------------------------------- signal divergence ----
def detect_divergence(channels: dict, policies: dict) -> dict:
    """Disagreement between search / community / commerce / supply channels is
    a first-class discovery signal, not noise (docs/12)."""
    pol = policies["market_discovery"]["divergence"]
    hi, lo = float(pol["high"]), float(pol["low"])
    c = {k: _clamp01(float(channels.get(k, 0))) for k in
         ("search_interest", "community_activity", "commerce_supply",
          "product_saturation", "workaround_density")}
    patterns = []
    if c["community_activity"] >= hi and c["search_interest"] <= lo and c["commerce_supply"] <= lo:
        patterns.append("EARLY_EMERGENCE")
    if c["search_interest"] >= hi and c["product_saturation"] >= hi and c["community_activity"] <= lo:
        patterns.append("MATURE_COMMODITY")
    if c["workaround_density"] >= hi and c["search_interest"] <= 0.5:
        patterns.append("PRE_CATEGORY")
    if c["community_activity"] >= hi and c["commerce_supply"] <= lo:
        patterns.append("COMMUNITY_COMMERCE_GAP")
    spread = round(max(c.values()) - min(c.values()), 3)
    return {"channels": c, "patterns": patterns, "spread": spread}


# ------------------------------------------------------ robustness checks ---
def rank_stability(items: list[dict], weights: dict, perturbation: float) -> dict:
    """Config weights are policy, not law — so important decisions get a
    bounded perturbation check. Perturb one weight at a time by ±p and count
    how often the top-ranked item changes. STABLE / SENSITIVE /
    HIGHLY_SENSITIVE — never a fake probability (docs/14 §43)."""
    def util(feats, w):
        pos = sum(v for v in w.values() if v > 0) or 1.0
        return sum(w[k] * float(feats.get(k, 0)) for k in w) / pos

    if len(items) < 2:
        return {"status": "STABLE", "flips": 0, "trials": 0}
    base_top = max(items, key=lambda it: util(it.get("features") or {}, weights))["id"]
    flips = trials = 0
    for key in weights:
        for direction in (1 + perturbation, 1 - perturbation):
            w2 = dict(weights)
            w2[key] = weights[key] * direction
            trials += 1
            top = max(items, key=lambda it: util(it.get("features") or {}, w2))["id"]
            if top != base_top:
                flips += 1
    ratio = flips / max(1, trials)
    status = "STABLE" if flips == 0 else ("SENSITIVE" if ratio <= 0.25 else "HIGHLY_SENSITIVE")
    return {"status": status, "flips": flips, "trials": trials,
            "base_top": base_top, "perturbation": perturbation}

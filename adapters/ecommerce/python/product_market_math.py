"""PRODUCT_ANCHORED_DISCOVERY math (docs/13, docs/14): reverse-fit routing.

R(n|p) answers "how much research budget does this product↔market bridge
deserve?" — never "will this sell". Same receipt discipline as market_math:
formula id, inputs, weights, total, config hash on every result.
"""
from __future__ import annotations

import re

import market_math as mm

_word = re.compile(r"[a-z0-9']+")


def reverse_fit_utility(bridge: dict, policies: dict) -> dict:
    """R(n|p) over decomposed 0..1 features carried on the bridge (θ estimates
    with lineage; φ combines). assumption_distance / saturation / redundancy
    carry negative weights."""
    pol = policies["product_anchored"]["reverse_fit"]
    w = pol["weights"]
    feats = bridge.get("features") or {}
    inputs = {k: float(feats.get(k, 0)) for k in w}
    total = sum(w[k] * inputs[k] for k in w)
    pos_mass = sum(v for v in w.values() if v > 0)
    score = max(0.0, min(1.0, total / pos_mass))
    if score >= pol["explore_threshold"]:
        disp = "EXPLORE"
    elif score >= pol["maybe_threshold"]:
        disp = "MAYBE"
    else:
        disp = "PRUNE"
    return {"formula": "reverse_fit_v1", "bridge_id": bridge.get("id"),
            "inputs": inputs, "weights": dict(w), "total": round(score, 3),
            "disposition": disp, "config_hash": mm._cfg_hash(w)}


def _bridge_tokens(b: dict) -> set:
    parts = [b.get("market_scope") or "", b.get("niche") or "",
             b.get("subniche") or "", b.get("meaning_id") or ""]
    parts += list(b.get("jobs") or [])
    return set(_word.findall(" ".join(str(p) for p in parts).lower()))


def _bridge_similarity(a: dict, b: dict) -> float:
    ta, tb = _bridge_tokens(a), _bridge_tokens(b)
    return len(ta & tb) / max(1, len(ta | tb))


def diversity_select_bridges(bridges: list[dict], receipts: list[dict],
                             policies: dict) -> list[str]:
    """Top bridges must be meaningfully DIFFERENT markets — not four names for
    the same audience (docs/13). Greedy adjusted-utility selection."""
    pol = policies["product_anchored"]["reverse_fit"]
    lam = float(pol.get("diversity_lambda", 0.5))
    target = int(pol.get("bridge_target", 3))
    by_id = {b["id"]: b for b in bridges if b.get("id")}
    pool = [r for r in receipts if r["disposition"] != "PRUNE" and r["bridge_id"] in by_id]
    selected: list[str] = []
    while pool and len(selected) < target:
        best, best_adj = None, None
        for r in pool:
            penalty = max((_bridge_similarity(by_id[r["bridge_id"]], by_id[sid])
                           for sid in selected), default=0.0)
            adj = r["total"] - lam * penalty
            if best_adj is None or adj > best_adj:
                best, best_adj = r, adj
        selected.append(best["bridge_id"])
        pool.remove(best)
    return selected


def bridge_rank_stability(bridges: list[dict], policies: dict) -> dict:
    pol = policies["product_anchored"]
    return mm.rank_stability(bridges, pol["reverse_fit"]["weights"],
                             float(pol["robustness"]["perturbation"]))

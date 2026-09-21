"""NICHE_LOADOUT math layer (docs/09): θ generates the possibility space;
φ turns it into an optimization problem.

Three deterministic controls — none of them is an opportunity score, and none
pretends to be a calibrated probability:
1. frontier_utility  — where is it worth THINKING one more hop?
2. voi_priority      — which unanswered question should be RESEARCHED next?
3. select_portfolio  — which 3-6 products form the best SET (not top-N list)?
Plus: surface_gain (KEEP_BRANCH / COLLAPSE_TO_PARENT receipts) and
insider_fidelity (the "someone who actually does this built it" receipt).
"""
from __future__ import annotations


# ------------------------------------------------------- frontier utility --
def frontier_utility(branch: dict, policies: dict) -> dict:
    """U(b|s) from deterministic branch features (each 0..1 or small counts).
    Expected branch keys: new_jobs, new_frictions, new_slots,
    insider_specificity, transfer_strength, commerce_reachability,
    redundancy, inference_distance, research_cost."""
    pol = policies["frontier_utility"]
    w = pol["weights"]
    u = sum(w[k] * float(branch.get(k, 0)) for k in w)
    # normalize into ~0..1 by the positive weight mass so thresholds are stable
    pos_mass = sum(v for v in w.values() if v > 0)
    score = max(0.0, min(1.0, u / pos_mass))
    if score >= pol["explore_threshold"]:
        disp = "EXPLORE"
    elif score >= pol["maybe_threshold"]:
        disp = "MAYBE"
    else:
        disp = "PRUNE"
    return {"branch": branch.get("name", "?"), "utility": round(score, 3),
            "disposition": disp}


def rank_frontier(branches: list[dict], policies: dict) -> list[dict]:
    out = [frontier_utility(b, policies) for b in branches]
    return sorted(out, key=lambda x: -x["utility"])


# --------------------------------------------------- value of information --
def voi_priority(question: dict, policies: dict) -> dict:
    """Deterministic VoI proxy: yield x role-importance x decision-impact / cost.
    Question keys: id, source_family, missing_role_importance (0..1),
    decision_impact (0..1), expected_cost (>=0.1, relative units)."""
    yields = policies["value_of_information"]["default_source_yield"]
    y = yields.get(question.get("source_family", "community"), 0.5)
    pri = (y * float(question.get("missing_role_importance", 0.5))
           * float(question.get("decision_impact", 0.5))
           / max(0.1, float(question.get("expected_cost", 1.0))))
    return {"question": question.get("id", "?"), "priority": round(pri, 3)}


def rank_questions(questions: list[dict], policies: dict) -> list[dict]:
    return sorted((voi_priority(q, policies) for q in questions),
                  key=lambda x: -x["priority"])


# --------------------------------------------------------- surface gain ----
def surface_gain(parent: str, child: str, delta: dict, policies: dict) -> dict:
    """Gain(child|parent): does this split reveal materially new surface?"""
    pol = policies["surface_gain"]
    gain = sum(pol["weights"].get(k, 0) * float(delta.get(k, 0)) for k in pol["weights"])
    return {"parent": parent, "child": child, "delta": delta,
            "gain": round(gain, 2),
            "disposition": "KEEP_BRANCH" if gain >= pol["keep_threshold"] else "COLLAPSE_TO_PARENT"}


# --------------------------------------------------- portfolio selection ---
def _coverage_value(selected: list[dict], key: str) -> float:
    """min(1, coverage) summed over distinct values covered."""
    covered = set()
    for p in selected:
        covered.update(p.get(key) or [])
    return float(len(covered))


def _redundancy(a: dict, b: dict) -> float:
    ja, jb = set(a.get("physical_jobs") or []), set(b.get("physical_jobs") or [])
    ma, mb = set(a.get("moments") or []), set(b.get("moments") or [])
    j = len(ja & jb) / max(1, len(ja | jb))
    m = len(ma & mb) / max(1, len(ma | mb))
    same_family = 1.0 if a.get("mechanism_family") == b.get("mechanism_family") else 0.0
    return (j + m + same_family) / 3.0


def portfolio_value(selected: list[dict], policies: dict) -> float:
    """F(S): job coverage + role coverage + quality + moment coverage
    - pairwise redundancy. Submodular-flavored; greedy gives a good set."""
    w = policies["portfolio"]["weights"]
    val = (w["job_coverage"] * _coverage_value(selected, "physical_jobs")
           + w["role_coverage"] * _coverage_value(selected, "collection_roles")
           + w["moment_coverage"] * _coverage_value(selected, "moments")
           + w["quality"] * sum(float(p.get("quality", 0)) for p in selected))
    red = sum(_redundancy(a, b) for i, a in enumerate(selected)
              for b in selected[i + 1:])
    return val - w["redundancy_penalty"] * red


def select_portfolio(candidates: list[dict], policies: dict) -> dict:
    """Greedy marginal-gain selection (MMR-style) of the 3-6 item loadout.
    Candidate keys: id, name, quality (0..1), physical_jobs[], moments[],
    collection_roles[], mechanism_family."""
    pol = policies["portfolio"]
    selected: list[dict] = []
    pool = list(candidates)
    while pool and len(selected) < pol["size_max"]:
        best, best_gain = None, None
        base = portfolio_value(selected, policies)
        for p in pool:
            gain = portfolio_value(selected + [p], policies) - base
            if best_gain is None or gain > best_gain:
                best, best_gain = p, gain
        if best_gain is not None and best_gain <= 0 and len(selected) >= pol["size_min"]:
            break
        selected.append(best)
        pool.remove(best)
    return {"selected": [p["id"] for p in selected],
            "set_value": round(portfolio_value(selected, policies), 2),
            "size": len(selected),
            "covered_jobs": sorted({j for p in selected for j in p.get("physical_jobs") or []}),
            "covered_roles": sorted({r for p in selected for r in p.get("collection_roles") or []})}


# --------------------------------------------------- insider fidelity ------
def insider_fidelity(loadout: dict, policies: dict) -> dict:
    """IF(L) receipt: deterministic dimensions (each 0..1 supplied from state
    facts, e.g. traceability = fraction of items with a lived-moment link),
    with an explicit genericness penalty. A receipt, never a probability."""
    pol = policies["insider_fidelity"]
    w = pol["weights"]
    dims = {k: float(loadout.get(k, 0)) for k in w if k != "genericness_penalty"}
    score = sum(w[k] * v for k, v in dims.items())
    score += w["genericness_penalty"] * float(loadout.get("genericness", 0))
    status = "PASS" if score >= pol["pass_threshold"] else "FAIL_INSIDER_FIDELITY"
    return {"dimensions": dims, "genericness": loadout.get("genericness", 0),
            "score": round(score, 2), "status": status}

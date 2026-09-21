"""Role-coverage satisfaction — deficit-oriented, receipts not scores.

The loop never asks "do we have lots of evidence?"; it asks "which required
evidence ROLES remain unsatisfied?" (docs/04 §6, §25). Receipts keep raw
metrics so a future policy change can be recomputed against them.
"""
from __future__ import annotations

import verifiers
from models import now


def _roles_present(state: dict) -> dict[str, list[str]]:
    """role -> observation ids establishing it (field evidence only)."""
    out: dict[str, list[str]] = {}
    # docs/25: population-discovery field records are admitted through the same
    # evidence contract and establish roles like any observation
    for o in list(state["data"]["observations"]) + [r for r in state["data"].get("field_records") or [] if isinstance(r, dict)]:
        if o.get("contradicts"):
            continue
        for r in o.get("evidence_roles") or []:
            out.setdefault(r, []).append(o["id"])
    # Normalized supplier candidates ARE live supply-side evidence (L3):
    # parsed price/MOQ from a live listing establishes the supplier roles.
    for s in state["data"]["supplier_candidates"]:
        if s.get("price_usd_low") is not None or s.get("moq_units"):
            out.setdefault("SUPPLIER_AVAILABILITY", []).append(s["id"])
            if s.get("price_usd_low") is not None:
                out.setdefault("PRICE_EVIDENCE", []).append(s["id"])
            if s.get("moq_units"):
                out.setdefault("MOQ_EVIDENCE", []).append(s["id"])
    return out


def evidence_coverage(state: dict, policies: dict) -> dict:
    """Per-requirement coverage receipt for the physical-product matrix."""
    reqs = policies.get("physical_product_requirements") or {}
    present = _roles_present(state)
    ind = verifiers.independence_groups(list(state["data"]["observations"]) + [r for r in state["data"].get("field_records") or [] if isinstance(r, dict)])
    min_groups = (policies.get("independence_defaults") or {}).get("minimum_independent_groups", 3)
    searched = state["rounds"]["research"] >= 1
    coverage: dict[str, dict] = {}
    for name, spec in reqs.items():
        roles = spec.get("roles") or []
        hits = [r for r in roles if present.get(r)]
        satisfied = bool(hits)
        # mechanism support may arrive as a SUPPORTED mechanism object rather
        # than a field observation (conceptual support enters at hypothesize,
        # not from comments) — accept either.
        if name == "mechanism" and not satisfied:
            satisfied = any(m.get("status") == "SUPPORTED" for m in state["data"]["mechanisms"])
        # contradiction search: performing the search and finding nothing IS
        # a result (absence recorded after real search != skipped search).
        if name == "contradiction_search" and not satisfied:
            satisfied = bool(spec.get("allow_empty_after_search")) and searched
        coverage[name] = {
            "roles_required": roles, "roles_present": hits,
            "supporting_ids": sorted({i for r in hits for i in present.get(r, [])})[:10],
            "required_now": bool(spec.get("required")),
            "required_for": spec.get("required_for") or [],
            "satisfied": satisfied,
        }
    core = [n for n, s in reqs.items() if s.get("required")]
    core_ok = all(coverage[n]["satisfied"] for n in core)
    independent_ok = ind["independent_groups"] >= min_groups
    missing = [n for n in core if not coverage[n]["satisfied"]]
    if not independent_ok:
        missing.append(f"independence(min {min_groups} groups, have {ind['independent_groups']})")
    return {
        "requirements": coverage,
        "independence": ind,
        "core_satisfied": core_ok and independent_ok,
        "missing": missing,
        "computed_at": now(),
    }


def recompute(state: dict, policies: dict) -> dict:
    """Recompute + persist the satisfaction receipt (append-only history:
    cycles are causally frozen, old receipts are never rewritten)."""
    cov = evidence_coverage(state, policies)
    cov["cycle"] = state["rounds"]["research"]
    history = state.setdefault("satisfaction_history", [])
    history.append(cov)
    state["satisfaction"] = cov
    return cov


def lead_tier(state: dict, policies: dict) -> str:
    """QUALIFIED_LEAD / PROVISIONAL_LEAD / WEAK based on coverage, never counts."""
    cov = state.get("satisfaction") or evidence_coverage(state, policies)
    if not cov["core_satisfied"]:
        return "WEAK"
    reqs = cov["requirements"]
    supply_ok = all(reqs[n]["satisfied"] for n in reqs
                    if "QUALIFIED_LEAD" in (reqs[n].get("required_for") or []))
    return "QUALIFIED_LEAD" if supply_ok else "PROVISIONAL_LEAD"

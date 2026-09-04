"""Edge-condition evaluation. Conditions are FACTS computed from state +
policies — never model opinions. θ proposes; φ decides admissibility."""
from __future__ import annotations


def _live_hypothesis_ids(state: dict) -> set:
    return {h["id"] for h in state["data"]["hypotheses"]
            if h.get("status") not in ("REJECTED", "HOLD")}


def _open_gaps(state: dict) -> list[dict]:
    """Open gaps whose hypothesis is still live — gaps of REJECTED/HOLD
    hypotheses are moot and must not block or force research."""
    live = _live_hypothesis_ids(state)
    return [g for g in state["data"]["gaps"]
            if g.get("status") == "open" and g.get("hypothesis_id") in live]


def no_generative_signal(state: dict, policies: dict) -> bool:
    prim = state["data"].get("primitives") or {}
    return prim != {} and not prim.get("generative_signal")


def generative_signal_present(state: dict, policies: dict) -> bool:
    return bool((state["data"].get("primitives") or {}).get("generative_signal"))


def _opp_rounds_cap(state: dict, policies: dict) -> int:
    """User may TIGHTEN the round budget (ADVANCED_SAFE); the policy value is
    the hard ceiling — min() keeps it unweakenable."""
    import settings as _settings
    hard = policies["evidence"]["max_research_rounds"]
    return min(hard, int(_settings.effective(
        state, "opportunity_research.max_research_rounds", hard)))


def material_gap_exists(state: dict, policies: dict) -> bool:
    if not _open_gaps(state):
        return False
    # forced verdict after max rounds: gaps stop being researchable
    return state["rounds"]["research"] < _opp_rounds_cap(state, policies)


def evidence_sufficient(state: dict, policies: dict) -> bool:
    gaps = state["data"]["gaps"]
    if not gaps:
        return False  # no gaps compiled yet means nothing was challenged, not sufficiency
    cap = _opp_rounds_cap(state, policies)
    if _open_gaps(state) and state["rounds"]["research"] < cap:
        return False
    if state["rounds"]["research"] >= cap:
        # FORCED VERDICT (measured 2026-09-03 on a live run): with the research
        # budget spent and no supported gap, neither edge out of `gaps` was
        # ready and the run stalled forever. The evidence is as sufficient as
        # it will ever get — the mechanism node must now pronounce
        # NO_DEFENSIBLE_BRIDGE (it cannot mark a mechanism SUPPORTED without
        # supporting observations), never the graph going silent.
        return True
    live = _live_hypothesis_ids(state)
    supported = [g for g in gaps if g.get("status") == "supported" and g.get("hypothesis_id") in live]
    return bool(supported) and len(state["data"]["observations"]) >= policies["evidence"]["min_total_observations"]


def mechanism_supported(state: dict, policies: dict) -> bool:
    return any(m.get("status") == "SUPPORTED" for m in state["data"]["mechanisms"])


def no_defensible_bridge(state: dict, policies: dict) -> bool:
    ms = state["data"]["mechanisms"]
    return bool(ms) and all(m.get("status") != "SUPPORTED" for m in ms)


# ---- discovery modes (docs/12-14) ------------------------------------------
def _open_gaps_any(state: dict) -> bool:
    """Discovery gaps hang off whitespace/bridges, not hypotheses — no
    hypothesis-liveness filter here."""
    return any(g.get("status") == "open" for g in state["data"].get("gaps") or [])


def identity_resolved(state: dict, policies: dict) -> bool:
    pid = state["data"].get("product_identity") or {}
    return pid.get("identity_state") in ("EXACT", "PROBABLE")


def identity_unresolved(state: dict, policies: dict) -> bool:
    return not identity_resolved(state, policies)


def _rounds_cap(state: dict, policies: dict, mode: str) -> int:
    """Policy default, overridable ONLY through the resolved settings snapshot
    (ADVANCED_SAFE, bounded by the settings schema — never weakenable laws)."""
    import settings as _settings
    return int(_settings.effective(state, f"{mode}.max_research_rounds",
                                   policies[mode]["max_research_rounds"]))


def market_research_needed(state: dict, policies: dict) -> bool:
    return (_open_gaps_any(state)
            and state["rounds"]["research"] < _rounds_cap(state, policies, "market_discovery"))


def market_research_done(state: dict, policies: dict) -> bool:
    return not market_research_needed(state, policies)


def pa_research_needed(state: dict, policies: dict) -> bool:
    return (_open_gaps_any(state)
            and state["rounds"]["research"] < _rounds_cap(state, policies, "product_anchored"))


def pa_research_done(state: dict, policies: dict) -> bool:
    return not pa_research_needed(state, policies)


def loadout_discovery_needed(state: dict, policies: dict) -> bool:
    """The discovery_loop_gate executor already decided (target vs ceiling vs
    stagnation) — conditions only read the recorded fact."""
    return bool((state.get("discovery_loop") or {}).get("continue"))


def loadout_discovery_done(state: dict, policies: dict) -> bool:
    return not loadout_discovery_needed(state, policies)


# ---------------------------------------------------------------- registry maintenance (docs/23)
def _cands(state: dict) -> list[dict]:
    return [c for c in state["data"].get("registry_candidates") or [] if isinstance(c, dict)]


def _research_visits(state: dict) -> int:
    return sum(1 for h in state.get("history") or [] if isinstance(h, dict) and h.get("to") == "research")


def candidate_needs_field_evidence(state: dict, policies: dict) -> bool:
    """A discovery candidate below its recurrence bar gets ONE research visit;
    after that it is held, never researched forever."""
    if _research_visits(state) >= 1:
        return False
    return any(c.get("evidence_status") == "needs_field_evidence" for c in _cands(state))


def candidate_evidence_sufficient(state: dict, policies: dict) -> bool:
    return not candidate_needs_field_evidence(state, policies)


def promotion_eligible(state: dict, policies: dict) -> bool:
    return any(c.get("promotion_status") == "ELIGIBLE" for c in _cands(state))


def all_rejected_or_held(state: dict, policies: dict) -> bool:
    return bool(_cands(state)) and not promotion_eligible(state, policies)



# ---------------------------------------------------------------- LIVED-WORLD-V2 (docs/25)
def population_round_needed(state: dict, policies: dict) -> bool:
    """The population_gate executor already decided (anchors vs ceilings vs
    stagnation vs wall clock) — conditions only read the recorded fact."""
    return bool((state.get("population_loop") or {}).get("continue"))


def lived_world_present(state: dict, policies: dict) -> bool:
    return not population_round_needed(state, policies) and bool(state["data"].get("lived_clusters"))


def lived_world_empty(state: dict, policies: dict) -> bool:
    """No field record survived any round: hypotheses may still be written,
    but every one of them is CORPUS_ONLY and can never qualify on its own."""
    return not population_round_needed(state, policies) and not state["data"].get("lived_clusters")


CONDITIONS = {
    "no_generative_signal": no_generative_signal,
    "generative_signal_present": generative_signal_present,
    "material_gap_exists": material_gap_exists,
    "evidence_sufficient": evidence_sufficient,
    "mechanism_supported": mechanism_supported,
    "no_defensible_bridge": no_defensible_bridge,
    "identity_resolved": identity_resolved,
    "identity_unresolved": identity_unresolved,
    "market_research_needed": market_research_needed,
    "market_research_done": market_research_done,
    "pa_research_needed": pa_research_needed,
    "pa_research_done": pa_research_done,
    "loadout_discovery_needed": loadout_discovery_needed,
    "loadout_discovery_done": loadout_discovery_done,
    "candidate_needs_field_evidence": candidate_needs_field_evidence,
    "candidate_evidence_sufficient": candidate_evidence_sufficient,
    "promotion_eligible": promotion_eligible,
    "all_rejected_or_held": all_rejected_or_held,
    "population_round_needed": population_round_needed,
    "lived_world_present": lived_world_present,
    "lived_world_empty": lived_world_empty,
}


def evaluate(name: str, state: dict, policies: dict) -> bool:
    fn = CONDITIONS.get(name)
    if fn is None:
        raise KeyError(f"unknown edge condition: {name}")
    return fn(state, policies)

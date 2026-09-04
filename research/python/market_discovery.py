"""MARKET_DISCOVERY deterministic executors (docs/12, docs/14 §4-§12).

φ owns: signal merge, frontier utility + diversity selection, signal
divergence, gap compilation, evaluation application, promotion. θ owns:
proposing scopes, queries, whitespace hypotheses — through graph submissions
only. Lane isolation is enforced upstream by ContextContracts; nothing here
may re-mix lanes before merge_market_signals has run.
"""
from __future__ import annotations

from models import stable_id

_LANE_KEYS = ["field_signals", "trend_signals", "corpus_signals", "supply_signals",
              "commerce_signals"]
_WHITESPACE_GAP_ROLES = ["FRICTION_EVIDENCE", "WORKAROUND_EVIDENCE",
                         "BEHAVIOR_SUPPORT", "PRODUCT_COMPLAINT"]


def merge_market_signals(state: dict, policies: dict) -> str:
    """Dedupe across lanes, keep origin provenance. This is the FIRST moment
    lanes may see each other — anchoring protection ends here by design."""
    seen, counts = set(), {}
    for key in _LANE_KEYS:
        unique = []
        for s in state["data"].get(key) or []:
            sid = s.get("id") or stable_id("sig", key, s.get("summary", ""))
            s["id"] = sid
            if sid in seen:
                continue
            seen.add(sid)
            unique.append(s)
            counts[s.get("origin", "?")] = counts.get(s.get("origin", "?"), 0) + 1
        state["data"][key] = unique
    state["data"]["signal_provenance"] = counts
    return f"merged lanes: {counts} ({len(seen)} unique signals)"


def market_frontier(state: dict, policies: dict) -> str:
    """M(s) receipts + diversity-aware retention + robustness check."""
    import market_math as mm
    import settings as _settings
    div = _settings.effective(state, "market_discovery.diversity", None)
    if div in ("LOW", "NORMAL", "HIGH"):
        fr = policies["market_discovery"]["frontier"]
        lam = {"LOW": 0.25, "NORMAL": 0.5, "HIGH": 0.75}[div]
        policies = {**policies, "market_discovery": {**policies["market_discovery"],
                    "frontier": {**fr, "diversity_lambda": lam}}}
    scopes = state["data"].get("market_scopes") or []
    receipts = [mm.market_frontier_utility(s, policies) for s in scopes]
    retained = set(mm.diversity_select(scopes, receipts, policies))
    for s in scopes:
        s["status"] = "RETAINED" if s["id"] in retained else "COLLAPSED"
    items = [{"id": s["id"], "features": s.get("features") or {}} for s in scopes]
    stability = mm.rank_stability(items, policies["market_discovery"]["frontier"]["weights"],
                                  float(policies["market_discovery"]["robustness"]["perturbation"]))
    state["data"]["market_frontier_receipts"] = receipts
    state["data"]["market_frontier_stability"] = stability
    return (f"frontier M(s): retained {len(retained)}/{len(scopes)} diverse scopes; "
            f"ranking {stability['status']} under ±{stability.get('perturbation', 0)} weights")


def signal_divergence_gate(state: dict, policies: dict) -> str:
    """Per retained scope: channel disagreement as a first-class object."""
    import market_math as mm
    obs = state["data"].get("observations") or []
    out = []
    for s in state["data"].get("market_scopes") or []:
        if s.get("status") != "RETAINED":
            continue
        f = s.get("features") or {}
        wk = sum(1 for o in obs
                 if o.get("scope_id") == s["id"]
                 and "WORKAROUND_EVIDENCE" in (o.get("evidence_roles") or []))
        channels = {"search_interest": f.get("attention", 0),
                    "community_activity": f.get("community", 0),
                    "commerce_supply": f.get("sourceability", 0),
                    "product_saturation": f.get("saturation", 0),
                    "workaround_density": min(1.0, wk / 3.0)}
        div = mm.detect_divergence(channels, policies)
        out.append({"id": stable_id("div", s["id"]), "scope_id": s["id"], **div})
    state["data"]["signal_divergences"] = out
    n_pat = sum(len(d["patterns"]) for d in out)
    return f"divergence computed for {len(out)} scopes ({n_pat} named patterns — disagreement IS information)"


def market_gaps(state: dict, policies: dict) -> str:
    """Compile validation gaps + channel queries for open whitespace."""
    import executors as _ex
    gaps, queries = state["data"]["gaps"], state["data"]["queries"]
    known = {g["id"] for g in gaps}
    added_g = added_q = 0
    for wh in state["data"].get("whitespace_hypotheses") or []:
        if wh.get("state") not in (None, "PROPOSED", "WEAKENED"):
            continue
        questions = (wh.get("next_validation") or [wh["observed_mismatch"]])[:2]
        for q in questions:
            gid = stable_id("mgap", wh["id"], q)
            if gid in known:
                continue
            known.add(gid)
            gaps.append({"id": gid, "whitespace_id": wh["id"], "question": q,
                         "status": "open",
                         "required_evidence_roles": list(_WHITESPACE_GAP_ROLES),
                         "required_freshness": ["FAST", "LIVE"]})
            added_g += 1
            for channel, tpl, family, why, expected in _ex._CHANNEL_TEMPLATES:
                queries.append({"id": stable_id("mq", gid, channel), "gap_id": gid,
                                "query": tpl.format(q=q), "channel": channel,
                                "source_family": family, "why_this_source": why,
                                "expected_evidence_roles": expected,
                                "cannot_satisfy": ["SUPPLIER_AVAILABILITY", "PRICE_EVIDENCE",
                                                    "MOQ_EVIDENCE"]})
                added_q += 1
    open_n = len([g for g in gaps if g["status"] == "open"])
    return f"compiled {added_g} whitespace gaps, {added_q} queries ({open_n} open)"


def revise_whitespace(state: dict, policies: dict) -> str:
    """Curate the round, then move whitespace states from gap outcomes.
    Evidence decides; θ never mutates whitespace state directly."""
    import executors as _ex
    note = _ex.comments(state, policies)  # dedupe + close gaps + round++
    by_wh: dict[str, list] = {}
    for g in state["data"]["gaps"]:
        if g.get("whitespace_id"):
            by_wh.setdefault(g["whitespace_id"], []).append(g)
    moved = 0
    for wh in state["data"].get("whitespace_hypotheses") or []:
        gs = by_wh.get(wh["id"]) or []
        if not gs:
            continue
        sup = sum(1 for g in gs if g["status"] == "supported")
        con = sum(1 for g in gs if g["status"] == "contradicted")
        old = wh.get("state")
        if con and con >= sup:
            wh["state"] = "CONTRADICTED"
        elif sup and not con and all(g["status"] != "open" for g in gs):
            wh["state"] = "SUPPORTED"
        elif sup:
            wh["state"] = "REFINED"
        if wh.get("state") != old:
            moved += 1
    import gap_analysis as _ga
    gap_note = _ga.demand_gap_analysis(state, policies)   # refresh typed gaps from revised states
    return f"{note} | whitespace states moved: {moved} | {gap_note}"


def apply_market_evaluations(state: dict, policies: dict) -> str:
    """Shared L4 application for discovery modes: evaluations target
    whitespace hypotheses (market) or market bridges (product-anchored).
    REJECT -> CONTRADICTED, REVISE -> WEAKENED/WEAK; receipts recorded."""
    targets: dict[str, dict] = {}
    for wh in state["data"].get("whitespace_hypotheses") or []:
        targets[wh["id"]] = wh
    for b in state["data"].get("market_bridges") or []:
        targets[b["id"]] = b
    state.setdefault("l4_receipts", [])
    applied = 0
    for ev in state["data"].get("evaluations") or []:
        subj = targets.get(ev.get("hypothesis_id"))
        if subj is None:
            continue
        verdict = ev.get("verdict")
        is_bridge = "meaning_id" in subj
        if verdict == "REJECT":
            subj["state"] = "CONTRADICTED"
        elif verdict == "REVISE":
            subj["state"] = "WEAK" if is_bridge else "WEAKENED"
        state["l4_receipts"].append({"subject_id": ev.get("hypothesis_id"),
                                     "status": verdict,
                                     "decisive_falsifier": (ev.get("reasons") or [None])[0]})
        applied += 1
    return f"L4 verdicts applied to {applied} discovery subjects (receipts recorded)"


def capture_gate(state: dict, policies: dict) -> str:
    """CaptureFeasibility (docs/17 §16-17): θ estimated decomposed dims with
    evidence; φ combines into a categorical routing judgment + receipt. Never
    a market-share probability."""
    import market_math as mm
    pol = policies["capture_feasibility"]
    w = pol["weights"]
    receipts = []
    for a in state["data"].get("capture_assessments") or []:
        dims = a.get("dimensions") or {}
        inputs = {k: float(dims.get(k, 0)) for k in w}
        pos = sum(v for v in w.values() if v > 0) or 1.0
        score = max(0.0, min(1.0, sum(w[k] * inputs[k] for k in w) / pos))
        if score >= pol["easy_threshold"]:
            result = "EASY_ENTRY"
        elif score >= pol["plausible_threshold"]:
            result = "PLAUSIBLE"
        elif score >= pol["difficult_threshold"]:
            result = "DIFFICULT"
        else:
            result = "HOSTILE"
        a["result"] = result
        receipts.append({"formula": "capture_feasibility_v1", "scope_id": a.get("scope_id"),
                         "inputs": inputs, "weights": dict(w), "total": round(score, 3),
                         "result": result, "config_hash": mm._cfg_hash(w)})
    state["data"]["capture_receipts"] = receipts
    n_h = sum(1 for r in receipts if r["result"] == "HOSTILE")
    return (f"capture feasibility: {len(receipts)} scopes judged "
            f"({n_h} HOSTILE — great demand can still be a hostile entry)")


def market_promotion(state: dict, policies: dict) -> str:
    """Promote 3-8 scopes with surviving whitespace or a discovery-grade
    divergence pattern. Shallow supply check only — deep sourcing belongs to
    the child modes (docs/12)."""
    pol = policies["market_discovery"]["frontier"]
    wh_by_scope: dict[str, list] = {}
    for wh in state["data"].get("whitespace_hypotheses") or []:
        wh_by_scope.setdefault(wh["market_scope_id"], []).append(wh)
    div_by_scope = {d["scope_id"]: d for d in state["data"].get("signal_divergences") or []}
    hostile = {a.get("scope_id") for a in state["data"].get("capture_assessments") or []
               if a.get("result") == "HOSTILE"}
    rejected_l4 = {r["subject_id"] for r in state.get("l4_receipts") or []
                   if r.get("status") == "REJECT"}
    promoted = []
    for s in state["data"].get("market_scopes") or []:
        if s.get("status") != "RETAINED":
            continue
        whs = [w for w in wh_by_scope.get(s["id"], [])
               if w.get("state") in ("SUPPORTED", "REFINED") and w["id"] not in rejected_l4]
        patterns = (div_by_scope.get(s["id"]) or {}).get("patterns") or []
        discovery_patterns = [p for p in patterns
                              if p in ("EARLY_EMERGENCE", "PRE_CATEGORY", "COMMUNITY_COMMERCE_GAP")]
        if not whs and not discovery_patterns:
            continue
        if s["id"] in hostile:   # attractive demand, hostile entry — recorded, not promoted
            continue
        types = {w["type"] for w in whs}
        if "CURATION_WHITESPACE" in types or "STYLE_WHITESPACE" in types:
            mode = "NICHE_LOADOUT"
        elif types & {"PRODUCT_WHITESPACE", "MECHANISM_WHITESPACE", "VALUE_WHITESPACE"}:
            mode = "OPPORTUNITY_RESEARCH"
        else:
            mode = "NICHE_LOADOUT"
        promoted.append({"id": stable_id("promo", s["id"]), "scope_id": s["id"],
                         "market": s.get("market"), "niche": s.get("niche"),
                         "subniche": s.get("subniche"),
                         "whitespace_ids": [w["id"] for w in whs],
                         "divergence_patterns": patterns,
                         "recommended_mode": mode})
    import settings as _settings
    cap = int(_settings.effective(state, "market_discovery.retained_markets",
                                  pol.get("retain_max", 8)))
    promoted = promoted[: min(cap, int(pol.get("retain_max", 8)))]
    for s in state["data"].get("market_scopes") or []:
        if s["id"] in {p["scope_id"] for p in promoted}:
            s["status"] = "PROMOTED"
    state["data"]["promoted_scopes"] = promoted
    state["verdict"] = "MARKET_SCOPES_READY" if promoted else "NO_PROMISING_MARKETS"
    import candidates as _cand
    note = _cand.auto_emit(state, policies)
    return (f"verdict: {state['verdict']} ({len(promoted)} scopes promoted, "
            f"{len(hostile)} hostile-entry excluded; deep sourcing deferred) | {note}")


EXECUTORS = {
    "python.merge_market_signals": merge_market_signals,
    "python.market_frontier": market_frontier,
    "python.signal_divergence": signal_divergence_gate,
    "python.market_gaps": market_gaps,
    "python.revise_whitespace": revise_whitespace,
    "python.apply_market_evaluations": apply_market_evaluations,
    "python.market_promotion": market_promotion,
    "python.capture_gate": capture_gate,
}

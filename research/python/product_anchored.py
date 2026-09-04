"""PRODUCT_ANCHORED_DISCOVERY deterministic executors (docs/13, docs/14 §13-§20).

The inverted mode: product → meanings → bridges → actual communities. Its
law: do not ask "who can I sell this to?" — ask "in whose lived world does
this object already make sense?". φ owns identity gating, claim quarantine,
reverse-fit selection, evidence-driven bridge revision and the terminal gate.
θ proposes meanings/bridges/reframes through graph submissions only.
"""
from __future__ import annotations

from models import stable_id

_BRIDGE_GAP_ROLES = ["BEHAVIOR_SUPPORT", "FRICTION_EVIDENCE",
                     "WORKAROUND_EVIDENCE", "PURCHASE_INTENT"]


def identity_gate(state: dict, policies: dict) -> str:
    """An ambiguous product may not proceed as if the name were certain."""
    pid = state["data"].get("product_identity") or {}
    st = pid.get("identity_state")
    if st in ("EXACT", "PROBABLE"):
        return (f"identity resolved: {pid.get('canonical_name')} ({st}, "
                f"{len(pid.get('aliases') or [])} aliases)")
    state["verdict"] = "PRODUCT_IDENTITY_UNRESOLVED"
    return f"identity {st or 'MISSING'}: refusing to research a product we cannot name"


def claim_quarantine(state: dict, policies: dict) -> str:
    """User/supplier positioning becomes UNVERIFIED ProductClaims. The user's
    idea guides research; it never gets evidence authority for free."""
    seed = state["data"].get("product_seed") or {}
    claims = state["data"].setdefault("product_claims", [])
    known = {c["id"] for c in claims}
    added = 0
    for origin, key in (("SELLER", "seller_claims"), ("USER", "user_hypotheses")):
        for raw in seed.get(key) or []:
            if isinstance(raw, dict):
                text, ctype = raw.get("claim", ""), raw.get("claim_type", "MARKET")
            else:
                text, ctype = str(raw), "MARKET"
            cid = stable_id("claim", origin, text)
            if not text or cid in known:
                continue
            known.add(cid)
            claims.append({"id": cid, "claim": text, "origin": origin,
                           "claim_type": ctype, "state": "UNVERIFIED"})
            added += 1
    return f"quarantined {added} claims as UNVERIFIED ({len(claims)} total) — seller copy is not evidence"


def merge_product_signals(state: dict, policies: dict) -> str:
    import market_discovery as _md
    return _md.merge_market_signals(state, policies)


def reverse_fit_gate(state: dict, policies: dict) -> str:
    """R(n|p) receipts + diversity-aware bridge retention + robustness."""
    import product_market_math as pmm
    import settings as _settings
    target = _settings.effective(state, "product_anchored.market_bridges_target", None)
    if target:
        rf = policies["product_anchored"]["reverse_fit"]
        policies = {**policies, "product_anchored": {**policies["product_anchored"],
                    "reverse_fit": {**rf, "bridge_target": int(target)}}}
    bridges = state["data"].get("market_bridges") or []
    receipts = [pmm.reverse_fit_utility(b, policies) for b in bridges]
    retained = set(pmm.diversity_select_bridges(bridges, receipts, policies))
    for b in bridges:
        b["state"] = "RETAINED" if b["id"] in retained else "PRUNED"
    stability = pmm.bridge_rank_stability(
        [{"id": b["id"], "features": b.get("features") or {}} for b in bridges], policies)
    state["data"]["reverse_fit_receipts"] = receipts
    state["data"]["reverse_fit_stability"] = stability
    return (f"reverse fit R(n|p): retained {len(retained)}/{len(bridges)} diverse bridges; "
            f"ranking {stability['status']} (budget routing, never success probability)")


def bridge_gaps(state: dict, policies: dict) -> str:
    """Evidence gaps for retained bridges: who actually owns/uses/discusses
    this, in their own words."""
    import executors as _ex
    gaps, queries = state["data"]["gaps"], state["data"]["queries"]
    known = {g["id"] for g in gaps}
    added_g = added_q = 0
    for b in state["data"].get("market_bridges") or []:
        if b.get("state") not in ("RETAINED", "REFINED", "WEAK"):
            continue
        q = (f"who actually owns/uses/discusses this product as "
             f"{b.get('meaning_id')} in {b.get('market_scope')}, in their own words")
        gid = stable_id("bgap", b["id"])
        if gid in known:
            continue
        known.add(gid)
        gaps.append({"id": gid, "bridge_id": b["id"], "question": q, "status": "open",
                     "required_evidence_roles": list(_BRIDGE_GAP_ROLES),
                     "required_freshness": ["FAST", "LIVE"]})
        added_g += 1
        for channel, tpl, family, why, expected in _ex._CHANNEL_TEMPLATES:
            queries.append({"id": stable_id("bq", gid, channel), "gap_id": gid,
                            "query": tpl.format(q=f"{b.get('market_scope')} {q[:60]}"),
                            "channel": channel, "source_family": family,
                            "why_this_source": why,
                            "expected_evidence_roles": expected,
                            "cannot_satisfy": ["SUPPLIER_AVAILABILITY", "PRICE_EVIDENCE"]})
            added_q += 1
    open_n = len([g for g in gaps if g["status"] == "open"])
    return f"compiled {added_g} bridge gaps, {added_q} queries ({open_n} open)"


def revise_bridges(state: dict, policies: dict) -> str:
    """Evidence moves bridge and claim states — θ proposes, evidence decides.
    Dedupes the round's observations, closes gaps, recomputes states."""
    d = state["data"]
    seen, unique = set(), []
    for o in d.get("observations") or []:
        key = (o.get("quote_ref") or "").strip().lower() or o.get("id")
        if key in seen:
            continue
        seen.add(key)
        unique.append(o)
    d["observations"] = unique
    min_src = policies["evidence"]["min_independent_sources"]
    for g in d["gaps"]:
        if g.get("status") != "open" or not g.get("bridge_id"):
            continue
        need = set(g.get("required_evidence_roles") or [])
        sup = [o for o in unique if o.get("gap_id") == g["id"] and not o.get("contradicts")
               and (not need or need & set(o.get("evidence_roles") or []))]
        con = [o for o in unique if o.get("gap_id") == g["id"] and o.get("contradicts")]
        if len(con) > len(sup):
            g["status"] = "contradicted"
        elif len({o.get("source") for o in sup}) >= min_src:
            g["status"] = "supported"
    moved = 0
    for b in d.get("market_bridges") or []:
        if b.get("state") == "PRUNED":
            continue
        direct_sup = [o for o in unique if o.get("bridge_id") == b["id"] and not o.get("contradicts")]
        direct_con = [o for o in unique if o.get("bridge_id") == b["id"] and o.get("contradicts")]
        gsup = [g for g in d["gaps"] if g.get("bridge_id") == b["id"] and g["status"] == "supported"]
        gcon = [g for g in d["gaps"] if g.get("bridge_id") == b["id"] and g["status"] == "contradicted"]
        old = b.get("state")
        sources = {o.get("source") for o in direct_sup}
        if len(direct_con) > len(direct_sup) or gcon and not gsup:
            b["state"] = "CONTRADICTED"
        elif (gsup or len(sources) >= min_src) and not gcon:
            b["state"] = "SUPPORTED"
        elif direct_sup or gsup:
            b["state"] = "REFINED"
        b["supporting_evidence"] = sorted({o["id"] for o in direct_sup})
        b["contradicting_evidence"] = sorted({o["id"] for o in direct_con})
        if b.get("state") != old:
            moved += 1
    for c in d.get("product_claims") or []:
        sup = [o for o in unique if c["id"] in (o.get("supports_claims") or [])]
        con = [o for o in unique if c["id"] in (o.get("contradicts_claims") or [])]
        if con and len(con) >= len(sup):
            c["state"] = "CONTRADICTED"
        elif sup and con:
            c["state"] = "PARTIAL"
        elif sup:
            c["state"] = "SUPPORTED"
        c["evidence_refs"] = sorted({o["id"] for o in sup + con})
    state["rounds"]["research"] += 1
    return (f"revised bridges: {moved} state changes; round {state['rounds']['research']}; "
            f"claims audited against field evidence")


def market_bridge_gate(state: dict, policies: dict) -> str:
    """Terminal gate. NO_DEFENSIBLE_MARKET is a valid success outcome —
    forcing product-market fit is the failure mode this mode exists to avoid."""
    d = state["data"]
    rejected_l4 = {r["subject_id"] for r in state.get("l4_receipts") or []
                   if r.get("status") == "REJECT"}
    supported = [b for b in d.get("market_bridges") or []
                 if b.get("state") == "SUPPORTED" and b["id"] not in rejected_l4]
    reframed = any(r.get("user_frame_state") in ("WEAKENED", "CONTRADICTED")
                   for r in d.get("market_reframes") or [])
    if not supported:
        state["verdict"] = "NO_DEFENSIBLE_MARKET"
    elif reframed:
        state["verdict"] = "PRODUCT_REFRAMED"
    else:
        state["verdict"] = "PRODUCT_MARKETS_READY"
    d["top_bridges"] = [{"id": b["id"], "market_scope": b.get("market_scope"),
                         "meaning_id": b.get("meaning_id"),
                         "supporting": len(b.get("supporting_evidence") or [])}
                        for b in supported]
    import candidates as _cand
    note = _cand.auto_emit(state, policies)
    return (f"verdict: {state['verdict']} ({len(supported)} supported bridges"
            + (", user frame reframed by evidence" if reframed else "") + f") | {note}")


EXECUTORS = {
    "python.identity_gate": identity_gate,
    "python.claim_quarantine": claim_quarantine,
    "python.merge_product_signals": merge_product_signals,
    "python.reverse_fit_gate": reverse_fit_gate,
    "python.bridge_gaps": bridge_gaps,
    "python.revise_bridges": revise_bridges,
    "python.market_bridge_gate": market_bridge_gate,
}

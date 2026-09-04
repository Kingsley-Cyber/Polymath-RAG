"""docs/20 §1 — the evidence allocation law.

Run 3 (2026-09-03) showed the collapse point of the research loop: one
hypothesis absorbed the whole first research round, the other live
hypotheses were then REJECTED with one or two threads behind their gaps, and
ideation ran on a single mechanism. Starvation looked like refutation.

Two deterministic rules fix that:

1. `hypothesis_allocation` measures, per live hypothesis, how far each gap is
   from the independent-thread bar and ranks the starved hypotheses first;
   `gap_compiler` interleaves the compiled queries in that order and the
   web_research envelope carries the table.
2. `starved_rejections` refuses a challenge verdict of REJECTED for a
   hypothesis that still has open gaps below the bar, no contradicted gap,
   and research budget left. REJECT needs a contradiction or an exhausted
   budget; otherwise the verdict is CHALLENGED (or HOLD) and the next round
   routes evidence to it.
"""
from __future__ import annotations

import verifiers as _ver


def _counts_for(gap: dict):
    """The SAME admission filter curate applies (executors.comments): an
    observation counts toward a gap only if it carries a required role and,
    when the gap demands it, a required freshness class. Counting without
    these filters made a trend-led hypothesis look fed while curate kept its
    gaps open (R4, 2026-09-03) — the allocation table must never disagree
    with the gate that closes gaps."""
    need = set(gap.get("required_evidence_roles") or [])
    fresh_ok = set(gap.get("required_freshness") or [])

    def _ok(o: dict) -> bool:
        if fresh_ok and ((o.get("freshness") or {}).get("class") not in fresh_ok):
            return False
        return not need or bool(need.intersection(o.get("evidence_roles") or []))
    return _ok


def _threads(state: dict, gap) -> int:
    gap = gap if isinstance(gap, dict) else {"id": gap}
    ok = _counts_for(gap)
    sup = [o for o in state["data"].get("observations") or []
           if o.get("gap_id") == gap.get("id") and not o.get("contradicts") and ok(o)]
    return _ver.independence_groups(sup)["independent_groups"] if sup else 0


def hypothesis_allocation(state: dict, policies: dict) -> list[dict]:
    pol = policies.get("evidence") or {}
    need = int(pol.get("min_independent_sources", 3))
    cap = int(pol.get("max_research_rounds", 3))
    rounds = int((state.get("rounds") or {}).get("research", 0))
    gaps = state["data"].get("gaps") or []
    queries = state["data"].get("queries") or []
    out = []
    for h in state["data"].get("hypotheses") or []:
        if h.get("status") in ("REJECTED", "HOLD"):
            continue
        rows = []
        for g in [g for g in gaps if g.get("hypothesis_id") == h.get("id")]:
            t = _threads(state, g)
            rows.append({"gap_id": g["id"], "status": g.get("status"), "threads": t,
                         "required_freshness": g.get("required_freshness") or [],
                         "need_more": max(0, need - t) if g.get("status") == "open" else 0})
        short = [r for r in rows if r["status"] == "open" and r["threads"] < need]
        contradicted = [r for r in rows if r["status"] == "contradicted"]
        short_ids = {r["gap_id"] for r in short}
        out.append({"hypothesis_id": h.get("id"), "status": h.get("status"), "gaps": rows,
                    "open_gaps": sum(1 for r in rows if r["status"] == "open"),
                    "supported_gaps": sum(1 for r in rows if r["status"] == "supported"),
                    "contradicted_gaps": len(contradicted),
                    "min_threads": min((r["threads"] for r in rows), default=0),
                    "need_more_total": sum(r["need_more"] for r in rows),
                    "floor_reached": not short,
                    "budget_exhausted": rounds >= cap,
                    "starved": bool(short) and not contradicted and rounds < cap,
                    "queries": [q["id"] for q in queries if q.get("gap_id") in short_ids][:12]})
    out.sort(key=lambda a: (not a["starved"], a["min_threads"], -a["need_more_total"], str(a["hypothesis_id"])))
    for i, a in enumerate(out):
        a["rank"] = i + 1
    return out


def starved_rejections(new_hyps: list[dict], state: dict, policies: dict) -> list[str]:
    """Errors for REJECTED verdicts on starved hypotheses (docs/20 §1 rule 2)."""
    alloc_pol = ((policies.get("evidence") or {}).get("allocation") or {})
    if not alloc_pol.get("enforce_no_starved_rejection", True):
        return []
    pol = policies.get("evidence") or {}
    need = int(pol.get("min_independent_sources", 3))
    cap = int(pol.get("max_research_rounds", 3))
    rounds = int((state.get("rounds") or {}).get("research", 0))
    alloc = {a["hypothesis_id"]: a for a in hypothesis_allocation(state, policies)}
    errs = []
    for h in new_hyps:
        if not isinstance(h, dict) or h.get("status") != "REJECTED":
            continue
        a = alloc.get(h.get("id"))
        if a and a["starved"]:
            short = [r["gap_id"][:8] for r in a["gaps"] if r["status"] == "open" and r["need_more"]]
            errs.append(f"{h.get('id')}: cannot be REJECTED for lack of evidence — {len(short)} open gap(s) {short[:4]} "
                        f"below the {need}-thread bar after research round {rounds} of {cap} and no gap contradicted; "
                        f"keep it CHALLENGED (or HOLD) and run its queries first: {a['queries'][:6]} (starvation is not refutation)")
    return errs


def interleave_queries(queries: list[dict], allocation: list[dict], gaps: list[dict]) -> list[dict]:
    """Round-robin the compiled queries across live hypotheses, starved first,
    so a research round cannot spend itself on one branch by reading the list
    top to bottom. Stamps hypothesis_id + allocation_rank; stable for ties."""
    hyp_of_gap = {g["id"]: g.get("hypothesis_id") for g in gaps}
    order = [a["hypothesis_id"] for a in allocation]
    buckets: dict = {hid: [] for hid in order}
    rest = []
    for q in queries:
        hid = q.get("hypothesis_id") or hyp_of_gap.get(q.get("gap_id"))
        q["hypothesis_id"] = hid
        (buckets[hid] if hid in buckets else rest).append(q)
    merged: list[dict] = []
    while any(buckets.values()):
        for hid in order:
            if buckets[hid]:
                merged.append(buckets[hid].pop(0))
    merged += rest
    for i, q in enumerate(merged):
        q["allocation_rank"] = i + 1
    return merged

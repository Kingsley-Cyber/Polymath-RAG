"""Autonomous RegistryCandidate emission (docs/17 §1).

Every terminal gate calls auto_emit(): a deterministic harvest of potentially
reusable knowledge from the run's own receipts — the run never stops to
update CSVs, never mutates the active registry, and the user never has to ask.
SQLite accumulates candidates; maintenance_triggers.py decides when they
deserve a Registry Maintenance run.

Registry growth compounds REASONING, not database size: a candidate is only
emitted when the run's evidence actually exercised it (query closed a gap,
source yielded admissible evidence, whitespace survived L4, bridge was
SUPPORTED, motif recurred). Emission never touches verdicts.
"""
from __future__ import annotations

from models import stable_id


def _emit(state: dict, kind: str, name: str, payload: dict, refs: list) -> bool:
    cands = state["data"].setdefault("registry_candidates", [])
    cid = stable_id("rc", kind, name)
    if any(c.get("id") == cid for c in cands):
        return False
    cands.append({"id": cid, "kind": kind, "name": name, "payload": payload,
                  "evidence_refs": sorted(set(refs))[:10],
                  "source_run": state["run_id"],
                  "authority": "CANDIDATE",          # seed rows never = evidence
                  "status": "PROPOSED"})
    return True


def auto_emit(state: dict, policies: dict) -> str:
    d = state["data"]
    n = 0
    obs = d.get("observations") or []
    closed_gaps = {g["id"] for g in d.get("gaps") or [] if g.get("status") == "supported"}

    # query patterns that actually PRODUCED admitted observations on closed
    # gaps (docs/19): an observation names the query that found it
    # (`query_id` or `query_used`); compiled strings nobody ran are not patterns
    by_id = {q.get("id"): q for q in d.get("queries") or []}
    for o in obs:
        if o.get("gap_id") not in closed_gaps:
            continue
        q = by_id.get(o.get("query_id"))
        used = o.get("query_used") or (q or {}).get("query")
        if not used:
            continue
        n += _emit(state, "QUERY_PATTERN_CANDIDATE",
                   f"{(q or {}).get('channel') or (o.get('source_identity') or {}).get('platform') or 'web'}:{str(used)[:60]}",
                   {"channel": (q or {}).get("channel"), "query": str(used)[:200],
                    "source_family": (o.get("source_identity") or {}).get("source_family"),
                    "roles_yielded": o.get("evidence_roles")},
                   [o["id"]])
    # sources that yielded admissible evidence on closed gaps
    for o in obs:
        if o.get("gap_id") in closed_gaps and o.get("source"):
            ident = o.get("source_identity") or {}
            n += _emit(state, "SOURCE_CANDIDATE",
                       f"{ident.get('platform') or 'web'}:{ident.get('source_family')}",
                       {"platform": ident.get("platform"),
                        "source_family": ident.get("source_family"),
                        "roles_yielded": o.get("evidence_roles")},
                       [o["id"]])
    # surviving whitespace = whitespace motifs; contradicted = negative motifs
    for wh in d.get("whitespace_hypotheses") or []:
        if wh.get("state") in ("SUPPORTED", "REFINED"):
            n += _emit(state, "WHITESPACE_MOTIF_CANDIDATE", wh.get("type", "?"),
                       {"type": wh.get("type"),
                        "mismatch": (wh.get("observed_mismatch") or "")[:200]},
                       wh.get("supporting_signals") or [])
        elif wh.get("state") == "CONTRADICTED":
            n += _emit(state, "NEGATIVE_REASONING_MOTIF",
                       f"contradicted:{wh.get('type', '?')}",
                       {"type": wh.get("type"),
                        "mismatch": (wh.get("observed_mismatch") or "")[:200]},
                       wh.get("contradicting_signals") or [])
    # supported market bridges = reusable product->market bridge patterns
    for b in d.get("market_bridges") or []:
        if b.get("state") == "SUPPORTED":
            n += _emit(state, "MARKET_BRIDGE_PATTERN_CANDIDATE",
                       f"{b.get('meaning_id')}→{(b.get('market_scope') or '')[:50]}",
                       {"meaning": b.get("meaning_id"), "jobs": b.get("jobs")},
                       b.get("supporting_evidence") or [])
    # demand reroutes that survived = reroute motifs
    for rr in d.get("demand_reroutes") or []:
        if rr.get("state") in (None, "PROPOSED", "SUPPORTED"):
            n += _emit(state, "DEMAND_REROUTE_MOTIF_CANDIDATE",
                       rr.get("reroute_dimension", "?"),
                       {"dimension": rr.get("reroute_dimension"),
                        "existing_demand": (rr.get("existing_demand") or "")[:120]},
                       rr.get("evidence_refs") or [])
    # docs/19 — the missing half of the flywheel: a SUPPORTED bridge feeds the
    # registry's OWN vocabulary (mechanisms.csv / friction_library / activities)
    supported_h = [h for h in d.get("hypotheses") or [] if h.get("status") == "SUPPORTED"]
    if supported_h:
        prim = d.get("primitives") or {}
        try:
            import registry as _reg
            fams = set(((_reg.load_snapshot() or {}).get("friction_families") or []))
        except Exception:  # noqa: BLE001
            fams = set()
        for m in d.get("mechanisms") or []:
            if m.get("status") == "SUPPORTED":
                n += _emit(state, "MECHANISM_CANDIDATE", m.get("name", "?"),
                           {"principle": (m.get("principle") or "")[:300],
                            "removes_friction": m.get("removes_friction"),
                            "hypothesis_id": m.get("hypothesis_id"),
                            "support_count": len(m.get("supporting_observation_ids") or [])},
                           m.get("supporting_observation_ids") or [])
        for fam in prim.get("frictions") or []:
            n += _emit(state, "FRICTION_CANDIDATE", str(fam),
                       {"in_registry": fam in fams, "context": (d.get("signal") or "")[:120]},
                       [h["id"] for h in supported_h])
        for job in (prim.get("physical_jobs") or [])[:6]:
            n += _emit(state, "ACTIVITY_CANDIDATE", str(job)[:80],
                       {"predicates": prim.get("shared_predicates")}, [h["id"] for h in supported_h])
    # genesis of SUPPORTED hypotheses = reasoning motifs
    for h in d.get("hypotheses") or []:
        if h.get("status") == "SUPPORTED" and h.get("genesis"):
            n += _emit(state, "REASONING_MOTIF_CANDIDATE",
                       f"{h['genesis']}:{h.get('target_mechanism', '?')}",
                       {"genesis": h["genesis"],
                        "mechanism": h.get("target_mechanism"),
                        "invariant": h.get("invariant")}, [h["id"]])
    n += emit_communities(state)
    return f"auto-emitted {n} registry candidates (SQLite accumulates; maintenance decides)"


def emit_communities(state: dict) -> int:
    """docs/25 §1: an ANCHOR cluster proves a community actually spoke — it
    becomes a COMMUNITY_CANDIDATE for the registry (approval still human)."""
    n = 0
    for c in state["data"].get("lived_clusters") or []:
        if not isinstance(c, dict) or c.get("authority") != "ANCHOR":
            continue
        n += _emit(state, "COMMUNITY_CANDIDATE", str(c.get("community")),
                   {"community": c.get("community"), "friction_family": c.get("friction_family"),
                    "records": c.get("record_count"), "threads": c.get("thread_count"),
                    "independent_voices": c.get("independent_voices"), "seed_population": c.get("seed_population")},
                   list(c.get("record_ids") or []))
    return n

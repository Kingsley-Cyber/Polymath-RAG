"""Context Compiler (docs/10) — durable cognition on top of durable memory.

Ownership law: SQLite owns workflow truth (via memory.py ONLY — this module
never touches SQL), the corpus backend owns source truth, the pinned RegistrySnapshot
owns priors, graph/policy files own rules, and THIS module owns the temporary
context window presented to θ for one action. The model context is a
projection, never the memory system.

Invariant: delete chat history, generated Markdown and model memory —
`controller.py step --run <id>` must still determine the next legal action and
reconstruct the context required to perform it.

BACKFILL recovers already-known canonical state from its owner. It may never
browse, hypothesize, create evidence or change a verdict — that is research,
and research only happens through graph nodes.
"""
from __future__ import annotations

import hashlib
import json

import graph as graphmod
import memory
import models

# requirable keys that do not live in state["data"] and their canonical owner
_SPECIAL_OWNERS = {"run_identity": "controller", "registry_snapshot": "registry",
                   "evidence_authority_rules": "policies"}

# context priority (docs/10): trim P4 -> P3 -> P2 under budget pressure;
# P0 (constitution + action) and P1 (decision-critical) are never dropped.
_PRIORITY = {
    "signal": 1, "scope_request": 1, "primitives": 1, "world_model": 1,
    "hypotheses": 1, "gaps": 1, "challenges": 1, "satisfaction": 1,
    "evaluations": 1,
    "observations": 2, "corpus_evidence": 2, "lived_situations": 2,
    "slot_candidates": 2, "product_candidates": 2, "leads": 2, "queries": 2,
    "loadout": 2, "loadout_receipt": 2,
    "cross_domain_analogies": 3, "mechanisms": 3, "lenses": 3,
    "registry_snapshot": 3, "frontier_branches": 3, "frontier_rankings": 3,
    "research_plan": 3, "supplier_candidates": 3,
    # discovery modes (docs/12-14)
    "market_seed": 1, "product_seed": 1, "product_identity": 1,
    "product_claims": 1, "market_scopes": 1, "market_bridges": 1,
    "product_meanings": 1, "whitespace_hypotheses": 1, "handoff_packet": 1,
    "signal_divergences": 1, "market_reframes": 1, "promoted_scopes": 1,
    "demand_gaps": 1, "demand_reroutes": 1, "capture_assessments": 1,
    "field_signals": 2, "commerce_signals": 2, "query_nodes": 2,
    "trend_signals": 3, "corpus_signals": 3, "supply_signals": 3,
    # LIVED-WORLD-V2 (docs/25): clusters and situations are decision-critical;
    # raw records and leads are evidence-tier; questions/examples are priors
    "lived_clusters": 1, "lived_situations": 1, "provenance": 1,
    "field_records": 2, "population_leads": 2, "community_leads": 2,
    "participant_cards": 3, "corpus_questions": 3, "example_terms": 3,
}
# historical branches are P4 by default (contradicted items stay visible —
# they are decision-critical; only dead branches drop)
_STATUS_DROP = {"REJECTED", "REJECT", "COLLAPSED", "PRUNED"}


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _hash(obj) -> str:
    return hashlib.sha256(_canonical(obj).encode()).hexdigest()[:16]


def contract_of(g: dict, node: str) -> dict:
    return graphmod.node_spec(g, node).get("context") or {}


# --------------------------------------------------------------- run brief --
def build_run_brief(state: dict, g: dict, pol: dict) -> dict:
    """Small, stable, always present: the investigation in 30 seconds."""
    d = state["data"]
    decisions = [h for h in state.get("history", []) if h.get("event") == "advance"][-6:]
    open_gaps = [x.get("question") for x in d.get("gaps") or []
                 if isinstance(x, dict) and x.get("status") == "open"][:6]
    ctx_pol = pol.get("context") or {}
    return {
        "run_id": state["run_id"],
        "mode": (g.get("graph") or {}).get("id"),
        **({"corpus": state["corpus"]} if state.get("corpus") else {}),
        "original_user_goal": (d.get("signal") if isinstance(d.get("signal"), str)
                               else (d.get("signal") or {}).get("interpretation", ""))
                              if d.get("signal") else "",
        "current_scope": (d.get("scope_request") or {}).get("scope")
                         if isinstance(d.get("scope_request"), dict) else None,
        "current_node": state["node"],
        "status": state["status"],
        "verdict": state.get("verdict"),
        "rounds": state["rounds"],
        "hard_invariants": ctx_pol.get("hard_invariants") or [],
        "major_decisions": [{"node": x["node"], "to": x.get("to")} for x in decisions],
        "unresolved_critical_gaps": open_gaps,
        "progress_signature": _hash({k: len(v) if isinstance(v, list) else 1
                                     for k, v in d.items() if v}),
    }


# ----------------------------------------------------------- key resolvers --
def _resolve_special(key: str, state: dict, g: dict, pol: dict):
    if key == "run_identity":
        ident = {"run_id": state["run_id"], "mode": (g.get("graph") or {}).get("id"),
                 "node": state["node"]}
        if state.get("corpus"):
            ident["corpus"] = state["corpus"]
        return ident, "controller"
    if key == "registry_snapshot":
        try:
            import registry
            snap = registry.load_snapshot() or {}
            return {"build_id": snap.get("build_id"),
                    "counts": snap.get("counts") or
                              {k: len(v) for k, v in snap.items() if isinstance(v, list)},
                    "note": "query via registry.py CLIs — the snapshot is pinned, not inlined"}, "registry"
        except Exception:
            return None, "registry"
    if key == "evidence_authority_rules":
        rules = {k: pol.get(k) for k in
                 ("evidence_roles", "source_suitability", "freshness_requirements")
                 if pol.get(k)}
        return rules or None, "policies"
    return None, None


def _filter_items(key: str, items: list, contract: dict, state: dict) -> list:
    out = [x for x in items if not (isinstance(x, dict)
                                    and (str(x.get("status", "")).upper() in _STATUS_DROP
                                         or str(x.get("state", "")).upper() in _STATUS_DROP))]
    roles = contract.get("evidence_roles")
    if key == "observations" and roles:
        out = [o for o in out if set(o.get("evidence_roles") or []) & set(roles)]
    scope = (state["data"].get("scope_request") or {}).get("scope") \
        if isinstance(state["data"].get("scope_request"), dict) else None
    if (contract.get("branch_scope") or {}).get("current_only") and scope:
        out = [x for x in out if not isinstance(x, dict)
               or x.get("scope") in (None, scope)]
    return out


def _resolve_key(key: str, state: dict, g: dict, pol: dict, contract: dict):
    """-> (value, source, backfilled). Empty list = attempt backfill from the
    Work Graph mirror; recovery of known state, never creation of new state."""
    if key in _SPECIAL_OWNERS:
        val, src = _resolve_special(key, state, g, pol)
        return val, src, False
    d = state["data"]
    val = d.get(key) if key in d else state.get(key)
    if isinstance(val, list):
        val = _filter_items(key, val, contract, state)
        if not val:
            ntype = memory._NODE_TYPES.get(key)
            if ntype:
                rows = memory.load_work_nodes(state["run_id"], ntype)
                rows = [{k: v for k, v in r.items() if k != "_node_type"} for r in rows]
                rows = _filter_items(key, rows, contract, state)
                if rows:
                    return rows, "sqlite_work_graph", True
            return [], "state", False
        return val, "state", False
    if val in (None, "", {}):
        return None, "state", False
    return val, "state", False


def _sanitize(key: str, val, spec: dict):
    """L4 isolation: evaluator nodes get receipts, never the generator's
    persuasive narrative (docs/10 — same law as the dossier)."""
    if spec.get("sanitize") != "dossier" or key != "hypotheses" or not isinstance(val, list):
        return val
    import evaluator
    return [{k: h.get(k) for k in evaluator.DOSSIER_HYP_FIELDS if h.get(k) is not None}
            for h in val if isinstance(h, dict)]


# ---------------------------------------------------------------- compile ---
def compile_envelope(state: dict, g: dict, pol: dict, node: str | None = None) -> dict:
    """ContextContract -> RunBrief + ActionContext -> ContextEnvelope.
    Deterministic: same canonical state -> same context_hash."""
    node = node or state["node"]
    spec = graphmod.node_spec(g, node)
    contract = contract_of(g, node)
    require = list(contract.get("require") or [])
    prefer = list(contract.get("prefer") or [])
    exclude = set(contract.get("exclude") or [])
    bad = (set(require) | set(prefer)) & exclude
    if bad:
        raise ValueError(f"contract for {node!r} both requires and excludes {sorted(bad)}")

    brief = build_run_brief(state, g, pol)
    working, sources, deficits, backfilled = {}, {}, [], []
    for key in require + prefer:
        val, src, was_backfilled = _resolve_key(key, state, g, pol, contract)
        empty = val in (None, "", {}) or val == []
        if empty and key in require:
            deficits.append({"key": key,
                             "owner": _SPECIAL_OWNERS.get(key, "graph_routing"),
                             "detail": "required object does not exist yet — it must be "
                                       "produced by its owning step, never invented here"})
            continue
        if empty:
            continue
        working[key] = _sanitize(key, val, spec)
        sources[key] = src
        if was_backfilled:
            backfilled.append(key)

    import settings as _settings
    action_ctx = {
        "node": node,
        "objective": spec.get("prompt") or spec.get("executor") or node,
        # docs/16: workers learn the user's desired behavior from the frozen
        # envelope, never from chat history
        "user_preferences": _settings.for_mode(state, (g.get("graph") or {}).get("id")),
        "output_contract": spec.get("outputs") or [],
        "evidence_roles": contract.get("evidence_roles") or [],
        "branch_scope": contract.get("branch_scope") or {},
        "prohibited": sorted(exclude),
        "working_set": working,
        "law": "Everything required for this action is HERE. Do not rely on prior "
               "conversation turns; they are not deterministic infrastructure.",
    }
    excluded_budget = _apply_budget(action_ctx, contract, pol)
    status = "BLOCKED_CONTEXT_INCOMPLETE" if deficits else "READY"
    core = {"run_brief": {k: v for k, v in brief.items()},
            "action_context": action_ctx}
    manifest = {
        "context_id": "ctx_" + _hash({"run": state["run_id"], "node": node,
                                      "core": core}),
        "run_id": state["run_id"], "node": node,
        "sources": {"workflow_state": sources,
                    "registry": memory.config_hashes()["registry_build"],
                    "graph": (g.get("graph") or {}).get("id"),
                    "policy_hash": memory.config_hashes()["policy_hash"]},
        "included_objects": {k: ([x.get("id") for x in v if isinstance(x, dict) and x.get("id")]
                                 if isinstance(v, list) else "singleton")
                             for k, v in working.items()},
        "backfilled": backfilled,
        "excluded_due_to_budget": excluded_budget,
        "required_contract_complete": not deficits,
        "deficits": deficits,
        "context_hash": _hash(core),
        "compiled_at": models.now(),
    }
    return {"status": status, "run_brief": brief, "action_context": action_ctx,
            "manifest": manifest}


def _apply_budget(action_ctx: dict, contract: dict, pol: dict) -> list[str]:
    """Deterministic trimming: drop P4 then P3 then P2. Never P0/P1."""
    budget = int(((pol.get("context") or {}).get("budgets") or {})
                 .get("max_chars", 60000))
    budget = int((contract.get("budget") or {}).get("max_chars", budget))
    ws = action_ctx["working_set"]
    dropped: list[str] = []
    for level in (4, 3, 2):
        if len(_canonical(ws)) <= budget:
            break
        for key in sorted(ws, key=lambda k: -_PRIORITY.get(k, 4)):
            if _PRIORITY.get(key, 4) != level:
                continue
            if len(_canonical(ws)) <= budget:
                break
            dropped.append(key)
            del ws[key]
    return dropped


# ------------------------------------------------------------- checkpoints --
def build_checkpoint(state: dict, phase: str) -> dict:
    """Deterministic phase snapshot: recovery = latest checkpoint + deltas,
    not a semantic replay of the whole run."""
    d = state["data"]
    return {
        "phase": phase, "run_id": state["run_id"], "node": state["node"],
        "rounds": dict(state["rounds"]),
        "surviving_hypotheses": [h["id"] for h in d.get("hypotheses") or []
                                 if isinstance(h, dict)
                                 and h.get("status") not in ("REJECTED",)],
        "unresolved_gaps": [x.get("id") or x.get("question") for x in d.get("gaps") or []
                            if isinstance(x, dict) and x.get("status") == "open"],
        "resolved_gaps": [x.get("id") or x.get("question") for x in d.get("gaps") or []
                          if isinstance(x, dict) and x.get("status") not in (None, "open")],
        "counts": {k: len(v) for k, v in d.items() if isinstance(v, list) and v},
        "progress_signature": _hash({k: len(v) if isinstance(v, list) else 1
                                     for k, v in d.items() if v}),
    }


# ------------------------------------------- working_context.md projection --
_MD_WARNING = ("> **GENERATED FROM SQLITE + RUN STATE — DO NOT EDIT AS CANONICAL "
               "STATE.** One-way projection for humans and emergency recovery; "
               "if deleted, `controller.py context-export` rebuilds it.\n")


def export_working_context(state: dict, g: dict, pol: dict) -> str:
    d = state["data"]
    brief = build_run_brief(state, g, pol)
    run = memory.get_run(state["run_id"]) or {}
    cp = memory.latest_checkpoint(state["run_id"])
    lines = [f"# Run {state['run_id']}", "", _MD_WARNING,
             f"## Goal\n{brief['original_user_goal'] or '(no signal recorded)'}",
             f"\n## Position\nmode `{brief['mode']}` · node `{state['node']}` · "
             f"status **{state['status']}**"
             + (f" · verdict **{state['verdict']}**" if state.get("verdict") else "")
             + f" · research rounds {state['rounds']['research']}"]
    if cp:
        lines.append(f"\n## Latest checkpoint\n`{cp.get('phase')}` — "
                     f"signature `{cp.get('progress_signature')}`")
    live = [h for h in d.get("hypotheses") or [] if h.get("status") == "SUPPORTED"]
    if live:
        lines.append("\n## What we currently believe")
        for h in live:
            lines.append(f"- **{h.get('target_mechanism')}** — path "
                         f"{' → '.join(h.get('path') or [])}")
    if d.get("challenges"):
        lines.append("\n## Critical contradictions")
        for c in (d["challenges"] or [])[:6]:
            lines.append(f"- {c.get('statement') or c.get('id') or c}")
    if d.get("leads") or d.get("loadout"):
        lines.append("\n## Surviving products")
        for p in (d.get("leads") or d.get("loadout") or [])[:8]:
            lines.append(f"- {p.get('product_name') or p.get('name') or p.get('id')}")
    if brief["unresolved_critical_gaps"]:
        lines.append("\n## Open evidence gaps")
        lines += [f"- {q}" for q in brief["unresolved_critical_gaps"]]
    lines.append("\n## Next legal action")
    spec = graphmod.node_spec(g, state["node"])
    lines.append(f"node `{state['node']}` ({spec.get('type')}) — outputs "
                 f"{spec.get('outputs') or '(deterministic executor)'}")
    lines.append("\n## Config pins")
    lines.append(f"registry `{run.get('registry_build')}` · policy `{run.get('policy_hash')}` "
                 f"· graph `{run.get('control_graph_hash')}` · revision {run.get('revision')}")
    lines.append(f"\n## Progress signature\n`{brief['progress_signature']}`\n")
    return "\n".join(lines)

#!/usr/bin/env python3
"""Graph runner — the deterministic spine the agent drives.

The agent NEVER decides what runs next; it asks the controller.

  init    create a work state at the graph entry
    controller.py init --state candidates/run1.json --signal "storytelling ..."
  status  show current node, its type, what it needs, and edge readiness
    controller.py status --state candidates/run1.json
  submit  validate + merge reasoning outputs for the CURRENT node
    controller.py submit --state candidates/run1.json --node hypothesize --file out.json
  step    execute transforms/gates and advance along the first satisfied edge
    controller.py step --state candidates/run1.json

Loop for the agent:  status → (do what the node asks) → submit → step → repeat
until status reports node=stop. Illegal submissions and transitions are
rejected with explicit reasons — that is the point.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bridge
import context as contextmod
import executors
import memory
import graph as graphmod
import models
import transitions

SCHEMA_BY_KEY = {"product_concepts": "product_concept", "approvals": "approval",
                 "hypotheses": "hypothesis", "observations": "observation",
                 "mechanisms": "mechanism", "product_candidates": "product_candidate",
                 "supplier_candidates": "supplier_candidate", "evaluations": "evaluation",
                 # discovery modes (docs/12-14)
                 "field_signals": "market_signal", "trend_signals": "market_signal",
                 "corpus_signals": "market_signal", "supply_signals": "market_signal",
                 "commerce_signals": "market_signal",
                 "market_scopes": "market_scope", "query_nodes": "query_node",
                 "whitespace_hypotheses": "whitespace_hypothesis",
                 "product_identity": "product_identity",
                 "product_meanings": "product_meaning",
                 "market_bridges": "market_bridge",
                 "market_reframes": "market_reframe",
                 "demand_reroutes": "demand_reroute",
                 "demand_gaps": "demand_gap",
                 "capture_assessments": "capture_assessment",
                 # LIVED-WORLD-V2 (docs/25): authority labels are enforced by schema + Python, never prompt text
                 "population_leads": "population_lead", "community_leads": "population_lead",
                 "field_records": "field_record", "participant_cards": "participant_evidence_card",
                 "lived_clusters": "lived_evidence_cluster", "lived_situations": "lived_situation",
                 "slot_candidates": "product_slot", "world_model": "community_world_model"}
SINGULAR_KEYS = {"signal", "primitives", "scope_request", "world_model",
                 "market_seed", "product_seed", "product_identity", "corpus_backend",
                 "promotion_summary", "registry_patch", "row_relevance"}
MODE_GRAPHS = {"opportunity_research": "control_graph.yaml",
               "niche_loadout": "loadout_graph.yaml",
               "market_discovery": "market_discovery_graph.yaml",
               "product_anchored": "product_anchored_graph.yaml",
               "registry_maintenance": "maintenance_graph.yaml"}


def node_output_specs(g, node):
    """Derive submit specs from the graph's own `outputs` declaration — makes
    the controller graph-generic. `optional_outputs` (docs/17) are accepted at
    submit but never required to advance."""
    fixed = OUTPUT_SPECS.get(node)
    spec = graphmod.node_spec(g, node)
    if fixed:
        # docs/21: graph-declared optional outputs ride along even where a node has a fixed spec
        extra = [k for k in (spec.get("optional_outputs") or []) if k not in {f[0] for f in fixed}]
        return list(fixed) + [(k, SCHEMA_BY_KEY.get(k), k not in SINGULAR_KEYS) for k in extra]
    outs = (spec.get("outputs") or []) + (spec.get("optional_outputs") or [])
    return [(k, SCHEMA_BY_KEY.get(k), k not in SINGULAR_KEYS) for k in outs]


def node_required_keys(g, node):
    fixed = OUTPUT_SPECS.get(node)
    if fixed:
        return [k for k, _, _ in fixed]
    return list(graphmod.node_spec(g, node).get("outputs") or [])


# node -> (state.data key, schema, is_list)
OUTPUT_SPECS = {
    "understand":      [("signal", None, False)],
    "corpus":          [("corpus_evidence", None, True)],
    "primitives":      [("primitives", None, False)],
    "hypothesize":     [("hypotheses", "hypothesis", True)],
    "semantic_review": [("evaluations", "evaluation", True)],
    "challenge":       [("challenges", None, True), ("hypotheses", "hypothesis", True)],
    "web_research":    [("observations", "observation", True)],
    "mechanism":       [("mechanisms", "mechanism", True),
                        ("product_candidates", "product_candidate", True)],
    "supplier_search": [("supplier_candidates", "supplier_candidate", True)],
}


def _emit(obj):
    print(json.dumps(obj, indent=1, ensure_ascii=False))


def _node_needs(g, node):
    spec = graphmod.node_spec(g, node)
    ntype = spec.get("type")
    need = {"node": node, "type": ntype}
    if ntype in ("reason",) or spec.get("prompt"):
        need["prompt_file"] = os.path.join("prompts", f"{spec.get('prompt', node)}.md")
    if node == "semantic_review":
        need["dossier_cmd"] = "python/evaluator.py dossier --state <state>"
        need["law"] = ("FRESH subagent only (delegate_task, reasoning-role model, never the "
                       "generator's context); feed it ONLY the dossier + prompt")
    if ntype in ("reason", "retrieve", "agent"):
        need["submit_keys"] = [k for k, _, _ in node_output_specs(g, node)]
        need["action"] = "produce the listed outputs, submit them, then step"
    elif ntype in ("transform", "gate"):
        need["action"] = f"run `step` — deterministic executor {spec.get('executor')}"
    elif ntype == "terminal":
        need["action"] = "run complete"
    return need


def cmd_init(args):
    g = graphmod.load_graph(getattr(args, "graph", None) or "control_graph.yaml")
    errs = graphmod.validate_graph(g)
    if errs:
        _emit({"ok": False, "graph_errors": errs}); return 1
    state = models.new_state(os.path.splitext(os.path.basename(args.state))[0], args.signal or "")
    state["graph_file"] = getattr(args, "graph", None) or "control_graph.yaml"
    state["node"] = g["graph"]["entry"]
    if getattr(args, "corpus", None):  # provenance only — never changes behavior
        state["corpus"] = args.corpus
    if getattr(args, "document_id", None):  # docs/26 §8: document scope for the corpus lanes (retrieve + plan; never an unscoped /chat)
        state["document_scope"] = list(dict.fromkeys(args.document_id))
    if getattr(args, "settings", None) or getattr(args, "preset", None):
        import settings as settingsmod
        overrides = {}
        if getattr(args, "settings", None):
            with open(args.settings, encoding="utf-8") as f:
                overrides = json.load(f)
        try:  # preset + overrides resolved ONCE, snapshot + hash pinned
            state["settings"] = settingsmod.resolve(overrides, getattr(args, "preset", None))
        except ValueError as e:
            _emit({"ok": False, "error": "SETTINGS_REJECTED", "detail": str(e)})
            return 1
    memory.create_run(state["run_id"], args.signal or "", state["node"])
    if state.get("settings"):
        memory.record_event(state["run_id"], "SETTINGS_RESOLVED", state["settings"])
    models.save_state(state, args.state)
    _emit({"ok": True, "node": state["node"], "needs": _node_needs(g, state["node"]),
           "settings_hash": (state.get("settings") or {}).get("hash")})
    return 0


def cmd_status(args):
    state = models.load_state(args.state)
    g, pol = graphmod.load_graph(state.get("graph_file", "control_graph.yaml")), graphmod.load_policies()
    edges = []
    for e in graphmod.outgoing(g, state["node"]):
        cond = e.get("when")
        edges.append({"to": e["to"], "when": cond,
                      "ready": True if not cond else transitions.evaluate(cond, state, pol)})
    ctx = None
    if graphmod.node_spec(g, state["node"]).get("type") in ("reason", "retrieve", "agent"):
        env = contextmod.compile_envelope(state, g, pol)
        ctx = {"status": env["status"], "context_hash": env["manifest"]["context_hash"],
               "deficits": env["manifest"]["deficits"]}
    gaps_view, alloc_view = [], []
    if state["node"] in ("web_research", "curate", "gaps", "challenge", "triage"):
        import verifiers as _ver
        import allocation as _alloc
        alloc_view = [{k: a[k] for k in ("rank", "hypothesis_id", "status", "open_gaps", "supported_gaps", "contradicted_gaps",
                                         "min_threads", "need_more_total", "starved", "floor_reached")}
                      for a in _alloc.hypothesis_allocation(state, pol)]
        need_n = int((pol.get("evidence") or {}).get("min_independent_sources", 3))
        live = {h["id"] for h in state["data"].get("hypotheses") or [] if h.get("status") not in ("REJECTED", "HOLD")}
        for gp in state["data"].get("gaps") or []:
            if gp.get("hypothesis_id") not in live:
                continue
            sup = [o for o in state["data"].get("observations") or [] if o.get("gap_id") == gp["id"] and not o.get("contradicts")]
            groups = _ver.independence_groups(sup)["independent_groups"] if sup else 0
            gaps_view.append({"gap_id": gp["id"], "status": gp.get("status"), "independent_threads": groups,
                              "need_more": max(0, need_n - groups) if gp.get("status") == "open" else 0,
                              "question": (gp.get("question") or "")[:100]})
    _emit({"ok": True, "run_id": state["run_id"], "node": state["node"],
           "status": state["status"], "verdict": state.get("verdict"),
           "rounds": state["rounds"], "needs": _node_needs(g, state["node"]),
           "gaps": gaps_view, "allocation": alloc_view,
           "utilization": (__import__("utilization").compute(state) if state["node"] in ("qualify", "stop") else None),
           "lived_world": __import__("lived_world").summary(state) if state.get("graph_file", "control_graph.yaml") == "control_graph.yaml" else None,
           "edges": edges, "context": ctx,
           "counts": {k: len(v) if isinstance(v, list) else 1 for k, v in state["data"].items() if v}})
    return 0


def cmd_submit(args):
    state = models.load_state(args.state)
    g = graphmod.load_graph(state.get("graph_file", "control_graph.yaml"))
    if state["status"] == "paused":
        _emit({"ok": False, "error": "RUN_PAUSED", "detail": "resume before submitting"})
        return 1
    if args.node != state["node"]:
        _emit({"ok": False, "error": f"current node is {state['node']!r}, not {args.node!r} — no out-of-order submissions"})
        return 1
    with open(args.file, encoding="utf-8") as _pf:
        _peek = json.load(_pf)
    if "capability_failure" in _peek:
        # docs/15 §4: an unavailable external capability is RECORDED as a
        # coverage deficit, never faked and never a silent stall
        ntype = graphmod.node_spec(g, args.node).get("type")
        if ntype not in ("agent", "retrieve"):
            _emit({"ok": False, "error": "capability_failure only applies to agent/retrieve nodes"})
            return 1
        cf = dict(_peek["capability_failure"], node=args.node, at=models.now())
        state.setdefault("capability_failures", []).append(cf)
        state["history"].append({"node": args.node, "event": "capability_failure",
                                 "capability": cf.get("capability"), "at": models.now()})
        models.save_state(state, args.state)
        memory.record_event(state["run_id"], "CAPABILITY_FAILURE", cf)
        _emit({"ok": True, "recorded": "CAPABILITY_FAILURE", "node": args.node,
               "capability": cf.get("capability"),
               "law": "the run continues with an honest coverage deficit — "
                      "downstream gates decide what that costs"})
        return 0
    specs = node_output_specs(g, args.node)
    if not specs:
        _emit({"ok": False, "error": f"node {args.node!r} takes no submissions"}); return 1
    with open(args.file, encoding="utf-8") as f:
        payload = json.load(f)
    merged, errors = [], []
    pol_now = graphmod.load_policies()
    if "row_relevance" in payload and any(k == "row_relevance" for k, _, _ in specs):
        # docs/26 §2: a later node (hypothesize) may classify rows it is about to cite; the map
        # MERGES into the run's relevance and is applied before the hypotheses are validated
        import lived_world as _lw
        _rerr = _lw.validate_relevance_map(payload.get("row_relevance") or {}, state, pol_now)
        if _rerr:
            _emit({"ok": False, "schema_errors": _rerr[:20]}); return 1
        _lw.merge_relevance(state, payload.get("row_relevance") or {})
        merged.append("row_relevance")
    for key, schema, is_list in specs:
        if key == "row_relevance":
            continue
        if key not in payload:
            continue
        state["data"].setdefault(key, [] if is_list else {})
        items = payload[key] if is_list else [payload[key]]
        if schema:
            for i, item in enumerate(items):
                errors += [f"{key}[{i}]: {e}" for e in models.validate(item, schema)]
        if key == "hypotheses":
            # docs/19: evidence-side hops must cite corpus rows / observations the run holds
            known = {r.get("id") for r in state["data"].get("corpus_evidence") or [] if isinstance(r, dict)}
            known |= {o.get("id") for o in state["data"].get("observations") or [] if isinstance(o, dict)}
            # docs/25: field records and lived clusters are citable lanes too
            known |= {r.get("id") for r in state["data"].get("field_records") or [] if isinstance(r, dict)}
            known |= {c.get("id") for c in state["data"].get("lived_clusters") or [] if isinstance(c, dict)}
            errors += [f"bridge: {e}" for e in bridge.validate_all(items, pol_now, known_ids=known)]
            if args.node == "hypothesize":
                # docs/26 §2 LINEAGE LAW (fail-closed): a corpus row cited by a hop must be
                # classified (this payload may classify it via row_relevance) and not IRRELEVANT
                import lived_world as _lw
                for h in items:
                    if isinstance(h, dict):
                        _refs = [rid for v in (h.get("hop_refs") or {}).values() for rid in v or []]
                        errors += [f"relevance: {e}" for e in _lw.lineage_ref_errors(_refs, state, state["data"].get("row_relevance") or {}, f"{h.get('id')} hop_refs")]
                # docs/25 §5: the lane is declared where the bridge is written; later
                # status updates (challenge) never re-litigate anchors
                import lived_world as _lw
                errors += [f"lived: {e}" for e in _lw.validate_hypothesis_anchors(items, state, pol_now)]
                errors += [f"bridge: {e}" for e in bridge.validate_portfolio(items, pol_now)]
                errors += [f"lived: {e}" for e in _lw.validate_portfolio_anchors(items, state, pol_now)]
            if args.node == "challenge":
                # docs/20 §1: starvation is not refutation
                import allocation as _alloc
                errors += [f"allocation: {e}" for e in _alloc.starved_rejections(items, state, pol_now)]
        if key == "primitives" and items and isinstance(items[0], dict):
            # docs/26: source-agnostic interpretation objects ride inside primitives; validated
            # here and mirrored into their own data keys (Work Graph objects, context priorities).
            # LINEAGE LAW (fail-closed): every evidence_ref must exist and, for corpus rows, be
            # classified in row_relevance and not IRRELEVANT — an unclassified row is readable,
            # never citable.
            import lived_world as _lw
            prim = items[0]
            _rel = {**(state["data"].get("row_relevance") or {}), **(prim.get("row_relevance") or {})}
            errors += _lw.validate_relevance_map(prim.get("row_relevance") or {}, state, pol_now)
            for i, x in enumerate(prim.get("latent_structures") or []):
                errors += [f"latent_structures[{i}]: {e}" for e in models.validate(x, "latent_structure")]
                errors += _lw.lineage_ref_errors((x or {}).get("evidence_refs"), state, _rel, f"latent_structures[{i}]")
            for i, x in enumerate(prim.get("corpus_observations") or []):
                errors += [f"corpus_observations[{i}]: {e}" for e in models.validate(x, "corpus_observation")]
                errors += _lw.lineage_ref_errors((x or {}).get("evidence_refs"), state, _rel, f"corpus_observations[{i}]")
            for k, refs in (prim.get("evidence_refs") or {}).items():
                errors += _lw.lineage_ref_errors(refs, state, _rel, f"primitives.evidence_refs.{k}")
            if not errors:
                state["data"]["latent_structures"] = list(prim.get("latent_structures") or [])
                state["data"]["corpus_observations"] = list(prim.get("corpus_observations") or [])
                _lw.merge_relevance(state, prim.get("row_relevance") or {})
        if key in ("population_leads", "community_leads"):
            import lived_world as _lw
            errors += [f"lead: {e}" for e in _lw.validate_leads(items, state)]
        if key == "field_records":
            import lived_world as _lw
            errors += [f"record: {e}" for e in _lw.validate_records(items, state, pol_now)]
        if key == "lived_situations":
            import lived_world as _lw
            errors += [f"situation: {e}" for e in _lw.validate_situations(items, state, pol_now)]
        if key == "product_concepts" and items:
            # docs/19 portfolio law: 3-6 distinct concepts, >=2 variations each, on SUPPORTED mechanisms
            import ideation as _ideation
            errors += [f"ideation: {e}" for e in _ideation.validate_concepts(items, state, pol_now)]
        if key == "observations":
            import verifiers
            _, verrs = verifiers.admit_observations(items, graphmod.load_policies())
            errors += [f"evidence: {e}" for e in verrs]
        if not errors:
            if is_list:
                existing = {x.get("id") for x in state["data"][key] if isinstance(x, dict)}
                fresh = [x for x in items if not (isinstance(x, dict) and x.get("id") in existing)]
                # challenge node may UPDATE hypothesis statuses in place
                if args.node == "challenge" and key == "hypotheses":
                    by_id = {x.get("id"): x for x in items if isinstance(x, dict)}
                    for idx, old in enumerate(state["data"][key]):
                        if old.get("id") in by_id:
                            state["data"][key][idx] = by_id.pop(old["id"])
                    fresh = list(by_id.values())
                state["data"][key].extend(fresh)
            else:
                state["data"][key] = items[0]
            merged.append(key)
    if errors:
        _emit({"ok": False, "schema_errors": errors[:20]}); return 1
    if not merged:
        _emit({"ok": False, "error": f"payload had none of {[k for k, _, _ in specs]}"}); return 1
    disposition, action_ref = memory.apply_submission(state["run_id"], args.node, payload)
    if disposition == "ALREADY_APPLIED":
        _emit({"ok": True, "idempotent": "ALREADY_APPLIED", "action_id": action_ref,
               "note": "identical payload was already applied — no duplicate mutation"})
        return 0
    if disposition == "CONFLICT":
        _emit({"ok": False, "error": "IDEMPOTENCY_CONFLICT",
               "action_id": action_ref,
               "detail": "a DIFFERENT result was already applied for this node at this "
                         "revision — refusing divergent duplicate; inspect before retrying"})
        return 1
    state["history"].append({"node": args.node, "event": "submit", "keys": merged, "at": models.now()})
    models.save_state(state, args.state)
    memory.sync_work_nodes(state["run_id"], state)
    _emit({"ok": True, "merged": merged, "action_id": action_ref}); return 0


def cmd_step(args):
    state = models.load_state(args.state)
    g, pol = graphmod.load_graph(state.get("graph_file", "control_graph.yaml")), graphmod.load_policies()
    run = memory.get_run(state["run_id"])
    if run is None:
        memory.create_run(state["run_id"], state["data"].get("signal", ""), state["node"])
        run = memory.get_run(state["run_id"])
    # terminal runs are immutable AND readable — config evolution after a run
    # finished is not drift, so check terminal first
    if state["status"] == "stopped" or run.get("status") == "stopped":
        _emit({"ok": True, "node": state["node"], "status": "stopped",
               "verdict": state.get("verdict") or run.get("verdict"),
               "terminal": "immutable — a terminal run never changes"})
        return 0
    if state["status"] == "paused":
        _emit({"ok": False, "error": "RUN_PAUSED", "node": state["node"],
               "detail": "human-operable lifecycle: `resume` to continue, `abandon` to end"})
        return 1
    drifted = memory.check_drift(run)
    if drifted:
        memory.record_event(state["run_id"], "BLOCKED_CONFIG_DRIFT", {"drifted": drifted})
        _emit({"ok": False, "error": "BLOCKED_CONFIG_DRIFT", "drifted": drifted,
               "detail": "graph/policy/loop/schema/prompt files changed since this run "
                         "started — never silently run an old Work Graph through new "
                         "rules. Finish/abandon the run or restore the artifacts."})
        return 1
    node = state["node"]
    spec = graphmod.node_spec(g, node)
    ntype = spec.get("type")
    note = None
    if ntype in ("transform", "gate"):
        fn = executors.EXECUTORS.get(spec.get("executor", ""))
        if not fn:
            _emit({"ok": False, "error": f"no executor {spec.get('executor')!r}"}); return 1
        note = fn(state, pol)
    elif ntype in ("reason", "retrieve", "agent"):
        missing = [k for k in node_required_keys(g, node) if not state["data"].get(k)]
        # PER-VISIT SUBMISSION (measured 2026-09-03 on a live run): a loop node
        # re-entered with last round's outputs still in state advanced on a
        # bare `step`, burning a research round with zero new evidence. Nodes
        # declaring `fresh_submission_per_visit: true` in the graph (the
        # evidence lanes) need a submission or capability_failure for EACH
        # entry; outputs left over from an earlier visit never satisfy it.
        # Accumulating nodes (the loadout dig loop) keep the default. The graph
        # entry node has no advance-into event, so `init --signal` still passes.
        hist = state.get("history") or []
        entries = [i for i, h in enumerate(hist) if h.get("event") == "advance" and h.get("to") == node] \
            if spec.get("fresh_submission_per_visit") else []
        if entries:
            since = hist[entries[-1] + 1:]
            answered = any(h.get("node") == node and h.get("event") in ("submit", "capability_failure")
                           for h in since)
            if not answered:
                missing = missing or list(node_required_keys(g, node))
                failed_this_visit = [h for h in since if h.get("node") == node
                                     and h.get("event") == "capability_failure"]
            else:
                failed_this_visit = None
        else:
            failed_this_visit = None
        failed_here = failed_this_visit if failed_this_visit is not None else [
            cf for cf in state.get("capability_failures") or [] if cf.get("node") == node]
        if missing and failed_here and ntype in ("agent", "retrieve"):
            # capability down: proceed WITH the deficit — coverage gates stay
            # honest downstream; never fake success, never stall forever
            note = (f"CAPABILITY_FAILURE({failed_here[-1].get('capability')}) — "
                    f"advancing without {missing}; coverage deficit recorded")
            missing = []
        if missing:
            # docs/10: compile the ContextEnvelope BEFORE exposing the action.
            # A blocked contract means a required object genuinely does not
            # exist — surface that, don't hand θ an under-specified prompt.
            envelope = contextmod.compile_envelope(state, g, pol, node)
            if envelope["status"] == "BLOCKED_CONTEXT_INCOMPLETE":
                memory.record_event(state["run_id"], "CONTEXT_BLOCKED",
                                    {"node": node,
                                     "deficits": envelope["manifest"]["deficits"]})
                _emit({"ok": False, "error": "BLOCKED_CONTEXT_INCOMPLETE",
                       "deficits": envelope["manifest"]["deficits"],
                       "detail": "backfill recovers known state only — it never "
                                 "researches; the owning step must produce these"})
                return 1
            action = memory.create_action(
                state["run_id"], node, f"{ntype.upper()}_{node}".upper(),
                {"needs": _node_needs(g, node), "missing": missing})
            frozen = memory.get_envelope(action["action_id"])
            if frozen is None:
                memory.attach_envelope(action["action_id"], state["run_id"], node, envelope)
                frozen = envelope
            _emit({"ok": False, "error": f"node {node!r} outputs not submitted yet: {missing}",
                   "needs": _node_needs(g, node),
                   "action_id": action["action_id"],
                   "attempt": action.get("attempt_count", 1),
                   "context_envelope": frozen,
                   "durable": "this exact pending action AND its frozen context survive "
                              "crashes — a re-step returns the SAME packet, never a "
                              "slightly different recompile"})
            return 1
    for e in graphmod.outgoing(g, node):
        cond = e.get("when")
        if cond is None or transitions.evaluate(cond, state, pol):
            # docs/19 on_enter: a deterministic executor that runs the moment the run
            # arrives at a node (e.g. corpus_plan compiles corpus reformulations)
            _enter = graphmod.node_spec(g, e["to"]).get("on_enter")
            if _enter:
                _fn = executors.EXECUTORS.get(_enter)
                if not _fn:
                    _emit({"ok": False, "error": f"no on_enter executor {_enter!r} for {e['to']!r}"}); return 1
                try:
                    _enter_note = _fn(state, pol)
                except Exception as exc:  # noqa: BLE001 — a hook failure is a visible deficit, never a stuck run
                    _enter_note = f"FAILED {type(exc).__name__}: {exc}"
                    state["history"].append({"node": e["to"], "event": "on_enter_error", "executor": _enter,
                                             "error": _enter_note, "at": models.now()})
                note = f"{note} | on_enter: {_enter_note}" if note else f"on_enter: {_enter_note}"
            state["history"].append({"node": node, "event": "advance", "to": e["to"],
                                     "note": note, "at": models.now()})
            state["node"] = e["to"]
            terminal = graphmod.node_spec(g, e["to"]).get("type") == "terminal"
            if terminal:
                state["status"] = "stopped"
                if not state.get("verdict"):
                    state["verdict"] = "STOPPED_WITHOUT_QUALIFICATION"
            models.save_state(state, args.state)
            memory.sync_work_nodes(state["run_id"], state)
            memory.record_event(state["run_id"], "NODE_ADVANCED",
                                {"from": node, "to": e["to"], "note": note})
            phase = spec.get("checkpoint")
            if phase:  # docs/10: recovery = latest checkpoint + deltas
                memory.record_event(state["run_id"], "CHECKPOINT",
                                    contextmod.build_checkpoint(state, phase))
            if state.get("satisfaction"):
                memory.write_check(state["run_id"], "ROLE_COVERAGE", "L2",
                                   "SATISFIED" if state["satisfaction"]["core_satisfied"] else "UNSATISFIED",
                                   state["satisfaction"])
            memory.update_run(state["run_id"], node=state["node"],
                              status="stopped" if terminal else None,
                              verdict=state.get("verdict") if terminal else None,
                              cycle=state["rounds"]["research"], bump_revision=True)
            if terminal:
                memory.record_event(state["run_id"], "TERMINAL_REACHED",
                                    {"verdict": state.get("verdict")})
            _emit({"ok": True, "advanced_to": state["node"], "note": note,
                   "status": state["status"], "verdict": state.get("verdict"),
                   "needs": _node_needs(g, state["node"])})
            return 0
    _emit({"ok": False, "error": f"no satisfied edge out of {node!r}", "note": note,
           "hint": "conditions are computed from evidence counts — add evidence or accept the verdict"})
    models.save_state(state, args.state)
    return 1


def cmd_context_export(args):
    """One-way projection SQLite/state -> working_context.md. Debug + human
    recovery only; NEVER canonical (docs/10 — Markdown is not the authority)."""
    state = models.load_state(args.state)
    g, pol = graphmod.load_graph(state.get("graph_file", "control_graph.yaml")), graphmod.load_policies()
    md = contextmod.export_working_context(state, g, pol)
    out = args.out or (os.path.splitext(args.state)[0] + ".working_context.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    _emit({"ok": True, "working_context": out,
           "law": "one-way projection — edits here never flow back into canonical state"})
    return 0


def cmd_handoff(args):
    """Mode handoff = a NEW child run with an explicit HandoffPacket
    (docs/14 §37-38). The parent run's type never mutates; the child inherits
    promoted canonical objects + unresolved questions, never the parent's
    whole context window."""
    parent = models.load_state(args.state)
    if args.to_mode not in MODE_GRAPHS:
        _emit({"ok": False, "error": f"unknown mode {args.to_mode!r}",
               "modes": sorted(MODE_GRAPHS)})
        return 1
    d = parent["data"]
    promoted = None
    for pool in (d.get("promoted_scopes"), d.get("market_scopes"),
                 d.get("top_bridges"), d.get("market_bridges"), d.get("leads")):
        promoted = next((x for x in pool or [] if x.get("id") == args.scope
                         or x.get("scope_id") == args.scope), None)
        if promoted:
            break
    if promoted is None:
        _emit({"ok": False, "error": f"promoted object {args.scope!r} not found in parent state"})
        return 1
    evidence_refs = sorted({o["id"] for o in d.get("observations") or []
                            if isinstance(o, dict) and o.get("id")})
    packet = {
        "source_run": parent["run_id"],
        "from_mode": (graphmod.load_graph(parent.get("graph_file", "control_graph.yaml"))
                      .get("graph") or {}).get("id"),
        "destination_mode": args.to_mode,
        "user_goal": d.get("signal") if isinstance(d.get("signal"), str)
                     else (d.get("signal") or {}).get("interpretation", ""),
        "promoted_scope": promoted,
        "evidence_refs": evidence_refs[:40],
        "unresolved_questions": [g.get("question") for g in d.get("gaps") or []
                                 if g.get("status") == "open"][:8],
        "prior_rejections": [x.get("id") for x in
                             (d.get("market_scopes") or []) + (d.get("market_bridges") or [])
                             if x.get("status") == "COLLAPSED" or x.get("state") in
                             ("PRUNED", "CONTRADICTED", "UNSUPPORTED")][:20],
        "registry_snapshot": memory.config_hashes()["registry_build"],
        "authority_boundaries": (graphmod.load_policies().get("authority_laws") or []),
        "source_checkpoint": (memory.latest_checkpoint(parent["run_id"]) or {}).get("phase"),
    }
    g = graphmod.load_graph(MODE_GRAPHS[args.to_mode])
    errs = graphmod.validate_graph(g)
    if errs:
        _emit({"ok": False, "graph_errors": errs}); return 1
    label = (promoted.get("market") or promoted.get("market_scope")
             or promoted.get("scope_id") or args.scope)
    child = models.new_state(os.path.splitext(os.path.basename(args.out))[0],
                             f"{packet['user_goal']} [handoff from {parent['run_id']}: {label}]")
    child["graph_file"] = MODE_GRAPHS[args.to_mode]
    child["node"] = g["graph"]["entry"]
    child["data"]["handoff_packet"] = packet
    memory.create_run(child["run_id"], child["data"]["signal"], child["node"])
    memory.record_event(parent["run_id"], "HANDOFF",
                        {"child_run_id": child["run_id"], "to_mode": args.to_mode,
                         "promoted": args.scope})
    memory.record_event(child["run_id"], "HANDOFF_RECEIVED",
                        {"parent_run_id": parent["run_id"],
                         "promoted": args.scope,
                         "source_checkpoint": packet["source_checkpoint"]})
    models.save_state(child, args.out)
    _emit({"ok": True, "child_state": args.out, "child_run_id": child["run_id"],
           "mode": args.to_mode, "entry": child["node"],
           "packet_keys": sorted(packet)})
    return 0


def cmd_pause(args):
    """Human-operable lifecycle (docs/15 §8): the user never needs to kill a
    process because a loop misbehaves."""
    state = models.load_state(args.state)
    if state["status"] != "running":
        _emit({"ok": False, "error": f"cannot pause a {state['status']} run"}); return 1
    state["status"] = "paused"
    models.save_state(state, args.state)
    memory.update_run(state["run_id"], status="paused")
    memory.record_event(state["run_id"], "RUN_PAUSED", {"node": state["node"]})
    _emit({"ok": True, "status": "paused", "node": state["node"],
           "note": "pending action + frozen envelope preserved; `resume` continues exactly here"})
    return 0


def cmd_resume(args):
    state = models.load_state(args.state)
    if state["status"] != "paused":
        _emit({"ok": False, "error": f"cannot resume a {state['status']} run"}); return 1
    state["status"] = "running"
    models.save_state(state, args.state)
    memory.update_run(state["run_id"], status="running")
    memory.record_event(state["run_id"], "RUN_RESUMED", {"node": state["node"]})
    _emit({"ok": True, "status": "running", "node": state["node"]})
    return 0


def cmd_abandon(args):
    state = models.load_state(args.state)
    if state["status"] == "stopped":
        _emit({"ok": False, "error": "already terminal — a terminal run never changes"}); return 1
    state["status"] = "stopped"
    state["verdict"] = "ABANDONED"
    models.save_state(state, args.state)
    memory.update_run(state["run_id"], status="stopped", verdict="ABANDONED",
                      terminal_reason=args.reason or "user abandoned")
    memory.record_event(state["run_id"], "RUN_ABANDONED",
                        {"node": state["node"], "reason": args.reason or "user abandoned"})
    _emit({"ok": True, "verdict": "ABANDONED", "node": state["node"],
           "note": "terminal and immutable; partial state remains readable and reportable"})
    return 0


def cmd_triage_run(args):
    """RUN TRIAGE: lay out the run's bugs (read-only). Exit 1 when a BLOCKER
    or DEFECT is present so scripts can gate on it."""
    import run_triage
    res = run_triage.triage(args.state, graphmod.load_policies(),
                            stale_minutes=args.stale_minutes)
    if args.markdown:
        print(run_triage.to_markdown(res))
        if getattr(args, 'markdown', False):
            print(run_triage.utilization_markdown(args.state))
    else:
        _emit(res)
    return 0 if res["ok"] else 1


def cmd_doctor(args):
    import doctor
    result = doctor.run()
    _emit(result)
    return 0 if result["ok"] else 1


def main():
    p = argparse.ArgumentParser(prog="controller")
    sub = p.add_subparsers(dest="cmd", required=True)
    dp = sub.add_parser("doctor")
    dp.set_defaults(_fn=cmd_doctor)
    for name in ("init", "status", "submit", "step", "context-export", "handoff",
                 "pause", "resume", "abandon", "triage-run"):
        sp = sub.add_parser(name)
        sp.add_argument("--state", required=True)
        if name == "triage-run":
            sp.add_argument("--markdown", action="store_true",
                            help="table for humans (default: JSON for the agent)")
            sp.add_argument("--stale-minutes", type=int, default=30, dest="stale_minutes",
                            help="a live action older than this is reported as stalled")
        if name == "init":
            sp.add_argument("--signal", default="")
            sp.add_argument("--graph", default=None)
            sp.add_argument("--settings", default=None)
            sp.add_argument("--preset", default=None)
            sp.add_argument("--corpus", default=None,
                            help="corpus backend identity for provenance (e.g. 'polymath-mcp', 'qdrant:mydocs')")
            sp.add_argument("--document-id", action="append", default=None, dest="document_id",
                            help="docs/26 §8: restrict the corpus lanes to these document ids (repeatable); /chat is never called unscoped while a scope is active")
        if name == "submit":
            sp.add_argument("--node", required=True)
            sp.add_argument("--file", required=True)
        if name == "context-export":
            sp.add_argument("--out", default=None)
        if name == "handoff":
            sp.add_argument("--to-mode", required=True, dest="to_mode")
            sp.add_argument("--scope", required=True)
            sp.add_argument("--out", required=True)
        if name == "abandon":
            sp.add_argument("--reason", default=None)
    args = p.parse_args()
    if getattr(args, "_fn", None):
        return args._fn(args)
    return {"init": cmd_init, "status": cmd_status, "submit": cmd_submit,
            "step": cmd_step, "context-export": cmd_context_export,
            "handoff": cmd_handoff, "pause": cmd_pause, "resume": cmd_resume,
            "abandon": cmd_abandon, "triage-run": cmd_triage_run}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())

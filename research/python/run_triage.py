#!/usr/bin/env python3
"""RUN TRIAGE — lay out a run's bugs (read-only, deterministic).

`controller.py triage-run --state <run.json> [--markdown] [--stale-minutes N]`

Everything a stuck or suspicious run can be wrong about, in one list, from the
two authorities the skill already has: the state JSON and SQLite (through
memory.py — the one module allowed to know SQLite exists). Nothing here
mutates anything. Each finding carries a severity, a stable code, WHERE it
was found, WHAT is wrong and the FIX the operator (or the agent) should apply:

  BLOCKER  the run cannot legitimately continue (JSON/SQLite disagree,
           config drift, broken one-writer law, ...)
  DEFECT   state that violates a law the controller enforces at submit time
           (rows that would be rejected today, inconsistent gap closure, ...)
  SMELL    honest deficits and stalls worth a look (starved gaps, unparsed
           suppliers, exhausted loops, recorded warnings, missing lanes)

qualify.py's architecture invariants are included verbatim (prefixed
QUALIFY) so this is a superset, not a rival. Verdict: ok == no BLOCKER and no
DEFECT.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bridge  # noqa: E402
import graph as graphmod  # noqa: E402
import memory  # noqa: E402
import models  # noqa: E402
import verifiers  # noqa: E402

SEVERITIES = ("BLOCKER", "DEFECT", "SMELL")
_NON_USD = ("¥", "€", "£", "₹", "₩", "RMB", "CNY", "EUR", "GBP", "JPY", "INR")


def _parse_ts(s: str | None) -> _dt.datetime | None:
    if not s:
        return None
    try:
        t = _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


class _Bugs:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, severity: str, code: str, where: str, message: str, fix: str) -> None:
        assert severity in SEVERITIES
        self.items.append({"severity": severity, "code": code, "where": where,
                           "message": message[:400], "fix": fix[:300]})


def _schema_by_key() -> dict:
    """data key -> schema name, derived the same way the controller does."""
    import controller  # local import: controller imports many modules
    out = {}
    for specs in controller.OUTPUT_SPECS.values():
        for key, schema, _is_list in specs:
            if schema:
                out[key] = schema
    out.update({k: v for k, v in controller.SCHEMA_BY_KEY.items() if v})
    return out


def triage(state_path: str, policies: dict, stale_minutes: int = 30) -> dict:
    bugs = _Bugs()
    state = models.load_state(state_path)
    g = graphmod.load_graph(state.get("graph_file", "control_graph.yaml"))
    d = state.get("data") or {}
    node = state.get("node")
    now = _dt.datetime.now(_dt.timezone.utc)

    # -- graph position -------------------------------------------------------
    try:
        graphmod.node_spec(g, node)
    except Exception:  # noqa: BLE001
        bugs.add("BLOCKER", "NODE_UNKNOWN", "state.node",
                 f"node {node!r} is not in {state.get('graph_file', 'control_graph.yaml')}",
                 "the graph file changed under the run: resume under the graph it was minted with")
    # -- graph dead end: no ready edge and nothing to submit --------------------
    try:
        import transitions as _tr
        spec = graphmod.node_spec(g, node)
        outs = graphmod.outgoing(g, node)
        if state.get("status") == "running" and spec.get("type") in ("transform", "gate") and outs \
                and not any((not e.get("when")) or _tr.evaluate(e["when"], state, policies) for e in outs):
            bugs.add("BLOCKER", "GRAPH_DEAD_END", f"graph.edges[{node}]",
                     "no outgoing edge condition is true and the node takes no submission — `step` will never advance",
                     "an edge-condition gap in the graph/transitions (report it); as an operator: abandon or hand-fix the state")
    except Exception:  # noqa: BLE001 — triage must not crash on an odd graph
        pass
    if state.get("status") == "running" and state.get("verdict") and node != "stop":
        bugs.add("SMELL", "VERDICT_BEFORE_STOP", "state.verdict",
                 f"verdict {state['verdict']!r} set while still running at {node!r}",
                 "expected only between a gate setting the verdict and the edge routing to stop; step once")

    # -- docs/20: starvation vs refutation, sourcing per concept --------------
    try:
        import verifiers as _ver
        _need = int((policies.get("evidence") or {}).get("min_independent_sources", 3))
        _cap = int((policies.get("evidence") or {}).get("max_research_rounds", 3))
        _rounds = int((state.get("rounds") or {}).get("research", 0))
        _gaps = d.get("gaps") or []
        for h in d.get("hypotheses") or []:
            if h.get("status") != "REJECTED":
                continue
            hg = [g for g in _gaps if g.get("hypothesis_id") == h.get("id")]
            if not hg or any(g.get("status") == "contradicted" for g in hg) or _rounds >= _cap:
                continue
            short = []
            for g in hg:
                sup = [o for o in d.get("observations") or [] if o.get("gap_id") == g["id"] and not o.get("contradicts")]
                t = _ver.independence_groups(sup)["independent_groups"] if sup else 0
                if g.get("status") == "open" and t < _need:
                    short.append((g["id"][:8], t))
            if short:
                bugs.add("DEFECT", "STARVED_REJECTION", f"data.hypotheses[{h.get('id')}]",
                         f"REJECTED with {len(short)} open gap(s) below the {_need}-thread bar {short[:4]}, no contradicted gap, round {_rounds}/{_cap}",
                         "starvation is not refutation: set CHALLENGED/HOLD and route the next research round to it (docs/20 §1)")
        if d.get("product_concepts") and node in ("normalize_supplier", "qualify", "stop", "report"):
            for c in d["product_concepts"]:
                cs = [s for s in d.get("supplier_candidates") or [] if s.get("concept_id") == c.get("id")]
                if not cs:
                    bugs.add("DEFECT", "CONCEPT_UNSOURCED", f"data.product_concepts[{c.get('id')}]",
                             f"concept {c.get('name')!r} has no supplier candidate of its own",
                             "run the concept's sourcing_plan job; if the market has nothing, the report says UNSOURCED (docs/20 §2)")
    except Exception:  # noqa: BLE001
        pass

    # -- JSON vs SQLite -------------------------------------------------------
    run = memory.get_run(state["run_id"])
    if not run:
        bugs.add("BLOCKER", "RUN_ROW_MISSING", "sqlite.runs",
                 "no run row — the state file is orphaned from the memory layer",
                 "run `step` once (it creates the row) or restore the DB this run was created in")
    else:
        if run.get("current_graph_node") != node:
            bugs.add("BLOCKER", "NODE_DISAGREE", "state.node vs sqlite.runs.current_graph_node",
                     f"JSON says {node!r}, SQLite says {run.get('current_graph_node')!r} — a step crashed between save_state and update_run",
                     "resume from SQLite's node: set state.node to it (the action log is the authority), then step")
        if (state.get("status") == "stopped") != (run.get("status") == "stopped"):
            bugs.add("BLOCKER", "STATUS_DISAGREE", "state.status vs sqlite.runs.status",
                     f"JSON {state.get('status')!r} vs SQLite {run.get('status')!r}", "reconcile before any further step")
        if state.get("verdict") and run.get("verdict") and state["verdict"] != run["verdict"]:
            bugs.add("BLOCKER", "VERDICT_DISAGREE", "state.verdict vs sqlite.runs.verdict",
                     f"JSON {state['verdict']!r} vs SQLite {run['verdict']!r}", "reconcile before reporting")
        drifted = memory.check_drift(run)
        if drifted:
            bugs.add("BLOCKER", "CONFIG_DRIFT", "sqlite.runs.*_hash",
                     f"run pinned to a different config than the tree: {drifted}",
                     "finish the run on the pinned config, or abandon and re-init; never edit the pins")
        if not run.get("registry_build"):
            bugs.add("DEFECT", "REGISTRY_UNPINNED", "sqlite.runs.registry_build",
                     "run not pinned to a registry build", "re-init: `python3 python/registry.py build` then init")

    # -- actions / events (the one-writer law and stalls) ----------------------
    audit = memory.run_audit(state["run_id"]) if run else None
    if audit:
        if audit["live_actions"] > 1:
            bugs.add("BLOCKER", "LIVE_ACTIONS_MULTI", "sqlite.actions",
                     f"{audit['live_actions']} live actions (one-writer law broken)",
                     "mark the stale one FAILED via the audit trail; never delete rows")
        if state.get("status") == "stopped" and audit["live_actions"]:
            bugs.add("BLOCKER", "TERMINAL_WITH_LIVE_ACTION", "sqlite.actions",
                     "terminal run still holds a live action", "close the action; terminal runs are immutable")
        if not audit["events_monotonic"]:
            bugs.add("BLOCKER", "EVENTS_NOT_MONOTONIC", "sqlite.events", "event log sequence not strictly increasing",
                     "the DB was written by two processes; keep the longer log, re-audit")
        if audit["model_actions"] and audit["model_actions_with_envelope"] < audit["model_actions"]:
            bugs.add("DEFECT", "ACTION_NO_ENVELOPE", "sqlite.context_envelopes",
                     f"{audit['model_actions'] - audit['model_actions_with_envelope']} model actions without a frozen ContextEnvelope",
                     "run `status` (it recompiles) then `step`; envelopes are minted at claim time")
        pend = memory.pending_action(state["run_id"])
        if pend:
            created = _parse_ts(pend.get("created_at"))
            age_min = (now - created).total_seconds() / 60 if created else None
            if age_min is not None and age_min > stale_minutes:
                bugs.add("SMELL", "LIVE_ACTION_STALE", f"sqlite.actions[{pend.get('action_id')}]",
                         f"{pend.get('action_type')} at {pend.get('graph_node')} pending for {age_min:.0f} min",
                         "the agent never submitted: re-read `status` needs, submit or record capability_failure")
        for et, n in sorted((audit.get("event_types") or {}).items()):
            if et in ("BLOCKED_CONFIG_DRIFT", "CONTEXT_BLOCKED") or "FAIL" in et:
                bugs.add("SMELL", "BLOCKED_EVENTS", "sqlite.events", f"{n} × {et}",
                         "read the event payloads: each names the invariant that blocked the step")

    # -- deficits the run already admitted --------------------------------------
    caps = [h for h in state.get("history") or [] if h.get("event") == "capability_failure"]
    for c in caps:
        bugs.add("SMELL", "CAPABILITY_DEFICIT", f"history[{c.get('node')}]",
                 f"{c.get('capability')}: {str(c.get('detail'))[:120]}",
                 "legitimate, but label the outcome by its deficit (docs/18 §6); never present as grounded")
    for w in state.get("warnings") or []:
        bugs.add("SMELL", "RECORDED_WARNING", w.get("where", "state.warnings"), str(w.get("error"))[:200],
                 "a non-fatal persistence failure; check the SQLite path and disk")

    # -- stored rows re-validated against today's schemas ----------------------
    by_key = _schema_by_key()
    for key, schema in sorted(by_key.items()):
        rows = d.get(key)
        if not isinstance(rows, list):
            continue
        bad = 0
        first = None
        for i, row in enumerate(rows):
            errs = models.validate(row, schema) if isinstance(row, dict) else [f"{key}[{i}]: not an object"]
            if errs:
                bad += 1
                first = first or f"{key}[{i}]: {errs[0]}"
        if bad:
            bugs.add("DEFECT", "SCHEMA_INVALID_ROWS", f"data.{key}",
                     f"{bad} of {len(rows)} rows fail schema {schema!r} (first: {first})",
                     "rows entered under a weaker validator; fix or drop them before the next submit")

    # -- corpus contract (docs/18 §3) ---------------------------------------
    corpus_rows = d.get("corpus_evidence") or []
    notes = [r for r in corpus_rows if not (isinstance(r, dict) and r.get("id") and r.get("summary") and r.get("source"))]
    if notes:
        bugs.add("DEFECT", "CORPUS_ROW_NOT_EVIDENCE", "data.corpus_evidence",
                 f"{len(notes)} of {len(corpus_rows)} rows lack id/summary/source — notes, not evidence",
                 "re-run the corpus adapter (python/corpus_polymath.py) or add the missing origin; notes cannot ground hypotheses")
    past_corpus = any(h.get("to") == "primitives" for h in state.get("history") or [] if h.get("event") == "advance")
    if past_corpus and not corpus_rows and not any(c.get("capability") == "corpus" for c in caps):
        bugs.add("SMELL", "CORPUS_ROWS_NONE", "data.corpus_evidence",
                 "past the corpus node with zero rows and no recorded corpus deficit",
                 "a signal-only run must be labeled: submit capability_failure(corpus) next time (docs/18 §6)")

    # -- evidence authority + independence (the demand-lane monopoly) --------
    obs = d.get("observations") or []
    _, verrs = verifiers.admit_observations(obs, policies)
    if verrs:
        bugs.add("DEFECT", "OBS_INADMISSIBLE", "data.observations",
                 f"{len(verrs)} observations violate the authority table today (first: {verrs[0][:120]})",
                 "a source proves only what it is qualified to prove; drop or re-source them")
    seen_q: dict[str, int] = {}
    for o in obs:
        q = (o.get("quote_ref") or "").strip().lower()
        if q:
            key = (q, o.get("gap_id"))           # docs/19: one quote may answer two gaps — a duplicate is the same quote on the SAME gap
            seen_q[key] = seen_q.get(key, 0) + 1
    dups = sum(n - 1 for n in seen_q.values() if n > 1)
    if dups:
        bugs.add("SMELL", "OBS_DUPLICATE", "data.observations", f"{dups} duplicate (quote, gap) observations",
                 "the curate step dedupes; if it already ran, a later submit re-added them")
    gaps = d.get("gaps") or []
    gap_ids = {gp.get("id") for gp in gaps}
    orphan = [o.get("id") for o in obs if o.get("gap_id") and o.get("gap_id") not in gap_ids]
    if orphan:
        bugs.add("SMELL", "OBS_ORPHAN_GAP", "data.observations", f"{len(orphan)} observations point at unknown gaps",
                 "they count for nothing; re-link to a real gap id")
    min_src = int((policies.get("evidence") or {}).get("min_independent_sources", 3))
    rounds = int((state.get("rounds") or {}).get("research", 0))
    for gp in gaps:
        support = [o for o in obs if o.get("gap_id") == gp.get("id") and not o.get("contradicts")]
        groups = verifiers.independence_groups(support)["independent_groups"] if support else 0
        if gp.get("status") == "supported" and groups < min_src:
            bugs.add("DEFECT", "GAP_SUPPORT_INCONSISTENT", f"data.gaps[{gp.get('id')}]",
                     f"marked supported on {groups} independent voice(s); policy needs {min_src}",
                     "closed under the old distinct-URL rule; reopen it (status=open) and let curate re-decide")
        if gp.get("status") == "open" and not support and rounds >= 1:
            bugs.add("SMELL", "GAP_OPEN_STARVED", f"data.gaps[{gp.get('id')}]",
                     f"open after {rounds} research round(s) with zero observations",
                     "either research it next or record why it cannot be observed")
    if (policies.get("evidence") or {}).get("max_research_rounds") is not None:
        if rounds >= int(policies["evidence"]["max_research_rounds"]) and state.get("status") == "running" \
                and node in ("web_research", "curate", "gaps", "challenge"):
            bugs.add("SMELL", "LOOP_EXHAUSTED", "rounds.research",
                     f"{rounds} rounds reached the policy maximum while still in the research loop",
                     "the next step forces a verdict; make sure the missing coverage is real, not un-submitted")

    # -- bridges (φ's admissibility, re-run on stored rows) ------------------
    for h in d.get("hypotheses") or []:
        if h.get("status") in ("WORKING_HYPOTHESIS", "CHALLENGED", "SUPPORTED"):
            errs = bridge.validate_bridge(h, policies)
            if errs:
                bugs.add("DEFECT", "BRIDGE_INADMISSIBLE", f"data.hypotheses[{h.get('id')}]",
                         f"{h.get('status')} bridge fails admissibility: {errs[0][:140]}",
                         "policies moved or the row was edited: revise the bridge or reject it")
    hyp_ids = {h.get("id") for h in d.get("hypotheses") or []}
    orphan_receipts = [r for r in state.get("l4_receipts") or [] if r.get("subject_id") not in hyp_ids]
    if orphan_receipts:
        bugs.add("SMELL", "L4_RECEIPT_ORPHAN", "state.l4_receipts",
                 f"{len(orphan_receipts)} receipts reference hypotheses no longer in state", "history only; nothing to fix unless rows were deleted by hand")

    # -- suppliers ------------------------------------------------------------
    for s in d.get("supplier_candidates") or []:
        raw = str(s.get("price_raw") or "")
        if any(m in raw for m in _NON_USD) and "$" not in raw and "USD" not in raw.upper() \
                and s.get("price_usd_low") is not None:
            bugs.add("DEFECT", "SUPPLIER_CURRENCY", f"data.supplier_candidates[{s.get('id')}]",
                     f"price_raw {raw!r} parsed as USD {s.get('price_usd_low')}",
                     "parsed under the old currency-blind regex; re-run the supplier step (it re-normalizes)")
        elif "price_usd_low" in s and (s.get("price_usd_low") is None or not s.get("moq_units")):
            bugs.add("SMELL", "SUPPLIER_UNPARSED", f"data.supplier_candidates[{s.get('id')}]",
                     f"price_raw={raw!r} moq_raw={str(s.get('moq_raw'))!r} did not parse",
                     "not counted toward supplier coverage; capture the listing's exact price/MOQ text")

    # -- qualify's invariants, verbatim ---------------------------------------
    try:
        import qualify
        for v in qualify.qualify_run(state_path, policies).get("invariant_violations") or []:
            if not any(v.startswith(x) for x in ("state/SQLite", "no run row", "event log", "terminal run still")):
                bugs.add("DEFECT", "QUALIFY", "qualify.py", v, "see docs/15 — architecture invariant")
    except Exception as exc:  # noqa: BLE001 — triage must always produce output
        bugs.add("SMELL", "QUALIFY_UNAVAILABLE", "qualify.py", f"{type(exc).__name__}: {exc}"[:200],
                 "qualify could not run; the checks above still stand")

    counts = {s: sum(1 for b in bugs.items if b["severity"] == s) for s in SEVERITIES}
    order = {s: i for i, s in enumerate(SEVERITIES)}
    items = sorted(bugs.items, key=lambda b: (order[b["severity"]], b["code"], b["where"]))
    return {"ok": counts["BLOCKER"] == 0 and counts["DEFECT"] == 0,
            "run_id": state["run_id"], "node": node, "status": state.get("status"),
            "verdict": state.get("verdict"), "counts": counts, "bugs": items,
            "checked_at": models.now()}


def utilization_markdown(state_path: str) -> str:
    import utilization as _util
    st = models.load_state(state_path)
    return "\n## Evidence utilization (docs/21)\n\n" + _util.to_markdown(_util.compute(st)) + "\n"


def to_markdown(res: dict) -> str:
    head = (f"# run triage — {res['run_id']}\n\n"
            f"node `{res['node']}` · status `{res['status']}` · verdict `{res.get('verdict')}` · "
            f"BLOCKER {res['counts']['BLOCKER']} · DEFECT {res['counts']['DEFECT']} · SMELL {res['counts']['SMELL']}\n\n")
    if not res["bugs"]:
        return head + "no findings — the run is consistent with every law triage knows.\n"
    lines = ["| severity | code | where | what | fix |", "|---|---|---|---|---|"]
    for b in res["bugs"]:
        cell = lambda s: str(s).replace("|", "\\|").replace("\n", " ")  # noqa: E731
        lines.append(f"| {b['severity']} | `{b['code']}` | `{cell(b['where'])}` | {cell(b['message'])} | {cell(b['fix'])} |")
    return head + "\n".join(lines) + "\n"


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="run_triage")
    ap.add_argument("--state", required=True)
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--stale-minutes", type=int, default=30)
    a = ap.parse_args()
    res = triage(a.state, graphmod.load_policies(), stale_minutes=a.stale_minutes)
    print(to_markdown(res) if a.markdown else json.dumps(res, indent=1, ensure_ascii=False))
    print(utilization_markdown(a.state)) if getattr(a, 'markdown', False) and getattr(a, 'state', None) else None
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

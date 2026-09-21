#!/usr/bin/env python3
"""Architecture Qualification Report (docs/15).

Recomputes the system's invariants over finished/in-flight run states and
their SQLite audit trail, then reports per-run: graph path, loops exercised,
actions generated, context recovery result, evidence-role coverage,
capability failures, terminal state, registry candidates, handoffs — and any
INVARIANT VIOLATIONS. Zero violations across adversarial fixtures is the
meaningful stopping condition for the v1 architecture freeze.

  qualify.py --states run1.json run2.json ... [--out report.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bridge
import graph as graphmod
import memory
import models
import verifiers

KNOWN_VERDICTS = {
    "opportunity_research": {"QUALIFIED_LEADS", "PROVISIONAL_LEADS", "NO_DEFENSIBLE_BRIDGE",
                             "MECHANISM_WITHOUT_SUPPLY", "NO_GENERATIVE_SIGNAL", "CORPUS_ECHO_UNGROUNDED",
                             "STOPPED_WITHOUT_QUALIFICATION", "ABANDONED"},
    "niche_loadout": {"LOADOUT_READY", "LOADOUT_INCOMPLETE",
                      "STOPPED_WITHOUT_QUALIFICATION", "ABANDONED"},
    "market_discovery": {"MARKET_SCOPES_READY", "NO_PROMISING_MARKETS",
                         "STOPPED_WITHOUT_QUALIFICATION", "ABANDONED"},
    "product_anchored": {"PRODUCT_MARKETS_READY", "PRODUCT_REFRAMED",
                         "NO_DEFENSIBLE_MARKET", "PRODUCT_IDENTITY_UNRESOLVED",
                         "STOPPED_WITHOUT_QUALIFICATION", "ABANDONED"},
    "registry_maintenance": {"MAINTENANCE_COMPLETE", "NO_CHANGES", "NEEDS_APPROVAL",
                             "STALLED", "BLOCKED", "EXHAUSTED", "ABANDONED"},
}


def qualify_run(state_path: str, policies: dict) -> dict:
    state = models.load_state(state_path)
    g = graphmod.load_graph(state.get("graph_file", "control_graph.yaml"))
    mode = (g.get("graph") or {}).get("id")
    d = state["data"]
    audit = memory.run_audit(state["run_id"])
    run_row = audit["run"] or {}
    violations: list[str] = []

    # -- invariants -----------------------------------------------------------
    if run_row:
        if (state["status"] == "stopped") != (run_row.get("status") == "stopped"):
            violations.append("state/SQLite terminal status disagree")
        if state.get("verdict") and run_row.get("verdict") \
                and state["verdict"] != run_row["verdict"]:
            violations.append("state/SQLite verdict disagree")
    else:
        violations.append("no run row in SQLite")
    if audit["live_actions"] > 1:
        violations.append(f"{audit['live_actions']} live actions (one-writer law broken)")
    if state["status"] == "stopped" and audit["live_actions"]:
        violations.append("terminal run still holds a live action")
    if not audit["events_monotonic"]:
        violations.append("event log not strictly monotonic")
    if audit["model_actions"] and audit["model_actions_with_envelope"] < audit["model_actions"]:
        violations.append(f"{audit['model_actions'] - audit['model_actions_with_envelope']} "
                          "model actions without a frozen ContextEnvelope")
    if state["status"] == "stopped" and state.get("verdict") != "ABANDONED" \
            and not audit["event_types"].get("TERMINAL_REACHED") \
            and not audit["event_types"].get("RUN_ABANDONED"):
        violations.append("terminal run without TERMINAL_REACHED event")
    if mode in KNOWN_VERDICTS and state.get("verdict") \
            and state["verdict"] not in KNOWN_VERDICTS[mode]:
        violations.append(f"unknown verdict {state['verdict']!r} for mode {mode}")
    if not run_row.get("registry_build"):
        violations.append("run not pinned to a registry build")

    # evidence re-admission: everything in state must STILL pass the authority
    # rules — a policy regression or smuggled observation shows up here
    _, verrs = verifiers.admit_observations(d.get("observations") or [], policies)
    if verrs:
        violations.append(f"{len(verrs)} observations no longer admissible "
                          f"(first: {verrs[0][:90]})")
    valid_roles = set((policies.get("evidence_roles") or {}).get("valid") or [])
    for o in d.get("observations") or []:
        bad = set(o.get("evidence_roles") or []) - valid_roles
        if bad:
            violations.append(f"observation {o.get('id')} carries unknown roles {sorted(bad)}")

    if mode == "opportunity_research":
        for h in d.get("hypotheses") or []:
            if h.get("status") == "SUPPORTED":
                errs = bridge.validate_bridge(h, policies)
                if errs:
                    violations.append(f"SUPPORTED bridge {h.get('id')} fails admissibility: {errs[0]}")
        cov = state.get("satisfaction") or {}
        if d.get("leads") and state.get("verdict") == "QUALIFIED_LEADS" \
                and not cov.get("core_satisfied"):
            violations.append("QUALIFIED_LEADS with unsatisfied core coverage")

    # -- recovery statement ---------------------------------------------------
    if state["status"] == "stopped":
        recovery = "TERMINAL_IMMUTABLE"
    elif audit["live_actions"] == 1:
        recovery = ("PENDING_ACTION_FROZEN"
                    if audit["model_actions_with_envelope"] else "PENDING_NO_ENVELOPE")
    else:
        recovery = "NO_LIVE_ACTION"

    advances = [h for h in state.get("history", []) if h.get("event") == "advance"]
    reg_cands = d.get("registry_candidates") or []
    cov = state.get("satisfaction") or {}
    return {
        "run_id": state["run_id"],
        "mode": mode,
        "graph_path": [h.get("to") for h in advances],
        "loops_exercised": {"research_rounds": state["rounds"]["research"]},
        "actions_generated": audit["actions_total"],
        "context_recovery": recovery,
        "checkpoints": audit["checkpoints"],
        "evidence_role_coverage": {name: spec.get("satisfied")
                                   for name, spec in (cov.get("requirements") or {}).items()},
        "capability_failures": [{"node": c.get("node"), "capability": c.get("capability")}
                                for c in state.get("capability_failures") or []],
        "terminal": {"status": state["status"], "verdict": state.get("verdict")},
        "settings_hash": (state.get("settings") or {}).get("hash"),
        "registry_candidates_emitted": len(reg_cands),
        "handoffs": {"out": audit["event_types"].get("HANDOFF", 0),
                     "in": audit["event_types"].get("HANDOFF_RECEIVED", 0)},
        "invariant_violations": violations,
    }


def build_report(state_paths: list[str]) -> dict:
    policies = graphmod.load_policies()
    runs = [qualify_run(p, policies) for p in state_paths]
    total = sum(len(r["invariant_violations"]) for r in runs)
    return {
        "report": "architecture_qualification",
        "version": "v1",
        "generated_at": models.now(),
        "config": memory.config_hashes(),
        "runs": runs,
        "modes_covered": sorted({r["mode"] for r in runs if r["mode"]}),
        "total_invariant_violations": total,
        "stopping_condition_met": total == 0,
    }


def main():
    p = argparse.ArgumentParser(prog="qualify")
    p.add_argument("--states", nargs="+", required=True)
    p.add_argument("--out")
    args = p.parse_args()
    report = build_report(args.states)
    text = json.dumps(report, indent=1, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(json.dumps({"ok": report["stopping_condition_met"], "out": args.out,
                          "total_invariant_violations": report["total_invariant_violations"]}))
    else:
        print(text)
    return 0 if report["stopping_condition_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

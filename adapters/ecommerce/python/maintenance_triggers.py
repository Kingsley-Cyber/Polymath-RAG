#!/usr/bin/env python3
"""Deterministic maintenance triggers (docs/17 §2).

Python evaluates cross-run evidence in SQLite and decides when accumulated
RegistryCandidates deserve a Registry Maintenance run — the user never has to
ask. The active registry still never mutates during research (per-run
snapshots stay pinned); this module only OPENS the maintenance lifecycle.

  maintenance_triggers.py evaluate
  maintenance_triggers.py evaluate --create-run candidates/maint_001.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import graph as graphmod
import memory
import models

# thresholds are policy-backed with safe defaults; SYSTEM behavior, not user knobs
_DEFAULTS = {"recurrence_min_runs": 2, "negative_min_runs": 2,
             "query_yield_min_runs": 2, "source_yield_min_runs": 2}


def _thresholds(policies: dict) -> dict:
    t = dict(_DEFAULTS)
    t.update((policies.get("maintenance_triggers") or {}))
    return t


def evaluate(policies: dict | None = None) -> dict:
    policies = policies or graphmod.load_policies()
    th = _thresholds(policies)
    stats = memory.candidate_recurrence()
    fired = []
    for row in stats:
        kind, name, runs = row["kind"], row["name"], row["runs"]
        if kind == "NEGATIVE_REASONING_MOTIF" and runs >= th["negative_min_runs"]:
            fired.append({"trigger": "FAILURE_TRIGGER", "kind": kind, "name": name,
                          "runs": runs,
                          "why": "same reasoning pattern repeatedly contradicted"})
        elif kind == "QUERY_PATTERN_CANDIDATE" and runs >= th["query_yield_min_runs"]:
            fired.append({"trigger": "QUERY_TRIGGER", "kind": kind, "name": name,
                          "runs": runs,
                          "why": "query formulation repeatedly produced useful evidence"})
        elif kind == "SOURCE_CANDIDATE" and runs >= th["source_yield_min_runs"]:
            fired.append({"trigger": "SOURCE_TRIGGER", "kind": kind, "name": name,
                          "runs": runs,
                          "why": "source repeatedly useful for an EvidenceRole"})
        elif runs >= th["recurrence_min_runs"]:
            fired.append({"trigger": "RECURRENCE_TRIGGER", "kind": kind, "name": name,
                          "runs": runs,
                          "why": "candidate recurs across independent runs"})
    return {"fired": fired, "candidates_seen": len(stats), "thresholds": th,
            "maintenance_due": bool(fired)}


def create_maintenance_run(result: dict, out_path: str) -> dict:
    """Open the Registry Maintenance lifecycle: a run state at the maintenance
    graph entry, preloaded with the triggering candidates. Promotion still
    walks the graph (dedupe → novelty → evidence → L5 human approval) — this
    NEVER edits CSVs itself."""
    g = graphmod.load_graph("maintenance_graph.yaml")
    state = models.new_state(os.path.splitext(os.path.basename(out_path))[0],
                             "automatic maintenance: " +
                             ", ".join(sorted({f["trigger"] for f in result["fired"]})))
    state["graph_file"] = "maintenance_graph.yaml"
    state["node"] = g["graph"]["entry"]
    rows = memory.load_candidates([f["name"] for f in result["fired"]])
    state["data"]["registry_candidates"] = rows
    state["data"]["maintenance_triggers"] = result["fired"]
    memory.create_run(state["run_id"], state["data"]["signal"], state["node"])
    memory.record_event(state["run_id"], "MAINTENANCE_TRIGGERED",
                        {"fired": result["fired"][:20]})
    models.save_state(state, out_path)
    return {"ok": True, "run_state": out_path, "run_id": state["run_id"],
            "candidates_loaded": len(rows),
            "triggers": sorted({f["trigger"] for f in result["fired"]}),
            "note": "maintenance executors walk the graph; promotion requires "
                    "L5 human approval — no autonomous CSV edits"}


def main():
    p = argparse.ArgumentParser(prog="maintenance_triggers")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("evaluate")
    e.add_argument("--create-run", dest="create_run", default=None)
    args = p.parse_args()
    result = evaluate()
    if args.create_run and result["maintenance_due"]:
        result["created"] = create_maintenance_run(result, args.create_run)
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""L4 evaluator support: sanitized dossier builder (anti nodding-loop).

The generator that produced a hypothesis is a poor sole judge of it. The
fresh evaluator subagent receives ONLY what this module emits — structural
facts, never the generator's persuasive narrative. Fields like `notes`,
challenge arguments, and analogies' sales pitch are deliberately stripped.

CLI:  evaluator.py dossier --state candidates/run.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models  # noqa: E402

DOSSIER_HYP_FIELDS = ["id", "source", "path", "target_mechanism", "invariant",
                      "evidence_boundary", "hop_refs", "gaps", "alternatives", "falsifiers",
                      "status", "exploratory"]


def build_dossier(state: dict) -> dict:
    d = state["data"]
    return {
        "instruction_file": "prompts/semantic_evaluation.md",
        "evidence_summaries": [
            {"id": e.get("id"), "summary": e.get("summary"),
             "can_establish": e.get("can_establish"),
             "cannot_establish": e.get("cannot_establish")}
            for e in d.get("corpus_evidence") or []],
        "primitives": {k: v for k, v in (d.get("primitives") or {}).items()
                       if k in ("behaviors", "constraints", "frictions",
                                "physical_jobs", "transferable_invariants")},
        "bridges": [{k: h.get(k) for k in DOSSIER_HYP_FIELDS if h.get(k) is not None}
                    for h in d.get("hypotheses") or []
                    if h.get("status") in ("WORKING_HYPOTHESIS", "WORKING_ANALOGY", "CHALLENGED")],
        "competing_paths_note": "bridges above compete with each other; judge each independently",
        "field_observations_exist": bool(d.get("observations")),
        "forbidden": ["generating new opportunities", "promoting evidence",
                      "trusting unstated generator reasoning"],
    }


def apply_evaluations(state: dict, policies: dict) -> str:
    """Deterministic application of L4 verdicts (called by the executor node):
    REJECT -> hypothesis REJECTED; REVISE -> CHALLENGED + missing intermediates
    appended as researchable gaps; PASS -> unchanged. Verdicts are recorded as
    L4 receipts — model judgment, never field truth."""
    evals = {e["hypothesis_id"]: e for e in state["data"].get("evaluations") or []}
    applied = {"PASS": 0, "REVISE": 0, "REJECT": 0}
    receipts = state.setdefault("l4_receipts", [])
    new_receipts: list[dict] = []
    for h in state["data"]["hypotheses"]:
        ev = evals.get(h["id"])
        if not ev:
            continue
        verdict = ev["verdict"]
        applied[verdict] = applied.get(verdict, 0) + 1
        if verdict == "REJECT" and h.get("status") not in ("REJECTED",):
            h["status"] = "REJECTED"
        elif verdict == "REVISE":
            if h.get("status") == "WORKING_HYPOTHESIS":
                h["status"] = "CHALLENGED"
            for mi in ev.get("missing_intermediates") or []:
                gap_q = f"evidence for missing intermediate: {mi}"
                if gap_q not in (h.get("gaps") or []):
                    h.setdefault("gaps", []).append(gap_q)
        rec = {"check_type": "SEMANTIC_BRIDGE_REVIEW", "level": "L4",
               "subject_id": h["id"], "status": verdict,
               "reasons": ev.get("reasons"),
               "decisive_falsifier": ev.get("decisive_falsifier"),
               "at": models.now()}
        receipts.append(rec)
        new_receipts.append(rec)
    # Persist exactly the receipts minted by THIS call. The previous slice
    # `receipts[-len(evals):]` degenerated to `receipts[0:]` when no
    # evaluation matched, re-writing every historical L4 receipt — and the
    # bare `except: pass` hid it. Persistence still never breaks the run,
    # but a failure is now recorded where triage can see it.
    if new_receipts:
        try:
            import memory
            for r in new_receipts:
                memory.write_check(state["run_id"], r["check_type"], "L4", r["status"],
                                   {"decisive_falsifier": r.get("decisive_falsifier")},
                                   r.get("reasons"), subject_id=r.get("subject_id"))
        except Exception as exc:  # noqa: BLE001 — recorded, not swallowed
            state.setdefault("warnings", []).append(
                {"at": models.now(), "where": "l4_receipt_persist",
                 "error": f"{type(exc).__name__}: {exc}"[:300]})
    return (f"L4 verdicts applied: {applied['PASS']} pass, {applied['REVISE']} revise "
            f"(missing intermediates -> gaps), {applied['REJECT']} reject — "
            f"recorded as L4 receipts, never as field truth")


def main():
    p = argparse.ArgumentParser(prog="evaluator")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dossier")
    d.add_argument("--state", required=True)
    args = p.parse_args()
    if args.cmd == "dossier":
        state = models.load_state(args.state)
        print(json.dumps(build_dossier(state), indent=1, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

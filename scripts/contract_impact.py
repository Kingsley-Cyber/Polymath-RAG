#!/usr/bin/env python3
"""Deterministic contract-impact checker (no LLM).

Answers "which architecture-level contracts does a change touch, and which are transitively
impacted?" — reads architecture/contract-dependencies.yaml, maps changed files → contracts by
path, and closes over `consumed_by` edges. Every impacted contract must receive a disposition
(UPDATED / TESTED_UNCHANGED / NOT_AFFECTED / DEFERRED / BLOCKED) in the change's work-log before
it is complete (AGENTS.md). Symbol-level structural blast radius is `graft callers <symbol>`
($0, deterministic); this tool is the contract-level backbone that sits above it.

Usage:
  contract_impact.py --staged                 # staged changes (pre-commit / interactive)
  contract_impact.py --range cf1ee4f..HEAD    # a commit range (audit)
  contract_impact.py --files a.py b.py         # explicit files
  contract_impact.py --check --staged          # exit 3 if a DEFERRED (out-of-scope) contract changed
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "architecture" / "contract-dependencies.yaml"
DISPOSITIONS = ("UPDATED", "TESTED_UNCHANGED", "NOT_AFFECTED", "DEFERRED", "BLOCKED")


def load_contracts(path: Path = MAP) -> dict:
    return yaml.safe_load(path.read_text())["contracts"]


def changed_files(args) -> list[str]:
    if args.files:
        return list(args.files)
    if args.staged:
        cmd = ["git", "diff", "--cached", "--name-only"]
    else:
        cmd = ["git", "diff", "--name-only", args.range or "HEAD~1..HEAD"]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def _owns(contract: dict, path: str) -> bool:
    for p in contract.get("paths") or ():
        if path == p or path.startswith(p.rstrip("/") + "/"):
            return True
    return False


def compute_impact(changed: list[str], contracts: dict) -> tuple[set[str], set[str]]:
    """Return (directly changed contracts, transitively impacted downstream contracts)."""
    direct = {name for path in changed for name, c in contracts.items() if _owns(c, path)}
    impacted, frontier = set(direct), list(direct)
    while frontier:
        for consumer in contracts.get(frontier.pop(), {}).get("consumed_by") or ():
            if consumer not in impacted:
                impacted.add(consumer)
                frontier.append(consumer)
    return direct, impacted - direct


def tests_for(names: set[str], contracts: dict) -> list[str]:
    return sorted({t for n in names for t in (contracts.get(n, {}).get("tests") or ())})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--range")
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--check", action="store_true",
                    help="exit 3 if a DEFERRED (out-of-scope) contract is directly changed")
    args = ap.parse_args()

    contracts = load_contracts()
    changed = changed_files(args)
    direct, transitive = compute_impact(changed, contracts)

    if not direct:
        print("CONTRACT IMPACT: none (no changed file maps to an architecture contract).")
        return 0

    print("CHANGED CONTRACTS")
    for n in sorted(direct):
        c = contracts[n]
        print(f"  {n}  [{c.get('status', '?')}]  spec={c.get('spec')}")
    print("\nTRANSITIVE IMPACT (downstream consumers)")
    for n in sorted(transitive) or []:
        print(f"  {n}  [{contracts.get(n, {}).get('status', '?')}]")
    if not transitive:
        print("  (none)")
    print("\nTESTS TO RUN (changed + impacted)")
    for t in tests_for(direct | transitive, contracts) or []:
        print(f"  {t}")
    print("\nEvery impacted contract needs a disposition in the work-log: "
          + " | ".join(DISPOSITIONS))
    print("Symbol-level blast radius: `graft callers <symbol>` (deterministic, $0).")

    if args.check:
        deferred = sorted(n for n in direct if contracts[n].get("status") == "deferred")
        if deferred:
            print("\nOUT OF SCOPE — directly changed DEFERRED contract(s): " + ", ".join(deferred))
            print("Deferred work (e.g. graph traversal / P10 resolution loop) is not in this mission.")
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

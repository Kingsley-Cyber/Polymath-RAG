#!/usr/bin/env python
"""Mission driver for the semantic corpus rebuild closeout.

Durable phase state so the work survives context resets, session
restarts and hand-offs. Any session can ask "what is next?" and get the
same answer, with dependencies and the one-re-ingest rule enforced.

    python scripts/mission_next.py              # what to do now
    python scripts/mission_next.py --status     # whole board
    python scripts/mission_next.py --done P2 --commit abc1234 \
        --result "chunk v2 promoted; concept regression inverted"
    python scripts/mission_next.py --partial P12 --result "4 of 17 cases"

Exit codes: 0 work remains · 3 mission complete · 4 blocked.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "eval" / "v5" / "killchain" / "MISSION-STATE.json"

DONE = {"DONE"}
OPEN = {"TODO", "PARTIAL", "BLOCKED"}


def load() -> dict:
    return json.loads(STATE.read_text())


def save(data: dict) -> None:
    STATE.write_text(json.dumps(data, indent=2) + "\n")


def by_id(data: dict) -> dict:
    return {p["id"]: p for p in data["phases"]}


def unmet(phase: dict, index: dict) -> list[str]:
    return [d for d in phase.get("depends_on", [])
            if index.get(d, {}).get("status") not in DONE]


def tree_clean() -> bool:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    return out.strip() == ""


def head() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def show_status(data: dict) -> None:
    index = by_id(data)
    done = sum(1 for p in data["phases"] if p["status"] in DONE)
    print(f"MISSION {data['mission']}")
    print(f"progress: {done}/{len(data['phases'])} phases · HEAD {head()} · "
          f"tree {'CLEAN' if tree_clean() else 'DIRTY'}\n")
    for p in data["phases"]:
        mark = {"DONE": "[x]", "PARTIAL": "[~]", "BLOCKED": "[!]"}.get(
            p["status"], "[ ]")
        blockers = unmet(p, index)
        note = ""
        if p["status"] in DONE and p.get("commit"):
            note = f"  ({p['commit']})"
        elif blockers:
            note = f"  waits on {','.join(blockers)}"
        elif p.get("needs_reingest"):
            note = "  [re-ingest gen]"
        print(f"  {mark} {p['id']:<4} {p['name']:<34}{note}")


def next_phase(data: dict) -> dict | None:
    index = by_id(data)
    for p in data["phases"]:
        if p["status"] in DONE:
            continue
        if unmet(p, index):
            continue
        return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--done", metavar="PHASE_ID")
    ap.add_argument("--partial", metavar="PHASE_ID")
    ap.add_argument("--blocked", metavar="PHASE_ID")
    ap.add_argument("--commit", default="")
    ap.add_argument("--result", default="")
    args = ap.parse_args()

    data = load()
    index = by_id(data)

    for flag, status in (("done", "DONE"), ("partial", "PARTIAL"),
                         ("blocked", "BLOCKED")):
        pid = getattr(args, flag)
        if pid:
            if pid not in index:
                print(f"unknown phase {pid}")
                return 1
            index[pid]["status"] = status
            if args.commit:
                index[pid]["commit"] = args.commit
            if args.result:
                index[pid]["result"] = args.result
            save(data)
            print(f"{pid} -> {status}")

    if args.status:
        show_status(data)
        return 0

    nxt = next_phase(data)
    if nxt is None:
        remaining = [p["id"] for p in data["phases"] if p["status"] not in DONE]
        if not remaining:
            print("MISSION COMPLETE — every phase DONE.")
            print("Close out: eval/v5/killchain/FINAL-SEMANTIC-CORPUS-V2-CLOSEOUT.md")
            return 3
        print(f"BLOCKED — remaining phases have unmet dependencies: {remaining}")
        return 4

    done = sum(1 for p in data["phases"] if p["status"] in DONE)
    print(f"=== NEXT: {nxt['id']} {nxt['name']}   "
          f"({done}/{len(data['phases'])} done · HEAD {head()})")
    print(f"\nSTATUS   {nxt['status']}")
    print(f"GOAL     {nxt['goal']}")
    print("\nACCEPTANCE")
    for a in nxt.get("acceptance", []):
        print(f"  - {a}")
    if nxt.get("needs_reingest"):
        print("\n!! RE-INGEST GENERATION PHASE")
        print("   Do NOT re-ingest production to test this. Qualify on the")
        print("   sentinel and fixtures; production rebuilds ONCE at P14.")
    if not tree_clean():
        print("\n!! TREE DIRTY — commit or revert before starting a new phase.")
    print("\nWhen finished:")
    print(f"  python scripts/mission_next.py --done {nxt['id']} "
          f"--commit <sha> --result \"<what was proved>\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

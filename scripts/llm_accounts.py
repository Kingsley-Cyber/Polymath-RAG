#!/usr/bin/env python3
"""LLM provider accounts: report, validate, drift-check and GENERATE the runtime files (registers 11.465 L1, 11.467 L3).

    .venv/bin/python scripts/llm_accounts.py report     # one row per account x model: owner, callers, quota, key set?
    .venv/bin/python scripts/llm_accounts.py validate   # errors (exit 1) and policy warnings (exit 0)
    .venv/bin/python scripts/llm_accounts.py diff       # registry vs config/cloud_providers.json + limiter.yaml
    .venv/bin/python scripts/llm_accounts.py write      # regenerate both runtime files from the registry (L3)

Reads config/llm_accounts.yaml, the only file to edit by hand. Load the fleet `.env` first (set -a; . ./.env; set +a)
for real key checks: only whether each variable is set is ever printed, never a value. No network, no database, no
model call. `write` touches only the two runtime files; they take effect at the next fleet bounce.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

from polymath_shared.llm_extraction import accounts as A


def _fmt_quota(q: dict) -> str:
    if not q:
        return "-"
    parts = [f"{k} {int(v):,}" for k, v in q.items() if v is not None]
    return ", ".join(parts)


def report(reg: A.Registry) -> int:
    rows = A.ownership_rows(reg)
    print(f"{'account':14s} {'model':38s} {'state':6s} {'slots':>5s}  {'stages':32s} {'owner':16s} {'key':4s} "
          f"{'acct':5s} quota / lanes")
    for r in rows:
        acct_id = "-" if r["account_id_set"] is None else ("yes" if r["account_id_set"] else "NO")
        owner = ",".join(r["owners"]) or ("shared" if r["slots"] > 1 else "-")
        print(f"{r['account']:14s} {r['model'][:38]:38s} {r['state']:6s} {r['slots']:>5d}  "
              f"{','.join(r['stages'])[:32]:32s} {owner[:16]:16s} {'yes' if r['key_set'] else 'NO':4s} {acct_id:5s} "
              f"{_fmt_quota(r['quota'])} | {', '.join(r['lanes'])}")
    active = sum(1 for r in rows if r["state"] == "active")
    print(f"\n{len(reg.accounts)} accounts, {len(reg.lanes)} lanes, {len(rows)} account x model pairs, {active} active")
    return 0


def validate(reg: A.Registry) -> int:
    findings = A.validate(reg)
    drift = A.runtime_drift(reg) + A.runtime_not_generated(reg)
    for d in drift:
        print(f"ERROR   DRIFT            {d}")
    for f in findings:
        print(f"{f.level.upper():7s} {f.code:22s} {f.message}")
    errors = len(drift) + sum(1 for f in findings if f.level == "error")
    print(f"\n{errors} errors, {sum(1 for f in findings if f.level == 'warning')} warnings")
    return 1 if errors else 0


def diff(reg: A.Registry) -> int:
    drift = A.runtime_drift(reg) + A.runtime_not_generated(reg)
    for d in drift:
        print(d)
    print("no drift" if not drift else f"{len(drift)} differences")
    return 1 if drift else 0


def write(reg: A.Registry) -> int:
    errors = [f for f in A.validate(reg, env={}) if f.level == "error"]
    for f in errors:
        print(f"ERROR   {f.code:22s} {f.message}")
    if errors:
        print("not written: fix the registry errors first")
        return 1
    changed = A.write_runtime(reg)
    print("\n".join(f"wrote {c}" for c in changed) or "runtime files already match the registry")
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "report"
    reg = A.load_registry()
    cmds = {"report": report, "validate": validate, "diff": diff, "write": write}
    return cmds.get(cmd, lambda _r: (print(__doc__), 2)[1])(reg)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

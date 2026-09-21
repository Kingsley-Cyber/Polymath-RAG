#!/usr/bin/env python3
"""Deterministic deployment of the ecommerce engine to an agent host (consolidation migration Phase 9).

ONE source: `adapters/ecommerce/` in this repository. A host such as Hermes loads a PHYSICAL COPY (its gateway runs under launchd, which
cannot read `~/Documents`), so the copy is made by this script and proven by the engine's own parity verifier — never maintained by hand.

    python3 scripts/deploy_ecommerce_skill.py --target ~/.hermes/standalone/opportunity-research            # DRY RUN: what would change
    python3 scripts/deploy_ecommerce_skill.py --target <dir> --execute                                       # copy, then verify + write the receipt
    python3 scripts/deploy_ecommerce_skill.py --target <dir> --check                                         # verify only (exit 1 on drift)
    ... --no-hermes-link        the target is a staging / test directory, not a Hermes home
    ... --allow-dirty           deploy although adapters/ecommerce has uncommitted changes (the receipt records the count)

What is copied is EXACTLY what `adapters/ecommerce/tests/mirror_check.py` compares (its `files()` minus `REPO_ONLY`): runtime state, candidate
runs, exports, compiled registry, review patches, SQLite files and the private field-evidence ledger are never part of it. Nothing in the target
is ever deleted; files the source does not have are reported by the verifier as `unexpected_in_deployed`. The receipt
(`<target>/MIRROR_RECEIPT.json`) names this repository's commit, the subdirectory, the engine version and the file count.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "adapters" / "ecommerce"
VERIFIER = SOURCE / "tests" / "mirror_check.py"


def _verifier():
    spec = importlib.util.spec_from_file_location("ecommerce_mirror_check", VERIFIER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def plan(target: pathlib.Path) -> dict:
    mc = _verifier()
    ref = {k: v for k, v in mc.files(str(SOURCE)).items() if not mc.REPO_ONLY.match(k)}
    have = mc.files(str(target)) if target.is_dir() else {}
    return {"new": sorted(k for k in ref if k not in have), "changed": sorted(k for k in ref if k in have and have[k] != ref[k]),
            "unchanged": sum(1 for k in ref if have.get(k) == ref[k]), "total": len(ref), "dirty_source_files": mc.git_dirty(str(SOURCE))}


def verify(target: pathlib.Path, *, hermes_link: bool, write: bool) -> int:
    cmd = [sys.executable, str(VERIFIER), "--deployed", str(target)] + ([] if hermes_link else ["--no-hermes-link"]) + (["--out", str(target / "MIRROR_RECEIPT.json")] if write else [])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        receipt = json.loads(proc.stdout)
        print(json.dumps({"parity": receipt.get("parity"), "reference": receipt.get("reference"), "deployed": receipt.get("deployed"), "missing_in_deployed": receipt.get("missing_in_deployed"),
                          "drift": receipt.get("drift"), "unexpected_in_deployed": receipt.get("unexpected_in_deployed"), "hermes_skill": receipt.get("hermes_skill")}, indent=1))
    except json.JSONDecodeError:
        print(proc.stdout[-2000:] + proc.stderr[-2000:])
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--no-hermes-link", action="store_true")
    ap.add_argument("--allow-dirty", action="store_true")
    a = ap.parse_args(argv)
    target = pathlib.Path(a.target).expanduser().resolve()
    if target == SOURCE.resolve() or SOURCE.resolve() in target.parents:
        print(json.dumps({"error": "the target must not be the source or sit inside it"})); return 2
    if a.check:
        return verify(target, hermes_link=not a.no_hermes_link, write=False)
    p = plan(target)
    print(json.dumps({"mode": "execute" if a.execute else "dry-run", "source": "adapters/ecommerce", "target": str(target), "to_write": len(p["new"]) + len(p["changed"]),
                      "new": p["new"][:20], "changed": p["changed"][:20], "unchanged": p["unchanged"], "total": p["total"], "dirty_source_files": p["dirty_source_files"]}, indent=1))
    if not a.execute:
        return 0
    if p["dirty_source_files"] and not a.allow_dirty:
        print(json.dumps({"error": f"adapters/ecommerce has {p['dirty_source_files']} uncommitted change(s): commit first, or pass --allow-dirty (the receipt records it)"})); return 2
    for rel in p["new"] + p["changed"]:
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / rel, dst)
        assert hashlib.sha256(dst.read_bytes()).hexdigest() == hashlib.sha256((SOURCE / rel).read_bytes()).hexdigest(), rel
    return verify(target, hermes_link=not a.no_hermes_link, write=True)


if __name__ == "__main__":
    sys.exit(main())

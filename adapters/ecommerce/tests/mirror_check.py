#!/usr/bin/env python3
"""Mirror parity receipt — is the DEPLOYED Hermes copy byte-identical to this git repo?

    python3 tests/mirror_check.py --deployed ~/.hermes/standalone/opportunity-research [--hermes-skill ~/.hermes/skills/business/opportunity-research] [--out MIRROR_RECEIPT.json]

REFERENCE = this repository (the skill's git repo is authoritative since GOVERNED-CONVERGENCE-V1: edit here, gate here,
then mirror). DEPLOYED = the untracked directory Hermes actually loads. Every file of the reference is compared by
sha256, excluding runtime artifacts and repo-only files (.github, .gitignore, README, LICENSE, this receipt). Exit 1 on
any drift or missing file, or when the Hermes skill link does not resolve to the deployed copy. The receipt lists the
reference commit and version, the deployed version, file counts, drift and the Hermes resolution — a checked-in proof,
never a claim. (`--standalone` is kept as an alias of `--deployed` for the pre-2.3.0 invocation.)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDE_DIRS = {"state", "candidates", "__pycache__", ".git", "compiled", "patches", "exports"}
EXCLUDE_FILES = {"research_evidence.csv", ".DS_Store"}
EXCLUDE_SUFFIX = (".sqlite3", ".sqlite3-shm", ".sqlite3-wal", ".pyc")
REPO_ONLY = re.compile(r"^(README\.md|\.gitignore|\.github/.*|MIRROR_RECEIPT\.json|LICENSE.*)$")          # never deployed, never compared
DEPLOYED_ONLY_OK = re.compile(r"^(MIRROR_RECEIPT\.json|README\.md|LICENSE.*)$")                                  # tolerated leftovers in the deployed copy


def files(root: str) -> dict[str, str]:
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            if f in EXCLUDE_FILES or f.endswith(EXCLUDE_SUFFIX):
                continue
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, root)
            with open(p, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def git_head(path: str) -> str | None:
    """HEAD of the git repo ROOTED at `path` — None for a directory that merely sits inside another repo (the deployed copy
    lives, untracked, inside the Hermes home repo: reporting THAT repo's HEAD would be a false provenance claim)."""
    try:
        top = subprocess.run(["git", "-C", path, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
        if os.path.realpath(top) != os.path.realpath(path):
            return None
        return subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def git_dirty(path: str) -> int | None:
    try:
        return len([l for l in subprocess.run(["git", "-C", path, "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.splitlines() if l.strip()])
    except Exception:  # noqa: BLE001
        return None


def version_of(skill_md: str) -> str | None:
    try:
        m = re.search(r"^version:\s*(\S+)", open(skill_md, encoding="utf-8").read(), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deployed", default=None, help="the directory Hermes loads (default: ~/.hermes/standalone/opportunity-research)")
    ap.add_argument("--standalone", default=None, help="alias of --deployed (pre-2.3.0 invocation)")
    ap.add_argument("--hermes-skill", default=os.path.expanduser("~/.hermes/skills/business/opportunity-research"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    deployed = os.path.abspath(os.path.expanduser(a.deployed or a.standalone or "~/.hermes/standalone/opportunity-research"))
    if not os.path.isdir(deployed):
        print(json.dumps({"parity": False, "error": f"deployed copy not found: {deployed}"})); return 1
    ref = {k: v for k, v in files(ROOT).items() if not REPO_ONLY.match(k)}
    dep = files(deployed)
    missing = sorted(k for k in ref if k not in dep)
    drift = sorted(k for k in ref if k in dep and dep[k] != ref[k])
    extra = sorted(k for k in dep if k not in ref and not DEPLOYED_ONLY_OK.match(k))
    hermes_target = os.path.realpath(a.hermes_skill) if os.path.exists(a.hermes_skill) else None
    hermes_is = ("deployed" if hermes_target == os.path.realpath(deployed) else "reference" if hermes_target == os.path.realpath(ROOT)
                 else "ELSEWHERE" if hermes_target else "absent")
    receipt = {"reference": {"path": ROOT, "commit": git_head(ROOT), "dirty_files": git_dirty(ROOT), "version": version_of(os.path.join(ROOT, "SKILL.md")), "files": len(ref)},
               "deployed": {"path": deployed, "version": version_of(os.path.join(deployed, "SKILL.md")), "files_compared": len([k for k in ref if k in dep])},
               "missing_in_deployed": missing, "drift": drift, "unexpected_in_deployed": extra,
               "hermes_skill": {"path": a.hermes_skill, "resolves_to": hermes_target, "is": hermes_is},
               "parity": not missing and not drift and hermes_is in ("deployed", "reference")}
    text = json.dumps(receipt, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text + "\n")
    print(text)
    return 0 if receipt["parity"] else 1


if __name__ == "__main__":
    sys.exit(main())

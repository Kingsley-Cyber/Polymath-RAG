#!/usr/bin/env python3
"""Mirror parity receipt — is the standalone skill repo byte-identical to this
reference tree, and is the deployed Hermes skill one of them?

    python3 tests/mirror_check.py --standalone /path/to/TRAIL_AGENT_AUTORESEARCH [--hermes-skill ~/.hermes/skills/business/opportunity-research] [--out MIRROR_RECEIPT.json]

Compares every tracked file of the reference package (this directory) against
the standalone by sha256, excluding runtime artifacts. Exit 1 on any drift,
missing file, or a Hermes skill whose SKILL.md version differs. The receipt
lists reference commit, standalone commit, file count, drift and the Hermes
resolution — a checked-in proof, never a claim.
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
STANDALONE_ONLY_OK = re.compile(r"^(docs/\d\d-.*\.txt|README\.md|\.gitignore|\.github/.*|MIRROR_RECEIPT\.json|LICENSE.*)$")


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
    try:
        return subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
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
    ap.add_argument("--standalone", required=True); ap.add_argument("--hermes-skill", default=os.path.expanduser("~/.hermes/skills/business/opportunity-research"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ref, sa = files(ROOT), files(a.standalone)
    ref = {k: v for k, v in ref.items() if k not in ("MIRROR_RECEIPT.json", ".gitignore", "README.md")}
    missing = sorted(k for k in ref if k not in sa)
    drift = sorted(k for k in ref if k in sa and sa[k] != ref[k])
    extra = sorted(k for k in sa if k not in ref and not STANDALONE_ONLY_OK.match(k))
    hermes_target = os.path.realpath(a.hermes_skill) if os.path.exists(a.hermes_skill) else None
    hermes_version = version_of(os.path.join(a.hermes_skill, "SKILL.md")) if hermes_target else None
    ref_version = version_of(os.path.join(ROOT, "SKILL.md"))
    hermes_files = {k: v for k, v in files(hermes_target).items() if k not in ("MIRROR_RECEIPT.json", ".gitignore", "README.md")} if hermes_target else {}
    hermes_drift = sorted(k for k in ref if hermes_files.get(k) != ref[k]) if hermes_target else None
    hermes_is = ("reference" if hermes_target and os.path.realpath(ROOT) == hermes_target else
                 "standalone" if hermes_target and os.path.realpath(a.standalone) == hermes_target else
                 "identical-to-reference" if hermes_target and not hermes_drift else
                 "DRIFTED" if hermes_target else "absent")
    receipt = {"reference": {"path": ROOT, "commit": git_head(ROOT), "version": ref_version, "files": len(ref)},
               "standalone": {"path": os.path.abspath(a.standalone), "commit": git_head(a.standalone), "version": version_of(os.path.join(a.standalone, "SKILL.md")), "files_compared": len([k for k in ref if k in sa])},
               "missing_in_standalone": missing, "drift": drift, "unexpected_in_standalone": extra,
               "hermes_skill": {"path": a.hermes_skill, "resolves_to": hermes_target, "is": hermes_is, "version": hermes_version,
                                "drift_vs_reference": (hermes_drift or [])[:10]},
               "parity": not missing and not drift and not extra and (not hermes_drift if hermes_target else True)}
    text = json.dumps(receipt, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text + "\n")
    print(text)
    return 0 if receipt["parity"] else 1


if __name__ == "__main__":
    sys.exit(main())

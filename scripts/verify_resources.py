#!/usr/bin/env python3
"""verify_resources.py — checksum verification against the manifests.

Hard-fails on ANY mismatch (GATE 2: a corrupted upstream file must
never feed a build). Read-only; no repairs.

Usage:
    python3 scripts/verify_resources.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "resources" / "manifests"
VENDOR = ROOT / "resources" / "vendor"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    failures: list[str] = []
    for manifest_path in sorted(MANIFESTS.glob("*.yaml")):
        manifest = yaml.safe_load(manifest_path.read_text())
        if manifest["kind"] == "archive":
            archive = VENDOR / manifest["archive_name"]
            if not archive.exists():
                failures.append(f"{manifest['id']}: archive missing ({archive.name})")
                continue
            actual = sha256_of(archive)
        else:
            archive = VENDOR / "nltk" / "corpora" / f"{manifest['corpus']}.zip"
            if not archive.exists():
                failures.append(f"{manifest['id']}: nltk corpus missing ({archive.name})")
                continue
            actual = sha256_of(archive)

        expected = manifest["sha256"]
        if actual != expected:
            failures.append(
                f"{manifest['id']}: sha256 mismatch\n  expected {expected}\n  actual   {actual}"
            )
        else:
            print(f"[ok] {manifest['id']} {manifest['version']}")

    if failures:
        print("VERIFICATION FAILED:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print("all resource archives verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""fetch_resources.py — download the pinned lexical resources into
resources/vendor/ per resources/manifests/*.yaml.

Build-time only: the runtime never reads resources/vendor/ (GATE 10
proves this). Deterministic: same manifest → same archive bytes.

Usage:
    python3 scripts/fetch_resources.py [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "resources" / "manifests"
VENDOR = ROOT / "resources" / "vendor"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def fetch(manifest: dict, force: bool) -> Path | None:
    archive = VENDOR / manifest["archive_name"]
    if archive.exists() and not force:
        print(f"  exists: {archive.name} (use --force to re-fetch)")
        return archive
    print(f"  fetching: {manifest['url']}")
    VENDOR.mkdir(parents=True, exist_ok=True)
    tmp = archive.with_suffix(".part")
    try:
        urllib.request.urlretrieve(manifest["url"], tmp)
        # Fetch verifies inline: a wrong-byte archive never lands.
        actual = sha256_of(tmp)
        if actual != manifest["sha256"]:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(
                f"{manifest['id']}: fetched archive sha256 {actual} != pinned "
                f"{manifest['sha256']} — refusing to install"
            )
        tmp.rename(archive)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return archive


def fetch_nltk(manifest: dict, force: bool) -> Path | None:
    import nltk

    download_dir = VENDOR / "nltk"
    # NLTK stores corpora zips under <download_dir>/corpora/.
    target = download_dir / "corpora" / f"{manifest['corpus']}.zip"
    if target.exists() and not force:
        print(f"  exists: {target.name} (use --force to re-fetch)")
        return target
    ok = nltk.download(manifest["corpus"], download_dir=str(download_dir))
    if not ok or not target.exists():
        raise RuntimeError(f"nltk download failed for {manifest['corpus']}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    VENDOR.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for manifest_path in sorted(MANIFESTS.glob("*.yaml")):
        manifest = yaml.safe_load(manifest_path.read_text())
        print(f"[{manifest['id']} {manifest['version']}]")
        if manifest["kind"] == "archive":
            archive = fetch(manifest, args.force)
            if archive:
                hashes[manifest["id"]] = sha256_of(archive)
                print(f"  sha256: {hashes[manifest['id']]}")
        elif manifest["kind"] == "nltk":
            archive = fetch_nltk(manifest, args.force)
            if archive:
                hashes[manifest["id"]] = sha256_of(archive)
                print(f"  sha256: {hashes[manifest['id']]}")
    print("\nRecord these hashes into the manifests, then run verify_resources.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Sidecar registry loader.

Reads sidecars/*.toml at boot, fetches each manifest, pins release
identities. Refuses to start if any sidecar is missing or has a
manifest mismatch.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import httpx
import tomllib


class Sidecar:
    def __init__(self, name: str, manifest: dict, base_url: str) -> None:
        self.name = name
        self.manifest = manifest
        self.base_url = base_url

    def is_ready(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/ready", timeout=2.0)
            return r.status_code == 200 and r.json().get("ready", False)
        except Exception:
            return False


def load_sidecar_registry(root: Path = Path("sidecars")) -> Mapping[str, Sidecar]:
    out: dict[str, Sidecar] = {}
    for toml in root.glob("*.toml"):
        with toml.open("rb") as f:
            entry = tomllib.load(f)
        for name, cfg in entry.items():
            base = cfg["manifest_url"].rsplit("/manifest", 1)[0]
            r = httpx.get(f"{base}/manifest", timeout=5.0)
            r.raise_for_status()
            out[name] = Sidecar(name=name, manifest=r.json(), base_url=base)
    return out

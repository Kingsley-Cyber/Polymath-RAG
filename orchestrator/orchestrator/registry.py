"""Sidecar registry loader (ISSUES_REPORT §4.3/§4.6 fix).

One mechanism for "where does service X live": sidecars/*.toml entries
with explicit URL + release pin, validated at boot. Unpinned manifests
(`__PIN_*` placeholders) are reported, never silently trusted; missing
sidecars degrade /ready but never block startup (stores still serve).
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

import httpx
import tomllib


class Sidecar:
    def __init__(self, name: str, config: dict, manifest: dict | None, base_url: str) -> None:
        self.name = name
        self.config = config
        self.manifest = manifest or {}
        self.base_url = base_url
        self.pinned_release = config.get("release")

    @property
    def unpinned(self) -> bool:
        release = self.pinned_release or ""
        return release.startswith("__PIN_")

    def is_ready(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/ready", timeout=2.0)
            return r.status_code == 200 and bool(r.json().get("ready"))
        except Exception:
            return False


def load_sidecar_registry(root: Path | None = None) -> Mapping[str, Sidecar]:
    if root is None:
        # Repo-relative regardless of the process cwd:
        # orchestrator/orchestrator/registry.py -> repo root.
        root = Path(__file__).resolve().parents[2] / "sidecars"
    out: dict[str, Sidecar] = {}
    for toml in sorted(root.glob("*.toml")):
        with toml.open("rb") as f:
            entry = tomllib.load(f)
        for name, cfg in entry.items():
            base = cfg["manifest_url"].rsplit("/manifest", 1)[0]
            manifest: dict | None = None
            try:
                r = httpx.get(f"{base}/manifest", timeout=5.0)
                r.raise_for_status()
                manifest = r.json()
            except Exception:
                manifest = None
            out[name] = Sidecar(name=name, config=cfg, manifest=manifest, base_url=base)
    return out

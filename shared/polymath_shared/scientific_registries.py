"""DECISION A1 — authoritative scientific registries.

Registry surfaces feed ENTITY DISCOVERY as confidence=authoritative
candidates. They do NOT bypass Entity Admission: every registry-derived
span passes the same admission gates, with provenance
source=scientific-registries recorded.

Lookup is exact-surface (case-insensitive), deterministic — never fuzzy,
never frequency-based.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_REGISTRY_PATH = (Path(__file__).parent.parent.parent / "resources"
                  / "registries" / "scientific-registries.yaml")


@lru_cache(maxsize=1)
def load_registries() -> dict[str, dict[str, str]]:
    """{lowercase surface: {type, source, section}} — deterministic."""
    with _REGISTRY_PATH.open() as fh:
        reg = yaml.safe_load(fh)
    index: dict[str, dict[str, str]] = {}
    for section, entries in (reg or {}).items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            surface = (e.get("surface") or "").strip()
            if surface:
                index[surface.lower()] = {
                    "type": e.get("type", ""),
                    "source": f"registry:{section}:{e.get('source', '')}",
                }
    return index


def registry_lookup(surface: str) -> dict[str, str] | None:
    """Exact authoritative match for one surface, else None."""
    return load_registries().get((surface or "").strip().lower())

"""KNOWLEDGE-ROUTER-V1.1: deterministic document classifier.

OWNER CORRECTION APPLIED (v1.1): the router is a COST OPTIMIZER, not a
gatekeeper. It decides EXTRACTION PRIORITY per knowledge mode — never
whether knowledge exists. One ingestion engine; multiple grounded
representations at different confidence levels.

Signals (authored weights, deterministic):
  1 metadata   front-matter key/values
  2 structure  step markers / section headers
  3 linguistic per-mode lexicon density

Classification runs at DOCUMENT level (full text) — chunks have no
context. Output carries the routing contract tiers:
always / preferred / optional / disabled.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_HERE = Path(__file__).parent


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    with (_HERE / "knowledge_types.yaml").open() as fh:
        cfg = yaml.safe_load(fh)
    if not cfg.get("modes"):
        raise ValueError("knowledge_types.yaml missing modes")
    return cfg


def _front_matter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"')
    return out


def _lexicon_density(text: str, terms: list[list]) -> float:
    low = text.lower()
    n_words = max(len(low.split()), 1)
    hits = 0.0
    for term, weight in terms:
        hits += weight * len(re.findall(r"(?<!\w)" + re.escape(term.lower())
                                        + r"(?!\w)", low))
    return round(hits * 100.0 / n_words, 2)


def classify_document(text: str,
                      metadata: dict[str, str] | None = None) -> dict:
    """Multi-label knowledge-mode classification with priority contract.
    Deterministic. Document-level input required."""
    cfg = load_config()
    meta = {**_front_matter(text), **(metadata or {})}
    signals: dict[str, dict] = {}

    for mode, hints in (cfg.get("metadata_hints") or {}).items():
        s = signals.setdefault(mode, {"metadata": 0.0, "structure": 0.0,
                                      "linguistic": 0.0})
        for h in hints:
            if str(meta.get(h["key"], "")).strip() == h["equals"]:
                s["metadata"] += h.get("weight", 1)

    for mode, pats in (cfg.get("structure_patterns") or {}).items():
        s = signals.setdefault(mode, {"metadata": 0.0, "structure": 0.0,
                                      "linguistic": 0.0})
        for p in pats:
            s["structure"] += p["weight"] * len(
                re.findall(p["regex"], text))

    for mode, terms in (cfg.get("lexicons") or {}).items():
        s = signals.setdefault(mode, {"metadata": 0.0, "structure": 0.0,
                                      "linguistic": 0.0})
        s["linguistic"] += _lexicon_density(text, terms)

    scored: list[tuple[str, float]] = []
    for mode in cfg["modes"]:
        s = signals.get(mode)
        if not s or sum(s.values()) == 0:
            continue
        scored.append((mode, s["metadata"] * 2 + s["structure"] * 2
                       + s["linguistic"]))
    total = sum(v for _, v in scored) or 1.0
    modes = sorted(
        ({"type": m, "confidence": round(v / total, 2)} for m, v in scored),
        key=lambda x: -x["confidence"])

    primary = modes[0]["type"] if modes else "REFERENCE"
    policy = ((cfg.get("routing_policy") or {}).get(primary)
              or {"always": ["entity"], "preferred": [], "optional": [],
                  "disabled": []})
    enabled = sorted(set(policy.get("always", []))
                     | set(policy.get("preferred", [])))
    return {
        "router_version": cfg["version"],
        "primary_mode": primary,
        "modes": modes[:5],
        # v1.1 contract: priorities, not gates
        "routing": {
            "always": sorted(policy.get("always", [])),
            "preferred": sorted(policy.get("preferred", [])),
            "optional": sorted(policy.get("optional", [])),
            "disabled": sorted(policy.get("disabled", [])),
        },
        # backward-compatible view (always + preferred lanes)
        "enabled_extractors": enabled,
        "signals": {m: v for m, v in signals.items() if any(v.values())},
    }

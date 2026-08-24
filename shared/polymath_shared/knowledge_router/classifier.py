"""KNOWLEDGE-ROUTER-V1: deterministic document classifier.

Owner architecture decision: the router is a TRAFFIC CONTROLLER between
intake and extraction. It decides WHICH EXTRACTION PATHS may operate —
it never weakens admission, never creates facts, never uses embeddings.

Signals (authored weights, deterministic):
  1 metadata   front-matter key/values (e.g. youtube transcripts)
  2 structure  step markers / section headers (regex counts)
  3 linguistic per-mode lexicon density (hits per 100 words)

Output: multi-label modes with confidences + primary mode + domains.
Classification is NOT permanent truth — profiles refine after
processing (observed_content shares stored alongside initial
prediction).
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
    """Multi-label knowledge-mode classification. Deterministic."""
    cfg = load_config()
    meta = {**_front_matter(text), **(metadata or {})}
    signals: dict[str, dict] = {}

    # signal 1: metadata hints
    for mode, hints in (cfg.get("metadata_hints") or {}).items():
        s = signals.setdefault(mode, {"metadata": 0.0, "structure": 0.0,
                                      "linguistic": 0.0})
        for h in hints:
            if str(meta.get(h["key"], "")).strip() == h["equals"]:
                s["metadata"] += h.get("weight", 1)

    # signal 2: structure patterns
    for mode, pats in (cfg.get("structure_patterns") or {}).items():
        s = signals.setdefault(mode, {"metadata": 0.0, "structure": 0.0,
                                      "linguistic": 0.0})
        for p in pats:
            s["structure"] += p["weight"] * len(
                re.findall(p["regex"], text))

    # signal 3: lexicon density
    for mode, terms in (cfg.get("lexicons") or {}).items():
        s = signals.setdefault(mode, {"metadata": 0.0, "structure": 0.0,
                                      "linguistic": 0.0})
        s["linguistic"] += _lexicon_density(text, terms)

    # normalize each signal axis to 0..1 across modes, then combine
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

    primary = modes[0]["type"] if modes else "FACTUAL"
    policy = (cfg.get("routing_policy") or {}).get(primary, ["entity"])
    return {
        "router_version": cfg["version"],
        "primary_mode": primary,
        "modes": modes[:5],
        "enabled_extractors": policy,
        "signals": {m: v for m, v in signals.items() if any(v.values())},
    }

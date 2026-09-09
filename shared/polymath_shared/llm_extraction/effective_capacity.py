"""EFFECTIVE-CAPACITY-V1 (RAG-PIPELINE-FINISH Phase 3).

Resolves each lane's EFFECTIVE capacity by a fixed precedence, so the scheduler
optimizes valid durable work against real limits instead of a guessed catalog
number (plan §1.6, §1.7):

    runtime provider headers   (highest — owned live by the limiter)
        > explicit account config   (config/extraction_models/limiter.yaml)
        > vendored reference seed    (config/rate_limit_seed/catalog.v1.json)
        > unknown (None)             (NEVER coerced to 0)

The vendored seed is the LOWEST authority and is a local snapshot on purpose:
production never depends on an external CDN (plan do-not-do list). `null`
catalog values stay `None` — an unknown limit must not masquerade as `0`.

This module reads the seed file and the lane's already-resolved config capacity
(from `lane_registry.LaneCapacity`); it makes NO provider call. Runtime header
truth is supplied by the caller as an optional `observed` mapping (the limiter is
its live owner); when absent, config governs. No secret is read or rendered.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SEED_FILE = _REPO_ROOT / "config" / "rate_limit_seed" / "catalog.v1.json"

EFFECTIVE_CAPACITY_VERSION = "effective-capacity-v1"

#: precedence source labels, strongest first
SRC_OBSERVED = "observed"     # runtime provider headers
SRC_CONFIG = "config"         # explicit account config (limiter.yaml)
SRC_SEED = "seed"             # vendored reference catalog
SRC_UNKNOWN = "unknown"       # no value anywhere (stays None, never 0)

_FIELDS = ("rpm", "tpm", "rpd", "conc_cap")


def load_seed() -> dict:
    """The vendored reference catalog. Missing/broken file ⇒ empty (production
    keeps working from config; the seed is optional by design)."""
    try:
        return json.loads(_SEED_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _provider_slug(provider_host: str, model: str) -> str:
    h = (provider_host or "").lower()
    m = (model or "").lower()
    if "groq" in h or m.startswith("groq/"):
        return "groq"
    if "generativelanguage" in h or "google" in h or m.startswith("gemini"):
        return "google"
    if "openrouter" in h:
        return "openrouter"
    if "siliconflow" in h:
        return "siliconflow"
    if "nvidia" in h or "integrate.api.nvidia" in h:
        return "nvidia"
    if "localhost" in h or "127.0.0.1" in h or not h:
        return "local"
    return h.split(".")[0] if h else "unknown"


def seed_for(provider_host: str, model: str, seed: Mapping | None = None) -> dict | None:
    """The reference limits for a lane's provider/model — exact model match first,
    then a provider `*` wildcard. Returns the `limits` dict or None."""
    seed = load_seed() if seed is None else seed
    slug = _provider_slug(provider_host, model)
    entries = seed.get("entries") or []
    model_l = (model or "").lower()
    best_wild = None
    for e in entries:
        if str(e.get("provider", "")).lower() != slug:
            continue
        em = str(e.get("model", "")).lower()
        if em and em != "*" and em in model_l:
            return e.get("limits") or {}
        if em == "*":
            best_wild = e.get("limits") or {}
    return best_wild


@dataclass(frozen=True)
class EffectiveCapacity:
    lane: str
    values: dict = field(default_factory=dict)   # field -> int | None
    sources: dict = field(default_factory=dict)  # field -> SRC_*
    seed_version: str | None = None

    def to_dict(self) -> dict:
        return {"lane": self.lane, "values": self.values, "sources": self.sources,
                "seed_version": self.seed_version}


def resolve(lane, observed: Mapping | None = None, seed: Mapping | None = None) -> EffectiveCapacity:
    """Resolve one `lane_registry.LaneInfo`'s effective capacity by precedence.

    `observed` is an optional per-lane mapping of runtime-header truth
    ({rpm/tpm/rpd/conc_cap: int}); the limiter is its live owner. A value present
    in a stronger layer wins; a missing value falls through; nothing is coerced to
    0 (a null seed and an absent config both leave the field None/unknown)."""
    seed = load_seed() if seed is None else seed
    seed_limits = seed_for(lane.provider_host, lane.model, seed) or {}
    cfg = lane.capacity
    obs = dict(observed or {})
    values: dict = {}
    sources: dict = {}
    for f in _FIELDS:
        cfg_v = getattr(cfg, f, None)
        obs_v = obs.get(f)
        seed_v = seed_limits.get(f)
        if obs_v is not None:
            values[f], sources[f] = obs_v, SRC_OBSERVED
        elif cfg_v is not None:
            values[f], sources[f] = cfg_v, SRC_CONFIG
        elif seed_v is not None:
            values[f], sources[f] = seed_v, SRC_SEED
        else:
            values[f], sources[f] = None, SRC_UNKNOWN
    return EffectiveCapacity(lane=lane.name, values=values, sources=sources,
                             seed_version=seed.get("version"))


def resolve_all(registry, observed: Mapping[str, Mapping] | None = None) -> list[EffectiveCapacity]:
    """Effective capacity for every lane in a registry. `observed` maps lane name →
    its runtime-header truth (optional)."""
    observed = observed or {}
    return [resolve(l, observed.get(l.name), seed=load_seed()) for l in registry.lanes]

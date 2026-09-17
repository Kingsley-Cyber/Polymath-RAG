"""CANONICAL-SURFACE-REGISTRY-V1 — the single deterministic source for how each typed
document-profile surface is treated (checklist P4a).

The profile compiler normalizes each labelled field into a typed retrieval surface; THIS
registry — not scattered per-file tuples — decides that surface's storage/projection/retrieval
treatment. It is a leaf module (no imports of document_profile / query_intent), so the three
historical definition sites can all read from it without the import cycle that forced
`query_intent._MECH` to be inlined.

Each surface declares:
  group          — direct | semantic | discovery | lexical | identity  (scout/mode surface sets)
  profile_vector — None | "dense" | "multi"   (the global document-profile point)
  atom_kind      — canonical PROFILE_ATOM kind, or None (the addressable atom lane)
  atom_family    — mechanism | relational | rediscovery | None
  lexical        — payload / lexical treatment (TERM, ANCHOR, TOPIC)
  graph          — "off" | "resolve_on_use"   (NEVER a direct edge from profile text;
                   resolve_on_use = a discovery surface that MAY become a PROFILE_SYNTHETIC
                   Neo4j edge only after both endpoints resolve to real corpus documents)

The tuple ORDER is load-bearing: it reproduces the historical `MULTI_SURFACES`,
`ATOM_KINDS`, `_ATTR_TO_KIND`, and family orderings exactly (see test_surface_registry).
"""
from __future__ import annotations

from dataclasses import dataclass

REGISTRY_VERSION = "surface-registry-v1"


@dataclass(frozen=True)
class SurfacePolicy:
    attr: str
    group: str
    profile_vector: str | None
    atom_kind: str | None
    atom_family: str | None
    lexical: bool
    graph: str


#: ordered — DO NOT reorder without updating the behaviour-preservation test.
SURFACES: tuple[SurfacePolicy, ...] = (
    SurfacePolicy("title",          "identity",  "dense", None,             None,          False, "off"),
    SurfacePolicy("identity",       "identity",  "dense", None,             None,          False, "off"),
    SurfacePolicy("theme",          "semantic",  "dense", None,             None,          False, "off"),
    SurfacePolicy("questions",      "direct",    "multi", None,             None,          False, "off"),
    SurfacePolicy("searches",       "direct",    "multi", None,             None,          False, "off"),
    SurfacePolicy("theories",       "semantic",  "multi", "THEORY",         "mechanism",   False, "off"),
    SurfacePolicy("concepts",       "semantic",  "multi", "CONCEPT",        "mechanism",   False, "off"),
    SurfacePolicy("latent_pattern", "discovery", None,    "LATENT_PATTERN", "mechanism",   False, "off"),
    SurfacePolicy("boundary",       "discovery", None,    "BOUNDARY",       "mechanism",   False, "off"),
    SurfacePolicy("seealso",        "discovery", "multi", "SEEALSO",        "relational",  False, "resolve_on_use"),
    SurfacePolicy("bridge",         "discovery", None,    "BRIDGE",         "relational",  False, "resolve_on_use"),
    SurfacePolicy("anchor",         "lexical",   None,    "ANCHOR",         "relational",  True,  "off"),
    SurfacePolicy("tension",        "discovery", None,    "TENSION",        "relational",  False, "resolve_on_use"),
    SurfacePolicy("inversion",      "discovery", None,    "INVERSION",      "relational",  False, "off"),
    SurfacePolicy("recallq",        "direct",    None,    "RECALLQ",        "rediscovery", False, "off"),
    SurfacePolicy("terms",          "lexical",   None,    None,             None,          True,  "off"),
    SurfacePolicy("topics",         "semantic",  None,    None,             None,          True,  "off"),
)

BY_ATTR: dict[str, SurfacePolicy] = {s.attr: s for s in SURFACES}
BY_KIND: dict[str, SurfacePolicy] = {s.atom_kind: s for s in SURFACES if s.atom_kind}

# ── global-profile projection surfaces (projection.py reads these) ──────────────
DENSE_SURFACES: tuple[str, ...] = tuple(s.attr for s in SURFACES if s.profile_vector == "dense")
MULTI_SURFACES: tuple[str, ...] = tuple(s.attr for s in SURFACES if s.profile_vector == "multi")

# ── atom taxonomy (profile_atom.py reads these) ─────────────────────────────────
ATOM_KINDS: tuple[str, ...] = tuple(s.atom_kind for s in SURFACES if s.atom_kind)
MECHANISM_KINDS: tuple[str, ...] = tuple(s.atom_kind for s in SURFACES if s.atom_family == "mechanism")
RELATIONAL_KINDS: tuple[str, ...] = tuple(s.atom_kind for s in SURFACES if s.atom_family == "relational")
REDISCOVERY_KINDS: tuple[str, ...] = tuple(s.atom_kind for s in SURFACES if s.atom_family == "rediscovery")
ATTR_TO_KIND: dict[str, str] = {s.attr: s.atom_kind for s in SURFACES if s.atom_kind}

# ── graph-resolution policy (P3b Neo4j discovery edges read this) ────────────────
#: discovery surfaces that MAY resolve to a PROFILE_SYNTHETIC edge once both endpoints are
#: real corpus documents — never a direct edge minted from the raw profile text.
GRAPH_RESOLVABLE_KINDS: tuple[str, ...] = tuple(s.atom_kind for s in SURFACES
                                                if s.atom_kind and s.graph == "resolve_on_use")


def group_surfaces(group: str) -> tuple[str, ...]:
    """Surface attrs in a semantic group — the raw material for scout/mode surface sets (P5/P8)."""
    return tuple(s.attr for s in SURFACES if s.group == group)


def graph_policy(kind: str) -> str:
    """'off' | 'resolve_on_use' for an atom kind (default 'off' — never a direct text edge)."""
    s = BY_KIND.get(kind)
    return s.graph if s else "off"

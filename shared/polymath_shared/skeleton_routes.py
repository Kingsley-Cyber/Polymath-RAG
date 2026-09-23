"""SKELETON-ROUTING-V1 — skeleton doors open from the plan and the mode, never from one intent word.

DOCUMENT-SKELETON-V1 §4.3 (owner 2026-09-23). The skeleton (document profile + atoms + pMAP) finds documents, similar
documents and abstract bridges; RAG handles surface semantics. Which doors a turn opens:

- HYBRID: the profile → pMAP door (lane E) and the mechanism atoms (THEORY / CONCEPT / LATENT_PATTERN / BOUNDARY) that
  nominate extra documents through it. The SEEALSO fan-out (lane G) opens when the scout nominated documents for this
  question (the plan carries PROFILE / BRIDGE probes) — the skeleton already said which neighbours matter.
- GRAPH: HYBRID plus SEEALSO fan-out and the graph destination (lane H): one hop through the relational skeleton
  (owner decision D8 — "for graph see more can be used for hops").
- WILDCARD: every abstract door (every atom kind, latent rescue, fan-out, graph destination) with more judged seats per
  route: the same question, searched and weighed differently, still grounded in real chunks.
- FAST / VECTOR and GNN stay exactly as the owner defined them (A + B; the GNN route alone).

Every opened door also switches on path ids (`skeleton_paths`), so its hits keep their own stratum in fusion and their own
judged seats. `POLYMATH_CHAT_CONTEXTUAL_JUDGE` separately enables the path-aware (cross-encoder, no LLM) judgement:
`1` = every opened mode, `wildcard` = WILDCARD only (the replay showed it changes no final set on ordinary turns while
costing 0.2–1.3 s, so it belongs where depth is the point).
Pure: no I/O. Default off (`POLYMATH_CHAT_SKELETON_ROUTES`)."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import replace

from polymath_shared.surface_registry import (
    ATOM_KINDS,
    MECHANISM_KINDS,
    RELATIONAL_KINDS,
)

FLAG = "POLYMATH_CHAT_SKELETON_ROUTES"
JUDGE_FLAG = "POLYMATH_CHAT_CONTEXTUAL_JUDGE"
_SKIP_MODES = frozenset({"FAST", "VECTOR", "GNN"})
_NOMINATING_ORIGINS = frozenset({"PROFILE", "BRIDGE"})


def enabled(env: Mapping[str, str] | None = None) -> bool:
    return (env if env is not None else os.environ).get(FLAG, "0") == "1"


def apply_skeleton_routes(budget, *, mode: str, plan=None, env: Mapping[str, str] | None = None):
    """The budget with this turn's skeleton doors opened (a new object; the input is never mutated)."""
    env = env if env is not None else os.environ
    if not enabled(env):
        return budget
    m = (mode or "HYBRID").strip().upper()
    if m in _SKIP_MODES:
        return budget
    nominated = any(str(getattr(q, "origin", "") or "") in _NOMINATING_ORIGINS for q in (getattr(plan, "queries", None) or ()))
    kinds = set(getattr(budget, "atom_kinds", ()) or ()) | set(MECHANISM_KINDS)
    if m in ("GRAPH", "WILDCARD"):
        kinds |= set(RELATIONAL_KINDS)
    if m == "WILDCARD":
        kinds |= set(ATOM_KINDS)
    overrides = {
        "skeleton_paths": True,
        "dualread_enabled": True,
        "latent_enabled": True if m == "WILDCARD" else bool(getattr(budget, "latent_enabled", False)),
        "seealso_fanout_enabled": m in ("GRAPH", "WILDCARD") or nominated,
        "graph_dest_enabled": m in ("GRAPH", "WILDCARD"),
        "atom_kinds": tuple(k for k in ATOM_KINDS if k in kinds),
        "route_prefix_seats": 3 if m == "WILDCARD" else 2,
        # room in the composer's aspect step for the opened routes (a path's representative displaces only the lowest
        # items no other path depends on; the relevance / diversity slots stay the question's)
        "compose_aspect_slots": max(int(getattr(budget, "compose_aspect_slots", 3) or 3), 6 if m == "WILDCARD" else 5),
        "contextual_judge": (env.get(JUDGE_FLAG, "0") == "1") or (env.get(JUDGE_FLAG, "0") == "wildcard" and m == "WILDCARD"),
    }
    return replace(budget, **{k: v for k, v in overrides.items() if hasattr(budget, k)})

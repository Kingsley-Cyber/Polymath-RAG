"""CANONICAL-PROFILE-SELECTION-V1 — the fitness-gated guard that stops a thinner newly
compiled profile from silently overwriting a richer last-known-good projection.

Checklist P4 (canonical selection is an explicit stage; a profile is judged "good for
what", not "good/bad"). The audited regression: profile selection is newest-wins and the
profile point is a doc-id-keyed unconditional upsert, so a thin vNext profile
(questions:1 / searches:1) could replace a rich one (questions:15 / searches:15) with
nothing comparing their richness.

Fitness is measured BY FAMILY from the projected surface counts — the same
`{surface: count}` the projection payload already carries, so no schema change is needed:

    DIRECT     = answerability surfaces (questions, searches)   → FAST / HYBRID core
    DISCOVERY  = exploration surfaces  (theories, concepts, seealso) → GRAPH / WILDCARD
    anchors    = identity + theme present (the answerability spine)

The rule protects the ANSWERABILITY core: a new profile that loses the anchors, or is
materially thinner on the DIRECT family, is a regression and is refused unless `force`
(the sanctioned rearm / operator override). Discovery-only shrinkage does NOT block —
a profile strong on direct but weak on discovery is still valid ("good for what").

Pure functions, no I/O. The worker fetches the active point's counts and calls `select()`.
"""
from __future__ import annotations

from dataclasses import dataclass

SELECTION_VERSION = "canonical-profile-selection-v1"

#: surface families (names match projection.MULTI_SURFACES / the payload `surfaces` keys)
DIRECT_SURFACES = ("questions", "searches")
DISCOVERY_SURFACES = ("theories", "concepts", "seealso")
PRESENCE_SURFACES = ("identity", "theme")

#: a replacement may keep at most this fraction below the active DIRECT unit count
#: before it counts as an answerability regression (loses > half the Q/SEARCH units).
REGRESSION_RATIO = 0.5


@dataclass(frozen=True)
class Fitness:
    """Retrieval fitness by family, derived from projected surface counts."""
    direct: int
    discovery: int
    has_anchors: bool

    def as_dict(self) -> dict:
        return {"direct": self.direct, "discovery": self.discovery, "has_anchors": self.has_anchors}


def profile_fitness(surface_counts: dict | None) -> Fitness:
    """Fitness from a `{surface: count}` map (the projection payload's `surfaces`)."""
    c = surface_counts or {}
    direct = sum(_count(c.get(s)) for s in DIRECT_SURFACES)
    discovery = sum(_count(c.get(s)) for s in DISCOVERY_SURFACES)
    has_anchors = all(_count(c.get(s)) >= 1 for s in PRESENCE_SURFACES)
    return Fitness(direct=direct, discovery=discovery, has_anchors=has_anchors)


def _count(v) -> int:
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class Decision:
    replace: bool
    reason: str
    existing: dict
    incoming: dict
    version: str = SELECTION_VERSION


def select(existing_counts: dict | None, incoming_counts: dict | None, *, force: bool = False) -> Decision:
    """Decide whether `incoming` should replace the active `existing` projection.

    - no existing            → replace (first projection)
    - force (rearm/override)  → replace
    - existing had anchors, incoming lost them            → KEEP (regression)
    - incoming DIRECT < existing DIRECT * REGRESSION_RATIO → KEEP (regression)
    - otherwise               → replace (equal / improvement / discovery-only change)
    """
    inc = profile_fitness(incoming_counts)
    if existing_counts is None:
        return Decision(True, "first_projection", {}, inc.as_dict())
    ex = profile_fitness(existing_counts)
    if force:
        return Decision(True, "forced", ex.as_dict(), inc.as_dict())
    if ex.has_anchors and not inc.has_anchors:
        return Decision(False, "regression_lost_anchors", ex.as_dict(), inc.as_dict())
    if ex.direct > 0 and inc.direct < ex.direct * REGRESSION_RATIO:
        return Decision(False, "regression_direct_thinned", ex.as_dict(), inc.as_dict())
    improved = inc.direct >= ex.direct and inc.discovery >= ex.discovery
    return Decision(True, "improvement" if improved else "accepted", ex.as_dict(), inc.as_dict())

"""Drift guard for surface-name literals curated OUTSIDE SurfaceRegistry.

The Librarian audit (2026-09-18) found two legitimate purpose-specific surface sets defined
locally: the profile-nomination sets in `projection.py` (ANSWER/EXPLORATION) and the P4 fitness
families in `selection.py` (DIRECT/DISCOVERY/PRESENCE). They are correct today, but they name
surfaces as string literals — a rename/removal in SurfaceRegistry would break them silently.
This guard asserts every such literal remains a valid registry surface (and that the nomination
sets stay within the projected surfaces), so the drift is caught by a test, not in production.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import surface_registry as R  # noqa: E402
from polymath_shared.document_profile import projection as PJ  # noqa: E402
from polymath_shared.document_profile import selection as SEL  # noqa: E402

VALID = set(R.BY_ATTR)  # every surface attr declared in the single source


def test_projection_nomination_literals_are_registry_surfaces():
    for name in ("ANSWER_SURFACES", "EXPLORATION_SURFACES"):
        for s in getattr(PJ, name):
            assert s in VALID, f"projection.{name}: '{s}' is not a SurfaceRegistry surface"


def test_projection_nomination_sets_stay_within_projected_surfaces():
    projected = set(R.DENSE_SURFACES) | set(R.MULTI_SURFACES)
    assert set(PJ.ANSWER_SURFACES) <= projected, "ANSWER_SURFACES names an unprojected surface"
    assert set(PJ.EXPLORATION_SURFACES) <= projected, "EXPLORATION_SURFACES names an unprojected surface"


def test_selection_fitness_family_literals_are_registry_surfaces():
    for name in ("DIRECT_SURFACES", "DISCOVERY_SURFACES", "PRESENCE_SURFACES"):
        for s in getattr(SEL, name):
            assert s in VALID, f"selection.{name}: '{s}' is not a SurfaceRegistry surface"

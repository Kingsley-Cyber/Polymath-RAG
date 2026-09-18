"""CANONICAL-PROFILE-SELECTION-V1 — the fitness-by-family guard that refuses to let a
thinner newly compiled profile overwrite a richer last-known-good projection (checklist P4)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared.document_profile import selection as S  # noqa: E402

RICH = {"identity": 1, "theme": 1, "questions": 15, "searches": 15, "theories": 10, "concepts": 10, "seealso": 10}
THIN = {"identity": 1, "theme": 1, "questions": 1, "searches": 1, "theories": 1}


def test_fitness_splits_direct_and_discovery_families():
    f = S.profile_fitness(RICH)
    assert f.direct == 30 and f.discovery == 30 and f.has_anchors is True
    t = S.profile_fitness(THIN)
    assert t.direct == 2 and t.discovery == 1 and t.has_anchors is True
    assert S.profile_fitness(None) == S.Fitness(0, 0, False)
    assert S.profile_fitness({"questions": 3}).has_anchors is False   # no identity/theme anchors


def test_first_projection_and_force_always_replace():
    assert S.select(None, THIN).replace is True and S.select(None, THIN).reason == "first_projection"
    d = S.select(RICH, THIN, force=True)
    assert d.replace is True and d.reason == "forced"


def test_thin_profile_is_refused_over_a_rich_one():
    d = S.select(RICH, THIN)
    assert d.replace is False and d.reason == "regression_direct_thinned"
    assert d.existing["direct"] == 30 and d.incoming["direct"] == 2


def test_losing_the_answerability_anchors_is_a_regression():
    no_anchor = {"questions": 20, "searches": 20}          # rich direct but no identity/theme
    d = S.select(RICH, no_anchor)
    assert d.replace is False and d.reason == "regression_lost_anchors"


def test_improvement_and_equal_replace():
    assert S.select(THIN, RICH).replace is True and S.select(THIN, RICH).reason == "improvement"
    assert S.select(RICH, RICH).replace is True                       # equal re-projection is allowed


def test_discovery_only_shrink_is_allowed_good_for_what():
    # keeps the full answerability core, only the exploration surfaces shrink → still valid
    direct_strong = {"identity": 1, "theme": 1, "questions": 15, "searches": 15, "theories": 0, "concepts": 0, "seealso": 0}
    d = S.select(RICH, direct_strong)
    assert d.replace is True and d.reason == "accepted"

"""PROJECTION-LIFECYCLE-V1 (P1/P2) — the deterministic projection state machine over the
extended projection_receipts manifest."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import projection_lifecycle as L  # noqa: E402


def test_states_are_the_four_lifecycle_values():
    assert L.STATES == ("PENDING", "PROJECTED", "STALE", "FAILED")


def test_reconcile_derives_state_from_expected_vs_observed():
    assert L.reconcile_state("h1", "h1") == L.PROJECTED                    # current
    assert L.reconcile_state("h1", "h2") == L.STALE                        # drifted
    assert L.reconcile_state("h1", None, observed_present=False) == L.PENDING   # intended, absent
    assert L.reconcile_state(None, None, observed_present=False) == L.STALE     # nothing to project
    assert L.reconcile_state("h1", "h1", failed=True) == L.FAILED          # attempt errored


def test_is_current_and_is_rebuildable_answer_the_manifest_questions():
    assert L.is_current(L.PROJECTED) and not L.is_current(L.STALE)
    assert L.is_rebuildable(L.STALE) and L.is_rebuildable(L.FAILED) and L.is_rebuildable(L.PENDING)
    assert not L.is_rebuildable(L.PROJECTED)


def test_transitions_allow_the_meaningful_moves_and_idempotent_reassert():
    assert L.can_transition(L.PENDING, L.PROJECTED)
    assert L.can_transition(L.PROJECTED, L.STALE)
    assert L.can_transition(L.STALE, L.PROJECTED)     # rebuilt
    assert L.can_transition(L.FAILED, L.PROJECTED)    # retried ok
    assert not L.can_transition(L.PROJECTED, "NONSENSE")
    for s in L.STATES:
        assert L.can_transition(s, s)                 # a projector may re-assert its own state

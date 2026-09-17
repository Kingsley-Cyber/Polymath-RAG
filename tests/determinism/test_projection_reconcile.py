"""PROJECTION-RECONCILE-V1 (P1/P2 slice c) — deterministic reconciliation over the manifest."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from polymath_shared import projection_reconcile as RC  # noqa: E402


def test_reconcile_classifies_every_object_by_lifecycle_state():
    expected = {"a": "h", "b": "h", "c": "h", "d": "h", "e": None}
    observed = {
        "a": {"hash": "h", "present": True},            # PROJECTED
        "b": {"hash": "old", "present": True},          # STALE (drift)
        "c": {"present": False},                        # PENDING (nothing observed)
        "d": {"hash": "h", "present": True, "failed": True},   # FAILED
        # e: expected None + absent → STALE (nothing to project)
        "z": {"hash": "h", "present": True},            # ORPHAN (observed, not expected)
    }
    r = RC.reconcile(expected, observed)
    assert r.projected == ("a",) and r.stale == ("b", "e") and r.pending == ("c",) and r.failed == ("d",)
    assert r.orphaned == ("z",)
    assert r.rebuildable() == ("b", "c", "d", "e")
    assert not r.is_reconciled()


def test_full_projection_is_reconciled_with_completeness_1():
    expected = {"a": "h1", "b": "h2"}
    observed = {"a": {"hash": "h1", "present": True}, "b": {"hash": "h2", "present": True}}
    r = RC.reconcile(expected, observed)
    assert r.is_reconciled() and r.completeness() == 1.0 and r.rebuildable() == ()
    assert r.as_dict()["completeness"] == 1.0 and r.as_dict()["reconciled"] is True


def test_partial_projection_reports_completeness():
    expected = {f"a{i}": "h" for i in range(4)}
    observed = {"a0": {"hash": "h", "present": True}, "a1": {"hash": "h", "present": True}}
    r = RC.reconcile(expected, observed)
    assert r.completeness() == 0.5 and set(r.pending) == {"a2", "a3"}


def test_observed_from_manifest_rows_maps_active_projected_to_present():
    rows = [
        {"entity_id": "a", "receipt_hash": "h", "active": True, "state": "PROJECTED"},
        {"entity_id": "b", "receipt_hash": "old", "active": False, "state": "STALE"},
        {"entity_id": "c", "receipt_hash": "", "active": False, "state": "FAILED"},
    ]
    obs = RC.observed_from_rows(rows)
    assert obs["a"] == {"hash": "h", "present": True, "failed": False}
    assert obs["b"] == {"hash": "old", "present": True, "failed": False}   # drifted, still present
    assert obs["c"]["failed"] is True and obs["c"]["present"] is False       # failed → absent
    # a manifest of {a projected, b stale, c failed} against an all-expected set reconciles cleanly:
    rep = RC.reconcile({"a": "h", "b": "h", "c": "h"}, obs)
    assert rep.projected == ("a",) and rep.stale == ("b",) and rep.failed == ("c",)

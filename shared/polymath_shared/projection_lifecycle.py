"""PROJECTION-LIFECYCLE-V1 — the deterministic lifecycle for the projection_receipts manifest
(librarian checklist P1/P2).

Pure state logic, no I/O. Given the canonical EXPECTED artifact hash and the store-OBSERVED
projection hash, derive PENDING / PROJECTED / STALE / FAILED and answer "is this current?" and
"can it be safely rebuilt?". The manifest ROW lives in `projection_receipts` (extended by
migration 0065) — this module never opens a second authority.

    Postgres canonical object/artifact
            ↓ artifact_hash (expected)
    projection intent/state  ← reconcile_state(expected, observed)
            ↓
    Qdrant / Neo4j projection
            ↓ observed_ref + receipt_hash (observed)
    reconcile against canonical expected state
"""
from __future__ import annotations

LIFECYCLE_VERSION = "projection-lifecycle-v1"

PENDING = "PENDING"      # a canonical object is intended for projection, not yet projected
PROJECTED = "PROJECTED"  # the observed projection matches the canonical expected artifact
STALE = "STALE"          # the observed projection drifted from / lags the canonical expected
FAILED = "FAILED"        # a projection attempt errored
STATES: tuple[str, ...] = (PENDING, PROJECTED, STALE, FAILED)

#: a projector may re-assert the same state (idempotent); otherwise these are the meaningful moves.
VALID_TRANSITIONS: dict[str, set[str]] = {
    PENDING:   {PENDING, PROJECTED, FAILED, STALE},
    PROJECTED: {PROJECTED, STALE, FAILED, PENDING},
    STALE:     {STALE, PENDING, PROJECTED, FAILED},
    FAILED:    {FAILED, PENDING, PROJECTED, STALE},
}


def reconcile_state(expected_hash: str | None, observed_hash: str | None, *,
                    failed: bool = False, observed_present: bool = True) -> str:
    """Derive the lifecycle state from canonical-expected vs store-observed.

    - `failed`                         → FAILED (a projection attempt errored)
    - nothing observed, an expectation → PENDING (intended, not yet projected)
    - nothing observed, no expectation → STALE (nothing to project / removed)
    - observed == expected             → PROJECTED (current)
    - observed != expected             → STALE (drifted — rebuildable from canonical)
    """
    if failed:
        return FAILED
    if not observed_present:
        return PENDING if expected_hash else STALE
    if expected_hash and observed_hash == expected_hash:
        return PROJECTED
    return STALE


def can_transition(frm: str, to: str) -> bool:
    return to in VALID_TRANSITIONS.get(frm, set())


def is_current(state: str) -> bool:
    """The projection matches canonical — nothing to do."""
    return state == PROJECTED


def is_rebuildable(state: str) -> bool:
    """A projection can be safely (re)built from canonical when it is not already current."""
    return state in (PENDING, STALE, FAILED)

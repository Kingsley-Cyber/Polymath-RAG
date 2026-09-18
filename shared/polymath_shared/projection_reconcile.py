"""PROJECTION-RECONCILE-V1 — deterministic reconciliation over the projection_receipts manifest
(librarian checklist P1/P2 slice c).

Pure logic (no I/O): given the canonical EXPECTED set (entity_id → authoritative artifact hash)
and the store-OBSERVED manifest (entity_id → {hash, present, failed}), classify every object by
its lifecycle state, and answer the integrity questions — how complete is the projection, what
drifted, what must be rebuilt, and what is orphaned (present in the store, absent from canonical).
Composes `projection_lifecycle.reconcile_state`; opens no second authority.
"""
from __future__ import annotations

from dataclasses import dataclass

from polymath_shared import projection_lifecycle as L

RECONCILE_VERSION = "projection-reconcile-v1"


@dataclass(frozen=True)
class ReconcileReport:
    total_expected: int
    projected: tuple[str, ...]
    pending: tuple[str, ...]     # expected, nothing observed yet
    stale: tuple[str, ...]       # observed drifted from / lags canonical
    failed: tuple[str, ...]      # last projection attempt errored
    orphaned: tuple[str, ...]    # observed but not expected (safe to remove)

    def completeness(self) -> float:
        return len(self.projected) / self.total_expected if self.total_expected else 1.0

    def rebuildable(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.pending) | set(self.stale) | set(self.failed)))

    def is_reconciled(self) -> bool:
        return not (self.pending or self.stale or self.failed or self.orphaned)

    def as_dict(self) -> dict:
        return {"version": RECONCILE_VERSION, "total_expected": self.total_expected,
                "projected": len(self.projected), "pending": list(self.pending),
                "stale": list(self.stale), "failed": list(self.failed), "orphaned": list(self.orphaned),
                "completeness": round(self.completeness(), 4), "reconciled": self.is_reconciled()}


def reconcile(expected: dict[str, str | None], observed: dict[str, dict]) -> ReconcileReport:
    """`expected`: entity_id → canonical artifact hash (the authoritative version to project).
    `observed`:  entity_id → {"hash": <observed>, "present": bool, "failed": bool}."""
    buckets: dict[str, list[str]] = {L.PROJECTED: [], L.PENDING: [], L.STALE: [], L.FAILED: []}
    for eid, exp_hash in expected.items():
        obs = observed.get(eid) or {}
        present = bool(obs.get("present", eid in observed))
        state = L.reconcile_state(exp_hash, obs.get("hash"), failed=bool(obs.get("failed")), observed_present=present)
        buckets[state].append(eid)
    orphaned = [oid for oid in observed if oid not in expected]
    return ReconcileReport(
        total_expected=len(expected),
        projected=tuple(sorted(buckets[L.PROJECTED])),
        pending=tuple(sorted(buckets[L.PENDING])),
        stale=tuple(sorted(buckets[L.STALE])),
        failed=tuple(sorted(buckets[L.FAILED])),
        orphaned=tuple(sorted(orphaned)),
    )


def observed_from_rows(rows: list[dict]) -> dict[str, dict]:
    """Adapter: manifest rows (as `receipts.projection_manifest_row` returns) → the `observed`
    map `reconcile` expects. `receipt_hash` is the observed projection identity; a row that is
    not active (superseded/failed) is treated as not present so it reconciles as STALE/FAILED."""
    out: dict[str, dict] = {}
    for r in rows:
        # a non-empty receipt_hash means a point was projected and (barring a verified store
        # loss) still exists; drift is then detected by hash mismatch, not by the `active` flag.
        # FAILED means the attempt errored → nothing present.
        state = r.get("state")
        out[r["entity_id"]] = {
            "hash": r.get("receipt_hash"),
            "present": bool(r.get("receipt_hash")) and state != L.FAILED,
            "failed": state == L.FAILED,
        }
    return out

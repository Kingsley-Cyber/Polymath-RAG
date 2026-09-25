---
change_id: PROJECTION-RECONCILE-V1
owner: king
date: 2026-09-17
status: complete
status_note: "Pure classifier only; live reconcile (L5) never wired. Leftover moved to the gap register as D-06 (wire or retire, with the writer). (was: implemented)"
architecture_impact: deterministic reconciliation over the projection manifest (completeness, drift, rebuild set)
last_reviewed: 2026-09-17
---

## Contract

Librarian checklist P1/P2 (slice c — reconciliation/integrity). Pure logic that answers the
manifest's integrity questions: given the canonical EXPECTED set and the store-OBSERVED manifest,
classify every object by lifecycle state, and report completeness, drift, the rebuild set, and
orphans. Composes `projection_lifecycle.reconcile_state`; opens no second authority; no I/O.

## Changes

- `shared/polymath_shared/projection_reconcile.py` (NEW): `reconcile(expected, observed) →
  ReconcileReport` (projected/pending/stale/failed/orphaned, `completeness()`, `rebuildable()`,
  `is_reconciled()`, `as_dict()`); `observed_from_rows()` adapts `receipts.projection_manifest_row`
  rows into the observed map (a non-empty receipt_hash = present; drift is a hash mismatch; FAILED
  = absent).
- `tests/determinism/test_projection_reconcile.py` (NEW): classification of every state, full vs
  partial completeness, and the manifest-row adapter.

## Proof

`pytest test_projection_reconcile test_projection_lifecycle test_projection_lifecycle_migration
test_projection_manifest_writer` → 17 passed. Reconciliation is deterministic and pure.

## Rejected claims

- "Read the manifest's recorded `state` directly in reconcile." Rejected — reconcile RE-DERIVES
  state from canonical-expected vs store-observed hashes, so it can catch a manifest that has
  drifted from reality; the recorded state is a cache, not the arbiter.

## Open contract gaps

- LIVE-QUALIFICATION QUEUE (L5): run reconciliation over the live projection_receipts + the real
  canonical sets (per projection/entity_kind) after migration 0065 applies; wire it into the
  verify stage alongside the existing chunk/routing/graph reconcile.
- Building the live `expected` and `observed` maps from the stores is the coordinated-window
  integration; the pure classifier + the row adapter are proven here.

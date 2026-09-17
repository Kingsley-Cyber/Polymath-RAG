---
change_id: PROJECTION-LIFECYCLE-V1
owner: king
date: 2026-09-17
status: implemented
architecture_impact: the projection_receipts manifest gains an explicit PENDING/PROJECTED/STALE/FAILED lifecycle + canonical linkage
last_reviewed: 2026-09-17
---

## Contract

Librarian checklist P1/P2 (slice a — schema). The projection state authority already exists —
`projection_receipts` (the active claim) + `projection_attempts` (append-only history),
written by `receipts.record_projection_attempt`, read by `projection_want` / `verify_worker` /
`semantic_readiness`. It tracked only a 2-state `active` flag. This EXTENDS that single
authority (never a second one) with an explicit lifecycle + canonical-linkage columns so the
repo can answer deterministically: what should be projected, from which artifact/version/hash,
where, what exact projection exists, whether it is PENDING/PROJECTED/STALE/FAILED, and whether
it is safely rebuildable. Reuse-before-invention: no new manifest table, no new subsystem.

Deferred by design (owner boundary): the per-CANDIDATE RETRIEVAL provenance table (query role /
origin / planner lineage) is NOT defined here — it depends on the unsettled P6 contract. This
slice is the PROJECTION manifest only.

## Changes

- `stores/postgres/migrations/0065_projection_lifecycle.sql` (NEW, NOT APPLIED): additive
  columns on `projection_receipts` — `state` (default PROJECTED, CHECK the 4 values),
  `artifact_hash`, `projection_version`, `observed_ref`, `error`, `updated_at`; a state index;
  and the SOLE backfill = a faithful `active=false → STALE` relabel. Capacity-only.
- `shared/polymath_shared/projection_lifecycle.py` (NEW): pure state machine — `reconcile_state`
  (expected vs observed → PENDING/PROJECTED/STALE/FAILED), `can_transition`, `is_current`,
  `is_rebuildable`.
- Tests (NEW): `test_projection_lifecycle.py` (the state machine); `test_projection_lifecycle_migration.py`
  (SQL is additive / capacity-only / one faithful backfill / never a second authority).

## Proof

`pytest test_projection_lifecycle test_projection_lifecycle_migration` → 8 passed. The migration
is proven by property assertions (the repo's own migration-test style — `test_semantic_contract_v2_migration`);
DDL is NOT applied to the shared live database (LIVE-QUALIFICATION QUEUE).

## Rejected claims

- "Create a new projection_manifest table." Rejected per owner reuse-before-invention —
  `projection_receipts` is the existing authority; a parallel table would be a second authority.
- "Define query-role / provenance columns now." Deferred — that is the P6 retrieval contract,
  not settled; defining it here would guess the contract.

## Open contract gaps

- LIVE-QUALIFICATION QUEUE (L3): apply migration 0065 to the shared DB during the coordinated
  window, then reconcile existing projection_receipts rows.
- Projector integration (slice b) — profile/pmap/atom projectors writing lifecycle transitions +
  observed_ref — and reconciliation helpers (slice c) follow. This slice is schema + state logic.

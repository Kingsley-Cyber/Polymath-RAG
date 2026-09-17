---
change_id: PROJECTION-LIFECYCLE-WRITER-V1
owner: king
date: 2026-09-17
status: implemented
architecture_impact: the projection writer records lifecycle state + canonical linkage; back-compatible, migration-safe
last_reviewed: 2026-09-17
---

## Contract

Librarian checklist P1/P2 (slice b — state transitions). The lifecycle SCHEMA (slice a) is now
writable through the EXISTING writer: `receipts.record_projection_attempt` gains optional
lifecycle fields, and two helpers record the FAILED transition and read the manifest row. This
is the state-transition MACHINERY; wiring individual live projectors is deferred to the
coordinated window (the stage test runs the worker against the real un-migrated DB, so a live
lifecycle write there would fail until migration 0065 is applied).

## Changes

- `shared/polymath_shared/receipts.py`:
  - `record_projection_attempt(..., state=None, artifact_hash=None, observed_ref=None,
    projection_version=None)` — when ANY lifecycle field is supplied, writes the extended
    manifest columns and sets `active` from the lifecycle (TRUE only for PROJECTED); with NONE
    supplied, writes the LEGACY claim unchanged (no reference to the new columns → safe to
    deploy ahead of migration 0065; every existing caller byte-for-byte identical).
  - `mark_projection_failed(...)` — records state=FAILED, active=FALSE, error (preserving prior
    receipt/artifact hashes).
  - `projection_manifest_row(...)` — reads the current row (state + observed identity + canonical
    linkage) for reconciliation, or None.
- `tests/determinism/test_projection_manifest_writer.py` (NEW): legacy path writes no lifecycle
  columns; PROJECTED writes them + active; PENDING is not active; mark_failed sets FAILED; the
  read helper returns the row or None. Fake connection — no live DB.

## Proof

`pytest test_projection_manifest_writer` → 5 passed. No existing test/caller passes the new args,
so the legacy claim path is provably unchanged.

## Rejected claims

- "Always write the new columns." Rejected — that couples every projector to migration 0065 and
  would break the real-DB stage test; the dynamic legacy/lifecycle split keeps deploy ordering free.
- "Wire the profile/pmap/atom projectors now." Deferred — those workers are exercised against the
  real un-migrated DB in tests; live wiring belongs in the coordinated window after 0065 applies.

## Open contract gaps

- LIVE-QUALIFICATION QUEUE (L4): after migration 0065 applies, wire the profile/pmap/atom (and
  chunk/neo4j) projectors to pass `state`/`artifact_hash`/`observed_ref`/`projection_version`
  and to `mark_projection_failed` on error, then verify manifest rows on a live run.

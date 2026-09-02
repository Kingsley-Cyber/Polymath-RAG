---
change_id: CENSUS-UNCACHED-DIRTY-V1
owner: governance
date: 2026-09-02
status: complete
architecture_impact: control census incremental dirty signal (one clause)
last_reviewed: 2026-09-02
---

# WORK LOG — CENSUS-UNCACHED-DIRTY-V1 (a complete chain pinned at `reconciling`)

## Contract
Found during the owner's "double check the work for progression"
pass on the 2-doc scale-out receipt: Netnography finished every chain
stage (verify 07:23:51Z, project_qdrant 07:24:27Z) and never promoted,
while its sibling Psychology of Gambling promoted at 07:24:32Z. Standing
order "production ready" covers it; the class is the one
CENSUS-DIRTY-SIGNAL-V2 documented (verdict replayed forever) with one
variant left open.

## Changes
- control/control/census.py, incremental mode: after the started_at /
  ticket-updated_at / new-run dirty sets, add every ACTIVE run that has
  no cached verdict. Gap verdicts are never cached (V2 guard 2), so a
  run evaluated mid-projection carries no verdict; when its last ticket
  closed at T and a sibling's later ticket had already advanced the
  GLOBAL watermark past T within the same tick, its close fell under
  the lookback window and it was never re-evaluated. Re-evaluating
  uncached actives costs one verdict per stuck run per tick and closes
  every variant of the watermark race (no watermark semantics changed).

## Proof
- tests/determinism/test_incremental_census.py — 5 green (4 prior +
  test_uncached_active_run_is_always_reevaluated: fresh watermark
  seeded with the run absent, run inserted with all-chain attempts 30+
  minutes older than the watermark and no cached verdict → the next
  incremental pass evaluates it). Note: the negative run (test without
  the clause) was not executed — the fixture's timestamps are older than
  the watermark by construction, so only the new clause can select it.
- Deploy = control.main bounce (supervisor respawn) 07:31:44Z.
- HONEST LIVE OUTCOME: Netnography did NOT promote after the fix —
  a direct `compute_census(mode="full")` showed its verdict is
  DEGRADE (`extraction_dropped_neighborhoods_6`, the
  EXTRACTION-COVERAGE-V1 barrier), not a stale gap: its 43 KB doc ran
  on the LOCAL lane (Qwen3.5-4B, everything ≤ cloud_min_bytes does)
  which quarantined 13 of 17 calls and dropped 6 of 10 neighborhoods.
  So the uncached-dirty clause was a real closure of the V2 race but
  was not this run's cause; the run is correctly held back by the
  coverage barrier. Two things surfaced for the register:
  (a) `apply_degrades` wrote `degraded_reasons` into runs.metadata but
  the row's status still reads `reconciling` (expected `degraded`) —
  open gap below; (b) the local lane's quality is the weakest in the
  fleet (every cloud run today: 0–2 quarantines, 0 drops) — owner
  decision on the ≤300 KB local-only rule (settings floor).

## Rejected claims
- Widening the 1 s overlap window — treats the symptom; any sibling
  finishing later still advances the global watermark past a slower
  run's close.
- Per-run watermarks — correct but a schema/state change for a
  condition the uncached-set clause already covers at O(active runs).

## Open contract gaps
- The verify-before-projection ORDERING itself (verify_projections
  completed before project_qdrant on this run) is legal under the
  ticket DAG but surprising; the census re-verifies receipts so the
  promotion stays correct — recorded, not changed.

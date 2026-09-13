---
title: "WORK LOG — PMAP-SCALE-OUT-V1: the pMAP stage was worker-bound, not pool-bound"
change_id: PMAP-SCALE-OUT-V1
date: 2026-09-11
owner: control
last_reviewed: 2026-09-11
status: complete (4 slots, demand-scaled; ~4x measured)
register: 11.207
package: "control/control/process_supervisor.py + control/control/fleet_autopilot.py"
architecture_impact: "Fleet shape only. No change to MAP_RELIABILITY_CAP, lane topology, auto-mint scope or any retrieval path."
---

> **Ledger:** found while running the owner-authorized cinema backfill (2026-09-11). Register **11.207**.

## Contract

- **Smallest acceptance:** pMAP throughput rises materially without exceeding the lane budget and without
  touching the reliability cap or the auto-mint scope.
- **Verifier / rollback:** the measurement below; rollback = restore the single slot.

## Changes

- `process_supervisor.py` — `doc_parent_map2/3/4` added beside `doc_parent_map`.
- `fleet_autopilot.py` — one worker per open `doc_parent_map` ticket, **capped at four**, matching the
  existing `extract` (cap 3) and `doc_profile` (cap 6) scale-out rules.

## Proof

- **The original one-slot decision was explicit and reasoned** — "the worker's own infer closure fails over
  across the six map_groq accounts in-run, so one slot drains the pool" — i.e. it assumed the POOL was the
  constraint. The backfill measured otherwise: **40 dispatches in ~70 minutes** against **5 lanes × 2 rpm =
  10/min available**, i.e. **~6% provider utilisation**. A worker maps ONE DOCUMENT at a time and pays
  skeleton-build, batch planning and projection-embed serially between dispatches, so the WORKER was the
  constraint.
- **After:** 4 workers resident, **52 SUCCESS batches in 4 minutes** against 103 in the preceding 30 minutes —
  3.4/min → ~13/min, ≈**4×**. Cinema mapped went 2,473 → 2,840 in ~3 minutes.
- Safe by construction: batch tickets are **leased per document**, so concurrent workers cannot double-map;
  four concurrent documents still sit inside the lane budget rather than straining it; autopilot parks all
  four when no pMAP ticket is open, so idle cost is unchanged.
- `-k "autopilot or supervisor"` determinism tests: 0 failures.

## Rejected claims

- **"Raise `MAP_RELIABILITY_CAP` to go faster."** REJECTED — owner-forbidden, and the evidence points the
  other way (the three historical dispatched-but-empty batches were all `expected_count=60` on real parents).
- **"Add more lanes."** REJECTED — utilisation was 6%; more lanes would have changed nothing.
- **"Keep one slot because the comment says so."** REJECTED — the comment states an assumption about where the
  constraint lies, and the assumption was measurably wrong for a backfill workload.

## Open contract gaps

- Cap 4 is chosen to sit inside 5 lanes × 2 rpm; it is not tuned. A future run could measure 6 or 8.
- Throughput was measured on cinema's mid-size documents; very large documents may behave differently.

---
change_id: performance-correction
owner: control
date: 2026-08-25
status: complete
architecture_impact: none
last_reviewed: 2026-08-25
---

# PERFORMANCE-CORRECTION: cache semantics fixed, budget reverted

## Owner correction (accepted in full)

King's review caught a boolean inversion in RECEIPT-BUDGET-V1:
the receipt-verdict TTL cache stored `not present` while a call site
read it back as `present`. A measured MISSING verdict could therefore
falsely ADVANCE a run — precisely the failure class this architecture
forbids. Additionally: the focused pytest run had TIMED OUT (>300s),
so nothing was verified; and the 53.8-minute cold-seed tick was never
phase-attributed before another throttle was proposed.

## Actions

1. REVERTED RECEIPT-BUDGET-V1 (0010c9c).
2. RECEIPT-VERDICT-STORE-V2: explicit semantic states PRESENT/MISSING
   (strings, asserted on write), asymmetric TTL (PRESENT=90s,
   MISSING=900s), single writer representation, `_verdict_get/_put`.
   Advancement consults the store; a cached MISSING blocks advancement
   WITHOUT querying the database.
3. Regression tests proving each directive invariant:
   - MISSING never becomes PRESENT from cache
   - PRESENT never becomes MISSING from cache
   - expired entry re-queries; absent entry invents nothing
   - cached MISSING blocks advancement with zero DB queries
     (ExplodingConn pattern)
   - set-based helper maps states correctly
   - repeat-query collapse (25 decisions -> 1 query)
4. Root-caused the focused-suite hang: a pre-store-refactor control
   process held a 28-minute transaction on scheduler_cursors /
   receipts rows; recycled control to HEAD, suite terminates fast.
5. Incremental-census tests stabilized (watermark-relative seeding;
   monotonic watermark GREATEST guard added earlier).

## Status

- Receipt-verdict correctness: MEASURED green (13/13 across three suites).
- 53.8-min cold-seed tick phase breakdown: NOT yet attributed >=95% —
  instrumentation of census internals is the FIRST item for the next
  session, before any further optimization.
- RECEIPT-BUDGET: reverted; may return ONLY as a configurable defensive
  cap AFTER incremental census is proven, with DEFERRED distinct from
  FAILED/MISSING and forward-progress guarantees tested.

## Contract

(Historical entry — the contract it worked under is stated in the entry body above.)

## Changes

(Historical entry — the changes are recorded in the entry body above.)

## Proof

(Historical entry — the proof and measured evidence are in the entry body above.)

## Rejected claims

(Historical entry — none recorded beyond the entry body above.)

## Open contract gaps

(Historical entry — see the entry body and the CURRENT_STATE chain above.)

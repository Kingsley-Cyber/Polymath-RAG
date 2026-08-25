---
change_id: TICK-ARITY-FIX-AND-PHASE-TELEMETRY
owner: control
date: 2026-08-25
status: implemented
architecture_impact: none
---

# TICK-ARITY-FIX-AND-PHASE-TELEMETRY (2026-08-25)

## Contract

`control.main.tick()` completes every cycle: lease → reconcile → ensure →
advance → supervise → census → schedule → promote/fail → heartbeat.
Owner: `control`. Receipt semantics stay RECEIPT-VERDICT-STORE-V2
(explicit PRESENT/MISSING, asymmetric TTL, advancement consults store).

## Changes

1. MEASURED LIVE DEFECT: since the store cutover commit (4e243cc) every
   real tick died with
   `_advance_pending_corpus() takes 2 positional arguments but 3 were
   given` — 1,864 consecutive failed ticks (control.log). Component
   tests passed because nothing exercised the `advance_tickets`
   entry point end-to-end. Consequence: no census watermark, no
   advancement, no promotions fleet-wide until this fix.
2. Fix: call site updated to `_advance_pending_corpus(conn, corpus_id)`;
   the dead per-tick memo dict removed (the verdict store is the only
   memo now, per V2).
3. CENSUS-PHASE-TIMING-V1: always-on phase telemetry inside
   compute_census (runs query / dirty select / attempts fetch / python
   loop / receipt checks ms + counts) surfaced through
   pop_census_timing(); main.tick logs phase_ms per tick in
   TICK-PHASE-TIMING-V1 detail. Zero behavior change; microsecond cost.
4. Regression: test_lock_contention_v2.py::test_advance_tickets_entry_point_wiring
   pins the entry-point wiring AND the 2-parameter signature so the
   arity class cannot silently return.

## Proof

- pytest: lock_contention_v2 (7/7 incl. new wiring+signature pins),
  receipt_verdict_store 5/5, incremental_census 4/4,
  event_adapter_dict_cursor 10/10 — all green, seconds.
- Post-deploy live proof recorded in cold-tick attribution report:
  first ok tick after restart seeds watermark and emits phase_ms.

## Rejected claims

- NOT claiming pre-fix pending backlog advanced during the outage — it
  did not; advancement resumes from durable cursors after deploy.
- No change to receipt TTLs, states, or advancement predicates.

## Open contract gaps

- The determinism suite has no transactional full-tick integration test;
  the fake-wiring test covers arity but not SQL-level regressions.
  Candidate slice behind POLYMATH_INTEGRATION=1.

---
change_id: AUTOPILOT-TAIL-DEMAND-V1
owner: governance
date: 2026-09-01
status: complete
architecture_impact: fleet_autopilot demand map (run-status filter + two unmapped stages)
last_reviewed: 2026-09-01
---

# WORK LOG — AUTOPILOT-TAIL-DEMAND-V1 (query_ready froze the tail)

## Contract
Found during the owner's live upload-anatomy test (Atomic Habits):
45 minutes after query_ready, compile_objects/parent_enrichment/
summaries/vocabulary tickets sat open with ZERO workers — the
autopilot had parked summaries ("no demand", 13:30:28Z) one minute
after promotion. Standing order "production ready" covers it.

## Root cause (three gaps, one class)
1. `_open_work`'s run-status filter counted only
   intake/reconciling/degraded — the moment a run flipped
   query_ready, every open tail ticket stopped registering as
   demand. query_ready is the CHAIN terminal, not the RUN terminal:
   the non-blocking tail is non-blocking BY DESIGN and still owns
   open tickets after the flip.
2. `parent_enrichment` appeared in NO lane's demand stages — an
   enrichment-only backlog could never wake the summaries worker.
3. `compile_objects` had no lane at all — its worker had NEVER been
   demand-woken since autopilot activation (it only ever ran under
   hand-started static fleets).

Why every earlier corpus still finished: their tails happened to
drain while chain traffic from sibling documents kept the workers
awake. A lone document exposes the gap deterministically.

## Changes (control/control/fleet_autopilot.py)
- run-status filter += 'query_ready' (addition, not swap).
- summary lane demand stages += parent_enrichment.
- new lane ("compile", (compile_objects,), {compile_objects}).

## Proof
- tests/determinism/test_fleet_autopilot_demand.py — 4 green: every
  tail stage maps to a lane; compile_objects maps to its own slot;
  enrichment wakes summaries; the SQL filter carries query_ready
  alongside the historical statuses.
- LIVE drain receipt: fleet rebooted with the fix at ~14:26Z;
  compile_objects (open since 13:29Z) completed 14:26:40 — the first
  demand-woken run of that worker ever — and the whole tail drained
  by 14:33:48 (enrichment 112/112 READY, all tickets done).

## Rejected claims
- "Park the tail until the next chain wakes it" (implicit prior
  behavior) — rejected: a promoted run's tail is contracted work,
  not opportunistic work; its latency budget is minutes, not
  next-upload.
- Removing intake/reconciling/degraded from the filter — untouched;
  the fix is an addition. Historical/test debris exclusion (the
  JOINs) stays exactly as measured in AUTOPILOT-WORKLOAD-HYGIENE-V1.

## Open contract gaps
- None for this defect. Broader note stands: demand mapping is a
  hand-maintained table; a future stage added without a lane row
  repeats gap 3. test_every_tail_stage_signals_some_lane pins the
  currently-known taxonomy only.

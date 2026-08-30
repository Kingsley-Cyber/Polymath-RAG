---
change_id: FOREGROUND-UNDER-BACKLOG
owner: governance
date: 2026-08-25
status: implemented
architecture_impact: claim ordering policy change; stale scale mass archived
last_reviewed: 2026-08-29
---

# FOREGROUND-UNDER-BACKLOG (2026-08-25)

## Contract

New work must reach query_ready without waiting on historical backlog;
the full audit may continue separately. Claiming stays deterministic:
fresh lane → ticketed lane → event_id FIFO, starvation-safe by
construction (backlog drains whenever the fresh lane empties).

## Changes

1. MEASURED violation: a probe document submitted under load completed
   intake+extract in <40 s, then stalled >1 hour at profile_document.
   Cause chain measured:
   a. worker claims were strict event_id FIFO — 238 older READY tickets
      parked ahead of the new document (0 drain in 120 s);
   b. the queue behind them was dominated by ONE corpus: scale-10k-v1
      held 10,253 of ~10,260 undelivered profile events (stale
      scale-qualification mass permanently occupying the scheduler).
2. Fix A (claim lanes): ORDER BY fresh-run-first (created <15 min),
   then legacy ticketed-first, then FIFO — one query, no extra trips,
   pinned by test_claim_starvation addition.
3. Fix B (mass disposition): 3,467 scale-10k-v1 pending/ready tickets →
   dead_letter_archive + status='superseded' + archived_at (the
   established terminal pattern; runs preserved; re-drivable). NOT
   touched: sealed corpora, real corpora, frozen eval artifacts.
4. Operational finding recorded: a boot did not survive shell-session
   recycling ("supervisor stopped" 11:43:17Z); boots must be disowned.
   Fleet relaunched detached; fence PASS after tree cleaned.

## Proof

- Probe run run_88602387…921: stalled ≥60 min pre-fix → **query_ready
  ≈90 s** post-fix, full chain intake→…→verify observed in
  stage_attempts.
- Ticks post-cleanup: 21.7–26.6 s wall with advance_tickets 12 s,
  schedule_gaps 5–8 s, barrier 3.5–5.8 s, census 70–130 ms
  (/tmp/polymath_fleet/tick_phases.jsonl).
- pytest: claim_starvation + adapter suites green (17/17 relevant).

## Rejected claims

- NOT claiming zero foreground wait under ANY arrival rate: the fresh
  lane bounds waiting to one in-flight item per worker type.
- NOT deleting any run or evidence row; superseded is reversible.

## Open contract gaps

- advance_tickets remains O(pending DAG walk) ≈12 s at current pending
  volume; set-based advancement is the next candidate slice if it stays
  flagged after drain.

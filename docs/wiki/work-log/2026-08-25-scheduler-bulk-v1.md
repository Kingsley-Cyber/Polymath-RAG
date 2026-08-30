---
change_id: SCHEDULER-BULK-V1
owner: control
date: 2026-08-25
status: implemented
architecture_impact: none
last_reviewed: 2026-08-29
---

# SCHEDULER-BULK-V1 (2026-08-25)

## Contract

`schedule_gaps(conn, census) -> int` materializes census gaps as outbox
events with idempotent content-hash keys; identical payloads re-arm the
same outbox row (delivered_at=NULL), never duplicate.

## Changes

1. MEASURED live phase telemetry (`/tmp/polymath_fleet/
   tick_phases.jsonl`): schedule_gaps cost **51.0s and 54.9s** of two
   consecutive ticks — the legacy loop ran 1-2 queries PER GAP
   (payload lookup + single-row INSERT) across tens of thousands of
   replayed gaps every tick.
2. Bulk rewrite: identity-only stage payloads (`project_*`, `verify`,
   `canonicalize`, `profile_document`) are computed locally with ZERO
   reads; intake/chunked payloads come from ONE `DISTINCT ON` query per
   event type; intake falls back to batched `runs.metadata` reads; all
   inserts go out as chunked multi-row `unnest` statements.
3. Idempotency keys are byte-identical to the legacy derivation — pinned
   by test against independently computed content hashes, so the same
   durable outbox rows re-arm exactly as before.

## Proof

- pytest scheduler_bulk 3/3; focused core 38/38 green.
- Post-deploy live tick phase table recorded in attribution artifacts
  (schedule_gaps expected to fall from ~52s to sub-second).

## Rejected claims

- NOT changing gap semantics: which runs/stages produce gaps is census
  behavior, untouched here.
- Insertion ORDER of new events within one tick may differ from the
  legacy loop (grouped by type); no contract consumes intra-tick
  event_id ordering across types.

## Open contract gaps

- advance_tickets remains ~20-25s live (per-ticket DAG walk);
  set-based advancement is the next candidate slice if telemetry keeps
  flagging it after this deploy.

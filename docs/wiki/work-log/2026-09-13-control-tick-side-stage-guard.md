---
title: "WORK LOG — CONTROL-TICK-SIDE-STAGE-GUARD-V1: a pending ticket for a non-DAG side stage killed every control tick for ~31 h; guard chain advancement the way the READY backfill already is"
change_id: CONTROL-TICK-SIDE-STAGE-GUARD-V1
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.256
architecture_impact: "control/control/tickets.py: `_try_advance_one` returns False (logged once per stage) for a stage outside STAGE_DAG instead of `DAG_ORDER.index` raising. No DAG change, no ticket semantics change: side stages (doc_parent_map, parent_enrichment) still mint their own READY tickets and never chain-advance. Restores ticket advancement for every corpus. Live via the supervisor's control restart (control.main loads the tree on spawn) + the code-drift fence cycling the workers."
---

> Owner (2026-09-13): "fix the control tick" — after the pMAP slice (11.255) traced the dead tick to its root cause.

## Contract
`advance_tickets` walks every PENDING ticket of every corpus through `_try_advance_one`, which orders
predecessors by `DAG_ORDER.index(stage)`. Two stages are DELIBERATELY absent from `STAGE_DAG`
(`doc_parent_map`, `parent_enrichment`: minted READY by their own triggers, never by chain advancement,
non-blocking for promotion). A ticket for such a stage in status `pending` therefore has no advancer and,
before this change, was a landmine: `.index` raised `ValueError` and the WHOLE tick aborted before
`auto_enrich`, `auto_map_parents`, `supervise`, census, scheduling and the heartbeat. The tick must be
robust to that row the way the READY backfill already is (its 2026-08-31 guard for the same class of bug).

## Changes
- **`control/control/tickets.py` `_try_advance_one`**: `if stage not in _STAGE_SPEC: return False` with a
  once-per-stage warning naming the ticket. Nothing else changes: DAG stages take the identical path.
- **`tests/determinism/test_control_tick_side_stage_guard.py`** (new, declared in TREE): (1) the side stages
  are outside the DAG and non-blocking by design; (2) `_try_advance_one` returns False for a side stage
  WITHOUT touching the database (a stub connection that raises proves it) while a DAG stage still queries;
  (3) real-Postgres, rolled back: a corpus whose only pending ticket is a `doc_parent_map` ticket advances
  cleanly (0 advanced, ticket still pending, no event emitted) — the exact production shape.

## Proof
- **Root cause (measured, not inferred)**: `control.log` carried 10,191 `control tick failed` entries ending in
  `ValueError: 'doc_parent_map' is not in list` at `tickets.py:459`; `control_heartbeats` newest row
  2026-09-11 23:53:02 UTC; the supervisor's boot log restarted `control.main` every 180 s ("control heartbeat
  stale (112149 s)"). 12 `doc_parent_map` tickets in status `pending` (all cinema, created 09-11 23:40:54 by
  `mint_doc_parent_map` as READY — the [:40] ticket-id formula — and flipped to `pending` at 23:55:55 as the
  forensic-hold pause; the 09-12 bootstrap log records that state: "36 done / 12 pending / 0 ready / 0 leased").
  The first pending side-stage ticket therefore killed the tick from the next cycle on.
- **Tests**: 14 green across the new file + `test_receipt_verdict_store` + `test_run_scoped_receipts` +
  `test_stage_dag_contract`.
- **Live (measured 17:21-17:27 UTC)**: the supervisor's 180-s restart spawned `control.main` on the new code at
  17:21:02; first `tick completed` 17:22:03 after ~41 h of failures; `control_heartbeats` fresh (age ≤ 65 s, 5 ticks
  per 5 min); the stall tracer immediately labelled the 12 paused tickets `PENDING_OWNER_STAGE` ("pending is never
  advanced"). The code-drift fence quarantined and respawned every slot (24 restarts, 0 exit-budget quarantines) →
  fleet 23 healthy / ONE hash `074de79f4bf7`. **Hold lifted (owner)**: the 12 tickets were re-armed at 17:22:31 via the
  production `mint_doc_parent_map` → 12 `ready` → the four pMAP stage workers claimed and closed ALL 12 (`done` 36 → 48)
  by 17:27 with **0 provider attempts and 0 new maps** (idempotent, as predicted). Ticket totals 831/6/230 →
  844/6/217 (done/failed/pending): the 217 remaining pending tickets wait on their own failed predecessors
  (6 failed: 5 project_qdrant + 1 intake), pre-existing and outside this slice.

## Rejected claims
- **"Add `doc_parent_map` to STAGE_DAG"** — REJECTED: the stage is outside the DAG on purpose (auto-minted,
  non-blocking so a capacity-held pMAP never holds legacy QUERY_READY); putting it in the chain would change
  promotion semantics and every run's ticket chain.
- **"Filter the pending SELECT instead"** — REJECTED as the ONLY fix: `_try_advance_one` is the function that
  indexes the DAG; guarding it protects every caller and mirrors the READY-backfill guard. (The keyset scan
  still pages past side-stage rows at negligible cost.)
- **"The 63 `reconciling` cinema runs are caused by this"** — NOT CLAIMED: their pending summary/vocabulary
  tickets date from 09-05/07 and one run carries a `failed` project_qdrant; the dead tick since 09-11 merely
  froze whatever advancement remained. What the restored tick does with them is measured, not assumed.

## Open contract gaps
- **The 12 paused `doc_parent_map` tickets** — CLOSED (re-armed under the owner's lifted hold; 0 spend). None remain.
- **Pre-existing chain blockers** (failed project_qdrant ticket, 09-05/07 pending summaries) are outside this slice.

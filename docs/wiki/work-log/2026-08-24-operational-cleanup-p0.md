---
change_id: operational-cleanup-p0
owner: control
date: 2026-08-24
status: complete
architecture_impact: none (compatibility adapter at consumption boundary + health-baseline archive)
last_reviewed: 2026-08-24
---

# OPERATIONAL-CLEANUP-P0: legacy event adapter + dead-letter archive

## Contract

Workers consume CANONICAL event payloads only. Legacy-shape events are
normalized (with best-effort recovery) at the claim boundary; a payload
that cannot be recovered fails its ticket ONCE with a typed reason
(LEGACY_EVENT_UNRECOVERABLE) instead of crashing the stage loop on a
missing key. Health baselines evaluate current system state: historical
invalid probes are archived with an explicit reason and excluded from
dead-letter health, never silently purged.

Smallest acceptance criteria:

1. `shared/polymath_shared/event_adapter.py` normalizes known legacy
   shapes to canonical payloads; recovery consults tickets/artifacts.
2. Unrecoverable poison fails the ticket deterministically (attempt
   burned once, typed last_error), zero worker KeyError crash-loops.
3. Migration 0032 adds `dead_letter_archive` + `archived_at`/
   `archived_reason` on stage_tickets; probe-enf2 archived as
   `historical invalid probe`, excluded_from_health=true.
4. Convergence watcher counts only non-archived failures.

## Changes

- shared/polymath_shared/event_adapter.py (new)
- shared/polymath_shared/worker_runtime.py (normalize at claim)
- stores/postgres/migrations/0032_dead_letter_archive.sql (new)
- workers/workers/extract_worker.py (typed failure path)

## Proof

Determinism tests + live behavior in session log.

## P1 ARTIFACT-PERSISTENCE proof (same slice session)

Migration 0033 applied. Live corpus `p1-genre-probe-v1`:
- SOP doc -> procedure_artifacts row: 4 steps, tools [Splunk forwarder,
  SIEM console, ...], confidence 0.8, bundle-stamped.
- Philosophy doc -> 3 concept_artifacts (discipline of assent,
  Amor fati, + heading-glued first entry flagged as polish).
- Qdrant collection for the corpus: 10 points including
  routing_procedure x1 and routing_concept x3 with text composed from
  goal/steps/tools and name/description respectively.
- Idempotency: re-ingest of identical bytes reuses content-addressed
  artifact ids (ON CONFLICT DO NOTHING).

## PHASE 2+3 proof (same session)

- SUMMARY-WORKER-FLEET-V1 wired into supervisor ('summaries' slot,
  pipeline+converge profiles); in-process drive of the real contracts
  produced parent_summaries=2 -> document_summaries=2 -> corpus map=1
  on the genre corpus; vocabulary admitted 0 families by design
  (single-doc support, fail-closed).
- QUERY-ROUTER-V1 + /ask route: deterministic lexicon classifier;
  acceptance 4/4 PASS (FACT/PROCEDURE/CONCEPT/POLYMATH), grounded=True
  everywhere (stored-objects-only), citations resolve.
- Fixes folded in: barrier SQL SyntaxError (control ticks were failing
  whenever promotions existed) + superseded-history miscount;
  concept-name heading glue cleanup; fact-lane SQL-side prefilter.

## Flagged for next session (Phase-6 performance)

scale-10k verify/projection transactions hold locks >26 min
(corpus-wide COUNT(*) per document inside one tx); control tick is
lock-blocked behind them, freezing ticket creation fleet-wide until
they finish. Not a correctness defect; it is THE throughput item and
it starves small interactive ingests while a large backlog drains.

## PHASE 4A LOCK-CONTENTION-V2 proof

Measured root causes (two independent defects compounded):
1. control/control/tickets.py::_receipts_present ran a corpus-wide
   anti-join COUNT per candidate ticket per projection inside the
   tick's single transaction — O(pending x chunks x receipts). On
   scale-10k this held ticks open for minutes; combined with the
   barrier SyntaxError (fixed earlier today) the control loop had been
   effectively dead since Aug 23 12:41 UTC (heartbeat gap proven).
2. verify reconciliation executed Qdrant/Neo4j network I/O inside the
   caller's transaction (minutes-long snapshot).

Fixes: EXISTS early-exit + per-pass (run_id,projection) memoization in
ticket advancement; verify read-phase moved to short autocommit
connections with the outer tx bounded to writes. Regression tests:
tests/determinism/test_lock_contention_v2.py (shape pin, memo
single-query, missing-receipt detection).

Live: heartbeat resumed 2026-08-25 02:04 UTC after >1 day gap;
small-corpus invariant A passes — lock-test-a-v1 received its full
12-ticket DAG during peak backlog saturation.

## SESSION CLOSEOUT (2026-08-25)

Continuation packet: docs/contexts/session-packet-2026-08-25.md
Handoff: NEXT_SESSION_HANDOFF.md (rewritten at closeout)
Next engineering item: incremental census (telemetry-justified), then
contract freezes + three-mode benchmark + real-corpus pilot.

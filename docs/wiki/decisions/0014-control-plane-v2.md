---
owner: control
last_reviewed: 2026-08-16
last_touched: 2026-08-16
status: accepted
---

# ADR-0014: Control Plane V2 — explicit execution authority

Status: accepted (2026-08-16, CONTROL-PLANE-V2 gate)

## Context

I4R exposed a class of failures that are not extraction failures:
12-hour-old worker processes claim re-armed events and silently
produce no stage attempts; evaluators run against reconciling corpora
(retrieval 0/30); versioning-fixture debris blocks convergence; the
operator debugs with ps/lsof/nohup. The orchestration was implicit:
event appears → worker hopefully claims → stage hopefully finishes →
receipts hopefully reconcile.

## Decision

Finish the control plane as a deterministic execution authority over
the existing Postgres substrate. Four mechanisms:

1. **Worker identity + compatibility gating.** Every worker
   registers (worker_id, type, pid, build SHA, contract versions) and
   heartbeats. A work unit carries the run's execution contract
   (extraction contract hash, model revisions, policy versions, pack,
   rescue stages, worker build). Incompatible or stale workers are
   REFUSED leases and marked — the 12-hour-old-worker class becomes a
   visible supervisor state instead of silent behavior.

2. **Durable stage tickets.** Handoff is explicit: each run holds a
   ticket chain (intake → extract → profile_document → project_qdrant
   → project_neo4j → canonicalize → project_canonical → verify).
   A ticket becomes READY only after the control plane verifies the
   predecessor's artifact keys, receipts, and contract hash. The
   outbox event for a stage is EMITTED by ticket readiness — workers
   never infer readiness from event existence. Leases are ticket-
   scoped with expiry.

3. **Generation readiness barrier.** QUERY_READY for a corpus
   generation requires all tickets DONE, zero pending repair tickets,
   projection desired == actual (per-object reconciliation — the
   census's missing-receipt diff becomes exact repair tickets, not
   "rerun the stage and hope"), and verify success.

4. **Evaluation snapshot barrier.** Evaluators acquire a snapshot
   token (corpus, generation, state hash). Validation failure aborts
   the evaluation loudly. Evaluation never races the control plane.

Throughput posture: the ticket chains of different documents progress
independently (pipelined fan-out); per-stage pending-ticket high
watermarks pause upstream ticket creation (backpressure); promotion is
the only barrier. The control plane is a traffic controller, not a
serial workflow engine.

## Consequences

- Workers become executors of exactly-scoped legal work units; they
  keep their stage logic (process_event) unchanged.
- The old implicit flow (claim any undelivered event) is replaced by
  ticket-gated claiming; healthy fleets behave identically, unhealthy
  ones become visible.
- Deferred to V2.1: automatic drain/restart, typed artifact ledger
  (run/stage/artifact_kind identity), experiment coordinator, GLiNER
  dynamic batching service, capacity-aware scheduling.

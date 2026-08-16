---
change_id: control-plane-v2
owner: control
date: 2026-08-16
status: complete
architecture_impact: adds-explicit-execution-authority-over-workers
last_reviewed: 2026-08-16
---

# CONTROL-PLANE-V2: execution authority (tickets, gating, barriers)

## Contract

Authorized 2026-08-16 after the I4R closeout ("extraction design is no
longer the main architectural risk"). FOUR initial targets only:

1. Worker generation/config compatibility — workers advertise identity
   (build SHA + contract versions); work is leasable ONLY by compatible
   workers; stale workers are marked, not mysteriously served.
2. Durable stage tickets + lease semantics — explicit handoff: a stage's
   work event exists only after the control plane VERIFIES the
   predecessor's artifacts/receipts/contract; leases are ticket-scoped.
3. Convergence/readiness barrier — QUERY_READY for a corpus generation
   requires: all tickets DONE, no pending repair tickets, projection
   desired == actual, verify ok.
4. Evaluation snapshot barrier — evaluators acquire a snapshot token
   (corpus, generation, state hash); state change during evaluation
   aborts it loudly instead of measuring garbage (retrieval 0/30 class).

Throughput amendment (second directive): pipelined execution — every
document's ticket chain progresses independently (fan-out), projection
repairs are per-object tickets, promotion is barriered. Bounded
per-stage queues with a high watermark pause upstream ticket creation
(backpressure). The control plane is a traffic controller, never a
serial workflow engine.

OUT of scope (V2.1, not built): automatic worker drain/restart,
typed artifact ledger (kind-scoped artifact identity), experiment
coordinator, GLiNER dynamic batching service.

## Changes

- ADR-0014 (execution model).
- Migration 0012: `stage_tickets`, `worker_registrations`,
  `corpus_snapshots`, `runs.execution_contract`.
- `shared/polymath_shared/execution.py` — worker identity/registration/
  heartbeat, run execution-contract assembly, compatibility rules.
- `control/control/tickets.py` — per-run stage DAG with per-stage
  required artifacts/receipts; ticket advance (verify → READY → emit
  event); per-object projection repair tickets; generation barrier;
  bounded-queue backpressure (high watermark).
- `control/control/supervisor.py` — stale-worker detection, lease
  revocation, fleet status ("N healthy / M stale").
- `shared/polymath_shared/worker_runtime.py` — one worker loop:
  register, heartbeat, claim ticket-gated events, process; all eight
  workers refactored onto it.
- `control/control/snapshots.py` + `eval/i4r/snapshot_barrier.py` —
  snapshot acquire/validate for evaluators (frozen harness untouched).
- Control tick: reconcile = desired-vs-actual repair tickets;
  QUERY_READY promotion gated by the generation barrier.

## Proof

- Unit: ticket state machine, compatibility gating, barrier, snapshot
  invalidation, backpressure watermark.
- Integration: ticket-driven end-to-end run (intake → query_ready)
  through the refactored worker runtime; stale-worker lease denial.
- Full suite green; guards green; production defaults unchanged
  (ticket gating is active by default — it subsumes the old implicit
  handoff; behavior for healthy fleets is identical).

## Rejected claims

- No claim of large-corpus throughput yet: no load test performed;
  batching service and capacity-aware scheduling deferred to V2.1+.
- No worker auto-restart: supervisor marks/quarantines; restart stays
  an operator action.

## Open contract gaps

- V2.1 items named above; TEST-HARNESS-STABILITY remains separate.

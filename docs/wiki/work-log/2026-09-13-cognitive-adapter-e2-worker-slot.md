---
title: "WORK LOG — COGNITIVE-ADAPTER-TRAIL-E2E-V1 E2 close-out: the adapter step worker becomes a supervised fleet slot (registration + heartbeat; process_supervisor `adapter_step`)"
change_id: COGNITIVE-ADAPTER-TRAIL-E2E-V1-E2-WORKER-SLOT
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.263
architecture_impact: "workers/workers/adapter_step_worker.py registers a worker_registrations row (worker_type adapter_step) and heartbeats each loop; control/control/process_supervisor.py declares the `adapter_step` slot (health = fresh registration heartbeat, like every fleet worker). control/ + workers/ edits → live only after the production worktree takes this code and a fleet bounce."
---

> Plan §6: "workers/workers/…: durable adapter step execution"; E2 item 5: resume after orchestrator/worker restart — under the
> SUPERVISOR, not only under a test harness.

## Contract
The supervisor's health gate for a worker slot is a FRESH `worker_registrations` heartbeat for `worker_type == slot.name`
after the spawn; quarantine and the bundle fence key on the same row. A worker that never registers is invisible to the
fleet's self-healing (11.79) and cannot be a slot. The adapter worker must therefore register through the same path as every
other worker (`polymath_shared.execution.register_worker` / `heartbeat` with `worker_identity`).

## Changes
- **`workers/workers/adapter_step_worker.py`**: `WORKER_TYPE = "adapter_step"`; `worker_identity` + `register_worker` at start
  (records the execution bundle like every worker); `heartbeat(processed_count=1 per worked run)` after every claim cycle.
- **`control/control/process_supervisor.py`**: slot `("adapter_step", "workers.adapter_step_worker")` after the pMAP stage workers.
- **`tests/determinism/test_adapter_worker_registration.py`**: the slot is declared; a `--once` worker leaves a `healthy`
  `adapter_step` registration with a heartbeat newer than its spawn (the supervisor's exact gate), carrying a bundle hash.

## Proof
- 3 green: 2 registration tests + the live crash-resume test unchanged (the worker still resumes after `os._exit(137)`).
- Not yet live: the production fleet runs the pre-E2 tree; the slot appears at the next production switch + bounce.

## Rejected claims
- **"Reuse `run_worker`"** — REJECTED: it is the ticket/outbox loop (claim_ticket_events); adapter runs lease `adapter_runs`
  directly. The registration/heartbeat primitives are shared and reused as-is.

## Open contract gaps
- Production switch + bounce (next): then the supervisor owns the worker (restart budget, fence, quarantine) and the
  official-MCP-client acceptance run can rely on a supervised worker.

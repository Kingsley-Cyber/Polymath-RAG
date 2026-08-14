---
owner: control
last_reviewed: 2026-08-13
last_touched: 2026-08-13
status: accepted
---

# ADR-0004: Control plane is a separate process

## Context

v3.3's "control plane" is `services/control_plane/{ledger,
desired_state, reconciler, certificate}.py`: a Mongo collection plus
an inline loop inside the FastAPI backend process. When the backend
restarts (memory pressure, OOM, deploy, the 2026-07-04 RestartCount=37
incident), the control plane restarts with it. In-flight work is
paused. There's no leader election, no queue-driven resume, just "the
next tick of the loop, eventually."

## Decision

The control plane is a separate process (`control/control/main.py`),
supervised by systemd. It has its own log, its own heartbeat, and its
own crash-safety.

Communication:
- Reads: Postgres tables (`runs`, `stage_attempts`, `outbox`,
  `control_heartbeats`).
- Writes: Postgres tables (status transitions, outbox).
- Wakeups: the transactional outbox plus Postgres notifications. Any safety
  poll cadence must come from a recovery experiment and operations contract.

The control plane never serves user requests. The orchestrator never
decides "what to do next." Each does one job.

## Consequences

Easier:
- The orchestrator can crash without taking the control plane down.
  Intake requests 503 with retry-after; existing in-flight runs
  continue to be scheduled.
- The control plane can crash without taking the orchestrator down.
  Reads still work; writes are paused. Heartbeat staleness in
  `control_heartbeats` triggers an alert.
- Adding a new stage is a control-plane PR, not an orchestrator PR.
  The orchestrator doesn't need to know what stages exist.

Harder:
- One more process to supervise. `polymath-control.service` joins
  the unit file list.
- Heartbeats are load-bearing. If the control plane stops heart-
  beating, the alert fires but the system keeps running with stale
  state. The alert has to be loud.

## Triggered refactors

- `docs/wiki/refactors/0006-control-as-systemd-unit.md`

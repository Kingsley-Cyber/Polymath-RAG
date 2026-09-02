---
change_id: SIDECAR-READINESS-GATE-V1 + TICKET-TRANSIENT-RELEASE
owner: governance
date: 2026-09-02
status: complete
architecture_impact: SidecarClient.wait_ready; projection worker gates on the embedder before its first call; worker_runtime hands a ticket back WITHOUT an attempt on sidecar unavailability (+15 s backoff)
last_reviewed: 2026-09-02
---

# WORK LOG — a booting sidecar burned a ticket's whole retry budget in eight seconds

## Contract
Traced from the MCP upload test (owner law: anything stuck > 3 min is a
defect): after enrichment settled, the run's latent re-projection ticket
(`project_qdrant`) went `failed` and the summary tail (corpus_summary,
vocabulary) froze behind it — the stall tracer raised PENDING_ON_PREDECESSOR
on both.

## Root cause (from the qdrant worker log + supervisor log)
12:15:23 the autopilot woke `sidecar_embedder` AND the `qdrant` worker in
the same tick (embed: 1 open). The worker registered at 12:15:24, claimed
the ticket and failed it at 12:15:25, 12:15:28 and 12:15:33 — three
attempts in eight seconds — while the embedder was still loading its model
(supervisor: "sidecar_embedder not ready (1/5)" at 12:15:25; the client's
connection-refused breaker was open). A worker that depends on a sidecar
always loses that race, and `_fail_ticket` charges every loss as a stage
failure. Deterministic: it happens on every enrichment settle on an idle
fleet (the embedder is parked when nothing embeds).

## Changes
1. `SidecarClient.wait_ready(timeout_s=120, poll_s=2)`: polls `/ready`
   (bypassing the breaker); success clears the breaker for the host.
2. `project_qdrant_worker._embed_texts`: gates on `wait_ready` before the
   first embedder call (`POLYMATH_SIDECAR_READY_WAIT_S`, default 120);
   still not ready → SidecarUnavailable (a real failure).
3. `worker_runtime`: `SidecarUnavailable` anywhere in the cause chain is
   TRANSIENT — `_release_ticket_transient` hands the ticket back to READY
   with attempt UNCHANGED and a typed note, the worker backs off one
   breaker window (15 s) before its next poll. Attempts count executions
   that failed; a sidecar that never answered did not execute anything.
4. Recovery of the stuck run: `scripts/retry_failed_stage.py ecom-meta-v1
   project_qdrant --execute` (sanctioned tool) → re-projection ran with the
   embedder up → tail settled.

## Proof
- tests/determinism/test_sidecar_readiness_gate.py 4 green: wait_ready
  returns once /ready flips and clears the breaker; gives up after the
  budget without raising; the projection worker gates before verify_pin;
  the runtime classifies sidecar unavailability as transient.
  test_client_resilience 21 still green.
- LIVE: after the reset the fresh qdrant worker (spawned 12:17:16 with the
  embedder already up) projected the 54 new latent rows; corpus_summary
  and vocabulary followed; all 14 stages done at 12:18:41Z; 0 open stall
  episodes.

## Rejected claims
- Raising the retry cap — three instant failures against a booting
  sidecar would become five.
- Making the autopilot wake the sidecar a tick earlier — races by
  construction; the worker must own its dependency's readiness.

## Open contract gaps
- Other sidecar consumers (reranker at query time already has a breaker +
  rank-fusion fallback; the local extraction lane) should adopt the same
  gate when they next change.
- The failed attempts wrote receipts but no stage_attempts rows; the
  bookkeeping asymmetry is noted, not fixed here.

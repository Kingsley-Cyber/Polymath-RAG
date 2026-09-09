---
title: "WORK LOG — RAG-finish Phase 4: functional-pool drain assessment + pool-health primitive"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: governance (assessment + a reusable pool-health primitive; no runtime behavior change)
last_reviewed: 2026-09-09
status: complete (extraction+profile PASS; PMAP-as-drained-pool deferred to Phase 7 wiring)
register: 11.189 (pending)
package: shared/polymath_shared/llm_extraction/lane_registry.py, tests/determinism/test_lane_registry.py
architecture_impact: "No runtime behavior change. Assesses the functional-pool drain invariant against existing implementation+tests and adds a provider-free STAGE→pool + per-pool lane-health primitive (feeds Phase 12 live queue metrics). Bundle hash unchanged; no fleet fence."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` **PHASE 4** + register **11.189** (pending).

## Contract

Make GRAPH_EXTRACTION, DOCUMENT_PROFILE and PMAP true functional pools whose healthy lanes finish retryable
work (plan Phase 4). Reuse the existing durable ticket/lease/control-plane substrate — do NOT invent a
second orchestration system.

## Assessment — the drain invariant is already implemented + tested for 2 of 3 pools

The durable substrate the plan asks for EXISTS (`worker_runtime.py`: lease/claim, transient-requeue with no
attempt burned, `_fail_ticket` cap-3 terminal; `llm_provider.run_proposals._dispatch`: in-run cross-host
failover; `pool.py`: family-interleaved ring + pinned-stage sharding). Phase 4's fake-provider matrix maps
onto existing green tests:

| Phase-4 fake-pool case | covered by |
|---|---|
| A 429s, B succeeds → DONE via B | `test_transient_capacity_and_hold.py::test_provider_capacity_errors_are_transient` (429/lane-refused → ticket requeued READY, no attempt) + `test_extraction_pool.py::test_failover_ring_is_deterministic_and_crosses_lanes` |
| A times out, B/C healthy → drainable | same transient-requeue + cross-lane failover ring |
| one lane breaker opens → other keys continue | `test_lane_registry.py` (per-account `family: groq_acct_N` isolation) + `test_offline_conservation_replay.py` (per-lane breaker) |
| all lanes transiently unavailable → retryable, not DLQ | `test_transient_capacity_and_hold.py` (transient hold hands ticket back) |
| permanent deterministic failure → bounded retries then terminal | `test_transient_capacity_and_hold.py::test_real_transport_failures_still_fail` + `_fail_ticket` cap-3 |
| successful result exists → no duplicate regeneration | content-addressed run/batch/map identity (`ensure_run_tickets` born-DONE-if-prior-ok; `map_hash`/`batch_hash` idempotency) |

**Verdict:** GRAPH_EXTRACTION and DOCUMENT_PROFILE are true drained functional pools (in-run multi-lane
failover + whole-stage transient requeue), gate satisfied by existing tests.

## The PMAP gap (the goal's spine) — deferred to Phase 7 with an exact pointer

PMAP is **not yet a drained pool**: `doc_parent_map` is not in `STAGE_DAG`, has no registered worker, and
its only driver (`scripts/parent_map_backfill.py`) does NOT fail a 429'd batch over to a healthy lane in-run
(`doc_parent_map_worker.py:308-339` `break`s; the batch is left `partial` for a later run). Making PMAP a
true functional pool = wiring `doc_parent_map` as an auto-minted stage with a registered pool worker + in-run
cross-lane failover — the plan's **Phase 6 (grounding integration) → Phase 7 (lane-qualified drainable
batches) → the stage registration**. Tracked there; not duplicated here.

## Changes

- `lane_registry.py`: `STAGE_TO_FUNCTION` + `functional_pool_of(stage)` (DAG stage → pool) and
  `LaneRegistry.pool_lane_health()` (per-pool total/active/credential-absent/disabled + active lane names).
  These are the provider-free "healthy qualified lanes" primitive the Phase 12 canonical status joins against
  live `stage_tickets` queue depth/oldest-age.
- `tests/determinism/test_lane_registry.py`: +2 tests (stage→pool mapping; pool-lane-health counts). 11/11 green.

## Proof

- `pytest tests/determinism/test_lane_registry.py` → **11/11 green**; the drain-matrix tests above are green
  in their own modules.
- `bundle_integrity` READY, hash unchanged `7e97368daa92ec19`.
- `repo_guard` / `wiki_worm` / `agent_preflight` ok.

## Rejected claims

- **NOT claimed:** PMAP is a drained functional pool today. It is not — that is the spine, completed by the
  Phase 6/7 stage wiring. Overstating it would be the exact "a lane selection is not an HTTP dispatch /
  a ticket existing is not consumption" trap the plan warns against.
- **No second orchestration system built** — reused the existing ticket/lease substrate; added only a
  read-only mapping primitive.

## Open contract gaps

- PMAP drained-pool completion → Phase 6/7 + stage registration.
- Live per-pool queue metrics (pending/claimed/retryable/terminal/oldest-age/throughput) → Phase 12 joins
  `pool_lane_health()` with `stage_tickets` counts.

---
title: "WORK LOG — RAG-finish Phase 7: lane-qualified pMAP batch cap"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: governance (batch-planner policy + config; no runtime behavior change until the stage worker consumes it)
last_reviewed: 2026-09-09
status: complete (batch-cap qualification; in-run cross-lane failover lands with the stage worker)
register: 11.192 (pending)
package: shared/polymath_shared/document_profile/map_batches.py, workers/workers/doc_parent_map_worker.py, shared/polymath_shared/llm_extraction/lane_registry.py, config/cloud_providers.json, tests/determinism/test_map_batches.py, tests/determinism/test_lane_registry.py
architecture_impact: "The pMAP reliability cap is no longer a hard-coded global 15: plan_batches / run_document_mapping take a lane-qualified reliability_cap, and the registry exposes a per-lane map_batch_cap + pmap_pool_batch_cap() (min over active pMAP lanes, so every batch is drainable by every lane; architectural target 60 honored for a qualified pool). Default MAP_RELIABILITY_CAP=15 unchanged → byte-identical batch identities. No provider spend. Bundle hash unchanged; no fleet fence."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` **PHASE 7** + register **11.192** (pending).

## Contract

Prevent `MAP_RELIABILITY_CAP=15` from being a global functional limit: qualify/configure the effective pMAP
batch cap per account/model lane, preserve the architectural target 60 and the measured compound-mini value,
let the token envelope lower the functional target, keep large-document batches independently drainable.

## Changes

- `map_batches.plan_batches(..., reliability_cap=MAP_RELIABILITY_CAP)` threads the cap to
  `mapping_only_capacity(density, reliability_cap=...)`, which already mins it with the token envelope + the
  production target. Default unchanged.
- `doc_parent_map_worker.run_document_mapping(..., reliability_cap=MAP_RELIABILITY_CAP)` passes it to
  `plan_batches`.
- `lane_registry`: per-lane `map_batch_cap` (a WORKLOAD capability, distinct from provider RPM/TPM) +
  `pmap_pool_batch_cap(registry)` = MIN over active pMAP lanes (drain invariant), default
  `PMAP_DEFAULT_BATCH_CAP=15`.
- `config/cloud_providers.json`: `map_batch_cap: 15` on `map_groq1..6` (the measured compound-mini value;
  `pool.py` ignores the field, the registry reads it). A future 40/60-qualified lane raises its own.
- Tests: `test_map_batches::test_reliability_cap_is_lane_qualified` (raising the cap enlarges batches, target
  60 honored, envelope bounds a huge cap, default 15 unchanged); `test_lane_registry::
  test_pmap_pool_batch_cap_is_min_over_active_lanes`.

## Proof

- `pytest tests/determinism/test_map_batches.py tests/determinism/test_lane_registry.py` → **27/27 green**.
- Live registry: all six `map_groq*` lanes read `map_batch_cap=15`; `pmap_pool_batch_cap()=15`.
- `bundle_integrity` READY, hash unchanged; `repo_guard` / `wiki_worm` / `agent_preflight` ok.

## Rejected claims

- **No expensive live 15/30/40/60 benchmark run** (plan Phase 7 action 7 + do-not-do list): the
  compound-mini envelope is already known (measured 11.178); the cap is now configurable, so no provider
  spend was needed to change configuration.
- **NOT the whole PMAP drain** — in-run cross-lane failover (the other half of "large-document batches
  independently drainable by the PMAP pool") lives in the pMAP STAGE worker's infer closure, landing with the
  stage wiring.

## Open contract gaps

- The stage worker consumes `pmap_pool_batch_cap()` and adds in-run cross-lane failover across `map_groq*`
  (429/refusal → next healthy account IN-RUN, not defer) — completing the PMAP functional-pool drain (Phase
  4 gap) and enabling the auto-minted fresh-doc pMAP stage.

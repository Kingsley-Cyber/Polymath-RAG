---
title: "WORK LOG — RAG-finish: auto-minted pMAP stage (the spine) — worker + flag-gated mint"
change_id: RAG-PIPELINE-FINISH-V1
date: 2026-09-09
owner: worker (doc_parent_map stage) + control (flag-gated mint); governance for the plumbing
last_reviewed: 2026-09-09
status: complete (code + offline tests; goes live at the Phase 15 canary via a fleet restart + flag enable)
register: 11.193 (pending)
package: workers/workers/doc_parent_map_stage_worker.py, shared/polymath_shared/document_profile/map_trigger.py, control/control/scheduler.py, control/control/main.py, control/control/tickets.py, control/control/process_supervisor.py, tests/determinism/test_doc_parent_map_stage_worker.py, tests/determinism/test_doc_parent_map_trigger.py
architecture_impact: "Makes PMAP a real drained functional pool for FRESH uploads — the step that lets a new document reach VNEXT_COMPLETE (readiness floor unresolved_eligible_parents==0). Adds a doc_parent_map STAGE worker (in-run cross-lane failover over the six map_groq accounts; the first healthy lane finishes a batch, all-dark defers TRANSIENT with no attempt burned) driving the frozen durable core (ParentSkeleton -> plaintext MAP DSL -> deterministic compiler -> durable maps -> projection). The stage is minted like parent_enrichment: OUTSIDE STAGE_DAG, by a FLAG-GATED scheduler phase (auto_map_parents_on_chunks), and is non-blocking. FROZEN STAGE_DAG unchanged; only NON_BLOCKING_STAGES gains doc_parent_map. FORENSIC-HOLD SAFE: POLYMATH_DOC_PARENT_MAP_ENABLED defaults OFF => zero tickets minted => byte-identical current behavior, zero provider spend; an optional POLYMATH_DOC_PARENT_MAP_CORPUS scope keeps the cinema corpus untouched during the bounded canary. The fleet gains an idle doc_parent_map slot. Not yet live: requires a fleet restart (loads the new control code + slot) AND the flag — both deferred to the Phase 15 canary after the Phase 14 offline gate."
---

> **Ledger:** `RAG_PIPELINE_FINISH_PLAN.md` PHASE 6/7/8 (the pMAP-pool wiring) + `RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` S12 (fresh-doc pMAP) + register **11.193** (pending). The forensic hold on the cinema backfill is untouched.

## Contract

Wire `doc_parent_map` so a fresh upload's parents are mapped by the PMAP functional pool and the document can
reach `VNEXT_COMPLETE`, WITHOUT (a) changing the frozen STAGE_DAG contract, (b) re-mapping existing corpora
(the forensic hold), or (c) any provider spend until the owner-gated canary. Reuse the durable
ticket/lease/idempotency substrate; the frozen MAP DSL/compiler/chunker are untouched.

## Changes

- **`doc_parent_map_stage_worker.py`** (new fleet worker): resolve run → load document + parents → build
  `DocumentGroundingContextV1` → `run_document_mapping(infer=<in-run cross-lane failover>,
  reliability_cap=pmap_pool_batch_cap(), grounding=…)` → project active maps to Qdrant → write the
  `doc_parent_map` stage artifact. The infer closure walks the six `map_groq*` accounts (rotated per run); the
  FIRST healthy lane finishes a batch; if EVERY account is unavailable it raises `MapInferError` (carrying the
  dispatched flag) so the durable core defers the batch (partial) and the stage hands its ticket back
  TRANSIENT — no document-level failure while a qualified lane could do the job (the Phase 4/7 PMAP drain).
  Incomplete-with-capacity-signal → `TransientStageHold` (requeue, no attempt); incomplete without → a real
  failed attempt.
- **`map_trigger.py`** (new): `mint_doc_parent_map` (ticket + `doc_parent_map.v1` event, idempotent re-arm) +
  the `POLYMATH_DOC_PARENT_MAP_ENABLED` / `POLYMATH_DOC_PARENT_MAP_CORPUS` flag helpers. Mirrors
  `latent/trigger.mint_parent_enrichment`.
- **`scheduler.auto_map_parents_on_chunks`**: flag-gated mint for runs whose parents exist (intake done), no
  existing pMAP ticket, not archived, within the optional corpus scope + a stranded-ticket rescue — an exact
  mirror of `auto_enrich_on_chunks`. Returns 0 (no DB access) when disabled.
- **`control/main.py`**: `_phase("auto_map_parents", auto_map_parents_on_chunks, conn)` after the enrich kick.
- **`control/tickets.py`**: `doc_parent_map` added to `NON_BLOCKING_STAGES` (STAGE_DAG unchanged) — a pMAP
  ticket can never hold legacy QUERY_READY promotion.
- **`process_supervisor.py`**: an idle `doc_parent_map` fleet slot.

## Proof

- `pytest test_doc_parent_map_stage_worker.py test_doc_parent_map_trigger.py test_stage_dag_contract.py` →
  **16/16 green**: in-run failover (first healthy lane finishes; all-dark raises with the right dispatch flag;
  empty pool = pool_dark), contract determinism, transient-vs-deterministic incompleteness, process_event
  wiring (complete / transient-requeue / deterministic-fail / no-parents), flag defaults off, corpus scope,
  `is_blocking("doc_parent_map") is False`, STAGE_DAG frozen, mint writes ticket + event, **scheduler phase is
  a no-op with ZERO DB access when disabled** (proven by a raising fake conn).
- Control-plane suites green: `test_control_plane_v2`, `test_control_plane_liveness`, `test_scheduler_bulk`,
  `test_census_chain_verdict` (13). Import smoke of `control.{main,scheduler,tickets,process_supervisor}` +
  the worker → OK.
- `bundle_integrity` READY (semantic authorities untouched); `repo_guard` / `wiki_worm` / `agent_preflight` ok.

## Rejected claims

- **NOT live yet** — the running fleet still executes the pre-wiring code (byte-identical, flag would be off
  anyway). Going live needs a fleet restart (new control code + the doc_parent_map slot) AND the flag — both
  are Phase 15 (after the Phase 14 offline gate), and the flag will be corpus-scoped to the canary so cinema
  is never touched.
- **STAGE_DAG unchanged** — the pMAP stage is minted like parent_enrichment (outside the DAG), so the frozen
  DAG contract and its test are intact; no existing run gets a pMAP ticket while the flag is off.
- **No provider quota spent.**

## Open contract gaps

- Phase 12 canonical status must surface the pMAP stage (eligible/mapped/unresolved/batches + pool health).
- Phase 13: prove maps → parent-map projection → `vnext_readiness` reconcile end-to-end.
- Phase 14 offline gate, then Phase 15: fleet restart + `POLYMATH_DOC_PARENT_MAP_ENABLED=1` +
  `POLYMATH_DOC_PARENT_MAP_CORPUS=<canary>` + a 3–5 KB `/upload` canary timed to VNEXT_COMPLETE < 4 min.

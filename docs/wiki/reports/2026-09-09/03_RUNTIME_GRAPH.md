---
owner: "@king"
last_reviewed: 2026-09-09
status: ACTIVE
---

# 03 — Runtime Graph (FILE:SYMBOL)

Verified against HEAD `f1112ce`. graphify (`graphify-out/`, code-only refresh 2026-09-09) corroborates;
these are the hand-verified load-bearing paths.

## pMAP request/conservation chain
```
scripts/parent_map_backfill.py:main                     entry (ThreadPoolExecutor, concurrency)
  :_cohort                                              docs + tier='parent' chunks
  :_routed_infer→infer                                 ROUND-ROBIN over 6 map lanes; counts lane_selected vs dispatch; raises MapInferError
workers/workers/doc_parent_map_worker.py:run_document_mapping   durable orchestration (§28 no-tx-across-infer)
  :plan_batches (shared/.../document_profile/map_batches.py)    ≤ MAP_RELIABILITY_CAP=15 aliases/batch
  :claim_batch / active_parent_ids / persist_maps / record_batch_result   migration-0054 tables
  :MappingOutcome                                      conservation counters (11.185)
shared/polymath_shared/document_profile/parent_skeleton.py:build_parent_skeletons   deterministic S1
shared/polymath_shared/document_profile/map_prompt.py:build_map_prompt              (system,user) MAP DSL
shared/polymath_shared/document_profile/map_compiler.py:compile_maps                strict-identity compile
shared/polymath_shared/document_profile/parent_map_projection.py:vector_text/project_parent_maps   Qdrant
```

## LLM control plane (repaired 11.185)
```
shared/polymath_shared/llm_extraction/client.py:LLMExtractionClient.complete_one    admit→_chat→record
  :_chat                          returns (content, tin, tout, headers)  ← headers retained (Target B)
shared/polymath_shared/llm_extraction/limiter.py:AdaptiveLimiter.admit              → LimiterDecision(reason)
  :acquire                        bool wrapper (back-compat)
  :_sync_headers                  tokens→_tpm; requests→provider-RPD (NOT _rpm)  (Target A)
  :_provider_rpd_exhausted_locked / _observe_provider_rpd_locked                    conservative epoch
  :_FamilyGate                    per-family circuit (groq now per-account)
  :record_success/record_failure  AIMD + header sync
shared/polymath_shared/llm_extraction/pool.py:cloud_endpoints/stage_pin             lane roster
config/cloud_providers.json (stage_pins, providers) · config/extraction_models/limiter.yaml
```

## document_profile
```
workers/workers/doc_profile_worker.py:process_event    tiered _pool_complete (profile_groq→gemini→openrouter)
  vNext: FP.build_fingerprint (fingerprint.py:build_fingerprint) → PP.build_vnext_profile_prompt
  gated by POLYMATH_DOC_PROFILE_VNEXT ; MAX_OUTPUT_TOKENS=2400 ; 1 call/doc
```

## legacy parent_enrichment (dual-run→retire)
```
shared/polymath_shared/latent/runtime.py (parent_enrichments table) · latent/prompt.py (microbatch)
  pin: parent_enrichment (gemini5/5b/6/6b + openrouter1/2/3/5)
```

## readiness
```
shared/polymath_shared/semantic_readiness.py:vnext_readiness  → VNEXT_COMPLETE/INCOMPLETE/NOT_STARTED
  (unresolved==0 ∧ profiles==docs) ; scripts/vnext_readiness_report.py (read-only view)
```

## graph extraction
```
workers/workers/extract_worker.py → workers/workers/llm_provider.py (pool dispatch, REGISTRY.attach_store)
  client.extract()/extract_batched() ; structured=schema for the extract ring
```

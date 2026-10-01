# Polymath code wiki (CODE-WIKI-V1)

Start here. Every claim below this index is anchored to `path:LINE` and tagged [DERIVED] (visible in the code) or [INFERRED] (a
hypothesis: confirm it in the code before acting). `scripts/codewiki/verify.py` re-checks every page's VERIFY lines against the
live code (CI runs it); `scripts/codewiki/pages.py refresh` regenerates what changed. For WHY things are the way they are, read
`docs/wiki/` (plans, the register, work-logs); this wiki says HOW the code works NOW.

## dashboard
- units: 256 · pages ok 256 · partial 0 (some VERIFY lines or anchors dropped) · not generated 0
- provenance on unit pages: DERIVED 7533 · INFERRED 567
- flows: 8 · invariants: 1867 · vocabularies: 60 · routes: 94 · flags: 157 · tables: 79
- partial pages: none

## start here (by task)
| you have… | open |
|---|---|
| a symptom or an error | [failures/ledger.md](failures/ledger.md) (match shape tags) → the flow it happens on → the unit page |
| a suspicious value or limit | [invariants.md](invariants.md), then the literal in code next to it |
| "where is X handled?" | [facts/routes.md](facts/routes.md) (HTTP), [facts/mcp-tools.md](facts/mcp-tools.md) (MCP), [facts/imports.md](facts/imports.md) (who depends on whom) |
| a flag / env question | [facts/flags.md](facts/flags.md) (every read, its default, ⚠ where defaults disagree) |
| a data question | [facts/db.md](facts/db.md) (tables, writers, readers), [facts/qdrant.md](facts/qdrant.md) |
| a vocabulary / enum mismatch | [vocab/README.md](vocab/README.md) (authority vs every consumer), [specimens/prompts.md](specimens/prompts.md) |
| a hidden failure | [facts/fallbacks.md](facts/fallbacks.md) (every broad `except`, SWALLOWED ones first to suspect) |
| a deploy / "my fix did not ship" | [runtime/truth-tables.md](runtime/truth-tables.md) |
| a term you do not know | [glossary.md](glossary.md) |

## end-to-end flows
- [adapter-run](flows/adapter-run.md)
- [chat-turn](flows/chat-turn.md)
- [deep-research](flows/deep-research.md)
- [fleet-boot](flows/fleet-boot.md)
- [mcp-call](flows/mcp-call.md)
- [supplier-search](flows/supplier-search.md)
- [upload-to-searchable](flows/upload-to-searchable.md)
- [web-sign-in](flows/web-sign-in.md)

## how a weak agent should use this wiki
1. Never trust a page over the code: open the anchor, read the lines, then act.
2. Symptom → ledger shape tags → flow hop table → unit page contracts → the code at the anchor.
3. Before a refactor: read the unit's "refactor notes" and its importers ([facts/imports.md](facts/imports.md)); run `verify.py`.
4. After a change: run `.venv/bin/python scripts/codewiki/pages.py refresh`, then `scripts/codewiki/verify.py`.
5. Treat every [INFERRED] claim as a hypothesis.

## units (one page per source file ≥ 150 lines; smaller files grouped per directory)

**adapters/ecommerce/**  
[binding.py](units/adapters/ecommerce/binding.py.md)

**adapters/ecommerce/python/**  
[_small-modules-1](units/adapters/ecommerce/python/_small-modules-1.md) · [_small-modules-2](units/adapters/ecommerce/python/_small-modules-2.md) · [adapter_receipt.py](units/adapters/ecommerce/python/adapter_receipt.py.md) · [context.py](units/adapters/ecommerce/python/context.py.md) · [controller.py](units/adapters/ecommerce/python/controller.py.md) · [corpus_polymath.py](units/adapters/ecommerce/python/corpus_polymath.py.md) · [doctor.py](units/adapters/ecommerce/python/doctor.py.md) · [executors.py](units/adapters/ecommerce/python/executors.py.md) · [field_evidence.py](units/adapters/ecommerce/python/field_evidence.py.md) · [governed_run.py](units/adapters/ecommerce/python/governed_run.py.md) · [intelligence.py](units/adapters/ecommerce/python/intelligence.py.md) · [lived_world.py](units/adapters/ecommerce/python/lived_world.py.md) · [maintenance.py](units/adapters/ecommerce/python/maintenance.py.md) · [market_discovery.py](units/adapters/ecommerce/python/market_discovery.py.md) · [memory.py](units/adapters/ecommerce/python/memory.py.md) · [models.py](units/adapters/ecommerce/python/models.py.md) · [product_anchored.py](units/adapters/ecommerce/python/product_anchored.py.md) · [product_reality.py](units/adapters/ecommerce/python/product_reality.py.md) · [provenance.py](units/adapters/ecommerce/python/provenance.py.md) · [qualify.py](units/adapters/ecommerce/python/qualify.py.md) · [registry.py](units/adapters/ecommerce/python/registry.py.md) · [report.py](units/adapters/ecommerce/python/report.py.md) · [run_triage.py](units/adapters/ecommerce/python/run_triage.py.md) · [settings.py](units/adapters/ecommerce/python/settings.py.md) · [transitions.py](units/adapters/ecommerce/python/transitions.py.md)

**control/control/**  
[_small-modules](units/control/control/_small-modules.md) · [census.py](units/control/control/census.py.md) · [fleet_autopilot.py](units/control/control/fleet_autopilot.py.md) · [generation_swap.py](units/control/control/generation_swap.py.md) · [main.py](units/control/control/main.py.md) · [manifest_ingest.py](units/control/control/manifest_ingest.py.md) · [medic.py](units/control/control/medic.py.md) · [process_supervisor.py](units/control/control/process_supervisor.py.md) · [reconciliation.py](units/control/control/reconciliation.py.md) · [scheduler.py](units/control/control/scheduler.py.md) · [stall_tracer.py](units/control/control/stall_tracer.py.md) · [tickets.py](units/control/control/tickets.py.md)

**frontend-v2/src/**  
[App.tsx](units/frontend-v2/src/App.tsx.md) · [_small-modules](units/frontend-v2/src/_small-modules.md)

**frontend-v2/src/components/**  
[EvidenceInspector.tsx](units/frontend-v2/src/components/EvidenceInspector.tsx.md) · [ModelPicker.tsx](units/frontend-v2/src/components/ModelPicker.tsx.md) · [_small-modules](units/frontend-v2/src/components/_small-modules.md)

**frontend-v2/src/components/deep/**  
[DeepReport.tsx](units/frontend-v2/src/components/deep/DeepReport.tsx.md) · [LiveResearch.tsx](units/frontend-v2/src/components/deep/LiveResearch.tsx.md) · [_small-modules](units/frontend-v2/src/components/deep/_small-modules.md)

**frontend-v2/src/lib/**  
[_small-modules](units/frontend-v2/src/lib/_small-modules.md) · [api.ts](units/frontend-v2/src/lib/api.ts.md) · [chat.ts](units/frontend-v2/src/lib/chat.ts.md) · [contracts.ts](units/frontend-v2/src/lib/contracts.ts.md) · [deep.ts](units/frontend-v2/src/lib/deep.ts.md)

**frontend-v2/src/screens/**  
[Chat.tsx](units/frontend-v2/src/screens/Chat.tsx.md) · [ControlPlane.tsx](units/frontend-v2/src/screens/ControlPlane.tsx.md) · [Files.tsx](units/frontend-v2/src/screens/Files.tsx.md) · [Models.tsx](units/frontend-v2/src/screens/Models.tsx.md) · [Research.tsx](units/frontend-v2/src/screens/Research.tsx.md) · [Settings.tsx](units/frontend-v2/src/screens/Settings.tsx.md) · [_small-modules](units/frontend-v2/src/screens/_small-modules.md)

**frontend-v2/src/ui/**  
[_small-modules](units/frontend-v2/src/ui/_small-modules.md)

**mcp_server/**  
[polymath_mcp.py](units/mcp_server/polymath_mcp.py.md)

**orchestrator/orchestrator/**  
[_small-modules](units/orchestrator/orchestrator/_small-modules.md) · [main.py](units/orchestrator/orchestrator/main.py.md) · [mcp_principals.py](units/orchestrator/orchestrator/mcp_principals.py.md) · [mcp_server.py](units/orchestrator/orchestrator/mcp_server.py.md) · [web_accounts.py](units/orchestrator/orchestrator/web_accounts.py.md)

**orchestrator/orchestrator/api/**  
[_small-modules](units/orchestrator/orchestrator/api/_small-modules.md) · [acquisition.py](units/orchestrator/orchestrator/api/acquisition.py.md) · [adapter.py](units/orchestrator/orchestrator/api/adapter.py.md) · [ask.py](units/orchestrator/orchestrator/api/ask.py.md) · [chat.py](units/orchestrator/orchestrator/api/chat.py.md) · [chat_retrieval.py](units/orchestrator/orchestrator/api/chat_retrieval.py.md) · [compare_review.py](units/orchestrator/orchestrator/api/compare_review.py.md) · [corpus_plan.py](units/orchestrator/orchestrator/api/corpus_plan.py.md) · [deep_research.py](units/orchestrator/orchestrator/api/deep_research.py.md) · [evidence.py](units/orchestrator/orchestrator/api/evidence.py.md) · [evidence_rows.py](units/orchestrator/orchestrator/api/evidence_rows.py.md) · [fast.py](units/orchestrator/orchestrator/api/fast.py.md) · [graph.py](units/orchestrator/orchestrator/api/graph.py.md) · [graph_browse.py](units/orchestrator/orchestrator/api/graph_browse.py.md) · [health.py](units/orchestrator/orchestrator/api/health.py.md) · [hybrid.py](units/orchestrator/orchestrator/api/hybrid.py.md) · [intake.py](units/orchestrator/orchestrator/api/intake.py.md) · [polymath_style.py](units/orchestrator/orchestrator/api/polymath_style.py.md) · [reasoning.py](units/orchestrator/orchestrator/api/reasoning.py.md) · [retrieve.py](units/orchestrator/orchestrator/api/retrieve.py.md) · [ui.py](units/orchestrator/orchestrator/api/ui.py.md) · [web_auth.py](units/orchestrator/orchestrator/api/web_auth.py.md) · [web_settings.py](units/orchestrator/orchestrator/api/web_settings.py.md)

**shared/polymath_shared/**  
[_small-modules-1](units/shared/polymath_shared/_small-modules-1.md) · [_small-modules-2](units/shared/polymath_shared/_small-modules-2.md) · [_small-modules-3](units/shared/polymath_shared/_small-modules-3.md) · [admission_interpreter.py](units/shared/polymath_shared/admission_interpreter.py.md) · [answer_synthesis.py](units/shared/polymath_shared/answer_synthesis.py.md) · [blob_spool.py](units/shared/polymath_shared/blob_spool.py.md) · [bridge_compiler.py](units/shared/polymath_shared/bridge_compiler.py.md) · [bridge_integration.py](units/shared/polymath_shared/bridge_integration.py.md) · [bundle_integrity.py](units/shared/polymath_shared/bundle_integrity.py.md) · [candidate_engine.py](units/shared/polymath_shared/candidate_engine.py.md) · [canonicalizer.py](units/shared/polymath_shared/canonicalizer.py.md) · [chat_plan.py](units/shared/polymath_shared/chat_plan.py.md) · [clients.py](units/shared/polymath_shared/clients.py.md) · [compiler_context.py](units/shared/polymath_shared/compiler_context.py.md) · [concept_evidence.py](units/shared/polymath_shared/concept_evidence.py.md) · [concept_inventory.py](units/shared/polymath_shared/concept_inventory.py.md) · [contraction_resolution.py](units/shared/polymath_shared/contraction_resolution.py.md) · [contracts.py](units/shared/polymath_shared/contracts.py.md) · [control_plane_status.py](units/shared/polymath_shared/control_plane_status.py.md) · [corpus_activation.py](units/shared/polymath_shared/corpus_activation.py.md) · [corpus_explore_firing.py](units/shared/polymath_shared/corpus_explore_firing.py.md) · [corpus_mapping.py](units/shared/polymath_shared/corpus_mapping.py.md) · [dedup.py](units/shared/polymath_shared/dedup.py.md) · [discourse_reference.py](units/shared/polymath_shared/discourse_reference.py.md) · [divergent.py](units/shared/polymath_shared/divergent.py.md) · [document_region.py](units/shared/polymath_shared/document_region.py.md) · [document_status.py](units/shared/polymath_shared/document_status.py.md) · [embedding_contracts.py](units/shared/polymath_shared/embedding_contracts.py.md) · [endpoint_binding.py](units/shared/polymath_shared/endpoint_binding.py.md) · [entity_admission.py](units/shared/polymath_shared/entity_admission.py.md) · [entity_harbor.py](units/shared/polymath_shared/entity_harbor.py.md) · [entity_knowledge_admission.py](units/shared/polymath_shared/entity_knowledge_admission.py.md) · [event_adapter.py](units/shared/polymath_shared/event_adapter.py.md) · [evidence_assembly.py](units/shared/polymath_shared/evidence_assembly.py.md) · [evidence_packet.py](units/shared/polymath_shared/evidence_packet.py.md) · [evidence_resolution.py](units/shared/polymath_shared/evidence_resolution.py.md) · [evidence_utility.py](units/shared/polymath_shared/evidence_utility.py.md) · [execution.py](units/shared/polymath_shared/execution.py.md) · [execution_bundle.py](units/shared/polymath_shared/execution_bundle.py.md) · [extraction_context.py](units/shared/polymath_shared/extraction_context.py.md) · [facets.py](units/shared/polymath_shared/facets.py.md) · [gap_check.py](units/shared/polymath_shared/gap_check.py.md) · [hybrid.py](units/shared/polymath_shared/hybrid.py.md) · [identity_allocation.py](units/shared/polymath_shared/identity_allocation.py.md) · [identity_evidence.py](units/shared/polymath_shared/identity_evidence.py.md) · [lane_liveness.py](units/shared/polymath_shared/lane_liveness.py.md) · [latent_eligibility.py](units/shared/polymath_shared/latent_eligibility.py.md) · [manifest.py](units/shared/polymath_shared/manifest.py.md) · [materializer.py](units/shared/polymath_shared/materializer.py.md) · [metal.py](units/shared/polymath_shared/metal.py.md) · [observability.py](units/shared/polymath_shared/observability.py.md) · [parent_summary.py](units/shared/polymath_shared/parent_summary.py.md) · [pass1.py](units/shared/polymath_shared/pass1.py.md) · [pipeline_health.py](units/shared/polymath_shared/pipeline_health.py.md) · [query_constraints.py](units/shared/polymath_shared/query_constraints.py.md) · [query_intent.py](units/shared/polymath_shared/query_intent.py.md) · [query_policy.py](units/shared/polymath_shared/query_policy.py.md) · [query_receipts.py](units/shared/polymath_shared/query_receipts.py.md) · [ranked_fusion.py](units/shared/polymath_shared/ranked_fusion.py.md) · [ranked_lane.py](units/shared/polymath_shared/ranked_lane.py.md) · [raw_evidence.py](units/shared/polymath_shared/raw_evidence.py.md) · [reach.py](units/shared/polymath_shared/reach.py.md) · [reasoning_policy.py](units/shared/polymath_shared/reasoning_policy.py.md) · [receipts.py](units/shared/polymath_shared/receipts.py.md) · [region_role.py](units/shared/polymath_shared/region_role.py.md) · [rerank.py](units/shared/polymath_shared/rerank.py.md) · [resolution_lift_gather.py](units/shared/polymath_shared/resolution_lift_gather.py.md) · [retrieval.py](units/shared/polymath_shared/retrieval.py.md) · [retrieval_lineage.py](units/shared/polymath_shared/retrieval_lineage.py.md) · [runtime_budget.py](units/shared/polymath_shared/runtime_budget.py.md) · [scientific_concept.py](units/shared/polymath_shared/scientific_concept.py.md) · [semantic_readiness.py](units/shared/polymath_shared/semantic_readiness.py.md) · [settings.py](units/shared/polymath_shared/settings.py.md) · [source_region.py](units/shared/polymath_shared/source_region.py.md) · [span_repair.py](units/shared/polymath_shared/span_repair.py.md) · [summary_compiler.py](units/shared/polymath_shared/summary_compiler.py.md) · [summary_runtime.py](units/shared/polymath_shared/summary_runtime.py.md) · [synthesis_model.py](units/shared/polymath_shared/synthesis_model.py.md) · [verb_inventory.py](units/shared/polymath_shared/verb_inventory.py.md) · [vocabulary_mapping.py](units/shared/polymath_shared/vocabulary_mapping.py.md) · [wildcard_mapped.py](units/shared/polymath_shared/wildcard_mapped.py.md) · [worker_runtime.py](units/shared/polymath_shared/worker_runtime.py.md)

**shared/polymath_shared/acquisition/**  
[_small-modules](units/shared/polymath_shared/acquisition/_small-modules.md) · [cj_api.py](units/shared/polymath_shared/acquisition/cj_api.py.md) · [opencli.py](units/shared/polymath_shared/acquisition/opencli.py.md) · [searxng.py](units/shared/polymath_shared/acquisition/searxng.py.md) · [service.py](units/shared/polymath_shared/acquisition/service.py.md) · [supplier.py](units/shared/polymath_shared/acquisition/supplier.py.md)

**shared/polymath_shared/adapter/**  
[_small-modules](units/shared/polymath_shared/adapter/_small-modules.md) · [dossier.py](units/shared/polymath_shared/adapter/dossier.py.md) · [evidence_boundary.py](units/shared/polymath_shared/adapter/evidence_boundary.py.md) · [harness_guide.py](units/shared/polymath_shared/adapter/harness_guide.py.md) · [hypotheses.py](units/shared/polymath_shared/adapter/hypotheses.py.md) · [manifest.py](units/shared/polymath_shared/adapter/manifest.py.md) · [research_gaps.py](units/shared/polymath_shared/adapter/research_gaps.py.md) · [run_view.py](units/shared/polymath_shared/adapter/run_view.py.md) · [semantic_view.py](units/shared/polymath_shared/adapter/semantic_view.py.md) · [service.py](units/shared/polymath_shared/adapter/service.py.md) · [store.py](units/shared/polymath_shared/adapter/store.py.md) · [trail_client.py](units/shared/polymath_shared/adapter/trail_client.py.md) · [transitions.py](units/shared/polymath_shared/adapter/transitions.py.md)

**shared/polymath_shared/code/**  
[_small-modules](units/shared/polymath_shared/code/_small-modules.md) · [scope.py](units/shared/polymath_shared/code/scope.py.md)

**shared/polymath_shared/conformance/**  
[_small-modules](units/shared/polymath_shared/conformance/_small-modules.md) · [assess.py](units/shared/polymath_shared/conformance/assess.py.md) · [attempts.py](units/shared/polymath_shared/conformance/attempts.py.md) · [discovery.py](units/shared/polymath_shared/conformance/discovery.py.md) · [evidence.py](units/shared/polymath_shared/conformance/evidence.py.md)

**shared/polymath_shared/deep_research/**  
[_small-modules](units/shared/polymath_shared/deep_research/_small-modules.md) · [engine.py](units/shared/polymath_shared/deep_research/engine.py.md) · [evidence.py](units/shared/polymath_shared/deep_research/evidence.py.md) · [prompts.py](units/shared/polymath_shared/deep_research/prompts.py.md)

**shared/polymath_shared/document_profile/**  
[_small-modules](units/shared/polymath_shared/document_profile/_small-modules.md) · [compiler.py](units/shared/polymath_shared/document_profile/compiler.py.md) · [context.py](units/shared/polymath_shared/document_profile/context.py.md) · [fingerprint.py](units/shared/polymath_shared/document_profile/fingerprint.py.md) · [giant_profile.py](units/shared/polymath_shared/document_profile/giant_profile.py.md) · [groq_routing.py](units/shared/polymath_shared/document_profile/groq_routing.py.md) · [grounding.py](units/shared/polymath_shared/document_profile/grounding.py.md) · [map_batches.py](units/shared/polymath_shared/document_profile/map_batches.py.md) · [map_compiler.py](units/shared/polymath_shared/document_profile/map_compiler.py.md) · [parent_map_projection.py](units/shared/polymath_shared/document_profile/parent_map_projection.py.md) · [parent_skeleton.py](units/shared/polymath_shared/document_profile/parent_skeleton.py.md) · [profile_atom.py](units/shared/polymath_shared/document_profile/profile_atom.py.md) · [profile_atom_projection.py](units/shared/polymath_shared/document_profile/profile_atom_projection.py.md) · [profile_coverage.py](units/shared/polymath_shared/document_profile/profile_coverage.py.md) · [projection.py](units/shared/polymath_shared/document_profile/projection.py.md) · [shadow_route.py](units/shared/polymath_shared/document_profile/shadow_route.py.md)

**shared/polymath_shared/knowledge_objects/**  
[_small-modules](units/shared/polymath_shared/knowledge_objects/_small-modules.md) · [concept.py](units/shared/polymath_shared/knowledge_objects/concept.py.md) · [procedure.py](units/shared/polymath_shared/knowledge_objects/procedure.py.md)

**shared/polymath_shared/knowledge_router/**  
[_small-modules](units/shared/polymath_shared/knowledge_router/_small-modules.md)

**shared/polymath_shared/latent/**  
[_small-modules](units/shared/polymath_shared/latent/_small-modules.md) · [compiler.py](units/shared/polymath_shared/latent/compiler.py.md) · [gate.py](units/shared/polymath_shared/latent/gate.py.md)

**shared/polymath_shared/llm_extraction/**  
[_small-modules](units/shared/polymath_shared/llm_extraction/_small-modules.md) · [accounts.py](units/shared/polymath_shared/llm_extraction/accounts.py.md) · [client.py](units/shared/polymath_shared/llm_extraction/client.py.md) · [contract.py](units/shared/polymath_shared/llm_extraction/contract.py.md) · [gate.py](units/shared/polymath_shared/llm_extraction/gate.py.md) · [lane_registry.py](units/shared/polymath_shared/llm_extraction/lane_registry.py.md) · [limiter.py](units/shared/polymath_shared/llm_extraction/limiter.py.md) · [pool.py](units/shared/polymath_shared/llm_extraction/pool.py.md)

**sidecars/embedder/**  
[server.py](units/sidecars/embedder/server.py.md)

**sidecars/local_extractor/**  
[batched_server.py](units/sidecars/local_extractor/batched_server.py.md) · [json_mask.py](units/sidecars/local_extractor/json_mask.py.md)

**sidecars/reranker/**  
[server.py](units/sidecars/reranker/server.py.md)

**workers/workers/**  
[_small-modules](units/workers/workers/_small-modules.md) · [adapter_step_worker.py](units/workers/workers/adapter_step_worker.py.md) · [canonicalize_worker.py](units/workers/workers/canonicalize_worker.py.md) · [chunk_kind.py](units/workers/workers/chunk_kind.py.md) · [chunker.py](units/workers/workers/chunker.py.md) · [doc_parent_map_stage_worker.py](units/workers/workers/doc_parent_map_stage_worker.py.md) · [doc_parent_map_worker.py](units/workers/workers/doc_parent_map_worker.py.md) · [doc_profile_worker.py](units/workers/workers/doc_profile_worker.py.md) · [extract_worker.py](units/workers/workers/extract_worker.py.md) · [intake_worker.py](units/workers/workers/intake_worker.py.md) · [knowledge_artifacts.py](units/workers/workers/knowledge_artifacts.py.md) · [llm_direct.py](units/workers/workers/llm_direct.py.md) · [llm_provider.py](units/workers/workers/llm_provider.py.md) · [profile_worker.py](units/workers/workers/profile_worker.py.md) · [project_canonical_worker.py](units/workers/workers/project_canonical_worker.py.md) · [project_neo4j_worker.py](units/workers/workers/project_neo4j_worker.py.md) · [project_qdrant_worker.py](units/workers/workers/project_qdrant_worker.py.md) · [semantic_chunker.py](units/workers/workers/semantic_chunker.py.md) · [summary_worker_impl.py](units/workers/workers/summary_worker_impl.py.md) · [tier_chunker.py](units/workers/workers/tier_chunker.py.md) · [verify_worker.py](units/workers/workers/verify_worker.py.md)

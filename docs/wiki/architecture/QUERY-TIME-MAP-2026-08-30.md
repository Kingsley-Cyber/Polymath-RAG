---
change_id: QUERY-TIME-MAP-2026-08-30
owner: governance
date: 2026-08-30
status: reference
architecture_impact: none (code map; input to LATENT-TRANSFER-LAYER-V1-PLAN)
last_reviewed: 2026-08-30
---

# Query-time / retrieval architecture map (main@8f418d7, 2026-08-30)

Every entry is `path:line — symbol — role`, read from code (not prose docs).

## 1. Orchestrator HTTP API
- `orchestrator/orchestrator/main.py:46` `app = FastAPI(...)`; `:26 lifespan` (validate_startup + sidecar registry); `:72 _query_activity_signal` writes `runtime_signals('last_query')` for `/chat /chat/stream /retrieve /ask /fast /hybrid /graph`; `:92-98` router include order health, intake, retrieve, evidence, chat, ask, ui.
- `orchestrator/orchestrator/api/retrieve.py:116 POST /retrieve` — mode dispatch (`:128-142`); `:35 RetrieveRequest{query, corpus_id, corpus_ids, workspace, all_authorized, limit=10, mode}`; `:45 resolve_http_scope` (422/404/422); `:103 single_corpus_or_422`.
- `orchestrator/orchestrator/api/evidence.py:53 POST /evidence` (EvidenceBundle v2, no prose); `:43 EvidenceRequest`.
- `orchestrator/orchestrator/api/chat.py:55 POST /chat` → `grounded_answer`; `:46 ChatRequest`.
- `orchestrator/orchestrator/api/ask.py:219 POST /ask` (stored objects only); `:40 AskRequest`.
- `orchestrator/orchestrator/api/ui.py:1049 POST /chat/stream` (SSE `phase|token|reasoning|answer|error|done`) — the ONLY route the UI uses; `:768 StreamChatRequest` adds `synthesizer, reasoning, reasoning_blend, history, carry_context`; mode `VECTOR|HYBRID|GRAPH|ASK` (VECTOR→FAST).
- Internal engines (no `@router`): `api/fast.py:285 fast_retrieve(query, corpus_id, plan)`, `api/hybrid.py:73 hybrid_fast_retrieve`, `api/graph.py:71 graph_retrieve`. `/fast /hybrid /graph` exist only in the middleware path list (dead names).
- Other routes: health `api/health.py:14 /health, :19 /ready, :29 /semantic_readiness, :55 /sidecars, :72 /health/semantic, :135 /health/pipeline`; intake `api/intake.py:33 POST /intake, :50 GET /runs/{run_id}`; ui `api/ui.py:77 GET /corpora, :116 PATCH, :144 GET /documents, :198 POST /upload, :315 DELETE /documents/{id}, :439 POST /generated, :462 /reasoning_modes, :484 /ui_pulse, :501 /synthesizers, :533/542/568 /llm/providers, :580 POST /llm/test, :597 DELETE /corpora/{id}`.
- Stores: Postgres on every route (`corpora, query_workspaces, documents, chunks, runs, facts, evidence, entities, procedure_artifacts, concept_artifacts, concept_families, concept_aliases, corpus_summaries, runtime_signals`); Qdrant via `retrieve.py:275 _qdrant_search` (LEGACY) and `fast.py:53 FastSearcher._search` (FAST/HYBRID/GRAPH); Neo4j only via `retrieve.py:432 _neo4j_expand`; Redis unused.

## 2. Retrieval internals
- Scope: `shared/polymath_shared/query_scope.py:43 resolve_query_scope` → `:35 QueryScope(mode, corpus_ids)`; modes `CORPUS|CORPORA|WORKSPACE|ALL_AUTHORIZED`.
- Modes: `shared/polymath_shared/retrieval_modes.py:19-26` (`FAST|HYBRID|GRAPH|LEGACY`, `DEFAULT_MODE=LEGACY`), `:35 mode_plan`, `:42 hybrid_mode_plan`, `:32 HYBRID_PROMOTED_PLAN` (lexical on, MMR off λ=1.0), `:56 validate_mode`.
- Shaping: `shared/polymath_shared/query_shape.py:120 plan_for_query` (ONLY per-query plan mutation); `:60 is_enumeration_query`, `:76 depth_plan`, `:114 is_document_metadata_query`.
- Router (used by `/ask` only): `shared/polymath_shared/query_router.py:56 classify_query` → `FACT|PROCEDURE|CONCEPT|POLYMATH_QUERY`.
- Pass-1: `shared/polymath_shared/pass1.py:43 Pass1RetrievalPlan` (`plan_version="pass1-retrieval-v1"`, rrf_k 60, max_documents 5, sections/doc 2, children/section 3, final 10, rescue_reserved_slots 2, neighbor_expansion 0, demote_noisy_regions); `:350 pass1_retrieve(query, *, plan, embed_query, routing_search, rerank_children, neighbor_lookup, region_lookup)` — every store touch injected; kinds `:29-31`; arrival labels `:33-39`; `:176 _rrf_score`, `:180/198 aggregate_documents*`, `:246 resolve_sections`, `:285 _truncate_reserving_rescue`, `:309 _expand_neighbors`; `:117 LaneHit`, `:131 DocumentCandidate`, `:161 Pass1Result`.
- Hybrid: `shared/polymath_shared/hybrid.py:48 HybridRetrievalPlan`, `:152 hybrid_retrieve(... lexical_search, summary_vectors ...)` (pass1 with rerank off, then lexical fusion); `:102 mmr_select` (rejected by R1D); `orchestrator/api/hybrid.py:43 _lexical_search` = in-memory scan of child chunks via `retrieval.py:58 lexical_score`; `retrieval.py:90 rrf`.
- Legacy: `shared/polymath_shared/retrieval.py:126 run_lanes` (profile, parent summary, child dense, child lexical).
- Dense: `orchestrator/api/fast.py:159 _embed_query` (`EmbedderClient.embed([q],"query")`), `:147 _await_embedder` (budget `POLYMATH_EMBED_WAKE_BUDGET_S`=150); contracts `shared/polymath_shared/embedding_contracts.py:110 NEURAL_EMBED_CONTRACT`, `:141 active_contract`; collection `projection_contracts.py:74 qdrant_collection_name`.
- Rerank: `shared/polymath_shared/rerank.py:167 apply_rerank`, `:111 rerank_fused` (reorder only), `:161 rerank_enabled`; `fast.py:274 _rerank_children` degrades to fusion order (`:188 _RERANK_DEGRADED`, `:197 degradations`).
- Enrichment callbacks: `fast.py:208 _neighbor_lookup`, `:258 _region_lookup`, `:246 _liveness` → `lane_liveness.py:176 evaluate`; readiness `fast.py:99 _ensure_fast_ready` (run `query_ready` + non-empty collection).
- Summaries: `shared/polymath_shared/retrieval_summaries.py:100/140/210` (`retrieval-summary-v2`); read at query time via Qdrant payloads; `corpus_map_planning.py:45 plan_with_corpus_map` (`/ask` only).
- Graph: `retrieval.py:297 graph_expansion` (cap 20), `retrieve.py:432 _neo4j_expand` (bidirectional, predicate allowlist `:26`, auth filter, LIMIT 20), `:360 _corpus_seed_ids` (8 seeds), `:402 _authorized_fact_ids`, `:80 graph_expand_or_502`.
- Bundle/answer: `shared/polymath_shared/evidence_assembly.py:92 assemble_evidence_bundle` (contract `answer/evidence_bundle/v2`; typed `AssemblyError` → 502); resolvers `evidence.py:238/258/278/289/300`; `answer_synthesis.py:441 grounded_answer` (`deterministic-template-v3`), `:160/:253/:338`; LLM synthesizers `ui.py:950 _ollama_generate`, `:911 _litellm_generate`, `reasoning.py:153 apply_reasoning`.

## 3. MCP (`mcp_server/polymath_mcp.py`)
`:38 BASE=POLYMATH_API (7200)`; tools `:73 list_corpora → GET /corpora`, `:80 polymath_query → /ask|/chat`, `:103 polymath_retrieve → /retrieve`, `:117 list_documents`, `:124/:144 upload`, `:162 readiness`, `:170/:185 deletes`; `:195 _auth_wrapped` (`POLYMATH_MCP_API_KEY`); `:222 main --http`.

## 4. Frontend (`frontend/src`)
`api.ts:79 streamChat → POST /chat/stream` (manual SSE); `:9 /corpora, :16 PATCH, :26 /synthesizers, :31 /reasoning_modes, :36 /documents, :41 /semantic_readiness, :49 POST /upload`; `App.tsx:63 /ui_pulse`; `components/ModelsView.tsx /llm/*`; `MessageBubble.tsx:209 POST /generated`. The UI never calls `/retrieve`, `/evidence`, `/chat`, `/ask` directly.

## 5. Persistence (retrieval-relevant)
- `chunks` `0002_workflow.sql:38` (+`0013` chunk_contract_version/provider/heading_path/token_count, `0016:50 layout_map`, `0037` region_role/reason/contract).
- `retrieval_summaries` `0008:13` (routing-card source of truth); `parent_summaries/document_summaries/corpus_summaries/summary_jobs/summary_artifacts/concept_vocabulary` `0024:42/56/73/8/29/89` (+`0039` superseded_at, logical job identity); `concept_families/aliases/support` `0025`; `procedure_artifacts/concept_artifacts` `0033`; `mentions` `0009` (+`0011`); `canonical_entities/memberships` `0005`; `query_workspaces` `0035`; `corpora.embedding_contract_id` `0034:15`.
- Qdrant projection: `workers/workers/project_qdrant_worker.py:295-303` kinds (`routing_document_summary|routing_section_summary|routing_child|routing_procedure|routing_concept`), `:308 _routing_rows`, `:495 _write_routing_slice` (payload `{summary_id, chunk_id, representation_kind, corpus_id, doc_id, parent_id, source_name, embedding_contract, text}` = the read model), `:419 _already_current` (receipt guard), `:522 process_event`, `:122 _embed_texts` (batch 32).
- Neo4j projection: `project_neo4j_worker.py:63-86` (Document/Chunk/Entity/REL/Fact/Evidence), `project_canonical_worker.py:64-82`.
- Summary runtime: `shared/polymath_shared/summary_runtime.py:36 run_parent_summary_ticket` (claim → EXISTING on input_hash → build → artifact → supersede → job COMPLETE); `workers/workers/summary_worker_impl.py:44 _job_done, :60 _ensure_job, :71 _stage_ticket, :80 _parents_of_docs, :97 _facts_for_chunks, :116 _mentions_for_chunks, :127 _do_parents, :279 _DISPATCH`; `summary_worker.py:21` event kinds; stage DAG `control/control/tickets.py:43-46` + `:52 NON_BLOCKING_STAGES`; `fleet_autopilot.py:47`; `reconciliation.py:72`.

## 6. Settings
`shared/polymath_shared/settings.py:36 PostgresSettings, :47 SidecarSettings (embedder :8742, reranker :8743, g3_reranker), :146 WorkerSettings, :211 ControlSettings, :218 StoreSettings (qdrant_url, neo4j_uri, embedding_contract_id), :236 RescueSettings, :266 Settings`. Env-only knobs: `POLYMATH_EMBED_WAKE_BUDGET_S`, `POLYMATH_RERANK_WAKE_BUDGET_S`, `POLYMATH_OLLAMA_URL`, `POLYMATH_DEFAULT_SYNTHESIZER`, `POLYMATH_EVIDENCE_TEXT_CHARS`, `POLYMATH_REASONING_MODE`, `POLYMATH_GENERATED_DIR`.

## 7. Tests
Engines: `tests/determinism/test_pass1.py, test_hybrid.py, test_retrieval_invariants.py, test_depth_policy.py, test_document_region.py, test_rerank_wrapper.py, test_retrieval_summaries.py, test_production_reality.py, test_batched_pass1.py`. Scope/routing: `test_query_scope.py`, `tests/integration/test_query_scope_isolation.py, test_cross_domain_routing.py, test_corpus_scoped_graph.py`, `test_knowledge_router.py`. Bundle/answer: `test_evidence_assembly.py, test_answer_synthesis.py, test_answer_admission.py, test_evidence_truncation.py`, `tests/contracts/test_evidence_bundle_contract.py, test_chat_response_contract.py`. E2E: `tests/integration/test_r1c_fast_endpoint.py, test_chat_e2e.py, test_evidence_bundle_e2e.py, test_g5_rerank_answer_path.py, test_failure_transparency.py`. Summaries: `test_parent_summary*.py, test_summary_idempotency.py, test_summary_layer_s1.py, test_summary_projection.py, test_summary_workers.py`.

## 8. Extension seams (ranked)
1. `retrieval_modes.py:19/:35/:42/:56` — mode → plan table (keep `validate_mode` raising on unknown; `DEFAULT_MODE=LEGACY` frozen).
2. `pass1.py:350` / `hybrid.py:152` injected callables — add a lane without touching HTTP; `routing_search(collection, vector, filters) -> [{payload, score}]` sorted desc; payload must carry `{representation_kind, corpus_id, doc_id, parent_id, chunk_id|summary_id, text, source_name}`; `Pass1Result.trace` must keep `lane_sizes/pre_g3_order/post_g3_order`.
3. `query_shape.py:120 plan_for_query` — per-query adaptivity hook; deterministic; caps/flags only.
4. `retrieve.py:128-142` — HTTP wiring; scope first; typed `{error_code, message}` at 422/502.
5. `evidence_assembly.py:92` — every layer terminates here; ids must resolve or 502.
6. `project_qdrant_worker.py:308/:495` — new `representation_kind`s are born here; invisible to readers until a lane requests them.
7. `rerank.py:167 apply_rerank` — same set in/out; degrade, never raise at route level.
8. `ui.py:1049 chat_stream.generate()` — the UI path; SSE frames; `answer.retrieval{mode, evidence_count, graph_fact_count, chunks[], degraded}`; honour `carry_context/history`.

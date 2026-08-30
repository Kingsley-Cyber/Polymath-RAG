---
change_id: SESSION-DIFF-REPORT
owner: governance
date: 2026-08-29
status: complete
architecture_impact: LOCAL-LLM-EXTRACTION-V1 implementation (code analyzer input)
last_reviewed: 2026-08-29
---

# SESSION DIFF REPORT — LOCAL-LLM-EXTRACTION-V1 implementation

> Scope: every code change this session, `6a8bf11..HEAD` (18 commits,
> +4,577/−30 lines). For code analyzers:
>
> * Full unified diff: `/tmp/polymath_session_6a8bf11-HEAD.diff` (5,182 lines)
> * Machine-readable manifest: `/tmp/session_code_report.json`
> * Graphify graph (code-only, 12,947 nodes / 21,129 edges):
>   `graphify-out/graph.json` — zero isolated nodes in the new modules;
>   external callers: `tests/determinism/test_llm_limiter.py`,
>   `tests/integration/test_cross_domain_routing.py`,
>   `orchestrator/orchestrator/api/chat.py`,
>   `orchestrator/orchestrator/api/evidence.py`.

## New modules (11) + modified (4)

| Location | Purpose | LOC | Defs/entry points |
|---|---|---|---|
| `shared/polymath_shared/llm_extraction/contract.py` | polymath-extraction-v1 packet: EntityProposal, RelationProposal, RoutingDigest, ExtractionItem, ExtractionPacket, SanitizeResult | 117 | Pydantic models (annotation-referenced) |
| `shared/polymath_shared/llm_extraction/policy.py` | 300 KB cloud boundary: `select_lane`, `require_cloud_eligible`, `CloudBoundaryViolation`, `CLOUD_MIN_BYTES` | 63 | `select_lane` ← worker; `require_cloud_eligible` ← client |
| `shared/polymath_shared/llm_extraction/gate.py` | THE output gate: `strip_thinking`, `_repair_truncated`, `_salvage_objects`, `_loads_lenient`, `_enforce_budgets` (shape tolerance + caps), `sanitize`, `validate_and_normalize`, `map_core_type`, `ChunkView`, `NormalizedExtraction` | 509 | `sanitize`+`validate_and_normalize` ← client/worker |
| `shared/polymath_shared/llm_extraction/client.py` | transport: `LLMExtractionClient.extract` (local/cloud, limiter-wired), `extract_batched` (/infer_batch), `output_budget_for`, ontology prompt, thinking-off knobs | 353 | client ← llm_provider |
| `shared/polymath_shared/llm_extraction/ontology.py` | relation ontology: `RELATION_ONTOLOGY` (17+1), `PREDICATE_ALIASES`, `normalize_predicate`, `prompt_block` | 107 | prompt_block ← client; normalize ← gate |
| `shared/polymath_shared/llm_extraction/limiter.py` | `AdaptiveLimiter` (_DynamicSemaphore, _TokenBucket, _Breaker), `LimiterRegistry`, `ProviderLimit` | 258 | REGISTRY ← client |
| `workers/workers/llm_provider.py` | `build_neighborhoods` (balanced packing, ChunkKind/stub skip), `select_lane`, `make_client`, `run_proposals`, `to_precomputed_entities`, `to_evidence_spans`, `ledger_items`, `call_receipts` | 261 | all ← extract_worker LLM branch |
| `workers/workers/chunk_kind.py` | v3.3 ChunkKind taxonomy port (12 kinds, `classify_heading`, `is_noisy`, `NOISY_KINDS`, + 4 unwired v3.3 API fns) | 537 | `is_noisy` ← llm_provider |
| `sidecars/local_extractor/batched_server.py` | mlx_lm `batch_generate` server: `/infer_batch`, micro-batching `/v1/chat/completions`, `/ready` | 208 | HTTP endpoints |
| `sidecars/local_extractor/serve_4b.sh` | pinned mlx_lm.server launcher | 31 | manual/operator |
| `scripts/llm_quality_sample.py` | seeded attestation sampler | 134 | operator CLI |
| `workers/workers/extract_worker.py` | **modified**: provider seam, LLM branch (lane select, gated run, precomputed/evidence wiring, shadow cutoff, receipts), rescue skip in llm modes | +185 | `process_event` |
| `shared/polymath_shared/settings.py` | **modified**: extraction_provider, cloud_min_bytes, llm endpoints/models, concurrency, neighborhood cap | +81 | settings |
| `config/extraction_models/*.yaml` | locked model config + limiter seeds | 2 files | config |
| `tests/determinism/test_llm_extraction.py` | 24 tests | 364 | pytest |
| `tests/determinism/test_llm_limiter.py` | 8 tests | 124 | pytest |

## Dead-code pass results

**Fixed this pass (ruff F401/F841):** unused `CONTRACT_ID` import (client),
unused `expected` (client ×2), unused `by_id` (gate), unused `gen_tokens`
(batched_server).

**Removed:** `limiter.LimiterUnavailable` — exception class whose raise
path was deleted when the limiter moved to blocking-gate semantics.

**Unwired-by-design (documented, kept):** 4 v3.3 API functions ported with
`chunk_kind.py` — `should_summarize_parent`,
`parent_summary_required_clause`, `should_skip_ghost_b`,
`is_reference_block`. Wire targets exist in the register (parent
summaries, ghost-B skip). Not dead — not yet connected.

**False positives to ignore:** `EntityProposal`/`ExtractionItem`
(Pydantic annotation references — invisible to text grep), Flask handlers
(`chat_completions`, `ready`, `models` — decorator-registered),
`batched_server._run_micro_batch`/`_queue_collector` (`Thread(target=)`
references), `ontology.check_relation` (test-used convenience wrapper).

**Pre-existing, NOT from this session:** `extract_worker` ARG002
(`record_candidate_outcome(sl)`), ARG001 (`_persist_mentions
ordered_slices`) — legacy signatures, untouched.

**Graphify cross-check:** code-only rebuild (12,947 nodes / 21,129 edges);
the 219 nodes across the new modules have **zero isolated nodes**; the
call graph confirms the AST analysis. Log: `/tmp/graphify_session.log`.

## Known gaps (already registered, unchanged)

`extractor_version` does not stamp LLM-era facts; corpus_entities/entity_links
migration pending; digest→routing-card wiring pending; eval set unbuilt.
See `PLAN-AUTHORITY-REGISTER.md`.

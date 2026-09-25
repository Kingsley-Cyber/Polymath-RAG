---
change_id: LLM-BACKEND-BATCH1
owner: "@king"
date: 2026-09-24
status: complete
architecture_impact: "shared/ + workers/ + orchestrator/ + config: eight provider-backend fixes from the gap register (L-08, L-09, L-10, L-12, L-13, L-16, L-17, L-18). No retrieval or answer behaviour changes; the lane roster, limiter families and restore rule change; one new setting (POLYMATH_LLM_CLOUD_PRIMARY). Fence + one bounce."
last_reviewed: 2026-09-24
---

# LLM-BACKEND-BATCH1: the provider-backend clean-up

## Contract
- The owner, 2026-09-24: "clear groups 4 and 5 then go batch 1". Batch 1 = the eight quick fixes listed from the gap
  register (`docs/wiki/plans/GAP-REGISTER-LLM-BACKEND-AND-CODE-RAG.md`), roadmap track L.

## Changes
| Gap | Change | Where |
|---|---|---|
| L-09 | `LIMITER_REFUSED` (the process's own limiter saying "wait") is transient for doc_profile: the ticket is held, no attempt burned | `workers/workers/doc_profile_worker.py` `_TRANSIENT_ERR` |
| L-08 | saved limiter state carries `spec_fingerprint` (hash of kind, init/min/max, rpm, tpm, conc_cap, rpd, family); `restore()` reuses header-adopted ceilings only under the same fingerprint | `shared/polymath_shared/llm_extraction/limiter.py` `AdaptiveLimiter.spec_fingerprint/state/restore` |
| L-10 | one limiter family per OpenRouter account: `openrouter_acct_1` (openrouter1, openrouter2, compiler_alt), `_2` (openrouter3, profile_fallback_openrouter), `_3` (openrouter5, map_fallback_openrouter) | `config/extraction_models/limiter.yaml` |
| L-12 | `nvidia`, `nvidia2`, `siliconflow1..3` `enabled: false`; new setting `POLYMATH_LLM_CLOUD_PRIMARY` (default true) parks the Ollama primary while other providers exist (the roster never goes empty) | `config/cloud_providers.json`; `settings.py` `llm_cloud_primary`; `pool.cloud_endpoints` |
| L-13 | `compiler_alibaba_qwen` removed from the `chat_compiler` pin (the lane stays defined; re-pin = rollback). The DeepSeek lane stays: 3 of 3 calls ok since the 2026-09-23 thinking fix | `config/cloud_providers.json` |
| L-16 | per-lane `max_output_tokens`; `map_groq2q..6q` = 900 (orgs enforcing OTPM 1000 refused 2,400); pMAP and profiles send `lane_max_tokens(ep, stage_max)` | `pool.py` `CloudEndpoint.max_output_tokens`, `lane_max_tokens`; `doc_parent_map_stage_worker.py`; `doc_profile_worker.py` |
| L-17 | every LLM client carries `attempt_stage` / `attempt_function` (doc_profile, doc_parent_map, extract, parent_enrichment, chat_compiler, chat_bridge); the client records through `attempts.fallback_tags`, so rows from worker threads carry a stage; an explicit `attempt_context` still wins; `record()` keeps its signature | `conformance/attempts.py` `merged_tags`, `fallback_tags`; `client.py` `_record_attempt`; callers |
| L-18 | the unused `POLYMATH_GROQ_ROUTER=1` removed from the live `.env`; `POLYMATH_LLM_CLOUD_PRIMARY=0` added | live `.env` (not in git) |

## Proof
- New `tests/determinism/test_llm_backend_batch1.py`: 14 tests, all pass (worktree PYTHONPATH verified; they can only
  pass against the branch's code).
- Impacted suites (22 files: limiter, pool, lanes, telemetry, profile / pMAP stages, compiler, reasoning, Groq),
  worktree without `.env`, `POLYMATH_TEST_DSN` pointed at a dead address, `-k "not test_live_"`: branch 239 tests = 1
  failure, 4 skipped; unmodified production 225 tests = the SAME 1 failure, 4 skipped. The failure
  (`test_synthesis_attempt_telemetry::test_the_bound_retry_records_BOTH_attempts`) is order-dependent and needs a
  database; it passes alone on both.
- An earlier draft cleared the process-wide settings cache inside a test and made that failure appear only on the
  branch; the test now stubs `pool.get_settings` instead.
- Lint on the changed files: 138 findings vs 140 on production (all pre-existing); the new test file is clean.

**Contract impact** (`scripts/contract_impact.py --range production`): changed EVIDENCE_BOUNDARY_API and
PROFILE_SCOUT_WIRING (because `ui.py` changed: two tag assignments on the compiler / bridge clients) + 10 transitive.
- TESTED_UNCHANGED: EVIDENCE_BOUNDARY_API, PROFILE_SCOUT_WIRING, CANDIDATE_ENGINE, EVIDENCE_PACKET, QUERY_PLANNER,
  RESOLUTION_STATE, RETRIEVAL_RECEIPT, SUBQUERY_PROVENANCE, PROFILE_YIELD_RECEIPT, MCP_SURFACE (`test_mcp_server_v2`):
  12 suites, 172 tests; branch and production both fail only
  `test_chat_runtime::test_compiler_on_drives_the_same_retrieval_decision_on_both_routes` (documented pre-existing).
- DEFERRED (share the fleet Postgres or services, or delete rows): ACCEPTANCE, ADAPTER_RUNTIME and the adapter /
  MCP-principal / hosted contract suites, `test_query_receipts.py` (hard-coded fleet DSN),
  `tests/integration/test_cross_domain_routing.py` (deletes rows).

## Rejected claims
- "Clamp every restored ceiling to the configured TPM": wrong for lanes whose headers legitimately raise capacity
  (OpenRouter is seeded conservatively on purpose). The fingerprint keeps learned ceilings while the limits are
  unchanged and drops them when the lane's configuration changed.
- "Park both Alibaba compiler lanes": DeepSeek answers since the 2026-09-23 thinking fix.

## Open contract gaps
- L-06 (per-process buckets) and L-04 / L-05 (admission size, daily tokens) remain for L2 / L5.
- Live proof after the bounce: the first new attempt rows carry a stage; the pool log line lists no `primary`,
  `nvidia*`, `siliconflow*`.

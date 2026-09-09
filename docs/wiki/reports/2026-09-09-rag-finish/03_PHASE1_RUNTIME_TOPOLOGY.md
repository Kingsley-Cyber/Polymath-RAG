---
owner: "@king (executing agent)"
change_id: RAG-PIPELINE-FINISH-V1
phase: "PHASE 1 — reconstruct runtime truth (Graphify + direct symbol verification)"
date: 2026-09-09
last_reviewed: 2026-09-09
status: DONE
method: "graphify-out (fresh Sep-9 04:44, HEAD-current) + 3 read-only Explore traces + direct source reads"
---

# PHASE 1 — Fresh-document ingestion runtime topology

Source-of-truth verification for the RAG-finish work. Every row is grounded in current source at HEAD
`303e9e7` (code unchanged since the Sep-9 04:44 graphify run — intervening commits are docs-only).

## BLUF — the central gap

A fresh upload runs the **14-stage `STAGE_DAG`** and reaches legacy `query_ready` + `SEMANTIC_COMPLETE`,
but **cannot reach `VNEXT_COMPLETE`**, because the vNext readiness floor requires
`unresolved_eligible_parents == 0` (every retrieval-eligible parent pMAP-mapped or excluded) and
**`doc_parent_map` (pMAP) is not in `STAGE_DAG`, has no registered fleet worker, and runs only via
`scripts/parent_map_backfill.py`** ([tickets.py:24](../../../../control/control/tickets.py), verified). The
`doc_profile` (vNext) half **is** auto-minted (stage 14) with full pool failover. **Wiring `doc_parent_map`
as an auto-minted functional-pool stage is the spine of the whole finish work** (Phases 5→6→7→8→13→15).

## Fresh-upload flow — run identity + DAG minting

- `orchestrator/api/ui.py:386` `upload()` spools the file → `intake_submission.py:60 submit_intake()` (the
  ONLY run-identity creator): content-addressed `run_id` (sha256 of file in payload → replay = no-op), one
  `runs` row `status='intake'`, one `intake.v1` outbox event. **No stage tickets minted here.**
- The control tick mints the DAG: `control/main.py:71` → `tickets.py:764 fair_ensure_tickets…` →
  `tickets.py:88 ensure_run_tickets()` loops `STAGE_DAG` and mints ALL tickets up front (`intake` ready,
  rest pending/done-if-prior-ok). `advance_tickets` (`tickets.py:303`) verifies each predecessor's
  attempts+artifacts+receipts and emits the next stage's event. Reconciliation/blue-green mint the same chain.

## `STAGE_DAG` (14 stages) — auto-minted vs not ([tickets.py:24](../../../../control/control/tickets.py))

| # | stage | worker_type | blocking? | auto-minted for fresh upload? |
|---|---|---|---|---|
| 1 | intake | intake | yes | yes (born ready) |
| 2 | extract | extract | yes | yes (consumes chunked.v1) |
| 3 | profile_document | profile_document | yes | yes — OLD deterministic retrieval-profile (artifact `documents_profiled`), ≠ doc_profile |
| 4 | project_qdrant | project_qdrant | yes | yes |
| 5 | project_neo4j | project_neo4j | yes | yes |
| 6 | canonicalize | canonicalize | yes | yes |
| 7 | project_canonical | project_canonical | yes | yes |
| 8 | verify_projections | verify_projections | yes | yes |
| 9 | compile_objects | compile_objects | NON-blocking | yes |
| 10 | parent_summary | summaries | NON-blocking | yes |
| 11 | document_summary | summaries | NON-blocking | yes |
| 12 | corpus_summary | summaries | NON-blocking | yes |
| 13 | vocabulary | summaries | NON-blocking | yes |
| 14 | **doc_profile** | doc_profile | NON-blocking (Phase A) | **yes** — the vNext profile (`payload.doc_profile.vnext='true'`) |
| — | **doc_parent_map (pMAP)** | **none registered** | — | **NO — backfill-only** (`scripts/parent_map_backfill.py`) |
| — | profile-atom (`document_profile_atoms`) | none | — | NO — canary/backfill-only (`profile_atom_canary.py`) |
| — | parent_enrichment | summaries | NON-blocking | NO — owner button / `auto_enrich_on_chunks` only; deliberately absent |

## Function inventory (worker → lane → provider → limiter → artifact → projection → drain)

| function | worker / entry | lane selection | accounts / models | limiter key | durable artifact | projection | cross-lane drain |
|---|---|---|---|---|---|---|---|
| **GRAPH_EXTRACTION** | `extract_worker.py` → `llm_provider.run_proposals` | unpinned `cloud_ring` (family-interleaved, rank-sliced per active doc) | nvidia2, gemini1-4/1b-4b, openrouter1/2/3, siliconflow1-3 (Qwen3-8B), primary(Ollama) | per-endpoint `(llm_cloud,<name>)`; families nvidia/gemini/openrouter; siliconflow none | entities, mentions, facts, evidence, raw_*_proposals, extraction_call_receipts | `project_neo4j` + `project_qdrant` workers | **FULL** — in-run cross-host failover + whole-stage ticket requeue |
| **DOCUMENT_PROFILE** | `doc_profile_worker.py` → `_pool_complete` | pin `doc_profile`; `lane_order`/`attempt_lanes` (≤2 primaries + fallbacks, ≤4) | profile_groq1-6 (`groq/compound`) → gemini5/6, openrouter fallbacks | per-lane `profile_groqN`; families `groq_acct_1..6` | stage artifacts `doc_profile` + `doc_profile_qdrant` (receipt chain) | INLINE `project_profile` → Qdrant `polymath_document_profiles_<contract>` (no worker) | **FULL** — in-run multi-account/provider walk + `TransientStageHold` requeue |
| **PMAP** | `doc_parent_map_worker.run_document_mapping` (driven by `parent_map_backfill.py`) | pin `doc_parent_map`; round-robin per infer call | map_groq1-6 (`groq/compound-mini`); no fallback | per-lane `map_groqN`; families `groq_acct_1..6` | `document_parent_map_batches`, `document_parent_maps`, `document_parent_exclusions` (0054) | `parent_map_projection.project_parent_maps` → Qdrant, only via `--project` backfill (no worker) | **PARTIAL/UNVERIFIED** — 429/refusal `break`s (no in-run failover); re-claimed only by a later backfill run; no standing pool worker |

## Limiter & isolation ([limiter.py](../../../../shared/polymath_shared/llm_extraction/limiter.py))

- `AdaptiveLimiter` keyed per `(provider, endpoint/api_key)` — each lane owns its `_DynamicSemaphore`,
  `_TokenBucket`, AIMD state, `_Breaker`. `admit()` → `LimiterDecision` naming the gate; order
  `retry-after → family → breaker → concurrency → rpm → tpm → provider-rpd → local-rpd`. `admitted=False` ⇒
  zero HTTP / zero quota (the 11.185 conservation invariant).
- **Groq exception:** `family: groq_acct_N` binds account N's `profile_groqN` (compound) + `map_groqN`
  (compound-mini) under one `_FamilyGate` + shared daily budget (`groq_accounts.account_states`). Six
  accounts = six capacity domains. This is the ONLY cross-function credential sharing. SiliconFlow lanes
  carry no family (3 independent).

## Claim / lease / retry substrate ([worker_runtime.py](../../../../shared/polymath_shared/worker_runtime.py))

Durable, reusable (the plan's Phase 4 substrate exists at the ticket layer):
- claim = lease (`status='leased'`, 300 s, `FOR UPDATE SKIP LOCKED`); claiming is NOT an attempt.
- `_lease_keeper` renews lease+heartbeat every 60 s; past `POLYMATH_STAGE_DEADLINE_S` (14400 s) fails + exits.
- expired lease: stale owner → attempt+1+quarantine; alive owner → back to `ready`, no attempt.
- transient (429 / LIMITER_REFUSED / SidecarUnavailable / TransientStageHold) → `_release_ticket_transient`
  → `ready`, **no attempt burned**, backoff 15 s (60 s capacity).
- real failure → `_fail_ticket`: attempt+1, `failed` at attempt≥3 else `ready` (≤2 retries).

## Semantic readiness ([semantic_readiness.py](../../../../shared/polymath_shared/semantic_readiness.py))

Pure-Python reads (no `semantic_completion`/`vnext` DB columns — `vnext` is an `artifacts.payload` JSONB
field). Endpoint `/semantic_readiness`; verifier `scripts/vnext_readiness_report.py`.
- **Legacy** `semantic_completion()` → COMPLETE/INCOMPLETE/FAILED from runs/summaries/corpus map/
  procedure+concept artifacts + projection receipts + extraction coverage. `zero_yield_is_completion=True`.
- **vNext** `vnext_readiness()` → VNEXT_COMPLETE iff `unresolved_eligible_parents == 0`
  (eligible parent-tier chunks − active `document_parent_maps` − `document_parent_exclusions`) AND
  `vnext_profiles >= documents` (doc_profile artifacts with `vnext='true'`). Additive; the QUERY_READY flip
  (S13)/cutover (S14) gate on it. `NOT_STARTED` if the substrate/rows are absent.

## Retrieval / chat reader ([chat_retrieval.py](../../../../orchestrator/orchestrator/api/chat_retrieval.py))

- Entry `chat_retrieve_v2()` (L147) / `chat_retrieve_mode()` (L525) on the CANDIDATE-RETRIEVAL-V1 engine
  (`candidate_engine.py`). (`retrieval.py run_lanes` is the older G1/G2 primitive, not the chat path.)
- Modes→lanes: FAST=A+B, HYBRID=A+B+C (default), GRAPH=+hop-1, WILDCARD=+latent sweep. Lanes: A
  HIERARCHICAL_ROUTE, B GLOBAL_DENSE_CHILD, C GLOBAL_SPARSE_CHILD. vNext door (lane E dual-read):
  `profile_nominate` (doc-profile collection) → `search_parent_maps` (parent-map collection); optional
  PROFILE_ATOM `search_atoms`.
- **Citations = source child chunks only** (`locator=chunk:<id>`); profile/atom/parent-map/latent surfaces
  ROUTE but are never evidence.

## parent_enrichment classification (Phase 11 answer)

**Legacy/optional latent-transfer bridge.** Minted by `auto_enrich_on_chunks` (scheduler.py:235) /
enrichment button → `mint_parent_enrichment` (latent/trigger.py) → rows in `parent_enrichments` (0043) by
`latent/runtime.py`. **No retrieval reader reads the table directly**; consumed only via its Qdrant latent
projection (`latent_abstraction`/`latent_transfer`) on the **default-off** lane D and WILDCARD, always
labelled DERIVED / never evidence. Not a required retrieval reader; safe to leave as-is during the
functional-pool migration (retirement stays gated on latent-lane migration + the migration authority).

## Phase 1 gate — PASS

The runtime graph is complete enough to explain current behavior and to justify the phase order that
follows. The one load-bearing correction to prior docs: there is no `vnext` SQL column (JSONB payload),
and pMAP is backfill-only (not auto-minted). Proceed to Phase 2.

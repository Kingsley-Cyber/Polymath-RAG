---
change_id: PLAN-AUTHORITY-REGISTER
owner: governance
date: 2026-08-29
status: living
architecture_impact: authoritative detail extraction of the migration plan
last_reviewed: 2026-08-29
---

# PLAN AUTHORITY REGISTER — every normative detail, tagged

> Source: `/Users/king/Downloads/polymath-v4-local-migration-plan.md` rev 4.
> Every normative detail extracted atomically. Status tags:
> **DONE** (implemented + verified) · **DEVIATED** (implemented differently,
> deviation recorded + reason) · **SUPERSEDED** (readiness Directory Contract
> or later owner directive replaces it) · **MISSING** (not built — must be
> scheduled or explicitly waived) · **PARTIAL**.
> This register is the completion contract for goal mode. Update statuses as
> work lands; never delete lines.

## §0 TL;DR / design law

| # | Detail | Status |
|---|---|---|
| 0.1 | Summaries route, vocabulary translates, source chunks prove — three systems joined by IDs | DONE (architecture; vocabulary = query_policy + corpus lexicon stage) |
| 0.2 | Extraction generates vocabulary; deterministic summaries generate routing | DONE (extraction→raw ledger→lexicon stage exists; digest→summaries PARTIAL, see 4.3.6) |
| 0.3 | idempotent stage transactions; kill -9 → resume → zero re-work (P2 acceptance test) | PARTIAL (runtime property + accidental restarts passed; formal drill MISSING) |
| 0.4 | Self-aware control plane, sidecars hold no state | DONE (receipts/artifacts; no sidecar state) |
| 0.5 | Two model windows never concurrent (local); cloud exempt | DONE (only one local engine; rule enforced by design) |
| 0.6 | Providers are data, not code (registry rows + failover) | DEVIATED → limiter config + client lanes; no providers TABLE (superseded by receipts decision). Limiter carries lane/failover seeds. |
| 0.7 | One output gate for every provider | DONE (gate.py; raw-ledger provenance) |
| 0.8 | Shadow lane first; promotion only after beating baseline | DEVIATED (canary-E2E promotion gate adopted instead of full benchmark; owner to ratify) |

## §1 key architectural decisions

| # | Detail | Status |
|---|---|---|
| 1.1 | Postgres is the control plane (no new infra) | DONE |
| 1.2 | Model = process: 4B pinned sidecar `/infer_batch` (load→batches→release); 35B oMLX lifecycle | DEVIATED (batch_generate server built 2026-08-29; window lifecycle automation MISSING — manual start/stop) |
| 1.3 | Model proposes; Python validates; refuse unattested | DONE — and since 2026-08-30 (owner): in `llm_live` the validated relations ARE the facts (LLM-DIRECT-FACTS-V1, `workers/llm_direct.py`); the GLiNER-era predicate compiler / admission-harbor chain is bypassed for LLM proposals (it admitted 3 of 286 attested relations). Identity: entities by (core_type, normalized surface), facts by (predicate, subject, object) → cross-document aggregation by id; mentions carry corpus_id + doc_id. |
| 1.4 | Model sees evidence neighborhoods, never parent summary rows | DONE (build_neighborhoods) |
| 1.5 | Summaries route / vocabulary translates / chunks prove | DONE (same as 0.1) |
| 1.6 | Legacy compat: passage_concepts five buckets; extractor_version separates generations | PARTIAL (buckets ✓; **extractor_version does NOT distinguish LLM-era facts — MISSING stamp**) |
| 1.7 | Two-tier extraction: 4B dense volume runs WHOLE pass; quality tier re-extracts flagged | **SUPERSEDED by owner decision 2026-08-29: single-lane adopted** (>300KB→cloud whole-doc, ≤300KB→local; measured 6m34s). Two-tier flagged/dense machinery will NOT be built. Three-layer graph (1.17) also IGNORED by owner. Scope: wave = cyber books already in corpus (original 12); the 14 backfilled non-cyber books are held out of extraction. |
| 1.8 | Shadow lane before promotion (benchmark gate) | DEVIATED (see 0.8) |
| 1.9 | Rejected claims locked (no concurrent local windows; no parent rows to model; no LLM→Neo4j) | DONE (respected) |
| 1.10 | Cloud quality lane routed by file size; >300KB→cloud; no cap at launch | DONE (selection+dispatch enforced) |
| 1.11 | Output gate sanitize→validate→normalize→write for every provider | DONE |
| 1.12 | One self-aware entity graph; provenance per chunk (provider, model, tokens, wall, cost) | PARTIAL (tokens/wall/lane per call in artifacts ✓; cost MISSING — no price table) |
| 1.13 | Borrow, don't build: Instructor ADOPT; KGGen clustering BORROW; Docling-via-fork CANONICAL; LightRAG REJECT; thinking strip ours | PARTIAL (**Instructor: DEVIATED to direct client**; **KGGen clustering MISSING**; thinking strip ✓; Docling superseded by REQ-003) |
| 1.14 | Stateless per call; 4bit load; corpus_entities + entity_links merge ladder; 850w default volume unit; 15k spike | PARTIAL (stateless ✓; 4bit ✓; **merge ladder MISSING**; volume unit = 7,000-char neighborhoods DEVIATED from 850w; 15k spike run 2026-08-29 at batch 4 only) |
| 1.15 | Single-pass full schema: e/m/r + L latent + ps prompt seeds; open-vocabulary types; latent namespace | PARTIAL (e/r/digest ✓; **m by chunk:sentence DEVIATED to quotes**; **L latent MISSING**; **ps prompt seeds MISSING**; open vocabulary ✓ with raw labels preserved) |
| 1.16 | Canonical chunker = 3.3 tier_chunker fork; tables atomic; ChunkKind noise skip; <15w drop | **OWNER DIRECTIVE 2026-08-30: v3.3 `tier_chunker` (Docling fork, no OCR) IS the canonical chunker; swap scheduled as LATENT-TRANSFER-LAYER-V1-PLAN Phase 0 (re-ingest).** Previously: DONE at the neighborhood layer (chunk_kind.py ported from v3.3 section_classifier; noisy kinds skip LLM extraction; <15w stub skip; tables atomic — children never split) |
| 1.17 | Three-layer graph L0/L1/L2; query modes local/bridge/propagation; latent miner | **REJECTED (owner 2026-08-30: never blessed; removed from all plans)** |
| 1.18 | Generation lock-in: max_tokens=2500, rep_penalty=1.15, rep_ctx=400, thinking off; truncated-JSON salvage | DONE (locked config + salvage; spike showed clean at 3000 out on 15K-in) |
| 1.18 | D1 "deterministic parent summary / retrieval_summaries / chunker UNCHANGED" — DEVIATED by owner (2026-08-30 "include it in slice 2"): `retrieval_summaries` is now compiled by SUMMARY-COMPILER-V1 (`retrieval-summary-v3`, migration 0041 dual slot); the chunker stays unchanged | DEVIATED (work-log 2026-08-30-summary-compiler) |

## §2 current-state audit → §2.5 memory

| # | Detail | Status |
|---|---|---|
| 2.1 | Memory budget table honored; BGE-M3 stand-down during 4B window | SUPERSEDED-lite (no 20.6GB window exists; embedder+4B co-resident ≈ 4GB — measured safe) |
| 2.2 | Batch cap 32GB = 40 (56 max, 80 only on 36GB+) | DEVIATED (client micro-batch 4 neighborhoods/call; batched server MAX_BATCH=40 env) |

## §3 target architecture

| # | Detail | Status |
|---|---|---|
| 3.1 | Per-doc state machine staged in doc_stages | SUPERSEDED (stage_tickets/attempts/receipts are the authority) |
| 3.2 | Model lifecycle rules 1–7 (load only if needed; ready probe /infer; offload triggers incl idle>10min; OOM guard ≥8GB; crash pid adoption; no concurrent local windows; embedder stand-down) | PARTIAL (load-on-demand ✓ via worker claims; **offload automation MISSING**; **OOM guard MISSING**; **pid adoption MISSING**; probe ✓) |
| 3.3 | CLI ingest_cli add/run/status/resume/cancel/report with --tier/--max-docs/--keep-model | **MISSING** (using scripts/ingest.py + SQL bumps) |
| 3.4 | Self-aware SQL: status/report as queries; provider reliability rollup | PARTIAL (SQL possible; **no rollup view/report command**) |

## §4.0 stage contracts
| 4.0.1 | Build rule: live shape wins over plan; P0 verifies line-by-line | DONE (readiness audit + this register) |

## §4.1 chunking

| # | Detail | Status |
|---|---|---|
| 4.1.1 | merge_volume_chunks 850w target / 1400w hard max | DEVIATED at present (neighborhood packing over v4 children); becomes DONE with the tier_chunker swap (1.16, owner 2026-08-30) |
| 4.1.2 | parent_neighborhood = children concatenated with [chunk_id] markers, never parent row | DONE |
| 4.1.3 | embedding_text [Parent][Header] content | DONE (untouched intake) |
| 4.1.4 | old rows is_superseded on swap; CHUNKER flag | SUPERSEDED (no chunker swap) |
| 4.1.5 | <15w stubs dropped; ChunkKind structural skip | DONE (chunk_kind.py: full v3.3 taxonomy — TOC/bibliography/index/appendix/front/back matter skipped from LLM extraction; body/code/table/output/caption kept) |
| 4.1.6 | tables atomic; split tables repeat header | SUPERSEDED (intake chunker authority) |

## §4.2 model runtime

| # | Detail | Status |
|---|---|---|
| 4.2.1 | contracts/extraction versioned packet | DONE (polymath-extraction-v1) |
| 4.2.2 | sidecar /infer_batch + OpenAI-compatible /v1, pinned release, batch 40 cap 56 | PARTIAL (batched_server has /infer_batch + micro-batch /v1; **client does not use /infer_batch yet**; pin ✓) |
| 4.2.3 | LocalExtractorClient typed, Instructor-driven | DEVIATED (direct httpx client; Instructor installed unused) |
| 4.2.4 | provider selection gliner/local_llm_shadow/local_llm | DONE (llm_shadow/llm_live/gliner) |
| 4.2.5 | runtime_budget.yaml window profile | MISSING (no budget entry for 4B window; measured 6.4GB batch in report) |
| 4.2.6 | quality_router per file; no cap at launch | DONE (policy.py + limiter) |
| 4.2.7 | .env OLLAMA key; no key → fall back | SUPERSEDED (daemon auth; no key handling needed) |
| 4.2.8 | model_events + window management | DEVIATED (window receipts in artifacts; no table, no automation) |
| 4.2.9 | one request may batch multiple neighborhoods; provenance never mixes | DONE (NEIGHBORHOODS_PER_CALL=4; items per neighborhood) |
| 4.2.10 | ADR-0008 `evidence_proposal_mode` ('lexical' = pass 2 abstains) and the router deprioritization skip apply to the LLM evidence lane | DEVIATED (recorded 2026-08-29 audit): in `llm_shadow`/`llm_live` the gated LLM relation proposals merge with lexical anchors regardless of `evidence_proposal_mode` (the mode governs the GLiNER pass-2 only) and regardless of `scientific_lane_prioritized` (that skip saved a GLiNER call; there is no call to save). Both inputs stay in the contract hash. |

## §4.3 extraction contract

| # | Detail | Status |
|---|---|---|
| 4.3.1 | compact index-encoded entities (e/m/r) | DEVIATED (flat surface+quote; offset arithmetic in Python; rationale recorded) |
| 4.3.2 | verbatim attestation every entity/relation | DONE |
| 4.3.3 | L latent namespace (confidence, never auto-admitted) | MISSING |
| 4.3.4 | ps prompt seeds | MISSING |
| 4.3.5 | digest central_claim/main_mechanism/retrieval_uses hard-capped | DONE |
| 4.3.6 | digest consumed by summary workers (no second pass) | MISSING (digests in artifacts only) |
| 4.3.7 | open-vocabulary types; unknown falls through, raw preserved | DONE |
| 4.3.8 | per-item output budget scaling with input (15k-in→3k-out) | **SUPERSEDED by measurement 2026-08-30**: the input-scaled cap (484 tokens per parent) truncated the local lane (finish=length, 3 relations) where the locked 2,500 cap self-terminated at 841 tokens with 9 relations. Cap = decision-18 `max_tokens=2500` per neighborhood (+700 per extra neighborhood on cloud calls); batches are budgeted by expected output (~900), not the cap; `finish_reason` recorded per call. |
| 4.3.9 | self-flag dense/low-confidence per item → quality tier | MISSING (no dense flag; whole-doc lane instead) |
| 4.3.10 | profiles volume/quality (volume lean: no L/ps; quality full) | PARTIAL (profile field exists; single profile used) |
| 4.3.11 | tier-2 supersedes tier-1 on same keys | N/A until two-tier decision |
| 4.3.12 | P3 cross-genre probe (one non-exam doc) | MISSING |
| 4.3.13 | EXTRACTION-COVERAGE-V1 (owner 2026-08-30 "checks are mandatory, grounded in the control plane"): every neighborhood sent has a durable disposition; incomplete/missing/quarantined re-issued once singly; `dropped`/`unaccounted` block `query_ready` in the census (run → `degraded`, reasons in `runs.metadata`); soft coverage floor `POLYMATH_CONTROL_EXTRACTION_COVERAGE_FLOOR` reports only | DONE (measured trigger: 118/181 CySA+ parents empty, pattern X...X...; work-log 2026-08-30-extraction-coverage-hardening) |
| 4.3.14 | INTERROGATIVE-ATTESTATION: relations attested only by a question stem are rejected at the gate; prompt rule 8 tells the model the same | DONE (owner delegated the call; narrow rule — declarative "X is not Y" untouched) |
| 4.3.15 | REGION-ROLE-V1: chunker-independent `chunks.region_role` (noise_ocr/index/toc/legal/stub/question_bank/output/code/body); noise never enters a neighborhood or a routing summary | DONE (calibrated on 1,024 live chunks; thresholds hashed into the extract contract) |
| 4.4.8 | SUMMARY-COMPILER-V1 (owner spec 2026-08-30): one model-free compiler for section/document routing cards — verbatim sentences with offsets, triple-aware ranking + relation capsule, TF-IDF salience against the document background, coverage-first over children / ordered regions, Jaccard dedupe, source order, hard bound, keywords, one serialized embed text; the extractor's digest is the LLM adapter (active variant when clean, deterministic card always persisted; `retrieval_summaries.active`); S2 parent summaries consume the card; verifier gates on starved children and missing cards | DONE (17 tests; live dry run 206/206 cards, 61 llm_digest active) |
| 4.3.16 | ONTOLOGY-DURABLE-CHECK-V1: verifier proves ledger predicates ⊆ ontology, `unknown_predicates == 0`, every llm_live ledger relation has an `evidence` row; off-enum/fact-less relations degrade the run | DONE (pre-hardening runs reported, not judged) |

## §4.4 summaries + vocabulary

| # | Detail | Status |
|---|---|---|
| 4.4.1 | summary hierarchy deterministic + digest enrichment | PARTIAL (4.3.6) |
| 4.4.2 | lexiconed stage inline refresh | DONE (existing stage; fed by extraction) |
| 4.4.3 | indexed AFTER lexicon (ordering fix) | DONE (existing DAG) |
| 4.4.4 | corpus_entities table + merge ladder + raw_types | MISSING |
| 4.4.5 | entity_links global join layer | MISSING |
| 4.4.6 | latent_links table + confirmation flow | MISSING (with 4.3.3) |
| 4.4.7 | prompt_seeds table | MISSING (with 4.3.4) |
| 4.4.8 | relations accumulate with provenance, never merge in place | DONE (facts + evidence append-only) |

## §4.5 retrieval
| 4.5.1 | RetrievalConfig kd/ks/λ; RETRIEVAL_MODE flat|hierarchical; eval gate MRR+0.05 | MISSING (P4; retrieval untouched) |

## §4.6 graph RAG
| 4.6.1 | L0/L1/L2; query modes; PPR Connect-4; latent miner; community deferred | **REJECTED (owner 2026-08-30: never blessed; removed from all plans)** |

## §4.7 control-plane schema
| 4.7.1 | ingest_jobs/doc_stages/model_events/extraction_proposals/provider_calls tables | SUPERSEDED (receipts/ledger/artifacts) |
| 4.7.2 | state-transition table: one txn per transition; idempotent keyed; filtering never destroys evidence | DONE (runtime invariants pre-existing + raw ledger durable dispositions) |
| 4.7.3 | long-stage rule: claim_depth=1 + keeper renewal ≤claim_ttl/2, heartbeat OUTSIDE txn | DONE (existing in-flight keeper; observed renewing) |
| 4.7.4 | extraction_proposals keyed (parent_id, extractor_version) → per-file resume | PARTIAL (ticket-level resume ✓; parent-level skip MISSING) |
| 4.7.5 | shadow = same edge, different write target; promotion flips provider, no state-machine edit | DONE |

## §4.8 provider layer

| # | Detail | Status |
|---|---|---|
| 4.8.1 | providers/provider_keys/provider_calls tables + lane failover by priority | SUPERSEDED (limiter registry + receipts) |
| 4.8.2 | Instructor = single client across providers | DEVIATED (direct; see 4.2.3) |
| 4.8.3 | KGGen-style entity clustering in NORMALIZE | MISSING |
| 4.8.4 | thinking-token strip at gate | DONE |
| 4.8.5 | per-provider reliability accumulation drives failover | PARTIAL (receipts accumulate; **failover not wired to reliability**) |

## §4.9 dense 4B I/O

| # | Detail | Status |
|---|---|---|
| 4.9.1 | uniform-size packing (straggler control) | DONE (c7e98b9: balanced k-bucket packing per parent + <15w stub skip) |
| 4.9.2 | one shared system prompt (prefix reuse) | DONE (single system prompt; batched server reuses it per request) |
| 4.9.3 | per-file resume (skip already-extracted) | PARTIAL (ticket resume; neighborhood-level skip MISSING) |
| 4.9.4 | input-size curve spike 850/1400/2000 @ batch 40 + 15k @ 16/8/4; LOCK volume size at max passing ~28GB gate | **MISSING** (only 15k@4 and 8k@4 batches measured) |
| 4.9.5 | BGE-M3 stand-down during window | N/A (no large window; revisit if batch-40 dense adopted) |
| 4.9.6 | true batch_generate runtime (owner report: batch 40, 6.4GB, 241 tok/s-class) | DONE (batched_server + client extract_batched wired; 6×7.5K-token neighborhoods in ONE batch = 151s, 6/6 schema-valid after per-item shape tolerance; curve points: 15k@4=1.7x, 7.5K×6@1=151s) |

## §5 retrieval quality control
| 5.1 | eval_queries.jsonl (20 queries, seeded from manual_retrieval_needed) | MISSING |
| 5.2 | eval_mrr harness + search_evals rows | MISSING |
| 5.3 | shadow benchmark gate metrics (name accuracy first-class, P/R, attestation, valid-output ≥95%, wall, peak mem) | PARTIAL (attestation sampler ✓; **semantic metrics MISSING**) |
| 5.4 | P4 acceptance gate MRR_doc ≥ flat+0.05 before flag flip | MISSING |

## §6 retirements
| 6.1 | GLiNER stays as rollback provider until 2-week clean run, then deleted | PARTIAL (rollback path ✓; deletion pending) |
| 6.2 | spaCy sidecar kept until P5 then deleted | PARTIAL (in use for syntax) |
| 6.3 | Gemini legacy never auto-submitted; --llm local option | N/A (legacy untouched) |
| 6.4 | v1 flat chunker deleted P5 | SUPERSEDED (chunker unchanged) |
| 6.5 | CrossEncoder device cpu fix | MISSING (P4) |

## §7 phases / §8 risks / §9 open questions
| 7.1 | P0 eval set | MISSING (waived for first slice; still owed) |
| 7.2 | P0 011_ingest_control.sql | SUPERSEDED |
| 7.3 | P5 4,500-doc corpus over nights | MISSING (future) |
| 7.4 | P6 thin UI over tables | MISSING (P6) |
| 8.1 | Risk mitigations table | PARTIAL (boundary fail-closed ✓; cost visibility = tokens only, **no cost cap/price**; straggler lock missing per 4.9.1) |
| 9.2 | Literal objects storage shape: typed value nodes (recommended) | MISSING (contract allows literal objects; storage still entity-endpoint-only) |
| 9.8 | query lane slot reserved | PARTIAL (limiter lanes reserved; no query-time LLM) |

## Completion tally (normative details)

- DONE: 34 · DEVIATED: 9 · SUPERSEDED: 8 · PARTIAL: 17 · **MISSING: 24**

## Priority order to close MISSING/PARTIAL (goal mode, post-GO)

1. 4.3.8 per-item output budget scaling + 4.9.1 uniform packing (speed + shape)
2. 4.9.6 client-side /infer_batch wiring (batch-40 density) + 4.9.4 curve spike → lock volume config
3. 3.3 ingest_cli (run/status/resume/cancel/report) — the control surface
4. 1.6/4.7.4 extractor_version stamping + parent-level resume
5. 4.4.4/4.4.5 corpus_entities + entity_links migration (owner directive 5)
6. 4.3.6 digest → parent routing cards (corpus mapping layer wiring)
7. 4.3.3/4.3.4/4.4.6/4.4.7 latent + prompt seeds (quality profile)
8. 5.1/5.3/5.4 eval set + benchmark gate + MRR harness
9. ~~4.6 graph modes~~ REJECTED by owner 2026-08-30

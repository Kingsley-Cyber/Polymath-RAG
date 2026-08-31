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
| 4.3.17 | TERM-SURFACE-GATE (owner 2026-08-30): entity surfaces and relation endpoints must be TERMS — ≤8 words, no sentence punctuation, strengthened by exact-token clause-aux/clause-opener tests (case-sensitive; "IS NOT NULL"/"The Open Group" survive); rejection classes `NON_TERM_SURFACE`/`NON_TERM_ENDPOINT` | DONE (measured pre-landing: SQL 10/128, CySA+ 118/2624 caught, 0 false positives; known misses pinned in test_term_surface_gate; work-log 2026-08-30-control-plane-hardening) |
| 4.3.18 | TRANSPORT-RETRY-500-V1: a single transient 500 from the lane daemon retries once with backoff instead of failing the whole extract stage; repeat still fails closed | DONE (measured trigger: one Ollama 500 burned a 6-min cloud stage; receipt 7d46676d) |
| 4.3.19 | require_slices relaxation (llm_live): the evidence bundle for llm_live documents carries NO sentence-slice manifest (`write_bundle(require_slices=False)`) — the bundle is the raw ledger over chunks; the GLiNER-era "required evidence — may not be reconstructed" contract does NOT hold for the LLM era | DEVIATED (recorded 2026-08-30; either the LLM era grows its own slice-equivalent interpreter view or this stays the documented contract — owner call, see §10.2) |

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
| 4.7.6 | CENSUS-DIRTY-SIGNAL-V2: incremental-census dirtiness tracks `stage_tickets.updated_at` as well as `stage_attempts` (summary stages write no attempts); gap verdicts are NEVER cached; per-run `failed` (not the global fail list) gates promotion | DONE (measured trigger: both cysa runs pinned at `reconciling` with 24/24 tickets done; unstuck in 6 s by the forced full pass; pinned by test_census_dirty_signal) |
| 4.7.7 | HASH-FENCE-V2: the worker code fence fingerprints file CONTENT (sha256, stat-cached), not `size:mtime_ns` — a byte-identical rewrite (pytest restoring the ontology yaml) can no longer quarantine the fleet | DONE (replaces the "tests trip the stale-code fence" CLAUDE.md trap with a structural fix) |

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

## §10 Concept & procedure migration with the LLM lane (rev 5, 2026-08-30)

Authoritative section added to the migration plan
(/Users/king/Downloads/polymath-v4-local-migration-plan.md §10). Register items:

| # | Detail | Status |
|---|---|---|
| 10.1 | Wire `_persist_knowledge_artifacts` into llm_live (deterministic CONCEPT/PROCEDURE compilers, model-free, opportunity accounting preserved) | DONE (2026-08-30 KNOWLEDGE-ARTIFACT-LLM-V1: wired before the llm_live artifact write, gate-admitted surfaces as durable_surfaces, counts + `knowledge_artifacts_s` in the artifact; e2e receipt = next ingest's concepts/procedures counts) |
| 10.2 | Parent Semantic Compiler: one bounded forward pass per parent → summary + abstraction(1) + mechanisms(≤3) + affordances(≤3) + pseudo_queries(≤4); qual budget 1/2/2/3 = 8 latent vectors | MISSING (Adapter 2 contract; supersedes the digest adapter once active) |
| 10.3 | summary_vector stays PURE; enrichment = separate object keyed parent_id + source_content_hash + version | design fixed |
| 10.4 | Latent Qdrant namespaces first; Neo4j unchanged in phase 1 | design fixed (owner, Adapter 2) |
| 10.5 | Latent retrieval = additive seed generator → parent_ids → EXISTING evidence pipeline; fail-open, 100–300ms budget, per-channel flags, retrieval_mode baseline|baseline_plus_latent | design fixed |
| 10.6 | Per-channel attribution + P6 LATENT_TRANSFER_RECALL suite (LatentRecall@K, CrossDomainRecall@K, FalseAnalogyRate, AnswerLift ±latent) — separate from ordinary retrieval eval | MISSING |
| 10.7 | LLM-native extract.procedures (Adapter 1) DEFERRED unless opportunity accounting proves deterministic compiler gaps | decided |

## §11 One authority, three projections — storage model + governing principle (owner 2026-08-30)

Governing principle (owner, verbatim intent): **the model proposes;
deterministic Python owns truth.** The LLM never writes a store, never
assigns a canonical id, never becomes a survival dependency. Identity,
admission, the predicate contract, projections, and the control plane are
deterministic; the model is swappable, the guarantees are not.

### §11.0 Contract audit — is the governing design embedded in the control plane? (verified against code 2026-08-30, session 4)

| Claim | Where enforced | Verdict |
|---|---|---|
| Lane from durable `documents.byte_length`, ≤300 KB local; enforced at selection AND dispatch | `policy.py` `CLOUD_MIN_BYTES=300_000` clamped floor; `select_lane` + `require_cloud_eligible` raises `CloudBoundaryViolation` immediately before the socket | CONTRACTED |
| Local = GPU window: batched decode, OOM-halving, concurrency 1–4 | `client._infer_batch_call` (500→halve after slot release, budget `record_oom`), `limiter.yaml mlx_local max:4` | CONTRACTED |
| Cloud = rate problem: RPM/TPM buckets before send, AIMD, header sync, breaker | `AdaptiveLimiter` (closed→open→half-open one-probe breaker, `use_headers`), `ollama_cloud` seeds init 3 | CONTRACTED (ceiling raised 16→32 this session — it saturated with ZERO 429s, masking the discoverable limit) |
| Parent unit: model reads child chunks concatenated, never the stored parent row | extract neighborhoods built from `tier='child'` rows; gate `ChunkView`s are children | CONTRACTED |
| Noise never enters an LLM call | `chunks.region_role` (REGION-ROLE-V1) + neighborhood packing filters | CONTRACTED (4.3.15) |
| Output budget scales with input; generation config locked | `output_budget_for`; `GENERATION_CONFIG` = temp 0, rep_penalty 1.15, ctx 400, local `enable_thinking:false`, cloud `reasoning_effort:none` | CONTRACTED |
| Closed predicate enum, exact→alias→RELATED_TO, every fallback recorded | 74-entry `PREDICATE_ALIASES` + patterns; gate counts `predicate_fallbacks`; `predicate_raw`+`predicate_method` persisted on every evidence row AND in facts.provenance | CONTRACTED |
| Off-enum can never become a stored predicate | gate normalizes; `llm_direct` guards `pred not in RELATION_ONTOLOGY` (counted, never expected); verifier `ontology{}` degrades off-enum runs (4.3.16) | CONTRACTED |
| No-think guaranteed twice | engine-layer per lane (above) + `strip_thinking` at the gate | CONTRACTED |
| One control plane: tickets→leases→receipts→census, idempotent, kill-9 resume, lease keeper | `stage_transaction`/receipts, `_lease_keeper`, ticket DAG; census stuck-run class killed by CENSUS-DIRTY-SIGNAL-V2 (4.7.6) | CONTRACTED |
| Coverage accounted, not assumed | EXTRACTION-COVERAGE-V1 dispositions + census promotion barrier (4.3.13) | CONTRACTED |
| Shadow before trust | `llm_shadow` admits nothing; promotion = provider flip (4.7.5) | CONTRACTED |
| Graph hits ground to chunks; identity-admitted facts only | `Fact→Evidence→Chunk` rows written by identity in `llm_direct`; projector reads facts table only | CONTRACTED |
| Deterministic floor: summaries, concepts, procedures model-free | SUMMARY-COMPILER-V1 (4.4.8) + compile_objects stage (11.4) | CONTRACTED |
| Entities carry generation + open vocabulary (de-flattening) | was MISSING — closed by 11.1 | BUILT 2026-08-30 |
| Graph extractions first-class in FAST routing | was MISSING — closed by 11.2 | BUILT 2026-08-30 |
| Exact-name lexical recall (BM25) | was MISSING — 11.3 | BUILT (projection side) 2026-08-30 |

### §11 register items

| # | Detail | Status |
|---|---|---|
| 11.1 | GENERATION-STAMPING-V1 (closes 1.6): migration 0042 — `entities.extractor_version/generated_by_bundle_hash/raw_types(jsonb set-union, containment-guarded for observable idempotency)`, `facts.extractor_version` (indexed); `llm_direct` writes `llm-direct-v1` | DONE (2026-08-30 s4) |
| 11.2 | ROUTING-ENTITY-CARDS-V1: one content-addressed card per (entity, corpus) — surface + aliases + core type + predicate capsule; `representation_kind='routing_entity'`, payload `{entity_id, corpus_id, doc_ids}`; shared id derivation `projection_contracts.entity_card_id` (projector writes, verifier reconciles — one derivation); full receipt/incremental/reconcile parity with the other routing lanes | DONE (2026-08-30 s4) |
| 11.3 | SPARSE-BM25-V1: named `bm25` sparse vector (server-side IDF) on the routing collection; deterministic shared tokenizer `polymath_shared/sparse_bm25.py` (index side and query side MUST import the same function); children index attested entity surfaces + parent head; MEASURED: qdrant 1.13.4 cannot add sparse to an existing collection → new collections sparse-native, `scripts/migrate_routing_sparse.py` (copy-out/recreate/copy-back, dense preserved, owner-gated `--apply`) migrates legacy; legacy collections log `SPARSE_LANE_SKIPPED_LEGACY_COLLECTION`, never fail | DONE projection-side (2026-08-30 s4); query-side fusion = §4.5 work, PARTIAL |
| 11.4 | COMPILE-OBJECTS-STAGE-V1: concept/procedure compilers as their own non-blocking ticket stage (`compile_objects.v1`, after verify, before summaries) — own contract hash, attempts, receipts, artifact, opportunity accounting; supersedes the llm_live bolt-on (removed); legacy GLiNER inline call stays frozen behind the seam; supervisor slot + pipeline/converge profiles | DONE (2026-08-30 s4) |
| 11.5 | L0 authority hardening: `predicate_raw`/`predicate_method`/`raw_type` were already persisted per row (audit); remaining L0 item = none | DONE by audit |
| 11.6 | Query-side: FAST reads `routing_entity` cards; HYBRID fuses the `bm25` sparse lane (same tokenizer import) | DONE (2026-08-30 RETRIEVAL-FULL-FIX-V1: cards are a fused RRF lane in `pass1-retrieval-v2`; sparse fused in HYBRID + breadth lanes) |
| 11.7 | RETRIEVAL-FULL-FIX-V1 (audit F2/F6/F7/F8/F10/F11/F12): card lane fused into RRF; chunk lane children-only + 65 parent points retired; AI-designed breadth/depth caps (BREADTH-V2/DEPTH-V2) + synthesis budget 2000×48; multi-corpus FAST; sparse-tokenizer contract test; OBJECT-NAME-CONTRACT-V2 naming gate (compile + serve) | DONE (2026-08-30, work-log 2026-08-30-retrieval-full-fix.md) |
| 11.8 | EXTRACTION-POOL-V1 + LANE-AFFINITY-STEAL-V1 (owner 2026-08-30): extract slots get lane affinity (extract=local, extract2+=cloud) with a counted steal pass when the home lane is dry; cloud lane generalized to a deterministic multi-provider router pool (POLYMATH_LLM_CLOUD_EXTRA_ENDPOINTS, blake2b(doc_id) sharding, per-endpoint AIMD limiter lanes, roster in contract_identity). 300KB exfiltration boundary UNTOUCHED — providers widen throughput, never eligibility | DONE (2026-08-30, work-log 2026-08-30-extraction-pool.md) |
| 11.9 | CLOUD-ASSIST-V1 (owner rule v2, 2026-08-30, SUPERSEDES the 2026-08-29 exfiltration framing): byte threshold = throughput router — big docs always cloud; small docs prefer local but ride the cloud pool as an explicit ASSIST when a cloud-affinity worker holds them (own lane dry). Dispatch guard verifies assist INTENT (still fail-closed on caller bugs). Lane is operational not replay-deterministic; artifact records lane+reason+endpoint | DONE (2026-08-30, work-log 2026-08-30-cloud-assist.md) |
| 11.10 | MULTI-PROVIDER-AUTH-V1: committed provider registry config/cloud_providers.json (Groq LIVE on openai/gpt-oss-120b, extraction canary GREEN; NVIDIA pre-configured, parked until NVIDIA_API_KEY in .env). Auto-gate: key drop = activation, logged never silent. Bearer auth per endpoint, per-endpoint payload quirks, keys excluded from fingerprints/repr. extract3 cloud-affinity slot. Preflight scripts/probe_cloud_endpoints.py | DONE (2026-08-30, work-log 2026-08-30-multi-provider-auth.md) |
| 11.11 | NVIDIA-LATENT-PIN-V1: NVIDIA LIVE (key in .env) + DEDICATED to parent_enrichment (STAGE-PIN-V1). Model nemotron-3.5-lightning-30b-a3b, reasoning_effort "none" (verified: only knob that stops NIM thinking-burn; /no_think fails), temp 0, JSON mode, limiter seed 36 RPM/conc 4 (limiter.yaml per-provider blocks; groq seeded 30 RPM). Canary through the pinned path GREEN. Phase B must re-canary the enrichment schema | DONE (2026-08-30, work-log 2026-08-30-nvidia-latent-pin.md) |
| 11.12 | NVIDIA-DUAL-LANE-V1: second unlinked NVIDIA account live (NVIDIA_API_KEY_2); stage pins are GROUPS — parent_enrichment shards deterministically across [nvidia, nvidia2] (measured 103/97 over 200 docs), each with its own 36 RPM AIMD bucket (~72 RPM combined). One dark = reduced capacity logged; all dark = loud fail | DONE (2026-08-30, work-log 2026-08-30-nvidia-dual-lane.md) |
| 11.13 | GROQ-EXTRACTION-FLEET-V1: baseline extraction cloud = primary + groq1..groq5 (5 unlinked owner accounts, qwen/qwen3.8-27b, reasoning none, temp 0, STRICT JSON SCHEMA level-1 — live-canaried; 30 RPM AIMD each). DEDICATED-V1: nvidia lanes excluded from extraction sharding, enrichment-only. Old hermes groq key dropped from the pool | DONE (2026-08-30, work-log 2026-08-30-groq-extraction-fleet.md) |
| 11.14 | CROSS-PROVIDER-FAILOVER-V1: nvidia2<->groq5 role swap (extraction shards groq1-4+nvidia2+primary on super-120b extraction-canaried; enrichment group [nvidia, groq5]) + LANE-FAILOVER-V1 deterministic ring (transport-dead or limiter-refused batches retry once on the next lane, logged EXTRACTION_LANE_FAILOVER; pinned stages ring within group). Whole-provider outage stalls nothing | DONE (2026-08-30, work-log 2026-08-30-cross-provider-failover.md) |
| 11.15 | UI-V3-PRESENTATION-V1: PRD executed — presentation fields on every bundle item + FAST evidence (source_name bug dead, live-verified), citations human_locators, sections-tree endpoint + F13 query_enabled toggle, frontend Sources panel (human name › section + quote, provenance expander) + document section tree. Zero raw chunk ids in default view (browser-verified). All additive | DONE (2026-08-30, work-log 2026-08-30-ui-v3-presentation.md) |
| 11.16 | LATENT-PHASES-A-D-V1 + §0a buttons: latent package (contract/prompt/gate/compiler/runtime/projection/rescue), migration 0043, owner-triggered enrichment stage on the pinned cross-provider group, latent projection + verifier reconciliation, HYBRID rescue lane + latent flag through every surface, P6 harness. LIVE: 24 READY enrichments, 48 latent points, cross-domain reach proven (3 parents/9 children per query, 2 unique evidence gains per P6 case). latent default OFF until owner P6 GO | DONE (2026-08-31, work-log 2026-08-31-latent-phases-a-d.md) |
| 11.17 | ENRICHMENT-CONCURRENCY-V1: transport parallelized to the pinned endpoint limiter conc_cap (4/account, ~4x measured); HTTP_429 retry ladder (backoff → same lane → cross-lane → backoff) after a conc-4 burst 429-killed 30/40 AWS parents; INVALID rows upgrade in place on retry (re-click = recovery, proven 40/40 READY, 14 failovers); verify.v1 era-exempt (receipts-only) | DONE (2026-08-31, work-log 2026-08-31-enrichment-concurrency.md) |
| 11.18 | CENSUS-WEDGE-RESTORATION-V1: three stacked wedges fixed after latent projection took the corpus to corpus_not_ready — (1) DAG-less ticket KeyError killed advance_tickets fleet-wide; (2) 1C successor carry-gap (per-run artifact reads) parked + originals re-pinned; (3) the F6 children-only want-set had THREE copies (verify/census/tickets) — all aligned. query_ready restored, latent reach live on full corpus | DONE (2026-08-31, work-log 2026-08-31-census-wedge-restoration.md) |
| 11.19 | AUTO-ENRICH-UI-V1: enrichment auto-mints at run promotion (census tick = timer; retrieval-first rationale; enrichment_auto gate); ONE shared mint path (latent/trigger.py); /documents per-doc parents/enriched/failed; FilesView enrichment badges + conditional ✨ buttons + ＋Add-files + ＋new-corpus flow. Browser-verified | DONE (2026-08-31, work-log 2026-08-31-auto-enrich-ui.md) |

## §13 Enrichment lane scheduling & isolation (rev 6, 2026-08-30)

Authoritative section added to the migration plan (§13). Design decided:

| # | Detail | Status |
|---|---|---|
| 13.1 | External, in compile_objects (NOT native to extract) | DECIDED |
| 13.2 | Dedicated `llm_enrich` lane, separate provider/key — own AIMD/buckets/breaker, zero interaction with baseline cloud lane | DECIDED (provider/key choice pending owner) |
| 13.3 | ARM-ON-DRAIN: enrichment tickets arm per corpus when extract tickets all done | design fixed |
| 13.4 | BASELINE PREEMPTS: no enrichment claims while any extract ticket is ready/leased | design fixed |
| 13.5 | LOCAL ASSIST: manual, owner-deployed, post-drain only (GPU window belongs to baseline) | design fixed |
| 13.6 | Contract: parent-semantic-compiler-v1, bounded 1/3/3/4 = 8 latent vectors/parent; gate = coverage + refs⊆input + malformed-reject; (parent, source_hash, contract) keyed; STALE on diff | design fixed |
| 13.7 | SWEEP = re-arm compile_objects corpus-wide; DIFF = source_hash compare → STALE → regenerate | design fixed |
| 13.8 | Implementation: enrichment compiler inside compile_objects worker; no new stage, no new subsystem | build pending |

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

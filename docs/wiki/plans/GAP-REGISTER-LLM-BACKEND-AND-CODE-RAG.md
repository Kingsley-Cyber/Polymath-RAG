---
title: "Gap register: LLM provider backend, document retrieval and code RAG (confirmed items only)"
date: 2026-09-24
last_reviewed: 2026-09-24
status: "LIVING — every row OPEN until the slice named in 'Fix' closes it with proof; the roadmap is LLM-BACKEND-AND-CODE-RAG-ROADMAP-V1.md"
owner: "@king"
scope: "Consolidates the 2026-09-24 audit (register 11.459, report docs/wiki/reports/2026-09-24/CODE-RAG-AND-PROVIDER-KEYS-AUDIT.md) and the two external Astra reports of 2026-09-24 (production 69c2704). Only CONFIRMED items: each was executed (E) or read in source / config (R, file:line) and re-checked by hand. Hypotheses and unmeasured quality questions are listed separately at the end."
---

# Gap register: LLM backend, document retrieval, code RAG

**Rules.** A row enters only when its evidence was re-checked (E = executed and observed; R = read at file:line).
A row closes only when the slice in "Fix" proves the change (test, replay or live receipt) and records the proof here
(status → CLOSED + register number). Numbers are from production `69c2704`, 2026-09-24. Evidence scripts:
`docs/wiki/experiments/code-rag-key-audit-2026-09-24/audit_evidence.py` (keys, lanes, funnel, chunker) and
`docs/wiki/experiments/code-knowledge-c0-2026-09-24/` (census, capacity, calls, YAML).

Severity: **Critical** = loses data or silently gives wrong results · **High** = blocks the goal or wastes most capacity
· **Medium** = degrades quality or operations · **Low** = hygiene.

## L. LLM provider backend

| ID | Gap | Evidence | Sev. | Fix | Status |
|---|---|---|---|---|---|
| L-01 | **Accounts are not first-class.** 56 flat lane entries in `config/cloud_providers.json` plus per-lane specs in `config/extraction_models/limiter.yaml`, both keyed by lane name. An account exists only as an `api_key_env` string; models, limits and ownership are scattered. This is why "6 keys × 3 models" reads as "18 lanes, 11 on". | R `cloud_providers.json` (keys `_doc`, `stage_pins`, `providers`), `limiter.yaml` (`providers:` keyed by lane) | High | L1 | CLOSED 11.465 (registry `config/llm_accounts.yaml` + checks + report; the drift test keeps the runtime files equal; they become generated in L3) |
| L-02 | 7 of 18 Groq (key, model) pairs idle: key 1 runs gpt-oss-120b only; keys 2–6 run gpt-oss-20b + qwen3.8-27b only (1.4M tokens/day unused) | E `audit_evidence.json` → `groq` | High | L3 | CLOSED 11.467 (all 18 Groq pairs enabled, one owning slot each; `test_llm_ownership_l3`) |
| L-03 | The 2026-09-23 Groq setup has never run live: 0 calls on gpt-oss-120b / gpt-oss-20b / qwen3.8-27b; last Groq call 2026-09-21 05:20 UTC | E `llm_provider_attempts` | High | L4 | CLOSED 11.468 (all 18 Groq pairs answered live through the production client, 2026-09-25 02:44 UTC; Groq headers: 1K requests/day + 8K tokens/min per (key, model), independent) |
| L-04 | Admission counts `len(user_prompt) / 4` tokens: no system prompt, no output | R `llm_extraction/client.py:510` | High | L2 | CLOSED 11.466 for complete_one (profiles, pMAP, enrichment, compiler); batched extraction paths → L-21 |
| L-05 | No daily-token budget (Groq's binding limit is 200K tokens/day per key per model) | R `llm_extraction/limiter.py:62-80` (`ProviderLimit`: rpm, tpm, rpd only) | High | L2 | CLOSED 11.466 (rolling 24 h tpd per lane, persisted; per process until L3 / L5) |
| L-06 | Rate buckets are per process (`REGISTRY = LimiterRegistry()` module global); processes sharing a pair each believe they own its limits | R `limiter.py:1000` | High | L3 (ownership) + L5 (shared budget) | OPEN — 11.467: every Groq pair has ONE caller, so its per-process budget is the whole pair; the shared tier (cloudflare_map1/2, the two OpenRouter fallbacks, openrouter5) still splits per process → L5 |
| L-07 | All 6 doc_profile slots share one pair (pin has one primary: `profile_groq1`) | E pin; R `doc_profile_worker.py:133-166` | High | L3 | CLOSED 11.467 (profile slot N calls only profile_groqN, then the OpenRouter fallback) |
| L-08 | Stale ceilings restored unclamped: `adopted_tpm: 70000` on `profile_groq1` + `map_groq2…6`, `provider_rpd_limit: 250` on the map lanes (compound era); the adopted value overrides the configured 8K TPM | E `llm_controller_state`; R `limiter.py:483, 526-531` | Medium | L2 | CLOSED 11.464 (tests; live check after the bounce) |
| L-09 | doc_profile treats a local limiter refusal (`LIMITER_REFUSED`) as a failed attempt, so a document can fail permanently over quota that would refill (pMAP treats it as transient) | R `doc_profile_worker.py:48-49`, `client.py:528-530` | High | L2 | CLOSED 11.464 (tests; live check after the bounce) |
| L-10 | One `openrouter` limiter family spans 7 lanes on 3 accounts and 4 stages; on 2026-09-21, 140 real 429s on openrouter1 were followed by 4,210 local refusals across openrouter1/2/3/5 | R `limiter.yaml` (family lines); E ledger | High | L1 + L2 | CLOSED 11.464 (tests; live check after the bounce) |
| L-11 | 5 of 6 Cloudflare accounts parked: all 6 `CLOUDFLARE_API_TOKEN_N` set, only `CLOUDFLARE_ACCOUNT_ID_2` set (the URL template needs the account id) | E env booleans; R `pool.py:147-202` | High | L3 | OPEN (account 1 only) — 11.468: ids 3, 4, 5, 6 matched to their tokens read-only, written to `.env` and answered live; the owner's list repeated account 2's id (…1efb: token 1 gets 403 on it and 401 on a real call), so CLOUDFLARE_ACCOUNT_ID_1 is still empty; token 1 belongs to a sixth login |
| L-12 | Dead / slow lanes still in rotation: Ollama `default` (qwen3.5:397b-cloud) 34 × HTTP 402 of 38 calls; SiliconFlow 31 of 72 timeouts; NVIDIA median ~100 s | E ledger | Medium | L3 | CLOSED 11.464 (tests; live check after the bounce) |
| L-13 | Chat compiler depends on one lane: Ollama gemma 1,856 / 1,890 ok; Alibaba lanes 510 / 530 timeouts; `compiler_alt` 310 × 429 of 663 | E ledger | Medium | L3 | CLOSED 11.464 (tests; live check after the bounce) |
| L-14 | pMAP lane choice: 12 lanes sorted, rotated by a hash of the run, the run stays on its first lane until an error; fallbacks rotate in as equals | R `doc_parent_map_stage_worker.py:112-154` | Medium | L3 | CLOSED 11.467 (a pMAP slot walks its own key's two lanes, then the Cloudflare pair, OpenRouter last) |
| L-15 | Extraction pool front-loading: gemini1 155 attempts vs gemini5 4, gemini6 0 | E ledger | Medium | L3 | CLOSED 11.467 (a document's batches start at a lane chosen by a hash of the document; live proof with L4) |
| L-16 | qwen3.8-27b: some orgs enforce OTPM 1000 while pMAP asks `max_tokens` 2400 (canary: "Limit 1000, Requested 1750") | E canary 2026-09-23 result #11; R `doc_parent_map_stage_worker.py:55` | Medium | L2 + L3 | CLOSED 11.464 (tests; live check after the bounce) |
| L-17 | Attribution: `stage` is empty on 96.7 % of `llm_provider_attempts` rows (9,255 of 9,567) | E ledger | Medium | L2 | CLOSED 11.464 (tests; live check after the bounce) |
| L-18 | `POLYMATH_GROQ_ROUTER=1` is set live; its only reader (`document_profile/groq_routing.py:40`) has no production caller | E env; R | Low | L3 | CLOSED 11.464 (tests; live check after the bounce) |
| L-19 | No upload since 2026-09-17 has been shown to mint parent maps; the pMAP lanes were dead for new documents until the 2026-09-23 swap, and nothing new has run since. New code corpora depend on it | R `docs/wiki/work-log/2026-09-23-groq-model-swap.md:52`; the pMAP wiring-gap work-log (bookkeeping 11.463) | High (for code RAG) | L4 (one small pMAP document) | OPEN |
| L-20 | Two limiter families still span accounts: `gemini` covers all 6 Gemini accounts (18 lanes) and `nvidia` covers 2 (parked); one account's 429s damp every account in the family | E `scripts/llm_accounts.py validate` (FAMILY_SPANS_ACCOUNTS); R `config/extraction_models/limiter.yaml` | Medium | L3 | CLOSED 11.467 (Gemini: one family per (account, model), 12; NVIDIA: one per account) |
| L-21 | The batched extraction paths still admit `len(user prompts) / 4` (no system prompt, no output): `extract_batched`, `complete_batched`, `_extract_prompt` | R `shared/polymath_shared/llm_extraction/client.py:727, 905, 1004` | Low (they run on lanes without Groq daily budgets) | a follow-up to L2 | OPEN |
| L-22 | The operator pMAP backfill (`scripts/parent_map_backfill.py`) round-robins the WHOLE doc_parent_map pin (optionally an operator `--lanes` allow-list) without a slot index, so while it runs an owned Groq pair has a second calling process and the per-process budgets can overshoot the pair | R `scripts/parent_map_backfill.py:51-80` (11.467) | Low (owner-gated operator tool) | L5 (shared budget), or run it with `--lanes` on the shared tier | OPEN |

## O. Operations (fleet control plane)

| ID | Gap | Evidence | Sev. | Fix | Status |
|---|---|---|---|---|---|
| O-01 | No real-Postgres full-tick test exists (`control.main.tick` is never called by a test), and the tick died twice since its arity fix (register 11.18: ~2 h; 11.256: 10,191 failed ticks) | R `tests/determinism/test_lock_contention_v2.py:99`, `control/control/main.py:87` | Medium | a throwaway-Postgres tick test | OPEN |
| O-02 | The control tick takes ~55 s; census per-run receipt checks are 51.3 s of it (median of the last 200 ticks) and nobody owns them | E `/private/tmp/polymath_fleet/tick_phases.jsonl` (`census_receipt_checks`) | Medium | a slice (scope the census like BULK-RECEIPT did) | OPEN |
| O-03 | Stuck runs: 63 cinema runs `reconciling` since 2026-09-05..07, 6 commerce-v1 runs `reconciling` since 2026-09-21 (held at the generation barrier behind siblings that failed extract), 1 cinema run in `intake` since 2026-09-07 | E `runs` (read-only) | Medium | owner: the corpus clean-up (commerce-v1 is in its scope) | OPEN |
| O-04 | The runtime-budget profiles in `config/runtime_budget.yaml` (`pipeline`, `serve`, …) list no doc_profile, doc_parent_map or adapter_step slot, so setting `POLYMATH_PROFILE` would silently stop the profile and pMAP stages. Latent: the live `.env` sets no profile, so every FLEET slot runs | R `config/runtime_budget.yaml:115-160` (11.467) | Low | a small slice (add the slots, or derive the profile slot lists from FLEET) | OPEN |

## D. Document retrieval (independent of code; affects the live book corpora)

| ID | Gap | Evidence | Sev. | Fix | Status |
|---|---|---|---|---|---|
| D-01 | GRAPH hop-1 facts are `ORDER BY fact_id LIMIT 20`; `fact_id` is `fact_` + a 64-hex hash, so the 20 facts are an arbitrary pick, not the most relevant | R `orchestrator/api/retrieve.py:712`; E fact id format | Medium | D1 | OPEN |
| D-02 | MCP `polymath_search` trims text at 1,200 characters with no truncation marker (`_trim_hit` 1,400) | R `mcp_server.py:141, 302-303, 323-329` | Medium | D1 (marker) + C9 (full-unit reader) | OPEN |
| D-03 | An extraction-only blue/green re-ingest keeps the old run's facts: the swap purges chunk / evidence rows only for documents the successor re-chunked, so the previous run's facts stay in the fact tier and the graph | R `control/control/generation_swap.py:45-66` (the `EXISTS … n.chunk_contract_version = %s` guard); llm-direct-canon work-log | Medium (latent until the next extraction-only re-ingest) | new slice (owner) | OPEN |
| D-04 | The vocabulary stage's NO-GO verdict is not enforced: co-occurrence alias families are still written, and cinema has one family with 71,087 aliases; /ask planning and the resolution lift read them | R `workers/workers/summary_worker_impl.py:399`, `corpus_map_planning.py:113`, `resolution_lift_gather.py:147`; E live counts (bookkeeping 11.463) | High (quality) | owner: a merge rule or retire the stage | OPEN |
| D-05 | Canonical profile selection: the refusal path (keep last-known-good) never fired live, and no re-profile rearm passes `force=True` | R `workers/workers/doc_profile_worker.py:320`, `document_profile/projection.py:120`; E 10 of 10 selections were first projections (2026-09-21) | Medium (before the next re-profile) | a small slice | OPEN |
| D-06 | Projection lifecycle writer (L4) and live reconcile (L5) are dormant: no projector writes lifecycle fields (0 of 633,131 receipt rows), `projection_reconcile.py` is imported only by its test | R `shared/polymath_shared/receipts.py:334, 359`, `projection_reconcile.py`; E receipt counts | Low | owner: wire or retire | OPEN |
| D-07 | Interactive relief U3: the 40-turn after-check was never recorded; the judge deadline stays 12 s though the load it covered is gone | R `docs/wiki/reports/2026-09-07/UNFINISHED_WORK.md:69`; E `POLYMATH_RERANK_DEADLINE_S=12` | Low | owner: keep 12 s or return to 8 s | OPEN |
| D-08 | The query side hard-codes the neural embedding contract; harmless while every corpus is neural | R `orchestrator/orchestrator/api/fast.py:249, 269` | Low (latent) | when a second contract exists | OPEN |
| D-09 | Both live corpora are `purpose=probe`, so the `ALL_AUTHORIZED` scope resolves to zero corpora | R `query_scope.py:43`; E `corpora` rows | Low | owner: corpus purposes | OPEN |

## C. Code RAG (not built; confirmed gaps against CODE-KNOWLEDGE-V1)

**Ingestion**

| ID | Gap | Evidence | Sev. | Fix | Status |
|---|---|---|---|---|---|
| C-01 | Upload gates refuse code: UI and MCP accept only `.md .txt .html .pdf .epub .docx` | R `ui.py:457`; `mcp_server.py:60, 192, 217` | High | C1 | OPEN |
| C-02 | The chunker is one global setting (`tier_v3`), not chosen per document | R `intake_worker.py:194-219`, `settings.py:209-210` | High | C1 | OPEN |
| C-03 | tier_v3 on code loses real lines: `runtime_budget.yaml` 10 settings lines (`total_gb: 29.0`, the `control_plane:` block …), `doc_profile_worker.py` 334–336, `determinism.yml` line 1; comment lines become headings; functions split across parents | E `audit_evidence.json` → `tier_v3_on_code`; R `tier_chunker.py:52, 103-113` | Critical | C1 (routing) + C3 (provider) | OPEN |
| C-04 | Region roles guessed from prose shape misfile code: `noise_ocr` children are dropped at query time (62 of 1,822 code children); `code`-role parents get no section card | E (125-file sweep); R `region_role.py:61-95`, `profile_worker.py:191-194`, `candidate_engine.py:1301-1311` | High | C3 | OPEN |
| C-05 | LLM entity / fact extraction would run on code (only noise roles are skipped) and write into the shared Entity graph | R `extract_worker.py:77-81`, `llm_provider.py:96-106` | High | C1 | OPEN |
| C-06 | `doc_id = sha256(bytes)`: an edited file is a new document; containment ≥ 0.95 is classed a certain duplicate | R `identity.py:50-56`, `dedup.py:64`, `intake_worker.py:73-148` | High | C1 (path ledger + supersession) | OPEN |
| C-07 | Empty files raise `EmptyExtractionError` (empty `__init__.py` is common) | R `materializer.py:171` | Medium | C1 | OPEN |
| C-08 | Front matter is harvested for every document, including YAML that starts with `---` | R `intake_worker.py:328`, `frontmatter.py:14-37`; E synthetic | Medium | C1 | OPEN |
| C-09 | Chunk rows carry no line span, symbol id, qualified name, language, revision or tool version | R `intake_worker.py:390-411` | High | C2 | OPEN |
| C-10 | Budgets are counted in words, not tokens | R `tier_chunker.py:40-50` | Medium | C3 / C6 / C7 | OPEN |

**Meaning (profile / pMAP)**

| ID | Gap | Evidence | Sev. | Fix | Status |
|---|---|---|---|---|---|
| C-11 | Profile input is a 500-token sample (1,361 characters for a 21,984-character file) | R `doc_profile_worker.py:40`, `document_profile/context.py:199-262`; E | High | C7 | OPEN |
| C-12 | pMAP skeleton = heading + ≤ 30-word excerpt + regex "identifiers"; no signatures, children or relations | R `parent_skeleton.py:42-87` | High | C6 | OPEN |
| C-13 | Both compilers mangle identifiers: the MAP line splits on `\|` (a `dict \| None` signature is cut), `_` and `*` are stripped (`__init__` → `init`) | R `map_compiler.py:78, 236-251`, `compiler.py:267-271`; E synthetic | High | C6 / C7 | OPEN |
| C-14 | Enrichment reuse is keyed on content-addressed parents; no dependency-aware refresh (a caller's description is not refreshed when its callee changes) | R `doc_parent_map_worker.py:214-224` | Medium | C6 / C7 | OPEN |

**Retrieval**

| ID | Gap | Evidence | Sev. | Fix | Status |
|---|---|---|---|---|---|
| C-15 | No description → unit hydration: lane E deepens pMAP parents by a cosine search over their ORIGINAL children; the prompt carries ≤ 2,000 characters of child text | R `candidate_engine.py:929-945`, `ui.py:1522` | Critical (for code) | C9 | OPEN |
| C-16 | Chat FAST runs lanes A + B only (no sparse, no profile / pMAP door) | R `chat_retrieval.py:755-764`, `skeleton_routes.py:48-62` | High | C9 | OPEN |
| C-17 | HTTP `/retrieve` FAST runs `fast_retrieve`, a different path from chat FAST | R `api/retrieve.py:199-203` | Medium | C9 | OPEN |
| C-18 | MCP has no revision-bound source-unit reader (search trims, see D-02) | R `mcp_server.py:323-329, 395-408` | High | C9 | OPEN |
| C-19 | Route seats need `route_score`, set only by the contextual judge, which is scoped to WILDCARD live: structure-lane paths in HYBRID / GRAPH would compete on literal relevance | R `candidate_engine.py:1480, 1756`; E live flag | High | C10 | OPEN |
| C-20 | Fairness assumes a document is a book: lane A takes 6 documents; round 1 of the judged prefix seats one candidate per document | R `candidate_engine.py:142-143, 1620-1641` | High | C9 / C10 | OPEN |
| C-21 | The judge (Qwen3-Reranker-0.6B) reads 384 tokens per pair under a web-search instruction: long units are judged on their head only | R `sidecars/reranker/server.py:72-80` | Medium | C9 (judge descriptions, not code) | OPEN |
| C-22 | BM25 lowercases and keeps camelCase / PascalCase whole; tokens < 2 characters dropped (a frozen contract) | R `sparse_bm25.py:24-33` | Medium | C2 / C9 (a code sparse field) | OPEN |
| C-23 | `structural_noise_reason` drops chunks with ≥ 45 % bare numbers (numeric YAML / TOML) | R `candidate_engine.py:1541-1559` | Medium | C3 (role exemption) | OPEN |

**Graph and corpus**

| ID | Gap | Evidence | Sev. | Fix | Status |
|---|---|---|---|---|---|
| C-24 | GRAPH reads only `(:Entity)-[:REL]->(:Entity)`; no code edges exist anywhere | R `retrieve.py:686-712` | High | C2 + C8 + G1 | OPEN |
| C-25 | Code files would get `:Document` / `:Chunk` nodes from the existing projection beside the planned `:CodeDocument`; the delete path knows only Chunk / Evidence / Fact / REL / Document, so Code* nodes would be orphaned | R `ui.py:782-798` | Medium | C8 | OPEN |
| C-26 | All five modes require one corpus, and a content-addressed `doc_id` belongs to one corpus: one reference book cannot join two project corpora | R `ui.py:3755-3766`, `intake_worker.py:172, 226-236` | Medium | C1 decision (documented) | OPEN |
| C-27 | Profile and pMAP are non-blocking stages: `QUERY_READY` can be true while code descriptions are missing | R `control/tickets.py` (`NON_BLOCKING_STAGES`) | Medium | C12 | OPEN |

## T. Trail core embedded in Polymath (from refactor 0015, closed by the 2026-09-24 bookkeeping pass)

| ID | Gap | Evidence | Sev. | Fix | Status |
|---|---|---|---|---|---|
| T-01 | Trail judgement defects M1-01..03 are reproduced inside the embedded core and not fixed; they can end or corrupt a real ecommerce run, and the embedded core is the live mode | R `docs/migration/PARITY_MATRIX.md:37`, `docs/wiki/decisions/0021-trailsignal-core-embedded.md:31`, `tests/determinism/test_trail_core_recorded_equivalence.py:40` | High (before the next ecommerce run) | a Trail-repo fix, then a re-pin (owner) | OPEN |
| T-02 | ~57 % of the vendored Trail lines are contract models unrelated to research (`data_os`, `discovery`, `platform`) | R `docs/wiki/decisions/0021-trailsignal-core-embedded.md:30` | Low (no behaviour change) | a trim + `PROVENANCE.json` re-pin | OPEN |

## K. Knowledge roles and retrieval scope (owner-shared proposal, 2026-09-24)

| ID | Gap | Evidence | Sev. | Fix | Status |
|---|---|---|---|---|---|
| K-01 | Trail's evidence requests carry no source-use scope: `request_body` returns only `message, corpus_id, mode, corpus_explorer`; the legacy `/retrieve` path sends `query, corpus_ids, limit, mode` | R `shared/polymath_shared/adapter/evidence_boundary.py:166`, `workers/workers/adapter_step_worker.py:172` | High (once code shares a corpus) | K1 | OPEN |
| K-02 | No `knowledge_role` exists anywhere; `source_family` exists only as an accepted front-matter key | R `frontmatter.py:18`; grep of shared / workers / orchestrator / control | High | K1 | OPEN |

## Confirmed GOOD — keep (not gaps)

- No cosine / `score_threshold` floor on the chat path; ranked top-k only (R `api/fast.py:137-147`,
  `parent_map_projection.py:46-55`). The repo recorded cosine ranking an author bio (0.5955) above the answer (0.4894).
- Parent / child / pMAP links are deterministic: children store `parent_id`; pMAP rows store the same parent id;
  similarity only chooses which parent to open.
- The durable pMAP core (batching, partial repair, terminal states, failover), both output contracts, the collections
  and point ids, the receipts.
- The engine seam for "rank the description, cite the code": the judge scores the Qdrant payload text while the prompt
  fetches `chunks.text` by chunk id (R `rerank.py:134`, `evidence_assembly.py:333`).

## Not confirmed (measure, do not assume)

- Whether the σ floors (0.2 probe gate, 0.3 connection, 0.5 aspect / latent) suit code DESCRIPTIONS: UNKNOWN until C9
  exists; qualify on real code questions (roadmap C14), change a value only on an observed failure.
- Whether Qwen3-Embedding is enough on code descriptions: measured in C9 / C10.
- Parser-resolution percentages (C0a: 93.8 % of product-code internal calls linked without type inference) measure
  COVERAGE of name resolution on this repository, not the accuracy of a deployed call graph.
- Whether Groq reserves `max_tokens` against TPM: the L4 canary measures it.
- Refactor 0011 rows 15 (the `facts` table has no corpus / run column, `0002_workflow.sql:83`) and 21 (canonicalize merge rate) were measured under the retired GLiNER pipeline and never re-measured.

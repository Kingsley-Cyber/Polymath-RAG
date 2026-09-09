---
change_id: RETRIEVAL-MIGRATION-DEPENDENCY-V1
owner: governance
date: 2026-09-07
status: living
architecture_impact: "The authoritative migration/dependency & retirement plan of record for the vNext retrieval substrate (document profile vNext / profile atoms / parent MAP). Admitted verbatim from the owner-supplied FINAL RETRIEVAL MIGRATION / DEPENDENCY PLAN; the REPO EXECUTION STATUS LEDGER at the top is maintained in place as work lands. This is the retirement/classification/generation-invariant authority; DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md remains the build-slice detail — the two are consistent and cross-mapped below."
last_reviewed: 2026-09-07
last_touched: 2026-09-07
---

# REPO EXECUTION STATUS LEDGER (maintained in place — do not fork)

This block is the living implementation ledger for the plan below. The plan body
(from `# Polymath v4 — Final Retrieval Migration & Dependency Plan` onward) is the
owner-supplied contract, admitted verbatim; this ledger records what is actually
implemented against the live repository and is amended as each slice lands.

**Reconciliation.** This file is the migration/dependency & retirement authority
(classification vocabulary, migration gates, generation invariant, GAP closure).
`docs/wiki/plans/DOCUMENT-SEMANTIC-INDEX-V1-PLAN.md` remains the executable
build-slice detail; its slice numbers (repo S0–S16) differ from this plan's slice
numbers (§30, S0–S18), so the ledger is keyed by **capability** and names both.
The routing/synthesis half (`POLYMATH_FINAL_RETRIEVAL_ROUTING_SYNTHESIS_IMPLEMENTATION_PLAN`)
is a separate future admission, still missing from `~/Downloads` as of 2026-09-07.

**State vocabulary:** NOT STARTED · IN PROGRESS · IMPLEMENTED · VERIFIED · LANDED ·
GATED · BLOCKED · SUPERSEDED. (LANDED = committed to `main` with CI green; VERIFIED =
asserting test green but not yet on `main`; GATED = code-ready or design-fixed but
withheld pending owner LLM spend / fleet config / mass reindex.)

**Repo truth at last ledger review (2026-09-07):** branch
`architecture/evidence-first-v5`. The **entire deterministic migration substrate is now
built + tested + landed** this session (registers 11.138–11.145), each with its four
required CI checks green before ff `main`:

- 11.138 migration ledger admitted (this file, living);
- 11.139 **profile scale** — S5 `DocumentFingerprint` (adaptive, full-structure,
  self-sufficient vocabulary → GAP-04); 11.145 vNext profile prompt (research-index
  surfaces, additive; live compiler untouched);
- 11.140 S1 legacy dependency census (retirement gate); 11.141 S11 report-only
  readiness verifier;
- 11.142 **parent-MAP scale** — S9 durable worker (restart/partial-safe, injected
  inference); 11.143 S10 Qdrant projection contract; 11.144 map prompt (§19/§30).

Both semantic scales are deterministically complete end-to-end. **The owner then
authorized the controlled live migration (2026-09-07), and the live gates have been
crossed with evidence** (registers 11.146–11.152):

- **S5 budget canary** (11.146) → `DEFAULT_BUDGET_TOKENS = 500` (the plateau).
- **S8 profile/compiler wiring** (11.147) reversible (`POLYMATH_DOC_PROFILE_VNEXT`);
  **vNext profile QUALIFIED + ENABLED** (11.149) — self-retrieval 0.933 > 0.860 baseline.
- **S7 Groq shared-budget routing** — accounting (11.148) + `route_groq` + compound-mini
  lanes (11.152), reversible (`POLYMATH_GROQ_ROUTER`).
- **Parent-MAP LIVE** — activation on a 3-doc cohort (11.150, 50 maps, complete +
  restart-idempotent) + projection reconciliation + purge/rebuild (11.151, 50 points,
  Postgres==Qdrant).
- **Controlled cinema backfill** (11.153) — routed generation + projection; it SURFACED
  and fixed a router single-account-pinning bug (the point of a controlled backfill)
  before any mass run; `distinct_accounts_used: 6`. A full backfill is RPM/RPD-paced +
  resumable.
- **S8 shadow runtime route** (11.154) — profile → filtered parent-map → child deepening
  run as a SHADOW (read-only, no rank effect): nomination 1.000, parent-resolve 0.972,
  median 143 ms; **coverage tracks backfill completeness** (fully-mapped docs 0.80–1.00,
  partial docs proportionally lower). Routing substrate qualified; next is **S9 dual-read**
  (the first live-reader change — separately gated).

Everything reversible (flags / `--cleanup` / `--purge-only`). **Remaining (owner-gated
sequence, step 5 back half):** finish the controlled backfill, then the retrieval-runtime
integration — shadow → dual-read → compiler/title bridge → vNext-readiness/QUERY_READY →
cutover — then, only after zero-reader proof + a rollback window, retirement.

| Migration slice (§30) | Capability | Repo build-slice | Status | Evidence / next gate |
|---|---|---|---|---|
| S0 | Freeze migration audit (this doc) | — | **LANDED** | this file; register 11.138 |
| S1 | Automated dependency census | `scripts/legacy_dependency_census.py` | **IMPLEMENTED** | the code-dependency census is built + 8 determinism pins (register 11.140): word-boundary scan of all legacy symbol groups, kind-by-path (migration/test/eval/doc/config/runtime/script), heuristic runtime role. Snapshot at admission: **332 runtime occurrences** (reader 72, writer 43, producer 3, **reference 214** = the review queue the "no unknown runtime" gate names). Resolves the GAP-04 reader (`doc_profile_worker.py:102`) and the enrichment writer (`latent/runtime.py:90`). `scripts/semantic_lane_census.py` remains the complementary durable-state LANE census. **VERIFIED** pending human classification of the 214 references before any S15–S18 retirement. Recorded discrepancy: the plan §3 `chat/*.py` paths are `shared/polymath_shared/*.py` in the repo. |
| S2 | Parent skeleton + MAP compiler | repo S1 + S2 | **LANDED** | registers 11.130 / 11.131; `parent_skeleton.py` (v2), `map_compiler.py`; determinism tests green |
| S3 | Local model tournament (LFM 350M/1.2B/2.6B vs compound-mini) | — | **GATED** | owner (local-model benchmark + spend); the packed MAP contract is already proven LIVE on `groq/compound-mini` (register 11.136) |
| S4 | Additive SQL ledgers | repo S4 | **LANDED** | migration `0054_document_parent_maps.sql`; register 11.135; 5 durability pins on dev PG |
| S5 | Durable map worker / manifests | `workers/workers/doc_parent_map_worker.py` (repo S9) | **IMPLEMENTED** | durable orchestration + store ops over the 0054 tables (register 11.142): PREPARE → lease → infer-OUTSIDE-tx (§28) → compile → persist → repair-only-missing (§18.4); 5 durability pins incl. restart idempotency (§36.5 — second run re-infers nothing, active set stable) and supersede (one active/parent). The inference boundary is INJECTED (no spend) and the stage is NOT fleet-registered (no live-ingestion change). **VERIFIED LIVE (register 11.150):** `scripts/parent_map_canary.py` ran the full pipeline (`build_parent_skeletons → map_prompt → groq/compound-mini → run_document_mapping`) on a 3-doc cinema cohort — 50 parents mapped, complete, restart-idempotent, durable in the 0054 tables. **STILL GATED:** `STAGE_DAG` registration (fleet DAG) + the S7b router-into-pool for scaled backfill; broader generation is gated on step-4 projection reconciliation. |
| S6 | Parent-map Qdrant projector | `shared/polymath_shared/document_profile/parent_map_projection.py` (repo S10) | **IMPLEMENTED** | deterministic projection contract (register 11.143): contract-named collection `polymath_document_parent_maps_<embedding contract>` (§14 blue/green, never mixes with chunk/profile), stable per-parent point id, §9.2 vector text (signature + hooks + compact heading) + payload, embedding-contract-sensitive projection_key, and the §14 `reconcile` count gate (projected == active maps). `embed` + Qdrant `client` INJECTED (no network); 7 pins incl. deterministic end-to-end projection of real compiled maps. **VERIFIED** (fake I/O). **GATED** to RUN: the live embedder closure + Qdrant client + receipt persistence; **GAP-05 purge** integration in `ui.py` (live writer) is gated. |
| S7 | Global profile vNext independence | repo S5 | **VERIFIED (canary passed)** | deterministic `fingerprint.py` (11.139) + `profile_prompt_vnext.py` (11.145). The 500/1000/1500/2000 budget canary RAN LIVE (register 11.146, owner-authorized): 20/20 `groq/compound` calls, 0 errors; field + research-tag coverage saturates at 500 and the no-first-400-bias gate is met at 500 (late-structure 0.82), higher budgets cost ~2× for no gain → **`DEFAULT_BUDGET_TOKENS` selected = 500**. Evidence: `docs/wiki/experiments/document-profile-vnext-canary-2026-09-07`. GAP-04's live reader `doc_profile_worker.py:102` is now SKIPPED on the vNext path (S8, register 11.147). **S8 wiring DONE, reversible:** the compiler recognizes the 7 research tags (backward-compatible, no drift) and the worker builds the fingerprint + `profile_prompt_vnext` behind `POLYMATH_DOC_PROFILE_VNEXT` (default OFF = byte-identical live path; plan §28 rollback switch). **QUALIFIED + ENABLED (register 11.149):** the self-retrieval gate PASSED — vNext top-1 0.933 vs baseline 0.860 on the 67-doc cinema competitor set (evaluation-only canary collection, deleted after) — and `POLYMATH_DOC_PROFILE_VNEXT=1` is set in `.env` (reversible; effective next fleet reload; changes only new-doc profiling). Remaining profile-scale work: a controlled cinema re-profile (backfill) under vNext + query-side comparison (owner step 5). **DONE 2026-09-08 (11.169):** all 67 cinema doc_profiles regenerated under vNext (`backfill_document_profiles.py --rearm` → era-compatible re-arm, `compatible()=True`, no blue-green) — 67/67 `vnext=true`, 0 invalid; profile atoms re-extracted across all 10 kinds (609, reconciled + queryable). Cinema is now a COMPLETE vNext profile+atom generation. Query-side uplift comparison still pending parent-MAP coverage (D-10). |
| S8 | Shadow runtime route | repo S12 | **QUALIFIED (read-only, no rank effect)** | global profile → parent maps → child deepening as shadow, measured vs the current child lane (register 11.154). Pure store-abstracted `shadow_route` module + read-only `shadow_route_canary` + `test_shadow_route` (6/6). LIVE 36 probes / 6 mapped cinema docs: nomination **1.000**, parent-resolve **0.972**, mean overlap 0.665, median 143 ms. **Coverage tracks parent-map backfill completeness** (fully-mapped 0.80–1.00; Blain 33%→0.242, Anatomy 11%→0.017); nomination + resolve hold across all docs → the gap is unmapped parents (paced backfill 11.153), not routing. Next: **S9 dual-read** (first live-reader change, separately gated). |
| S9 | Dual-read feature flag | repo S12 | **LANDED (default off, qualified)** | Hybrid consumes new candidates; direct child lane stays unrestricted. `candidate_engine` lane E (register 11.156), additive + unioned last + `POLYMATH_CHAT_DUALREAD_ENABLED` (default off). Gate PASS: flag-off byte-identical (`chat_regression --check` 0 failing); flag-on exact-lookup control (`dualread_qualify.py`: L 15/15→15/15, B 13/15→13/15, 0 regressions). Now proceeds under FINAL-RETRIEVAL-ROUTING-SYNTHESIS-V1 as the profile→map→child spine (P1.spine). |
| S10 | Query-compiler title-context bridge | (ui.py `_compiler_titles`) | **ABLATED 2026-09-08 — no-op on a small corpus** | **GAP-02** ablation RAN: a prototype merged vNext `profile_nominate` doc_ids into `_compiler_titles`' ranking. On cinema the titles were **byte-identical** — `rank_documents` already fills `top_n=40` from content, and cinema shows 40/67 titles, so 16 profile-nominated docs appended beyond position 40 are cut (and the relevant ones are already in via content/alphabetical fill). Prototype reverted (inert scaffolding). **Unblocks when:** a valuable bridge needs an **RRF merge of the content ranking WITH the profile ranking** (so a profile-relevant doc the content ranker missed is promoted, not appended) — a change to the B16 `compiler_context` ranking — AND a **large corpus** (top_n ≪ corpus size) to demonstrate + qualify the lift. Deferred until a large corpus exists to ablate against. |
| S11 | Report-only vNext readiness verifier | `scripts/vnext_readiness_report.py` | **IMPLEMENTED** | report-only parent-map backfill VIEW (§2/§16/§19), read-only, availability-neutral, fence-free (register 11.141). Per corpus: legacy_query_ready_runs + eligible/mapped/excluded/unresolved parents + docs by map-state, preserving the generation invariant (partial ≠ complete). Live baseline: cinema 67 docs / 11,993 eligible parents, ecom 10 / 1,346, d7 3 / 78 — all NOT_STARTED (0 vNext maps; substrate empty by design). **VERIFIED** live on dev PG. Promotion into `semantic_readiness.py` as a first-class verdict + a vNext-profile column is the S11-proper step (deferred with S8). **S11-proper DONE 2026-09-08 (11.175):** `semantic_readiness.vnext_readiness` + the `vnext` field on `semantic_completion` — VNEXT_COMPLETE/INCOMPLETE/NOT_STARTED from durable parent-MAP (§19 unresolved==0) + vNext-profile coverage, additive (legacy verdict untouched), fail-open. Live: cinema VNEXT_INCOMPLETE (11993 eligible / 551 mapped / 368 excluded / 11074 unresolved; profiles 67/67). The readiness AUTHORITY now carries the verdict S13/S14 gate on. **Verdict transition PROVEN 2026-09-08 (11.176):** `d7-h1-test` reads **VNEXT_COMPLETE** (78/78 eligible parents mapped, 0 unresolved; 3/3 vNext profiles; pending []) — the FIRST corpus to flip INCOMPLETE→COMPLETE, confirming the floor `unresolved==0 ∧ profiles==docs` fires exactly as specified. |
| S12 | Existing corpus backfill | repo S14 | **FIRST CORPUS COMPLETE (d7-h1-test); cinema PARTIAL** | owner authorized backfill (2026-09-08). **`d7-h1-test` = VNEXT_COMPLETE 2026-09-08 (11.176)** — the whole data-regen chain driven end-to-end on a real corpus: 78/78 eligible parents mapped (0 unresolved), 3/3 vNext profiles, 30 atoms across all 10 kinds (reconciled 30==30). Capacity canary passed first (26/26 parents, 0 err, spread across 3 Groq accounts via CONCURRENCY-SPREAD-V1); sanctioned map/profile lanes only, no paid fallback. This is the first proof the migration substrate reaches its terminal readiness verdict autonomously. **cinema: profile scale DONE** — 67/67 re-profiled under vNext + 609 atoms all-kinds, reconciled (11.169); **parent-MAP scale PARTIAL** — 704/11,993 eligible parents mapped (advanced from 551 this session; 13/67 docs have maps), resumable/idempotent. No cutover before coverage + canary gates. **Two backfill defects 2026-09-08, BOTH FIXED:** (1) **FIXED — account pinning:** the backfill `infer` routed via `route()`, whose capacity view is BLIND for these unregistered map lanes (all placeholder→tied), so it pinned to the lexically-first account (measured 649/657 on `map_groq1`). Replaced with explicit ROUND-ROBIN across the six distinct-account endpoints (BACKFILL-SPREAD-V1, `parent_map_backfill.py`); live-verified even 109/109/109/109/108/108, test `test_parent_map_backfill_spread.py`. (2) **FIXED — large-doc batch OVER-SIZING (map-batches-v2):** docs ≥~430 parents mapped ≈0 (Ken Dancyger 2/430; Hey Whipple 0/469). **Root cause (corrected from the input-size hypothesis after capture):** `map_batches.plan_batches` capped batches by a token-envelope alias COUNT (`mapping_only_capacity`=60), but `groq/compound-mini` reliably returns a COMPLETE structured map only for SMALL batches — measured: **10-15 aliases 100% (10/10, 15/15 ×3), 20 mostly (occasional 18/20), ≥25 flakily EMPTY/partial** even though the prompt is tiny (~16 KB at 60 aliases). The token envelope was NOT the ceiling — the model's structured-output reliability is; 60-alias batches silently lost large-doc maps. **Fix:** `MAP_RELIABILITY_CAP=15` applied in `mapping_only_capacity` + `BATCH_PLANNER_VERSION`→`map-batches-v2` (batch_hash changes → large docs re-batch into 15s; maps persist by map_hash; resumable; small docs' single ≤15-batches unchanged). Tests: `test_map_batches` pins updated (capacity==15; 40→[15,15,10]; 60→4×15; 150→10×15); 24 planner-dependent tests green. **Qualified live:** the 469-parent Hey Whipple that mapped ~0 under the 60-cap mapped **75/469 in one capacity-limited pass** under the 15-cap (~20× better maps/call), with 15-alias batches measured 100% reliable under fresh capacity. **Remaining:** completing all cinema large docs is now purely CAPACITY-gated (multi-session — this session's diagnosis exhausted today's Groq budget), resumable via `parent_map_backfill.py --corpus cinema --project --concurrency 6`. Coverage → S13/S14 cutover (still also owner QUERY_READY flip). |
| S13 | New-document blocking gate | repo S13/S15 | **GATED** | owner QUERY_READY flip (BE-AWARE §7) |
| S14 | Existing corpus cutover | repo S14 | **GATED** | after backfill + shadow + dual-read qualify |
| S15 | Disable legacy enrichment producers | — | **GATED** | reversible flag; needs S1 census + shadow qualification |
| S16 | Remove legacy runtime readers | repo S16 | **GATED** | needs S1 census == 0 required readers + §23 ablation. **Census re-run 2026-09-08: runtime=334, unclassified=216** — inspected: the unclassified are overwhelmingly BENIGN (trace/telemetry keys like `"document_summary": len(doc_lane)`, lane-name constants `SECTION_SUMMARY_LANE`, and the chunker/intake PRODUCING summaries), NOT legacy READERS. The genuine readers are the classified 72 (summary/compiler-title/enrichment consumers); retiring them is COVERAGE-GATED — they read the legacy summaries vNext replaces, and migrate only when vNext is the live generation (S14 cutover). Exact next before S16: (a) reach vNext coverage + cutover; (b) confirm the 72 readers each migrated; (c) a census heuristic pass to auto-classify the benign trace/constant/producer patterns (shrinks the manual queue). |
| S17 | Stop obsolete legacy writers/stages | — | **GATED** | rollback window; zero-reader proof |
| S18 | Physical cleanup (tables/indexes/flags/collections) | repo S18 | **GATED** | only after rollback window expires |

**Generation invariant (enforced through migration):** a query uses a complete
legacy generation OR a complete qualified vNext generation, never a mixture
(plan §2, §16; BE-AWARE §7). Blue/green re-ingest
(`scripts/reingest_corpus.py --execute --blue-green`) is the outage-free path.

**Live dependencies NOT to retire until repo evidence proves zero readers**
(plan §10–§12, §22; BE-AWARE §10–§11): summaries
(`document_summaries` / `parent_summaries` / `section_summary` routing),
`parent_enrichment`, `compile_objects`, the compiler title context, Hybrid, Graph,
Wildcard, projection receipts, purge/rebuild paths, caches, and the current
`QUERY_READY` semantics.

**Exact next executable dependency (updated 2026-09-07, register 11.145 — GATE BOUNDARY):**
the entire deterministic substrate for BOTH scales is BUILT + TESTED + LANDED
(fingerprint + profile prompt; skeleton + map prompt + compiler + packer + SQL +
durable worker + projection contract; census + report-only verifier). **Every
remaining dependency requires an owner action to WIRE or RUN it — the code each gate
would execute already exists:**

1. **S5 quality canary** (profile vNext qualification): run the 500/1000/1500/2000
   `DocumentFingerprint` → `profile_prompt_vnext` canary on real documents → provider
   spend. Owner authorises spend; the smallest quality plateau is picked; then S8 switches.
2. **S8 `doc_profile` refactor + compiler tag-parse**: extend the LIVE `compiler.py` to
   parse the research-index tags (`profile_prompt_vnext.output_fields()` is the label
   set) and switch `doc_profile_worker.py` to build the fingerprint + `profile_prompt_vnext`,
   dropping the `major_concepts` reader at `doc_profile_worker.py:102` (GAP-04). Changes a
   LIVE stage + the live compiler + trips the fleet fence → owner (fleet) + gated behind (1).
3. **S7 Groq live-routing wiring**: wire the built `groq_router.choose` (11.134) +
   compound-mini lanes into `pool.py`/`limiter.py` — the live fleet provider layer →
   owner (fleet + spend).
4. **Worker/projector RUN**: give `run_document_mapping` a live Groq `infer` closure
   (`map_prompt` + the routed model) and register the stage; give `project_parent_maps`
   the embedder + Qdrant client + receipt persistence → provider spend + embedder + Qdrant
   + a DAG change to live ingestion. **S3 local-model tournament** feeds the `infer`
   choice (spend).
5. **S12 backfill → shadow → dual-read → S14 cutover → S15–S18 retirement**: mass
   generation (spend), then live-reader migration, then — only after the S1 census's
   214 runtime references are each classified non-reading — stop-writers/retire.

**Evidence that permits the next cutover** (none yet satisfied): the canary quality
gate (§29), the shadow/dual-read non-regression (§17/§23), the readiness floor
`unresolved_eligible_parents == 0` per document (§19, measured by
`scripts/vnext_readiness_report.py` — currently 0 mapped / 13,417 eligible across
corpora), and the census showing 0 required legacy readers for a symbol before its
retirement (§S16). Do NOT mass reindex before the canary gates pass (§26).

---

# Polymath v4 — Final Retrieval Migration & Dependency Plan

**Date:** 2026-09-07  
**Repository:** `Kingsley-Cyber/Polymath-RAG`  
**Scope:** final retrieval migration, dependency retirement, control-plane/readiness migration, query-time bridge, and rollback-safe cutover  
**Evidence basis:** GitHub `main` inspected on 2026-09-07, plus the repository handoff reports under `docs/wiki/reports/2026-09-07/`. The earlier handoff state referenced commit `fa49448ab11ec88d88d5bfdb784ad6af0acd597e`. This document does **not** attest to the state of any developer-local worktree.

---

## Executive decision

The next retrieval phase must **not** be implemented as a clean-room replacement of the current stack. The current system has live readers, writers, query-compiler inputs, state registrations, projection receipts, and deletion/cleanup paths that depend on artifacts which appear superficially “non-blocking.” In particular:

- summary/compiler stages remain in the control-plane stage set;
- `parent_enrichment` remains a recognized owner-triggered non-blocking stage outside the normal DAG;
- `document_summaries.major_concepts` is consumed by the current document-profile worker as optional semantic input;
- `retrieval_summaries` are still read by runtime/UI behavior and are treated as projected entities during corpus cleanup;
- the chat query compiler ranks documents using section-summary, document-summary, and child representations, then injects selected document titles into the compiler context;
- the current synthesis prompt intentionally excludes summary rows from citation-bearing evidence, but summaries still affect routing/context upstream;
- current `QUERY_READY` semantics do not require the future profile/parent-map contract.

Therefore the migration rule is:

> **Eliminate readers before stopping writers; stop writers before deleting state; delete state before dropping schema only after the rollback window expires.**

The new retrieval substrate is additive first. It becomes blocking only after backfill, shadow retrieval, dual-read qualification, and generation/contract-aware readiness are in place.

### Migration classification vocabulary

Every old component must be assigned one of these states:

| Classification | Meaning |
|---|---|
| **KEEP** | Still owns a unique, required capability. |
| **BRIDGE** | Temporarily feeds or protects the new architecture. |
| **DUAL-RUN** | Old and new readers/writers coexist during qualification. |
| **RETIRE** | Stop new writes only after all required readers have migrated. |
| **DELETE-LATER** | Physical code/table/index deletion after rollback safety expires. |
| **TRACE-BEFORE-CUTOVER** | Dependency is known or suspected but exact ownership still needs a code-level trace before destructive change. |

---

# 1. Verified current ingestion / control-plane graph

## VERIFIED CURRENT

`control/control/tickets.py` defines the normal stage DAG in this order:

```text
1  intake
2  extract
3  profile_document
4  project_qdrant
5  project_neo4j
6  canonicalize
7  project_canonical
8  verify_projections
9  compile_objects
10 parent_summary
11 document_summary
12 corpus_summary
13 vocabulary
14 doc_profile
```

The repository handoff and control code make an important distinction: several later semantic/summary stages exist in the stage universe but are intentionally **non-blocking** for present readiness. `parent_enrichment` is also recognized as an owner-triggered non-blocking stage outside the normal DAG.

The current authority chain is:

```text
control/control/tickets.py
    ↓
workers/*
    ↓
shared/polymath_shared/receipts.py
    ↓
Postgres authoritative metadata / attempts / receipts
    ↓
Qdrant + Neo4j rebuildable projections
```

Ticket lifecycle semantics include durable states such as `pending`, `ready`, `leased`, and `done`; expired leases are designed to be re-driven. This existing lease/receipt model should remain the orchestration primitive for parent-map work instead of inventing a second job engine.

## MIGRATION BRIDGE

The new retrieval stages should first enter this world as **non-blocking additive stages**, with their own durable artifacts and verifier. They should not immediately be inserted into the global legacy blocking barrier.

Recommended logical additions:

```text
build_document_fingerprint
compile_global_profile_vnext
build_parent_skeleton_manifest
map_parent_semantics
project_parent_maps
verify_retrieval_contract
```

These names are conceptual until implementation. Reuse existing ticket/lease/receipt conventions rather than creating a parallel scheduler.

---

# 2. Verified current QUERY_READY / promotion path

## VERIFIED CURRENT

Current readiness is based on the existing blocking stages and required projections. The current summary family and `doc_profile` are not all part of the blocking barrier. The repository comments already anticipate a later phase in which `doc_profile` may become blocking after qualification.

This produces a migration hazard: a document that is legitimately queryable under the current contract may have no parent maps and may not have the future profile contract. If the new requirements are globally added to `QUERY_READY`, legacy documents can be incorrectly demoted or stranded.

## PROPOSED TARGET

Readiness becomes **retrieval-contract aware**, not merely a single global Boolean interpreted identically across generations.

Suggested derived ledger:

```text
document_retrieval_readiness
    doc_id
    generation_id
    retrieval_contract
    source_chunks_ready
    source_projection_ready
    canonical_projection_ready

    global_profile_ready
    global_profile_projected

    parent_maps_expected
    parent_maps_active
    parent_maps_unresolved
    parent_maps_projected

    verifier_status
    query_ready
    blocker_reason
    checked_at
```

This ledger is a verifier/readiness view, **not a second orchestration engine**. Existing tickets remain the lifecycle authority.

### Target semantic readiness states

```text
NOT_STARTED
GLOBAL_PROFILE_RUNNING
GLOBAL_PROFILE_READY
MAP_BATCHING
MAP_REPAIRING
MAP_COMPLETE
PROJECTING
VERIFYING
QUERY_READY
DEGRADED
ERROR
```

### Contract migration rule

```text
legacy document
    └─ remains queryable under legacy retrieval contract

newly ingested vNext document after gate activation
    └─ requires global profile + complete parent maps + projection verification

legacy corpus backfill
    └─ promoted document-by-document / generation-by-generation

legacy contract retirement
    └─ only after corpus coverage + retrieval gates + rollback window
```

## RETIREMENT GATE

Do **not** mutate existing `QUERY_READY` semantics globally until all are true:

1. additive schema exists;
2. new profile/maps can be generated idempotently;
3. new Qdrant projection exists;
4. verifier is report-only and stable;
5. legacy corpus backfill can finish/restart safely;
6. query runtime supports old and new contracts concurrently;
7. no legacy document is made unavailable solely because it predates the new contract.

---

# 3. Current query-time execution graph

## VERIFIED CURRENT

The handoff dependency map identifies the query/runtime chain as:

```text
orchestrator/orchestrator/main.py
  → orchestrator/orchestrator/api/ui.py
  → orchestrator/orchestrator/api/chat_retrieval.py
  → chat/candidate_engine.py
  → chat/retrieval.py
  → chat/rerank_bge.py
  → chat/graph_retrieval.py
  → chat/query_compiler.py
  → chat/answer_prompt.py
```

`api/ui.py` is not a thin presentation layer; it contains meaningful runtime policy:

- chat compiler feature flags (`off | shadow | on`);
- corpus-aware document-title context generation;
- compiler lane failover;
- evidence legend construction;
- citation-to-chunk mapping;
- runtime/query receipt construction;
- legacy latent-transfer flag plumbing;
- corpus cleanup/deletion logic touching summary/projection entities.

The synthesis prompt has an explicit authority split:

```text
user intent     → task authority
corpus evidence → factual authority
```

That grounding contract should be retained through migration.

## Important current evidence behavior

`_evidence_legend()` intentionally removes `document_summary` and `section_summary` rows from citation-bearing evidence. The source code documents that those rows were frequently offered but not cited, so the final synthesis prompt now carries passage evidence rather than separate summary evidence rows.

This creates a useful architectural boundary:

> summary/profile/map artifacts may route retrieval, but factual claims must resolve to source evidence chunks.

That boundary should become a formal invariant of the vNext retrieval design.

---

# 4. Current Hybrid behavior

## VERIFIED CURRENT / PARTIAL TRACE

The current system already has direct/vector/keyword candidate machinery and reranking. Hybrid remains the baseline source-evidence route and should not be replaced by semantic profiles or maps.

The new semantic system must therefore be additive:

```text
QUERY
  ├─ direct child/vector lane       KEEP
  ├─ sparse/keyword lane            KEEP
  ├─ current summary routing        BRIDGE / ABLATE
  ├─ global profile route           ADD
  ├─ parent-map localization        ADD
  └─ graph assist                   KEEP / BRIDGE
          ↓
      source chunks
          ↓
      cross-encoder
          ↓
      evidence bundle
```

## Migration invariant

**Profile nominations never hard-gate direct source retrieval.**

If the global profile fails to nominate the correct document, the direct child lane must still have a path to recover it. This protects exact lookups, unusual terminology, codes, and queries whose semantics were not represented in a document-level abstraction.

---

# 5. Current Graph behavior

## VERIFIED CURRENT AT ARCHITECTURAL LEVEL

Graph retrieval is a live part of the runtime dependency chain. The future architecture must preserve the distinction between actual graph traversal and merely placing graph-like text into an LLM prompt.

Target graph path:

```text
Hybrid/source seeds
    ↓
canonical entity resolution
    ↓
Neo4j traversal with controlled hops
    ↓
Postgres fact / evidence / chunk hydration
    ↓
rerank
    ↓
source evidence
```

## PROPOSED TARGET

`SEEALSO`, `BRIDGE`, `LATENT-PATTERN`, and similar global-profile atoms can help decide **when graph assist is worth invoking**, but these atoms are routing hypotheses, not graph evidence.

The graph remains a separate evidence-expansion mechanism.

---

# 6. Current Wildcard / parent-enrichment behavior

## VERIFIED CURRENT

The control plane recognizes `parent_enrichment` as a non-blocking owner-triggered stage outside the normal DAG. The chat/runtime request model also still carries a `latent` flag labeled for the legacy latent-transfer path.

An API/runtime-side enrichment production path has been observed in `orchestrator/orchestrator/api/ui.py`; therefore enrichment is not safe to treat as an orphaned worker solely because it is outside the normal stage sequence.

## TRACE-BEFORE-CUTOVER

Before stopping enrichment, enumerate all of the following with repository search/tests:

```text
PRODUCERS
  API endpoints / UI actions
  manual owner-triggered minting
  ticket creators
  outbox/event producers
  backfill scripts

WORKERS
  enrichment / latent-transfer handlers
  retry handlers
  verifier hooks

READERS
  Wildcard runtime
  query compiler
  candidate engine
  debug/admin APIs
  UI/document inspection
  evaluation scripts

STATE
  stage registrations
  tables / rows
  receipts / projections
  Qdrant representations
  feature flags / env vars
```

## User decision for vNext Wildcard

**Do not build a new Wildcard executor now.**

The migration should index semantic surfaces that could support a future Wildcard/Research mode, then prove they materially improve retrieval. If they do not, no new Wildcard needs to be built.

## Safe retirement sequence

```text
1 inventory every producer and reader
2 add profile/maps in shadow
3 qualify new retrieval substrate
4 disable NEW enrichment minting behind a reversible flag
5 retain old enrichment reads for rollback window
6 remove runtime readers
7 remove ticket/event producers
8 remove stage registration / workers
9 remove projection cleanup hooks
10 drop old tables/indexes only after rollback window
```

---

# 7. Summary + deterministic compiler inventory

The user specifically suspected an older deterministic parent/section summary compiler. The current repo contains **multiple different concepts that must not be conflated**.

## 7.1 `summary_worker.py` / `summary_worker_impl.py`

### VERIFIED CURRENT

The summary worker family still exists and owns parent/document/corpus semantic-summary work. These artifacts are not all blocking for current query readiness, but they still have downstream readers.

### Classification

**BRIDGE**, then ablate. Do not retire merely because the stages are non-blocking.

---

## 7.2 `compile_objects_worker.py`

### VERIFIED CURRENT

A separate deterministic/structured compile stage still exists. It belongs to the artifact/summary-enrichment family but should not automatically be labeled “the parent summary compiler.” Its outputs may support structured concepts/procedures or downstream semantic stages.

### Classification

**TRACE-BEFORE-CUTOVER**, likely **KEEP** or **BRIDGE** depending on reader inventory.

---

## 7.3 `retrieval_summaries`

### VERIFIED CURRENT

`retrieval_summaries` remains a durable Postgres artifact family. `api/ui.py` includes it in corpus projection-identity cleanup and purge logic. It is also used by current document/section browsing behavior and by summary-based query compilation/ranking paths.

The deletion code treats retrieval summary IDs as projected IDs whose projection receipts must be removed. This proves the summary representation participates in the projection lifecycle, not just a dead historical table.

### Classification

**BRIDGE / DUAL-RUN**, then ablate.

### Retirement gate

No deletion until:

- runtime/UI readers = 0;
- compiler title ranker no longer depends on section/document summary representations, or has a qualified replacement;
- projection receipts no longer expect these IDs;
- corpus purge logic has been migrated;
- shadow/ablation metrics show no unacceptable regression.

---

## 7.4 `document_summaries.major_concepts`

### VERIFIED CURRENT FROM PRIOR REPO TRACE

The current `doc_profile_worker` reads `document_summaries.major_concepts` as optional input. That is a hidden upstream semantic dependency.

### Classification

**BRIDGE** until the vNext global document fingerprint/profile no longer reads it.

### Required migration

The vNext profile input should derive its semantic context from deterministic source/document structure rather than depending on a legacy generated document summary. Once that reader is removed and measured quality holds, the summary writer can be considered for retirement.

---

# 8. Corpus-aware top-K title injection path

## VERIFIED CURRENT

`orchestrator/orchestrator/api/ui.py::_compiler_titles()` builds corpus-aware title context for the query compiler.

The code:

1. loads the document catalog (`doc_id`, `source_name`);
2. obtains the current corpus Qdrant collections;
3. searches representations of:
   - section summaries,
   - document summaries,
   - child chunks;
4. uses the compiler-context ranker to convert those hits back to document ranking;
5. selects titles;
6. passes those titles to `compile_plan(...)`.

The ranking mode can be dense or sparse; failure degrades to title-overlap ranking. The override constructor explicitly uses `knobs.top_n or 40`, confirming the top-40 fallback behavior.

This is a dependency chain, not one isolated prompt feature:

```text
section-summary vectors ─┐
document-summary vectors ├─→ document ranker ─→ selected titles ─→ query compiler
child vectors ────────────┘
```

## MIGRATION BRIDGE

Do not immediately replace this with document profiles. Instead run the following ablation arms:

```text
A  titles from current summary/child ranker
B  titles from child-only ranker
C  profile nominations only
D  current titles + profile nominations
E  profile nominations + direct retrieval, no title block
```

Measure compiler plan quality and downstream retrieval, not just whether the “right title” appears.

## Retirement decision

The title context may survive as a cheap corpus identity prior even after summary representations retire. If summary vectors are removed, its candidate inputs can be rebuilt from child/profile nominations without changing the query compiler contract.

---

# 9. Current Postgres / Qdrant / Neo4j dependency surface

## 9.1 Postgres — authoritative

Current and migration-relevant families include:

```text
runs
stage_tickets
stage_attempts
receipts
outbox_events
artifacts
projection_attempts
projection_receipts

documents
chunks

retrieval_summaries
parent_summaries
document_summaries
corpus_summaries
summary_artifacts
summary_jobs

concept_families
procedure_artifacts
concept_artifacts

mentions
relation_candidates
canonical_entities
canonical_memberships
canonicalization_decisions
facts
evidence
```

The corpus-delete implementation proves that cleanup correctness depends on knowing every projected entity identity. New profile/map tables must therefore be wired into purge/rebuild logic before they are considered production complete.

## 9.2 Qdrant — rebuildable projection

Current source/summary representations feed retrieval and compiler context. New parent maps should live in an additive collection/representation contract rather than replacing the source vector collection in place.

Recommended collection:

```text
polymath_document_parent_maps_<embedding_contract>
```

One point per eligible parent.

Payload:

```text
doc_id
parent_id
corpus_id
alias
heading_path
chunk_index / parent_ordinal
profile_contract
map_hash
source_text_hash
```

Vector text:

```text
routing_signature + hooks + compact heading
```

## 9.3 Neo4j — rebuildable graph projection

Do not couple parent-map readiness to graph semantic atoms. Graph readiness should continue to mean that the required canonical graph projection exists and passes its own verification.

## Migration requirement

Every new projected representation must receive:

- stable deterministic identity;
- projection receipt semantics;
- verifier coverage;
- delete/purge coverage;
- backfill/rebuild path;
- contract/version tag.

---

# 10. Final retrieval target architecture

## PROPOSED TARGET

The final design has two semantic scales and one factual-evidence floor.

```text
                         DOCUMENT
                            │
             ┌──────────────┴──────────────┐
             │                             │
             ▼                             ▼
  deterministic global          deterministic parent
     source fingerprint             skeleton manifest
      ≤ 2K tokens                         │
             │                             ▼
             ▼                       local small model
       Groq Compound                 compact MAP records
   one strong call / doc                  │
             │                             ▼
             ▼                     parent semantic maps
   global semantic profile                │
             └──────────────┬──────────────┘
                            ▼
                     routing substrate
                            │
                            ▼
                      SOURCE CHUNKS
                            │
                            ▼
                       cross-encoder
                            │
                            ▼
                    factual evidence
```

The distinction is intentional:

```text
profile / maps = routing intelligence
source chunks   = factual authority
```

---

# 11. Old → new component bridge matrix

| Current component | Current dependency | Target | Classification | Cutover condition |
|---|---|---|---|---|
| source chunks/parents | all retrieval and evidence | remain factual floor | **KEEP** | never removed by this migration |
| source Qdrant vectors | direct retrieval | direct lane stays active | **KEEP** | n/a |
| canonical graph | graph retrieval | real graph assist | **KEEP** | n/a |
| `retrieval_summaries` | UI, routing, projection lifecycle | parent maps/profile or child-derived context | **BRIDGE / DUAL-RUN** | all readers migrated + ablation pass |
| parent summaries | document/corpus hierarchy | optional legacy context | **BRIDGE** | downstream readers removed |
| document summaries | `doc_profile.major_concepts`, ranking | deterministic fingerprint + global profile | **BRIDGE** | profile no longer reads it + ablation pass |
| corpus summaries | navigation/context if still read | direct corpus planning/profile aggregation | **TRACE** | exact readers inventoried |
| `compile_objects` | structured artifact support | retain if unique | **TRACE / likely KEEP** | only after reader inventory |
| `parent_enrichment` | legacy latent/Wildcard path | no vNext replacement yet | **DUAL-RUN → RETIRE** | old runtime/producers gone |
| current `doc_profile` | semantic document artifact | profile vNext | **UPGRADE / KEEP** | vNext contract backfilled |
| ranked title context | query compiler | titles + profile nomination, then ablate | **KEEP initially** | compiler/retrieval non-regression |
| query compiler | stage-0 intent/compiler | compiler + semantic route hints | **KEEP / EXTEND** | no replacement required |
| new parent maps | none | localize document candidate to parent | **ADD** | qualification gates pass |
| new readiness verifier | none | contract-aware readiness | **ADD** | report-only first |

---

# 12. Hidden dependency gap analysis

The migration must explicitly close these gaps before any destructive cutover.

## GAP-01 — non-blocking does not mean unused

**Evidence:** summary and enrichment stages can be non-blocking while their artifacts remain runtime inputs.

**Risk:** deleting writers because `QUERY_READY` ignores them causes slow, delayed breakage rather than immediate ingest failure.

**Closure:** reader/writer inventory test and feature-flagged stop-write phase.

---

## GAP-02 — query compiler depends on summary representations

**Evidence:** `_compiler_titles()` searches section-summary, document-summary, and child representations before injecting titles.

**Risk:** summary retirement silently changes query interpretation even if direct retrieval itself still works.

**Closure:** explicit compiler-context ablation and replacement path.

---

## GAP-03 — synthesis no longer cites summaries, but routing still consumes them

**Evidence:** `_evidence_legend()` filters summary text kinds from citation-bearing evidence while upstream ranking still uses summaries.

**Risk:** assuming “summaries are not in the prompt” means “summaries are unused.”

**Closure:** separate routing-dependency inventory from evidence-dependency inventory.

---

## GAP-04 — `doc_profile` has an upstream legacy-summary input

**Risk:** removing `document_summaries` changes profile quality or causes null/fallback behavior.

**Closure:** make vNext fingerprint self-sufficient; then ablate legacy input.

---

## GAP-05 — projected entity cleanup

**Evidence:** corpus deletion explicitly purges projection receipts for `retrieval_summaries` and other derived artifacts.

**Risk:** new maps/profile points survive corpus deletion or old receipts survive collection replacement, causing false “already projected” states.

**Closure:** add map/profile projected IDs to delete/rebuild coverage and verifier tests.

---

## GAP-06 — global readiness flip can strand legacy documents

**Closure:** retrieval-contract/generation-aware readiness and staged backfill.

---

## GAP-07 — parent map completeness can be semantically bad

A syntactically complete map set can contain generic or misattached maps.

**Closure:** semantic quality gate:

```text
self-retrieval to own parent
identifier retention
negation/counterexample preservation
source-support score
semantic duplication score
```

---

## GAP-08 — exact identifier failure

Abstraction lanes may miss `021`, `AU21`, `CVE-2026-0217`, part numbers, or unusual acronyms.

**Closure:** direct source lane remains unrestricted; skeletons preserve identifiers; map compiler tests exactness.

---

## GAP-09 — prompt injection during indexing

Parent skeleton source is untrusted corpus content.

**Closure:** map model receives a strict data-only contract; no tools/external actions; injection fixtures are part of acceptance.

---

## GAP-10 — long-document worker monopolization

**Closure:** durable per-document manifests plus fair batch scheduling across documents.

---

## GAP-11 — transaction scope around inference

**Closure:** never hold a DB transaction open over network or local model inference.

---

## GAP-12 — old feature flags and request fields

The runtime still carries compiler/retrieval/title-ranker/latent flags.

**Closure:** every retired lane must include config/env/request-schema cleanup after rollback, not before.

---

# 13. SQL schema migration order

## M1 — additive only

Create durable map ledgers without changing existing tables.

### `document_parent_map_batches`

```text
batch_id
run_id
doc_id
profile_contract
ordinal
status              pending | leased | partial | done | error
expected_count
valid_count
alias_manifest      JSONB
input_hash
raw_response_hash
inference_backend
model
attempt_count
lease_owner
lease_expires_at
last_error
created_at
updated_at
```

### `document_parent_maps`

```text
doc_id
parent_id
profile_contract
alias
batch_id
routing_signature
hooks               JSONB
map_source
inference_backend
model
source_text_hash
skeleton_hash
map_hash
active
created_at
updated_at
```

Required invariant:

```text
ONE active map per (doc_id, parent_id, profile_contract)
```

### Optional derived readiness ledger

Add only after deciding whether a materialized table is preferable to a view/verification result.

## M2 — no old schema deletion

Backfill and verify new tables while legacy summaries/enrichment continue unchanged.

## M3 — stop-write markers

After query cutover, mark legacy writers disabled via config/contract first. Do not drop columns/tables.

## M4 — cleanup migration

Only after rollback window and zero-reader test:

- remove obsolete stage-owned tables;
- remove obsolete indexes;
- update purge scripts;
- update migrations/tests documenting intentional removal.

---

# 14. Qdrant blue/green index migration

Do not mutate the existing source/summary collection contract in place.

```text
CURRENT COLLECTIONS
      │
      ├──────────────► remain live
      │
      ▼
NEW parent-map collection
      │
      ▼
shadow query
      │
      ▼
qualified dual-read
      │
      ▼
production route
```

Required map projection checks:

```text
Postgres active map count
    == expected eligible parent count
    == projected point count for contract

unresolved parents == 0
unknown aliases == 0
wrong-parent attachment == 0
```

Collection naming must include embedding/representation contract so re-embedding can occur without invalidating previous live readers.

---

# 15. Control-plane DAG migration

## Phase A — shadow / non-blocking

New profile/map stages may fail without demoting a legacy-ready document.

```text
existing blocking DAG
    ↓
legacy QUERY_READY

parallel semantic lane
    global profile vNext
    parent maps
    projection
    verifier report
```

## Phase B — new-document contract gate

Once frozen tests pass, documents ingested under `retrieval-vnext-*` require semantic readiness before they are considered vNext-query-ready.

## Phase C — legacy backfill promotion

Legacy documents receive the new contract asynchronously through normal durable tickets/manifests.

## Phase D — old semantic stages stop writing

Only after no production query path requires their newly generated artifacts.

## Phase E — stage universe cleanup

Remove retired stage registration only when:

- no producer creates its tickets;
- no worker consumes them;
- no verifier expects them;
- no admin/backfill endpoint emits them;
- no rollback plan depends on restarting them.

---

# 16. QUERY_READY generation / backfill migration

Recommended state model:

```text
Document D / Generation G

LEGACY_READY
    │
    ├─ normal legacy queries continue
    │
    └─ backfill semantic contract
            ↓
       PROFILE_READY
            ↓
       MAP_COMPLETE
            ↓
       MAP_PROJECTED
            ↓
       VERIFIED_VNEXT
            ↓
       QUERY_READY[VNext]
```

Do not rewrite historical receipt truth. Add a new contract verdict.

### Backfill completeness report

For every corpus:

```text
total_live_documents
legacy_query_ready
vnext_profile_ready
vnext_maps_complete
vnext_maps_projected
vnext_verified
vnext_failed
vnext_degraded
```

Cutover requires a documented policy for failures; do not silently mark a partially mapped document ready.

---

# 17. Query-time dual-read migration

## Shadow phase

Run new semantic routing without affecting production ranking; receipt:

```text
profile_doc_candidates
parent_map_candidates
resolved_parent_ids
shadow_child_candidates
shadow_overlap_with_final
shadow_gold_hit
latency_ms
```

## Dual-read phase

```text
QUERY
  │
  ├── CURRENT DIRECT / HYBRID LANES ───────────┐
  │                                            │
  ├── GLOBAL PROFILE SEARCH                    │
  │       ↓                                    │
  │    nominated docs                          │
  │       ↓                                    │
  │    ONE parent-map search filtered by docs  │
  │       ↓                                    │
  │    parent ids                              │
  │       ↓                                    │
  │    child hydration / filtered deepening ───┤
  │                                            │
  └── GRAPH ASSIST when requested ─────────────┤
                                               ▼
                                         candidate union
                                               ↓
                                             dedupe
                                               ↓
                                         cross-encoder
                                               ↓
                                         SOURCE EVIDENCE
```

### Performance rule

Do not issue one Qdrant parent-map search per nominated document. Use one filtered search across the nominated document set when the store supports it.

---

# 18. Global profile / profile-atom integration

## Input

Build an adaptive deterministic fingerprint from source structure and representative source material.

```text
PROFILE_CONTEXT_BUDGET_MIN = 500
PROFILE_CONTEXT_BUDGET_MAX = 2000
```

2,000 is a ceiling, not required padding. Benchmark 500 / 1000 / 1500 / 2000 and choose the smallest quality plateau.

## Source-anchored fields

```text
ONE
SUMMARY
TOPIC
TERM
Q
```

These should remain defensible from source material.

## Routing-inferred fields

```text
SEARCH
THEORY
CONCEPT
LATENT-PATTERN
ANCHOR
TENSION
BRIDGE
INVERSION
BOUNDARY
SEEALSO
RECALLQ
```

These are **routing hypotheses**, not factual citations.

### Naming note

The existing parser aliases `PATTERN`/`PATTERNS` into `CONCEPT`; retain the explicit `LATENT-PATTERN` label if a distinct field is required.

## Model division of labor

```text
Groq Compound
    → one strong global semantic profile call/document
```

Do not make the global profile depend on old generated `document_summaries` once vNext is promoted.

---

# 19. Parent-map integration

## ParentSkeleton

```text
ParentSkeleton
    parent_id
    alias
    ordinal
    heading_path
    region_role
    source_position
    excerpt
    key_terms[]
    identifiers[]
    text_hash
    skeleton_hash
```

### Deterministic skeleton rules

```text
1 normalize source text
2 rough sentence segmentation
3 discard boilerplate / too-short candidates
4 lexical salience score
5 choose highest-scoring extractive sentence/clause
6 earliest candidate wins ties
7 truncate deterministically
8 extract 3–5 high-information terms
9 preserve rare IDs/acronyms/numbers separately
```

No LLM should be required to create the skeleton.

## MAP contract

```text
MAP|P0017|Weight/time qualities govern perceived force|weight;time;impact
```

Constraints:

```text
signature <= 10–12 words
exactly 3 hooks
hooks normally 1–4 words
every expected alias exactly once
no invented aliases
preserve IDs/numbers/acronyms
preserve negation/boundary/counterexample meaning
```

## Compiler behavior

Classify each response row as:

```text
valid
missing
invalid
duplicate
unknown_alias
```

Tolerate whitespace/delimiter repair only when unambiguous. Unknown aliases can never create a new parent. Persist valid partial output; retry only unresolved aliases.

## Readiness floor

Every live eligible parent has one active compiled semantic map. Noise/non-content regions receive an explicit exclusion disposition such as:

```text
EXCLUDED_REGION
```

Final verifier:

```text
unresolved_eligible_parents = 0
fallback_only_eligible_parents = 0
```

---

# 20. Resolution Lift / Vocabulary Bridge integration

The purpose of the vocabulary bridge is not to fabricate evidence; it allows a user’s phrase to resolve toward source terminology the user may not know.

Example:

```text
user phrase
    "why does the punch feel heavy?"
        ↓
query compiler / semantic bridge
        ↓
possible source vocabulary
    Weight effort
    force quality
    acceleration / impulse
        ↓
profile + parent-map retrieval
        ↓
source chunks
```

## Guardrail

The bridge can expand a query but cannot become factual authority. Expanded terms must still land on source chunks before entering the answer evidence set.

## Migration

Reuse current `vocabulary`/compiler capability only where it provides measurable unique resolution. Do not keep an old vocabulary stage merely because it exists; ablate it against profile atoms, sparse retrieval, and query compiler expansion.

---

# 21. SEEALSO / BRIDGE → graph-assist integration

Profile atoms such as `SEEALSO` and `BRIDGE` can become **planner hints**:

```text
query resembles cross-domain relationship
    ↓
profile BRIDGE / SEEALSO candidates
    ↓
canonical entity seed check
    ↓
if useful → actual Neo4j traversal
    ↓
source hydration
```

They must not be materialized as factual graph edges unless supported by the normal graph extraction/canonicalization/evidence contract.

---

# 22. Parent-enrichment retirement plan

## Stage 1 — dependency census

Create a repository assertion/report that finds every occurrence of:

```text
parent_enrichment
latent
LATENT-TRANSFER
legacy Wildcard mode symbols
old enrichment table names
old enrichment representation kinds
old enrichment feature flags
```

Classify every hit as producer, worker, reader, test, migration, or dead documentation.

## Stage 2 — prevent new dependency growth

Document enrichment as legacy and prohibit new readers.

## Stage 3 — new retrieval shadow qualification

Profile/maps must demonstrate they cover the routing/localization value that is actually required by normal Hybrid retrieval. This does **not** mean recreating legacy Wildcard behavior.

## Stage 4 — stop minting new enrichments

Disable production/API creation behind a reversible switch. Continue legacy reads temporarily.

## Stage 5 — zero-reader proof

A test/repo scan plus runtime telemetry must show no production path reads enrichment.

## Stage 6 — unregister

Remove:

```text
API producers
outbox/ticket producers
worker routing
stage registry entry
feature flag/request plumbing
cleanup paths
```

## Stage 7 — data cleanup

Drop old tables/indexes only after rollback expires.

---

# 23. Summary/compiler keep-vs-retire ablation

Run this matrix on a frozen query set:

| Arm | Section summaries | Document summaries | Title context | Global profile | Parent maps |
|---|---:|---:|---:|---:|---:|
| A legacy | yes | yes | yes | current | no |
| B child-only | no | no | child-derived | no | no |
| C profile | no | no | no | yes | no |
| D profile+maps | no | no | optional | yes | yes |
| E bridge | yes | yes | yes | yes | yes |

Measure:

```text
document recall
parent recall / MRR
child recall
cross-encoder final recall
exact lookup success
compiler-plan correctness
unsupported abstraction rate
query latency
prompt tokens
index size
ingest cost
```

### Retirement rule

A legacy summary layer is retired only if the best no-layer arm meets the frozen non-regression threshold on the tasks the layer currently serves.

---

# 24. Title-context compiler migration

## Current behavior to preserve initially

The compiler is stage 0 of normal streaming turns when enabled. It has deterministic fallback, lane failover, and corpus title context.

## Target bridge

Rather than changing `compile_plan()` immediately, alter the **title candidate provider** behind it:

```text
Phase 1
current summary/doc/child title ranker

Phase 2
current ranker + profile document candidates

Phase 3
child/profile-derived title ranker, summary representations disabled in shadow

Phase 4
keep reduced title block OR retire title block based on compiler-plan evaluation
```

This minimizes query-compiler churn while summary representations are being removed.

---

# 25. Model/backfill routing: Compound + local maps + Compound Mini fallback

## Global profile

```text
one Groq Compound request / document when possible
```

The global task needs document abstraction, analogical structure, tensions, boundaries, and cross-domain routing hints.

## Parent maps

Preferred model tournament:

```text
1 LFM2.5-350M
2 LFM2.5-1.2B-Instruct
3 LFM2.5-2.6B
4 groq/compound-mini as fallback/control
```

Promotion:

```text
350M passes → use 350M
else 1.2B passes → use 1.2B
else 2.6B passes → use 2.6B
else Compound Mini
```

Backend contract should be interchangeable:

```text
map_backend = local_lfm | groq_compound_mini
```

The SQL, compiler, readiness, and retrieval semantics must not change by backend.

---

# 26. Existing corpus reindex/backfill procedure

```text
FOR each live document under legacy contract
    │
    ├─ verify source parents/chunks still match current generation
    │
    ├─ build deterministic global fingerprint
    │
    ├─ generate/compile profile vNext
    │
    ├─ build deterministic parent skeleton manifest
    │
    ├─ create durable map batch manifests
    │
    ├─ infer maps
    │
    ├─ repair unresolved only
    │
    ├─ verify exact expected manifest completeness
    │
    ├─ project profile/maps
    │
    ├─ verify projection receipts/counts
    │
    └─ mark vNext retrieval contract qualified
```

### Idempotency requirements

- source hash changes invalidate maps for that parent;
- completed identical maps are not regenerated;
- global profile is not rerun just because one map batch failed;
- expired batch lease can be safely reclaimed;
- document deletion while backfill is running terminates or invalidates the run safely;
- projected identity includes contract/hash so stale receipts cannot mask missing points.

---

# 27. New-document ingest procedure

After vNext blocking gate is enabled:

```text
INTAKE
  ↓
EXTRACT / PARENT-CHILD STRUCTURE
  ↓
SOURCE PROJECTIONS
  ↓
CANONICAL / GRAPH PROJECTIONS
  ↓
GLOBAL PROFILE
  ↓
PARENT SKELETON MANIFEST
  ↓
PARENT MAP INFERENCE
  ↓
MAP COMPILER / REPAIR
  ↓
PROFILE + MAP PROJECTION
  ↓
RETRIEVAL VERIFIER
  ↓
QUERY_READY[vNext]
```

Existing optional legacy summary/enrichment stages may coexist during migration but must not become accidental prerequisites of the new profile/map contract.

---

# 28. Failure recovery / rollback

## Inference transaction pattern

Never:

```text
BEGIN TRANSACTION
  → call Groq / local model
  → wait
  → write
COMMIT
```

Use:

```text
PREPARE
  short transaction creates manifest

WORKER
  lease batch
  commit lease
  infer outside transaction
  compile outside transaction
  short transaction persists valid results/status

AGGREGATOR
  calculate unresolved
  repair or finalize
```

## Rollback switches

Maintain independent flags for:

```text
profile_generation
parent_map_generation
parent_map_projection
profile_runtime_route
parent_map_runtime_route
vnext_readiness_blocking
legacy_enrichment_minting
legacy_summary_writers
legacy_summary_runtime_readers
```

This permits rollback of query behavior without discarding generated artifacts.

## Required rollback invariant

Until legacy readers are physically removed, disabling vNext routing must return the system to the previously qualified retrieval contract without re-ingesting the corpus.

---

# 29. Acceptance gates

## Parent-map compiler gates

```text
alias completion              100%
invented aliases              0
wrong-parent attachment       0
exact identifier loss         0
prompt-injection failures     0
unsupported map claims        ~0 / below frozen threshold
```

Test examples must include:

```text
021
AU21
CVE-2026-0217
negation
counterexamples
boundary conditions
duplicate headings
HTML/transcript noise
prompt injection embedded in source
```

## Retrieval gates

```text
document Recall@K
parent Recall@K
parent MRR
child Recall@K
final reranked evidence recall
exact lookup pass rate
profile-only miss recovery by direct lane
graph route correctness
query compiler plan accuracy
```

## Operational gates

```text
zero unresolved eligible parents at ready
projection counts match authoritative rows
no stale receipt false-positive
crash/restart idempotency
expired lease recovery
large-document fairness
corpus delete removes new projections/receipts
generation replacement invalidates stale maps
```

## Master E2E

Contract:

```text
DOCUMENT-SEMANTIC-ROUTE-E2E-V1
```

Laban-style semantic query:

```text
"why does an anime punch feel heavy?"
    ↓
global profile finds correct document
    ↓
parent map finds Weight/Effort neighborhood
    ↓
children provide actual source passage
    ↓
cross-encoder preserves it
    ↓
answer cites source evidence
```

Exact lookup control:

```text
"What is code 021?"
```

must still succeed even if profile/map abstraction contributes nothing.

---

# 30. Exact implementation slices and dependency order

The implementation should proceed in this order. A later slice must not start its destructive portion until the prior slice’s acceptance gate passes.

## S0 — Freeze migration audit

**Artifact:** this document.  
**Goal:** make old readers/writers/states explicit before durable schema decisions.

Deliverables:

- current dependency map;
- reader/writer matrix;
- retirement rules;
- feature-flag rollback plan.

---

## S1 — Automated dependency census

Add a repo test/script that inventories legacy semantic symbols/tables/stages.

Search targets include:

```text
retrieval_summaries
parent_summaries
document_summaries
corpus_summaries
summary_artifacts
summary_jobs
compile_objects
parent_enrichment
latent
LATENT-TRANSFER
REPRESENTATION_KIND_SECTION_SUMMARY
REPRESENTATION_KIND_DOCUMENT_SUMMARY
POLYMATH_CHAT_COMPILER_TITLES_RANK
```

Output each occurrence as reader/writer/producer/config/test/migration.

**Gate:** no “unknown runtime” occurrence before retirement work.

---

## S2 — Parent skeleton + MAP compiler

Suggested files:

```text
shared/polymath_shared/document_profile/parent_skeleton.py
shared/polymath_shared/document_profile/map_compiler.py

tests/determinism/test_parent_skeleton.py
tests/determinism/test_parent_map_compiler.py
```

Tests: 1, 80, 1000 parents; transcript; HTML; technical prose; duplicate headings; exact IDs; partial response; unknown alias; duplicate alias; injection text.

---

## S3 — Local model tournament

Benchmark real parent skeletons against a frozen control/gold set.

Metrics:

```text
skeleton_tokens_per_parent
MAP_tokens_per_parent
alias completeness
identifier retention
negation/counterexample accuracy
map→source support
semantic duplication
retrieval MRR / Recall
wall-clock throughput
peak RAM / VRAM
```

**Gate:** promote smallest model meeting semantic/retrieval thresholds.

---

## S4 — Additive SQL ledgers

Only now create parent-map batch/map tables and indexes.

**No old table changes.**

---

## S5 — Durable map worker/manifests

Implement leases, partial persistence, unresolved repair, crash recovery, and fair scheduling.

**Gate:** kill/restart tests produce exactly the same active map set.

---

## S6 — Parent-map Qdrant projector

Add contract-named collection, receipts, verifier, rebuild, and purge coverage.

**Gate:** Postgres authoritative rows == projected points.

---

## S7 — Global profile vNext independence

Upgrade fingerprint/profile fields and remove the *need* for legacy `document_summaries.major_concepts` in the vNext path.

Do not stop the legacy summary writer yet.

**Gate:** profile quality/retrieval ablation passes without legacy summary input.

---

## S8 — Shadow runtime route

Run global profile → parent maps → child deepening as shadow. Record candidate overlap and misses.

**Gate:** no production rank effect yet.

---

## S9 — Dual-read feature flag

Allow Hybrid to consume new candidates while direct child retrieval remains unrestricted.

**Gate:** frozen evaluation non-regression and exact lookup control passes.

---

## S10 — Query compiler title-context bridge

Add profile-derived document nominations into the current corpus title context and run ablations.

**Gate:** determine whether summary vectors remain necessary for compiler context.

---

## S11 — Report-only vNext readiness verifier

Produce per-document contract verdicts without affecting availability.

**Gate:** verifier stable across corpus backfill and restart.

---

## S12 — Existing corpus backfill

Backfill profile vNext + parent maps for all live documents.

**Gate:** target corpus coverage reached; failures explicitly classified.

---

## S13 — New-document blocking gate

New generations under the vNext contract require complete profile/maps/projections.

Legacy-ready documents remain queryable.

---

## S14 — Existing corpus cutover

Promote successfully backfilled legacy docs to vNext retrieval contract.

**Gate:** query receipts/metrics demonstrate stable production behavior.

---

## S15 — Disable legacy enrichment producers

Stop new `parent_enrichment` minting behind rollback flag.

Do not delete historical data or readers yet.

---

## S16 — Remove legacy runtime readers

Remove/replace:

- enrichment/Wildcard reads;
- summary reads no longer justified;
- summary-based query-compiler inputs if the selected ablation says they are redundant.

**Gate:** automated dependency census reports zero required production readers.

---

## S17 — Stop obsolete legacy writers/stages

Disable summary/enrichment writers whose outputs now have zero readers.

**Gate:** observe full rollback window with no regression.

---

## S18 — Physical cleanup

Only now:

- remove retired stage registration;
- remove obsolete workers;
- remove feature flags/request fields;
- remove old Qdrant representation kinds/collections;
- remove old tables/columns/indexes;
- update corpus purge/rebuild logic;
- update architecture/handoff docs.

---

# Dependency-critical “do not” list

```text
DO NOT make profile/maps globally blocking before legacy contract/backfill exists.
DO NOT delete enrichment code merely because parent_enrichment is non-blocking.
DO NOT retire summaries before removing their compiler/UI/profile readers.
DO NOT remove summary vectors without measuring query-compiler title-context regression.
DO NOT use profile/map text as factual citation evidence.
DO NOT hard-gate direct source retrieval behind document-profile nominations.
DO NOT hold SQL transactions open across inference.
DO NOT retry every parent when only a subset of MAP aliases failed.
DO NOT let unknown model aliases create parent identities.
DO NOT mutate current Qdrant collections in place for the new representation contract.
DO NOT trust projection receipts unless verifier confirms points actually exist.
DO NOT build Wildcard vNext until the semantic substrate proves it is worth building.
```

---

# Source-of-truth files inspected / required follow-up trace

## Verified current files

```text
control/control/tickets.py
workers/workers/summary_worker.py
workers/workers/summary_worker_impl.py
workers/workers/compile_objects_worker.py
orchestrator/orchestrator/api/ui.py
orchestrator/orchestrator/api/chat_retrieval.py
orchestrator/orchestrator/api/corpus_plan.py
docs/wiki/reports/2026-09-07/DEPENDENCY_MAP.md
docs/wiki/reports/2026-09-07/ARCHITECTURE_STATE.md
```

Previously verified relevant files/plans:

```text
workers/workers/doc_profile_worker.py
shared/polymath_shared/document_profile/context.py
docs/wiki/plans/DOCUMENT-PROFILE-V1.md
shared/polymath_shared/receipts.py
```

## Must be exhaustively traced by S1 before destructive migration

```text
exact parent_enrichment worker/handler path(s)
all legacy Wildcard/latent readers
all retrieval_summaries readers and writers
all parent/document/corpus summary readers
all compile_objects output readers
all vocabulary-stage readers
all admin/backfill scripts that mint legacy semantic stages
all representation-kind filters for section/document summaries
all purge/rebuild/receipt paths for derived projected artifacts
all feature flags/env vars for retired lanes
```

The fact that a filename is not obvious or a stage is not in the normal DAG is **not** evidence that it is unused.

---

# Final migration invariant

The end state should satisfy all of the following simultaneously:

```text
1 Every factual answer can be traced to source chunks.
2 Semantic document profiles improve discovery without becoming evidence.
3 Every eligible parent has one verified active semantic map.
4 Direct child retrieval remains capable of exact-match recovery.
5 Graph mode performs real graph traversal and source hydration.
6 Legacy enrichment has zero producers, readers, stage dependencies, and data obligations before deletion.
7 Legacy summary layers are retained only where ablation proves unique value.
8 Query compiler no longer has hidden dependencies on artifacts scheduled for retirement.
9 QUERY_READY is explicit about the retrieval contract/generation being satisfied.
10 Every derived projection has authoritative Postgres identity, receipts, verifier, rebuild, and purge coverage.
11 Existing corpora migrate without forced re-ingest and without availability loss.
12 A rollback can restore the previous qualified retrieval behavior until the retirement window closes.
```

The architectural principle is therefore:

> **Add the new semantic routing substrate first; prove it against the current runtime; migrate every reader; change readiness by contract; then retire the old artifacts from the outside in.**


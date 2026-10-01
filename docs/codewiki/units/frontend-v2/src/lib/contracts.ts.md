# unit: frontend-v2/src/lib/contracts.ts
anchor: frontend-v2/src/lib/contracts.ts:1-404

## purpose
Typed mirrors of the backend response contracts frontend-v2 consumes; header states "the backend is the authority. Every type here describes a response shape the backend already owns" and "Nothing here computes policy — if a field is absent, the UI shows it as unknown, it never derives a substitute" — frontend-v2/src/lib/contracts.ts:2-7 [DERIVED].
Declarations only: 57 exported interfaces, 1 const (`PUBLIC_MODES`), 1 derived type (`PublicMode`); zero imports, zero functions — frontend-v2/src/lib/contracts.ts:189-190 plus FACTS.symbols [DERIVED].
Consumed module-wide by: `frontend-v2/src/App.tsx`, `frontend-v2/src/lib/_small-modules`, `frontend-v2/src/lib/api.ts`, `frontend-v2/src/lib/chat.ts`, `frontend-v2/src/lib/deep.ts` — FACTS.importers [DERIVED].

## public surface
| symbol | kind | signature (shape) | anchor | used by |
|---|---|---|---|---|
| SemanticReadiness | interface | `/semantic_readiness?corpus_id=` → `verdict: string`, `counts`, `vnext{verdict, pending, parents{eligible,mapped,excluded,unresolved}, profiled?, vnext_served?}` | frontend-v2/src/lib/contracts.ts:13-34 | † |
| DocSummary | interface | row of `/documents/summary?corpus_id=` → `profile_present`, `profile_vnext`, `vnext_ready`, `profile_served?: "vnext" \| "basic" \| null` | frontend-v2/src/lib/contracts.ts:37-54 | † |
| DocumentRow | interface | `GET /documents?corpus_id=` → `doc_id`, `source_name`, `chunks`, `map_active` | frontend-v2/src/lib/contracts.ts:60-71 | † |
| DocumentRun | interface | `run_id`, `status`, `error: string \| null` | frontend-v2/src/lib/contracts.ts:73-78 | † |
| DocumentsResponse | interface | `corpus_id`, `documents: DocumentRow[]`, `runs: DocumentRun[]` | frontend-v2/src/lib/contracts.ts:80-84 | † |
| UploadResult | interface | `POST /upload` → `sha256`, `near_duplicate_override: boolean` | frontend-v2/src/lib/contracts.ts:87-93 | † |
| LlmProvider | interface | `GET /llm/providers` → `api_key` (masked), `api_key_set: boolean`, `models: string[]`, `ready` | frontend-v2/src/lib/contracts.ts:99-108 | † |
| ProviderUpsertBody | interface | `POST /llm/providers` body → `provider`, `api_key?`, `models`, `enabled` | frontend-v2/src/lib/contracts.ts:112-118 | † |
| LlmTestResult | interface | `POST /llm/test` → `ok: boolean`, `model`, `reply?`, `error?` | frontend-v2/src/lib/contracts.ts:121-126 | † |
| ControlPlane | interface | `/control_plane?corpus_id=` → `control_ready{state,label}`, `summary{semantic_ready,blocked,processing_stalled}`, `pools: Record<string, ControlPlanePool>` | frontend-v2/src/lib/contracts.ts:134-144 | † |
| ControlPlanePool | interface | `lanes?`, `queued?`, `processing?`, `retry?`, `failed?`, `provider?: Record<string, number \| null>` | frontend-v2/src/lib/contracts.ts:146-154 | † |
| PoolLanes | interface | `/control_plane/pool/{function}` → `models: { model: string; lanes: PoolLane[] }[]` | frontend-v2/src/lib/contracts.ts:157-160 | † |
| PoolLane | interface | `account_env`, `configured`, `capacity{rpm,tpm,rpd,concurrency,map_batch_cap}`, `live` | frontend-v2/src/lib/contracts.ts:162-171 | † |
| Corpus | interface | `/corpora` → `corpus_id`, `documents`, `query_ready`, `query_enabled` | frontend-v2/src/lib/contracts.ts:174-181 | † |
| PUBLIC_MODES | const | `["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const` | frontend-v2/src/lib/contracts.ts:189 | † |
| PublicMode | type | `(typeof PUBLIC_MODES)[number]` | frontend-v2/src/lib/contracts.ts:190 | † |
| Synthesizer | interface | `/synthesizers` row → `provider`, `provider_label`, `model` (grouping fields) | frontend-v2/src/lib/contracts.ts:195-199 | † |
| ReasoningMode | interface | `{ id: string; label: string; description: string }` | frontend-v2/src/lib/contracts.ts:200 | † |
| RetrievalReceipt | interface | `/chat/stream` `answer.retrieval` → `engine`, `mode`, `arrivals?: Record<string, string[]>`, `degraded?: string[]`, `latency_ms?: number \| Record<string, number \| null>` | frontend-v2/src/lib/contracts.ts:206-233 | † |
| AnswerFrame | interface | `kind: string`, `latency_ms?`, `result?`, `retrieval?: RetrievalReceipt` | frontend-v2/src/lib/contracts.ts:235-240 | † |
| RetrieveResponse | interface | `/retrieve` → `evidence`, `meta{mode, plan_version, evidence_count, degraded}`, `selected_documents`, `trace` | frontend-v2/src/lib/contracts.ts:244-251 | † |
| GraphEntity | interface | `normalized_surface`, `core_type: string \| null`, `mentions`, `entity_id` | frontend-v2/src/lib/contracts.ts:255-258 | † |
| GraphEntities | interface | `contract`, `corpus_id`, `query`, `entities: GraphEntity[]` | frontend-v2/src/lib/contracts.ts:259-261 | † |
| GraphSource | interface | `doc_id`, `chunk_id`, `source_name: string \| null`, `text` | frontend-v2/src/lib/contracts.ts:262-264 | † |
| GraphRelationship | interface | `fact_id`, `predicate`, `direction: "in" \| "out"`, `sources: GraphSource[]`, `source_count` | frontend-v2/src/lib/contracts.ts:265-271 | † |
| GraphRelationships | interface | `relationships: GraphRelationship[]`, `dropped_unattested: number` | frontend-v2/src/lib/contracts.ts:272-277 | † |
| CompareArm | interface | `mode`, `ok: boolean`, `latency_ms`, `retrieval?{lane_sizes, funnel_lanes, union_size, rows}` | frontend-v2/src/lib/contracts.ts:281-295 | † |
| CompareResponse | interface | `question`, `arms: CompareArm[]` | frontend-v2/src/lib/contracts.ts:296-298 | † |
| ReviewScores | interface | `grounding?`, `correctness?`, `unsupported_claims?: string[]`, `verdict?` | frontend-v2/src/lib/contracts.ts:300-304 | † |
| ReviewResponse | interface | `review: ReviewScores \| null`, `parse_error: string \| null`, `raw: string \| null` | frontend-v2/src/lib/contracts.ts:305-308 | † |
| RunSummary | interface | `run_id`, `adapter_id`, `status`, `outcome` | frontend-v2/src/lib/contracts.ts:311-316 | † |
| RunProgressRow | interface | `step_id`, `state`, `visits: number` | frontend-v2/src/lib/contracts.ts:317 | † |
| GateResult | interface | `gate_id?`, `minimum?`, `observed?`, `passed?: boolean` | frontend-v2/src/lib/contracts.ts:318 | † |
| OpenGap | interface | `gap_id?`, `question?`, `evidence_role?`, `hypothesis_id?` | frontend-v2/src/lib/contracts.ts:319 | † |
| Qualification | interface | `gate_results?: GateResult[]`, `open_gaps?: OpenGap[]` | frontend-v2/src/lib/contracts.ts:320-322 | † |
| ScoreRefusal | interface | `record_id?`, `reason_code?`, `detail?` | frontend-v2/src/lib/contracts.ts:323 | † |
| Admission | interface | `admitted?[]`, `rejected?{reason_code?, observation_id?}[]` | frontend-v2/src/lib/contracts.ts:324-327 | † |
| LivedCluster | interface | `community?`, `friction_family?`, `threshold{min_records,min_threads,min_independent_voices}` | frontend-v2/src/lib/contracts.ts:328-331 | † |
| ProductConcept | interface | `name?`, `buyer?`, `form_factor?`, `differentiator?` | frontend-v2/src/lib/contracts.ts:332 | † |
| ConceptReality | interface | `concept_id?`, `status?`, `existing_products?` | frontend-v2/src/lib/contracts.ts:333 | † |
| HypothesisView | interface | `hypothesis{hypothesis_id?, statement?, status?}` | frontend-v2/src/lib/contracts.ts:334 | † |
| RegistryPrior | interface | `registry_record_id?`, `prior_role?`, `label?: string \| null` | frontend-v2/src/lib/contracts.ts:336 | † |
| RegistryTerritory | interface | `territory_id?`, `territory?: string`, `territory_name?: string \| null` | frontend-v2/src/lib/contracts.ts:337 | † |
| RunRegistry | interface | `snapshot: {...} \| null`, `snapshot_ids: string[]`, `priors`, `territories` | frontend-v2/src/lib/contracts.ts:338-341 | † |
| RunView | interface | `run{status, terminal, gap}`, `progress: RunProgressRow[]`, `sections`, `report?: { available: boolean }`, `registry?: RunRegistry \| null` | frontend-v2/src/lib/contracts.ts:342-357 | † |
| DeepResearchPlan | interface | `POST /research/deep/plan` → `goals: DeepPlanGoal[]`, `estimate{searches?, llm_calls?, seconds?}` | frontend-v2/src/lib/contracts.ts:361-365 | † |
| DeepPlanGoal | interface | `{ id: string; goal: string; query: string; move: string }` | frontend-v2/src/lib/contracts.ts:366 | † |
| DeepCoverage | interface | `event: coverage` → `goals`, `documents?: number`, `passages?: number` | frontend-v2/src/lib/contracts.ts:368 | † |
| DeepCoverageGoal | interface | `learnings?: number`, `documents?: number \| string[]` | frontend-v2/src/lib/contracts.ts:369 | † |
| DeepReportModel | interface | `goals?`, `counter?`, `open_questions?: (string \| { question?; text? })[]`, `sources?`, `method?` | frontend-v2/src/lib/contracts.ts:371-375 | † |
| DeepReportGoal | interface | `findings?: DeepFinding[]`, `documents?: number \| string[]` | frontend-v2/src/lib/contracts.ts:376 | † |
| DeepFinding | interface | `text`, `cids?: string[]`, `confidence?` (strong \| single_source \| contested), `move?` | frontend-v2/src/lib/contracts.ts:378 | † |
| DeepCounterFinding | interface | `text`, `cids?: string[]`, `goal_id?` | frontend-v2/src/lib/contracts.ts:379 | † |
| DeepReportSource | interface | `doc_id?`, `title?`, `cids?: string[]`, `findings?: number` | frontend-v2/src/lib/contracts.ts:380 | † |
| DeepAudit | interface | `sentences?`, `cited?`, `uncited?: number[]`, `invalid_cids?: string[]` | frontend-v2/src/lib/contracts.ts:382 | † |
| ChatSynthesisFacet | interface | `id`, `covered?: boolean \| null`, `docs?`, `confidence?: string \| null` | frontend-v2/src/lib/contracts.ts:390-392 | † |
| ChatSynthesis | interface | `facets?`, `sources?: DeepReportSource[]`, `share{top_doc, top_share}`, `uncited?: number` | frontend-v2/src/lib/contracts.ts:393-398 | † |
| ChatGapClaim | interface | `text?`, `query?`, `found?`, `refuted?: boolean`, `edited?: string \| null` | frontend-v2/src/lib/contracts.ts:401-403 | † |
| ChatGapCheck | interface | `claims?: ChatGapClaim[]`, `searches?`, `section_added?: boolean`, `error?` | frontend-v2/src/lib/contracts.ts:404 | † |

† FACTS.importers are module-level (App.tsx, lib/_small-modules, lib/api.ts, lib/chat.ts, lib/deep.ts); per-symbol attribution is not in FACTS.

## contracts
- `SemanticReadiness` — endpoint `/semantic_readiness?corpus_id=`, contract `semantic-readiness-v1` — frontend-v2/src/lib/contracts.ts:12. `verdict` values documented as `SEMANTIC_COMPLETE | SEMANTIC_INCOMPLETE`, TS type is plain `string` — frontend-v2/src/lib/contracts.ts:16-17. `vnext.verdict`: `VNEXT_COMPLETE | VNEXT_INCOMPLETE` — frontend-v2/src/lib/contracts.ts:20-21. Pre: `profiled` and `vnext_served` absent on an older backend — frontend-v2/src/lib/contracts.ts:25-29.
- `DocSummary` — per-document vNext truth — frontend-v2/src/lib/contracts.ts:36. Written state (`vnext_ready` = "mapped + the latest card is vNext") vs served state (`profile_served`; absent when the profile index could not be read) — frontend-v2/src/lib/contracts.ts:49-53.
- `DocumentRow` — `GET /documents?corpus_id=`, identity authority for the Files screen; operational detail merged from DocSummary by `doc_id`; verified against orchestrator/api/ui.py::documents 2026-09-12 — frontend-v2/src/lib/contracts.ts:56-59.
- `LlmProvider` — `GET /llm/providers`; `api_key` is "either the last 4 chars, or the env var NAME (`env:NAME`)"; verified against orchestrator/api/ui.py::llm_providers 2026-09-12 — frontend-v2/src/lib/contracts.ts:95-98, frontend-v2/src/lib/contracts.ts:102.
- `ProviderUpsertBody` — empty `api_key` on an existing provider keeps the stored key (masked round-trip) — frontend-v2/src/lib/contracts.ts:110-111.
- `ControlPlane` — `/control_plane?corpus_id=` CONTROL-PLANE-STATUS-V1, verified live 2026-09-10: `pools` is a MAP keyed by function name; queue counters sit at the TOP level of each pool — frontend-v2/src/lib/contracts.ts:128-131. `control_ready` (GAP-1) and `summary.processing_active`/`processing_stalled` (GAP-4) are composed server-side; the UI renders, never re-derives from `/ready` + `/health/pipeline` — frontend-v2/src/lib/contracts.ts:131-133.
- `PoolLanes` — `/control_plane/pool/{function}`; "ENV NAMES only, never secrets" — frontend-v2/src/lib/contracts.ts:156.
- `Corpus` — `/corpora`; `query_ready` is carried ONLY so the UI can refuse to use it (plan §7) — frontend-v2/src/lib/contracts.ts:173.
- `PUBLIC_MODES` — public retrieval modes; VECTOR is a backend primitive, not a public mode; GNN (GNN-RETRIEVAL-V1) is the experimental fifth mode sent as `mode: "GNN"` through the very same /chat path — frontend-v2/src/lib/contracts.ts:185-189.
- `RetrievalReceipt` — `answer.retrieval` on the `/chat/stream` answer frame; the Query Inspector's whole source of truth — frontend-v2/src/lib/contracts.ts:202-206. `latency_ms`: v2 = per-stage map (absent stage is null), v1 = one number; "Render `total`, never the map itself (it rendered as 'NaNs')" — frontend-v2/src/lib/contracts.ts:230-232.
- Graph block — GRAPH-BROWSE-V1; `sources` on a relationship is "the reason this relationship may be shown at all"; `dropped_unattested` counts relationships withheld because nothing in THIS corpus attests them — frontend-v2/src/lib/contracts.ts:253, frontend-v2/src/lib/contracts.ts:269-276.
- Compare/Review — COMPARE-REVIEW-V1 — frontend-v2/src/lib/contracts.ts:279. `funnel_lanes` carries lane → chunk ids (not counts; `lane_sizes` has the counts) — frontend-v2/src/lib/contracts.ts:287-288. `ReviewResponse` models reviewer parse failure: `review: ReviewScores | null`, `parse_error: string | null`, `raw: string | null` — frontend-v2/src/lib/contracts.ts:305-308.
- Trail — TRAIL-INTERFACE-V1 (GET /adapter/runs, GET /adapter/{id}/view) — frontend-v2/src/lib/contracts.ts:310. `RunRegistry` is the owner's view only; "a friend's view has no `registry` key" — frontend-v2/src/lib/contracts.ts:335-336, frontend-v2/src/lib/contracts.ts:356.
- Deep — DEEP-RESEARCH-MODE-V1 §11.3 (DR7) — frontend-v2/src/lib/contracts.ts:359-360. `DeepResearchPlan` = "one model call, no run" — frontend-v2/src/lib/contracts.ts:360. `DeepReportModel` = the deterministic evidence model (§11.4) behind the Evidence / Sources / Method tabs — frontend-v2/src/lib/contracts.ts:370-371. `DeepFinding.confidence`: strong | single_source | contested — frontend-v2/src/lib/contracts.ts:377-378. `DeepAudit`: every prose sentence (headings skipped) checked for a valid `[cN]` — frontend-v2/src/lib/contracts.ts:381.
- `ChatSynthesis` — `result.meta.synthesis` on a GROUNDED_SYNTHESIS / CREATE_FROM_KNOWLEDGE turn; absent on QA/lookup turns and on every turn saved before F5; cids are the answer's own `[S#]` tags resolved through the chat receipt — frontend-v2/src/lib/contracts.ts:385-389.
- `ChatGapCheck` — `result.meta.gap_check`; the answer's "not covered" claims re-searched; the "More on this" addition carries the citations — frontend-v2/src/lib/contracts.ts:399-401.

## effect surface
None. FACTS report `tables_read: []`, `tables_written: []`, `constants: []` — FACTS [DERIVED]. No imports, network calls, files, subprocesses, or env reads anywhere in the file — frontend-v2/src/lib/contracts.ts:1-404 [DERIVED]. Sole runtime binding: `PUBLIC_MODES` — frontend-v2/src/lib/contracts.ts:189 [DERIVED].

## invariants
INVARIANT: PUBLIC_MODES.length == 5 — literals "FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN" — frontend-v2/src/lib/contracts.ts:189 [DERIVED]
  fails-if: a mode outside the five passed where `PublicMode` is expected fails to compile; a new backend mode not added here is unrepresentable.
INVARIANT: PublicMode == (typeof PUBLIC_MODES)[number] — frontend-v2/src/lib/contracts.ts:190 [DERIVED]
  fails-if: widening `PublicMode` manually to `string` disables mode discrimination at every call site.
INVARIANT: LlmProvider.api_key ∈ {masked last-4 chars, "env:NAME"} — never a raw key — frontend-v2/src/lib/contracts.ts:95-98, frontend-v2/src/lib/contracts.ts:102 [DERIVED]
  fails-if: a raw key in the field leaks through the provider UI.
INVARIANT: ControlPlane.control_ready.state ∈ {"ready", "blocked", "degraded"} — frontend-v2/src/lib/contracts.ts:137 [DERIVED]
  fails-if: an unlisted state string breaks exhaustive switches on the union.
INVARIANT: DocSummary.profile_served ∈ {"vnext", "basic", null} when present — frontend-v2/src/lib/contracts.ts:51-53 [DERIVED]
  fails-if: an unexpected label breaks the written-vs-served label logic.
INVARIANT: every entry in GraphRelationships.relationships carries `sources` attestation; unattested ones are counted in `dropped_unattested`, not listed — frontend-v2/src/lib/contracts.ts:269-276 [DERIVED]
  fails-if: displaying an unattested relationship violates the GRAPH-BROWSE-V1 evidence rule.
INVARIANT: RetrievalReceipt.latency_ms is number (v1) OR Record<string, number | null> (v2, absent stage = null); only `total` may be rendered — frontend-v2/src/lib/contracts.ts:230-232 [DERIVED]
  fails-if: rendering the map directly reproduces the "NaNs" bug named in the comment.
INVARIANT: ControlPlanePool.provider.limiter_refused counts local refusals (0 HTTP) while http_429 cost a real provider request — frontend-v2/src/lib/contracts.ts:152-153 [DERIVED]
  fails-if: summing both as one cost metric double-counts provider spend.
INVARIANT: ChatSynthesisFacet.confidence vocabulary == DeepFinding.confidence vocabulary (strong / single_source / contested, §11.4) — frontend-v2/src/lib/contracts.ts:377-378, frontend-v2/src/lib/contracts.ts:386-388 [DERIVED]
  fails-if: a new confidence level added to one interface but not the other splits the shared rendering path.

## determinism & idempotency
determinism: DETERMINISTIC — declarations only; no clock/random/uuid/network/db/env access, zero imports — frontend-v2/src/lib/contracts.ts:1-404 [DERIVED]
idempotency: SAFE — module evaluation only defines the const `PUBLIC_MODES` and types; no side effects — frontend-v2/src/lib/contracts.ts:189-190 [DERIVED]

## failure behaviour
No runtime code: nothing is thrown or swallowed in this file — frontend-v2/src/lib/contracts.ts:1-404 [DERIVED].
Failure shapes are modeled as data: `ReviewResponse.review: ReviewScores | null` + `parse_error: string | null` + `raw: string | null` — frontend-v2/src/lib/contracts.ts:305-308; `RetrievalReceipt.degraded?: string[]` — frontend-v2/src/lib/contracts.ts:229; `ControlPlanePool.failed?` / `retry?` — frontend-v2/src/lib/contracts.ts:150-151; `RunView.run.gap: { code?; message? } | null` — frontend-v2/src/lib/contracts.ts:346; `ChatGapCheck.error?` — frontend-v2/src/lib/contracts.ts:404; `DeepAudit.uncited?: number[]` / `invalid_cids?: string[]` — frontend-v2/src/lib/contracts.ts:382; `SemanticReadiness.warnings?: unknown[]` / `extraction?: unknown` — frontend-v2/src/lib/contracts.ts:32-33.

## dumb-code flags
- `latency_ms?: number | Record<string, number | null>` — one field carries two protocol versions; comment warns the map rendered as "NaNs" — frontend-v2/src/lib/contracts.ts:230-232.
- Large `unknown` pass-through block in `RetrievalReceipt` (`funnel?`, `composition?`, `aspects?`, `weak_aspects?`, `legend?`, `chunks?`, `used_evidence?`, `final_detail?`, `graph_seeds?`, `graph_bounds?`, `graph_degraded?`, `wildcard?`, `wildcard_diagnostics?`, `latent?`) — frontend-v2/src/lib/contracts.ts:212-228.
- Dual shapes: `documents?: number | string[]` in DeepCoverageGoal and DeepReportGoal ("a count, or the doc ids") — frontend-v2/src/lib/contracts.ts:367-369, frontend-v2/src/lib/contracts.ts:376; `open_questions?: (string | { question?; text? })[]` — frontend-v2/src/lib/contracts.ts:373.
- `verdict` fields typed plain `string` while their values are documented enums (`SEMANTIC_COMPLETE` etc.) — not compiler-checked; only `control_ready.state` is a real TS union — frontend-v2/src/lib/contracts.ts:16-21 vs frontend-v2/src/lib/contracts.ts:137.
- `Corpus.query_ready: boolean` exists only so the UI can refuse to use it — a dead-by-design field — frontend-v2/src/lib/contracts.ts:173.
- Backend-version probes encoded as optionality: `profiled?: number | null`, `vnext_served?: number | null` ("absent on an older backend") — frontend-v2/src/lib/contracts.ts:25-29.
- `latency_ms` means different things per interface: total on `AnswerFrame` — frontend-v2/src/lib/contracts.ts:237; total on `CompareArm` vs per-stage map on `CompareArm.retrieval.latency_ms` — frontend-v2/src/lib/contracts.ts:282, frontend-v2/src/lib/contracts.ts:290-291; v1/v2 union on `RetrievalReceipt` — frontend-v2/src/lib/contracts.ts:232.

## refactor notes
- Blast radius: all five importers (`App.tsx`, `lib/_small-modules`, `lib/api.ts`, `lib/chat.ts`, `lib/deep.ts`) re-typecheck on any change here — FACTS.importers.
- `PUBLIC_MODES` / `PublicMode` pair: adding a mode (as GNN was added) changes the union and every `PublicMode`-typed call site; the backend must accept the literal since modes go through the same `/chat` path — frontend-v2/src/lib/contracts.ts:185-190.
- Field renames must track the named backend routes (`orchestrator/api/ui.py::documents`, `orchestrator/api/ui.py::llm_providers`, verified live 2026-09-10/12); stated policy is "the backend is the authority" — frontend-v2/src/lib/contracts.ts:4-6, frontend-v2/src/lib/contracts.ts:56-59, frontend-v2/src/lib/contracts.ts:95-98.
- Optional fields are backend-age probes (`profiled`, `vnext_served`, `profile_served`); making them required breaks older-backend rendering — frontend-v2/src/lib/contracts.ts:25-29, frontend-v2/src/lib/contracts.ts:51-53.
- `DocumentRow` ↔ `DocSummary` merge is keyed by `doc_id`; renaming either identity field breaks the Files screen — frontend-v2/src/lib/contracts.ts:56-59.
- `DeepReportSource` is reused by `ChatSynthesis.sources`; changing it affects both deep-report tabs and chat synthesis rendering — frontend-v2/src/lib/contracts.ts:380, frontend-v2/src/lib/contracts.ts:394.
- `RunView.registry` is owner-view-only; consumers must handle its absence — frontend-v2/src/lib/contracts.ts:335-336, frontend-v2/src/lib/contracts.ts:356.
- `ReviewResponse` null triple (`review`/`parse_error`/`raw`) — consumers must render the parse-failure path — frontend-v2/src/lib/contracts.ts:305-308.

## VERIFY
```verify
grep -Fq 'export const PUBLIC_MODES = ["FAST", "HYBRID", "GRAPH", "WILDCARD", "GNN"] as const;' frontend-v2/src/lib/contracts.ts
grep -Fq 'export type PublicMode = (typeof PUBLIC_MODES)[number];' frontend-v2/src/lib/contracts.ts
grep -Fq 'latency_ms?: number | Record<string, number | null>;' frontend-v2/src/lib/contracts.ts
grep -Fq 'profile_served?: "vnext" | "basic" | null;' frontend-v2/src/lib/contracts.ts
grep -Fq 'dropped_unattested: number;' frontend-v2/src/lib/contracts.ts
! grep -Fq 'import ' frontend-v2/src/lib/contracts.ts
test "$(grep -c -F 'export interface ' frontend-v2/src/lib/contracts.ts)" -ge 55
```

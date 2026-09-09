# RAG Pipeline Finish Plan — Grounded Execution, Migration & Acceptance Criteria

**Date:** 2026-09-09  
**Repository:** `Kingsley-Cyber/Polymath-RAG`  
**Baseline inspected:** `main @ 1c61a6f476222d9df03c73ae3eac2c399f35dafd`  
**Status:** execution / acceptance overlay  
**Primary objective:** finish the RAG pipeline so a newly uploaded document reaches a fully observable, retrieval-usable terminal state, then reconcile the existing corpus without blind re-ingestion or repeated expensive testing.

> This file does **not** replace `PLAN.md` or the migration authority in `docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md`. The latter remains authoritative for retrieval-generation migration, retirement ordering, and cutover. This plan is the grounded execution/acceptance path for finishing the product pipeline. If this file conflicts with the migration authority, stop and reconcile the conflict instead of silently forking architecture.

---

## 0. Execution doctrine

The goal is **pipeline completion**, not a long sequence of ceremonial tests.

The operating rule for this plan is:

> **Prove each behavior at the cheapest layer that can actually fail for that behavior. Run the expensive end-to-end production proof once, after the offline contracts and wiring are coherent.**

Do not run the whole repository suite after every edit. Do not make a live provider call to prove a deterministic parser. Do not create a frontend test framework merely to prove that a number renders. Do not repeatedly upload fresh documents after each internal change when a cheaper contract or persistence test isolates the same defect.

### 0.1 Graphify is mandatory before modification

The execution model must use Graphify against its **actual local/current HEAD** before changing pipeline behavior. Graphify is used to reconstruct runtime edges and dependency ownership; it does not replace opening the real files and verifying the cited symbols.

At minimum, trace these paths:

```text
frontend/src/api.ts::uploadFile
  -> orchestrator/orchestrator/api/ui.py::upload
  -> shared/polymath_shared/intake_submission.py::submit_intake
  -> intake/materialization/chunk production
  -> extraction / compiler
  -> core projections
  -> control/control/tickets.py::STAGE_DAG
  -> document/profile stages
  -> doc_profile
  -> parent-MAP generation + projection
  -> parent_enrichment
  -> semantic readiness
  -> retrieval readers
  -> Files UI / document status UI
```

For every live stage, record:

| Question | Required answer |
|---|---|
| What event/ticket starts it? | exact `FILE:SYMBOL` |
| Which worker consumes it? | exact `FILE:SYMBOL` |
| What durable artifact/table proves completion? | exact table/artifact/receipt |
| What contract/version scopes current rows? | exact field/version |
| How is it retried/recovered? | exact ticket/receipt/idempotency path |
| Is it a current `query_ready` blocker? | yes/no + code authority |
| Does retrieval actually read it? | exact runtime reader |
| Which API exposes it? | endpoint + builder/query |
| Which UI consumes it? | component/API function |

**Gate:** no pipeline stage may be classified KEEP / BRIDGE / DUAL-RUN / RETIRE / DELETE-LATER from memory or comments alone.

---

# 1. Grounded current-state facts that this plan must reconcile

These are not design guesses. They are current-main facts observed in the files below and are the starting constraints for Graphify.

## 1.1 Upload already uses the canonical intake writer

`frontend/src/api.ts::uploadFile` POSTs `/upload`. `orchestrator/orchestrator/api/ui.py::upload` streams the upload to the blob spool, applies duplicate guards, builds the canonical intake payload, and calls the same `submit_intake` path used by `/intake`.

**Implication:** do not create a second “new upload pipeline” for the migration. The finish path must prove and extend this path.

Grounding:
- `frontend/src/api.ts`
- `orchestrator/orchestrator/api/ui.py`
- `orchestrator/orchestrator/api/intake.py`
- `shared/polymath_shared/intake_submission.py`

## 1.2 The live ticket DAG contains `doc_profile`, but it is still non-blocking

`control/control/tickets.py::STAGE_DAG` contains the normal chain through `verify_projections`, then the background intelligence stages and `doc_profile`. `NON_BLOCKING_STAGES` explicitly includes `doc_profile` and `parent_enrichment`.

The comments describe `doc_profile` rollout Phase A as non-blocking, with a future Phase B that changes the readiness barrier.

**Implication:** present `run.status == query_ready` does not, by itself, prove that the new document profile / parent-MAP retrieval generation is complete.

Grounding:
- `control/control/tickets.py::STAGE_DAG`
- `control/control/tickets.py::NON_BLOCKING_STAGES`
- `workers/workers/doc_profile_worker.py`

## 1.3 Legacy/core `query_ready` and vNext semantic readiness are intentionally separate today

`shared/polymath_shared/semantic_readiness.py` explicitly says `query_ready` is the control contract and must not be silently redefined. It now carries a separate `vnext` verdict.

`vnext_readiness()` already derives durable corpus-level parent-MAP/profile state:
- eligible parents,
- active mapped parents,
- explicit exclusions,
- unresolved parents,
- vNext profile count,
- `VNEXT_COMPLETE / VNEXT_INCOMPLETE / VNEXT_NOT_STARTED`.

**Implication:** the finish work should first expose and make this generation state correct at **document level**, rather than casually overloading the old `query_ready` flag.

Grounding:
- `shared/polymath_shared/semantic_readiness.py`
- `docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md`

## 1.4 The parent enrichment lane is live current code, not a forgotten historical idea

`workers/workers/summary_worker_impl.py::_do_enrichment` implements `parent_enrichment.v1` over parent sections and persists outcomes into `parent_enrichments`.

`control/control/scheduler.py::auto_enrich_on_chunks` auto-mints parent enrichment after intake, and `apply_promotions` contains a promotion-time backstop.

`orchestrator/orchestrator/api/ui.py` exposes corpus/document enrichment endpoints. `orchestrator/orchestrator/api/intake.py::pipeline_status` reads `parent_enrichments`. `frontend/src/components/FilesView.tsx` displays enrichment state and manual re-enrich actions.

**Implication:** enrichment must be traced and classified. It may remain additive/non-blocking, but it cannot be accidentally omitted from migration accounting.

Grounding:
- `workers/workers/summary_worker_impl.py::_do_enrichment`
- `control/control/scheduler.py::auto_enrich_on_chunks`
- `control/control/scheduler.py::apply_promotions`
- `orchestrator/orchestrator/api/ui.py::_mint_enrichment`
- `orchestrator/orchestrator/api/intake.py::pipeline_status`
- `frontend/src/components/FilesView.tsx::EnrichBadge`

## 1.5 Parent enrichment comments and scheduler behavior currently disagree

The `_do_enrichment` docstring still describes the stage as owner-triggered, while `scheduler.py` automatically mints it early and again at promotion.

**Implication:** treat comments as historical evidence, not runtime authority. Graphify must identify the live event mint path and the retrieval reader before deciding whether the stage is required, optional, superseded, or ready for retirement.

## 1.6 vNext profile support exists, but the worker switch defaults OFF in code

`workers/workers/doc_profile_worker.py::_vnext_enabled()` returns true only when `POLYMATH_DOC_PROFILE_VNEXT` is enabled. The code default is OFF.

The migration ledger records that vNext was qualified and enabled in deployment configuration, but a clean/current environment must not be assumed to inherit an untracked local `.env` value.

The old/default prompt `shared/polymath_shared/document_profile/prompt.py` already supports:
- ONE,
- SUMMARY,
- TOPIC,
- TERM,
- Q,
- SEARCH,
- THEORY,
- CONCEPT,
- SEEALSO.

The vNext prompt additionally supports:
- LATENT-PATTERN,
- ANCHOR,
- RECALLQ,
- TENSION,
- BRIDGE,
- INVERSION,
- BOUNDARY,

and uses the `DocumentFingerprint` path.

**Implication:** before the UI claims the new field inventory is production truth, prove which profile generation a brand-new upload actually uses under the production startup contract.

Grounding:
- `workers/workers/doc_profile_worker.py::_vnext_enabled`
- `workers/workers/doc_profile_worker.py::process_event`
- `shared/polymath_shared/document_profile/prompt.py`
- `shared/polymath_shared/document_profile/profile_prompt_vnext.py`
- `shared/polymath_shared/document_profile/fingerprint.py`

## 1.7 The profile compiler already supports vNext tags additively

`shared/polymath_shared/document_profile/compiler.py` has:
- `rag-profile-v3` schema,
- `rag-compiler-v3.1`,
- advisory targets for TOPIC / TERM / Q / SEARCH / THEORY / CONCEPT / SEEALSO,
- vNext Record fields for latent pattern / anchor / recallq / tension / bridge / inversion / boundary,
- tolerant tag aliases.

Counts are explicitly **soft coverage aims**, not hard validity quotas.

**Implication:** UI must report `actual count` separately from `aim`. An 8/10 TOPIC profile is not automatically invalid. Compiler validity and item quantity are different concepts.

## 1.8 Parent-MAP has durable orchestration and strict-identity compiler semantics

`workers/workers/doc_parent_map_worker.py` provides the durable map orchestration over:
- `document_parent_map_batches`,
- `document_parent_maps`,
- `document_parent_exclusions`.

It persists partial valid work and repairs only unresolved aliases.

`shared/polymath_shared/document_profile/map_prompt.py` freezes the plaintext contract:

```text
MAP|<alias>|<routing signature>|<hook1>;<hook2>;<hook3>
```

`shared/polymath_shared/document_profile/map_compiler.py` is explicitly **tolerant format, strict identity**.

**Implication:** no JSON Object Mode, no second parser, no schema layer that replaces the MAP compiler contract as part of finishing the pipeline.

## 1.9 Current Files UI exposes enrichment counts but not the complete document contract

`orchestrator/orchestrator/api/ui.py::documents` currently returns per-document:
- child chunks,
- distinct parents,
- READY enrichment count,
- unrecovered INVALID enrichment count.

`frontend/src/types.ts::DocumentRow` mirrors that shape. `frontend/src/components/FilesView.tsx` shows chunks, enrichment state, sections, recent runs, corpus semantic readiness, and retrieval visibility.

It does **not** currently show per document:
- materialized parent count versus parents-with-children,
- profile generation/version/validity,
- actual profile field counts,
- parent-MAP eligible/excluded/mapped/unresolved counts,
- semantic-index readiness,
- exact blocker(s),
- required projection completeness.

**Implication:** UI migration is a backend-contract problem first, a rendering problem second.

## 1.10 The old E2E checklist is stale in at least one concrete place

`RAG_E2E_CHECKLIST.md` still marks I1 manifest ingestion “NOT STARTED.” Current `control/control/manifest_ingest.py` explicitly implements “I1 manifest ingestion orchestration: plan / execute / status.”

**Implication:** do not blindly execute unchecked historical gates. Reconcile checklist claims against current code/runtime evidence first.

---

# 2. Definition of Done

The pipeline is finished only when all of the following are true.

## 2.1 Fresh-document product invariant

For any supported, valid new upload (`.md`, `.txt`, `.html`, `.pdf`, `.epub`, `.docx`) through the production `/upload` path:

1. the upload is durably accepted or receives a typed duplicate/refusal result;
2. materialization and chunking produce deterministic document/child/parent identities;
3. extraction and core projection settle without hidden dropped work;
4. the intended document-profile generation runs and persists a valid compiled profile;
5. required profile vectors are projected and receipted;
6. every retrieval-eligible parent is either:
   - actively MAP-mapped under the current map contract, or
   - explicitly excluded under the current exclusion contract;
7. required parent-MAP vectors are projected/reconciled;
8. parent enrichment is accounted for according to its final classification;
9. the backend reports the exact current blocker if any of the above are incomplete;
10. the Files UI displays the same authoritative counts/state;
11. normal retrieval/chat can retrieve the document and cite its source evidence;
12. rerunning/reconciling the same document does not duplicate durable state.

## 2.2 No-hidden-state invariant

A document may be `IN_PROGRESS`, `DEGRADED`, `FAILED`, `CORE_QUERY_READY`, `VNEXT/SEMANTIC_INDEX_READY`, etc., but it must never look “done” merely because one coarse status settled while required current-generation artifacts are still missing.

Every visible blocker must be derived from durable state, not from a worker-local counter or a log message.

## 2.3 Quantitative document invariant

For every document, the product must be able to answer **what actually exists now**, at minimum:

### Chunk / parent substrate
- `children_total`
- `parents_materialized`
- `parents_with_children`

### Document profile
- current schema version
- current compiler version
- current prompt version
- vNext true/false
- valid / invalid
- quality / format / coverage summary
- actual item count for every supported field
- advisory target/aim where the compiler defines one

### Parent MAP
- current map contract
- eligible parents
- explicitly excluded parents
- active mapped parents
- unresolved eligible parents
- batch total / complete / partial if operationally useful
- current failure/repair summary

### Enrichment
- ready
- invalid-unrecovered
- remaining applicable parents
- additive/required classification

### Projection/readiness
- required profile projection complete/incomplete
- required parent-MAP projection complete/incomplete
- core `query_ready`
- vNext/semantic-index verdict
- final blocker list

---

# 3. Canonical parent-count contract

The current code uses the word “parent” for multiple related populations. Do not build UI arithmetic until these are explicitly named.

## 3.1 Required definitions

Graphify and direct SQL/file inspection must establish these definitions:

```text
children_total
  = chunk rows where tier='child' for this doc

parents_materialized
  = chunk rows where tier='parent' for this doc

parents_with_children
  = DISTINCT child.parent_id for this doc

map_eligible
  = current MAP skeleton/eligibility universe for this doc

map_excluded
  = explicit current-contract parent exclusions

map_active
  = active current-contract document_parent_maps

map_unresolved
  = eligible parents not resolved by current active map/exclusion semantics

enrichment_applicable
  = the parent universe the current enrichment worker actually considers after its noise/role exclusions

enrichment_ready
  = current durable READY rows for applicable parents

enrichment_invalid_unrecovered
  = current durable INVALID rows without a later READY resolution
```

## 3.2 Do not assume equality until proved

Do **not** assume these are always equal:

```text
parents_materialized == parents_with_children == map_eligible == enrichment_applicable
```

The MAP skeleton builder and enrichment worker have independent exclusion/noise logic. The UI currently derives “parents” from `DISTINCT child.parent_id`, while `doc_profile_worker._load_inputs()` reads `tier='parent'` rows directly.

**Acceptance criterion:** the backend contract names each population instead of collapsing them into an ambiguous `parents` integer.

## 3.3 Current-contract scoping

Counts must ignore obsolete historical rows when a versioned successor exists.

For profile/MAP/enrichment/projection state, prove the scope used for “current”:
- active flag,
- map contract,
- compiler/prompt generation,
- input/content hash,
- projection contract,
- supersession state.

A count that silently mixes old and new generations is a migration failure.

---

# 4. Resolve the production document-profile generation

## 4.1 Required decision

Prove what a brand-new production upload uses today:

```text
legacy/current v3.2 prompt + lean context
OR
vNext DocumentFingerprint + profile_prompt_vnext
```

Do not infer this from the migration ledger alone. Verify startup configuration and the worker branch at runtime.

Relevant code:
- `workers/workers/doc_profile_worker.py::_vnext_enabled`
- `workers/workers/doc_profile_worker.py::process_event`
- `shared/polymath_shared/document_profile/prompt.py`
- `shared/polymath_shared/document_profile/profile_prompt_vnext.py`
- `shared/polymath_shared/document_profile/compiler.py`

## 4.2 Finish criterion

If vNext is the intended production generation, completion requires:

- a clean supported startup path enables it intentionally;
- startup/config diagnostics make that state observable;
- new documents persist `doc_profile.vnext=true`;
- the compiler version recognizes the full intended field vocabulary;
- profile projection uses the compiled current artifact;
- rollback remains explicit and version-safe.

Do not hard-code a local `.env` accident into architectural truth.

## 4.3 Required profile count payload

Expose actual compiled counts for:

### Source-anchored
- `ONE`
- `SUMMARY`
- `TOPIC`
- `TERM`
- `Q`

### Routing-inferred
- `SEARCH`
- `THEORY`
- `CONCEPT`
- `LATENT-PATTERN`
- `ANCHOR`
- `RECALLQ`
- `TENSION`
- `BRIDGE`
- `INVERSION`
- `BOUNDARY`
- `SEEALSO`

Return an `aim` only where a real compiler/prompt target exists. Never fabricate a target for the new optional research-index tags merely to make a progress bar look complete.

Example contract shape:

```json
{
  "profile": {
    "valid": true,
    "vnext": true,
    "schema_version": "rag-profile-v3",
    "compiler_version": "rag-compiler-v3.1",
    "prompt_version": "doc-profile-vnext-v1",
    "counts": {
      "ONE": {"actual": 1, "aim": 1},
      "SUMMARY": {"actual": 1, "aim": 1},
      "TOPIC": {"actual": 8, "aim": 10},
      "TERM": {"actual": 11, "aim": 10},
      "Q": {"actual": 14, "aim": 15},
      "SEARCH": {"actual": 13, "aim": 15},
      "THEORY": {"actual": 8, "aim": 10},
      "CONCEPT": {"actual": 9, "aim": 10},
      "LATENT-PATTERN": {"actual": 2, "aim": null}
    }
  }
}
```

The numbers above are illustrative only. Production values come from the persisted compiled artifact.

---

# 5. Profile compiler adversarial certification

The compiler should be reviewed by a **different capable model** to theorize realistic model-output failure modes, but that reviewer does not get authority to redesign or patch the compiler from speculation.

## 5.1 Reviewer task

Give the reviewer model the actual:
- production profile prompt(s),
- compiler source,
- representative valid outputs,
- existing tests.

Ask it to generate a categorized threat/scenario inventory covering outputs from a cheap but capable model.

At minimum consider:
- leading/trailing whitespace;
- CRLF vs LF;
- no final newline;
- markdown fence around otherwise valid output;
- small preamble or trailing sentence;
- bullets/numbering;
- missing colon variants already intended to be tolerated;
- wrapped lines;
- lower/variant labels;
- duplicate singleton ONE/SUMMARY;
- duplicate list items;
- unknown labels;
- `END` variants;
- Unicode punctuation;
- below-target but semantically valid lists;
- over-target lists and deterministic caps;
- optional vNext tags omitted;
- malformed vNext tag spelling;
- model refusal/apology;
- truncated output;
- a semantically empty core surrounded by many list items.

## 5.2 Convert theory to deterministic fixtures

Only scenarios that correspond to a real contract risk become fixtures.

Expected classification:

| Class | Expected compiler behavior |
|---|---|
| harmless presentation drift | accept/repair deterministically |
| soft count miss | compile; record coverage issue, do not invent |
| unknown optional text | receipt/issue without misclassification |
| missing semantic core | invalid/retry-review |
| malformed/untrusted content | never convert into invented structured meaning |
| duplicate/capped list | deterministic first/cap policy |

## 5.3 Test timing

**Run now:** targeted compiler tests only after compiler/prompt compatibility changes.  
**Do not run now:** provider call, full pipeline, whole repo suite.

The final production E2E later proves the real model can pass the compiler. These fixtures prove the compiler is not unfairly rejecting harmless model formatting.

---

# 6. Parent-MAP completion and compiler certification

## 6.1 Architecture remains frozen

Keep:

```text
MAP|<alias>|<routing signature>|<hook1>;<hook2>;<hook3>
```

Do not introduce:
- JSON Object Mode,
- function calling,
- a second model-facing schema,
- a second parser,
- a bypass around `map_compiler.py`.

Grounding:
- `shared/polymath_shared/document_profile/map_prompt.py`
- `shared/polymath_shared/document_profile/map_compiler.py`
- `workers/workers/doc_parent_map_worker.py`

## 6.2 Current forensic hold is a prerequisite, not the project finish line

The current Groq/MAP control-plane forensic repair must close its **offline** acceptance gate before any live MAP canary or backfill resumes.

Required preconditions include the already identified conservation chain:

```text
local scheduling
  -> limiter admission/refusal
  -> actual HTTP dispatch
  -> provider response/quota observation
  -> raw MAP response
  -> compiler yield
  -> persisted maps
```

A local refusal must never be counted as provider spend. Hidden `MappingOutcome.errors`, partial compiler outcomes, and retry waste must be observable before scaled migration resumes.

Do not let this work expand into unrelated provider tuning once those defects are proven/fixed.

## 6.3 Prove automatic new-document MAP wiring

The durable worker exists, but finishing the product requires proving how a **new upload** reaches it.

Graphify must locate:
- ticket/event mint,
- worker registration/fleet slot,
- inference adapter,
- projection trigger,
- completion/readiness reader.

If any edge is absent, that missing edge is P0 migration work.

Do not infer automatic execution merely because backfill/canary scripts exist.

## 6.4 MAP compiler adversarial fixtures

Use the same cheap deterministic strategy as the profile compiler.

Cover:
- whitespace around `MAP` and `|`;
- zero-padded/lowercase aliases;
- CRLF / no final newline;
- reordered valid MAP lines;
- valid MAPs surrounded by non-MAP prose;
- Unicode hyphen/space drift;
- fewer/more than three semantic hooks;
- empty hooks;
- generic hooks/signature;
- duplicate alias;
- unknown/invented alias;
- empty signature;
- missing aliases / partial response;
- valid partial response + garbage;
- refusal/apology/empty response;
- truncation mid-final MAP line.

Required behavior:

```text
harmless format drift        -> valid map survives
unknown/ambiguous identity   -> rejected, never cross-attached
partial valid output         -> valid maps persist
missing aliases              -> exact repair set
already-active parent        -> never needlessly regenerated
```

**Test timing:** targeted `map_compiler` / durable map-worker fake-inference tests now; real provider behavior only in the one bounded production canary after the offline gate.

---

# 7. Parent enrichment: trace, classify, preserve or retire intentionally

## 7.1 Required Graphify questions

Trace `parent_enrichment` end-to-end and answer:

1. Which retrieval path(s) read `parent_enrichments` today?
2. Which fields/surfaces from the compiled enrichment actually enter candidate generation/ranking?
3. Is absence intentionally invisible/fail-open, as the current additive design comments state?
4. What parent population is enrichment-eligible after region/noise filtering?
5. Does profile/MAP duplicate its function, complement it, or serve a different query lane?
6. Which code mints enrichment automatically versus manually?
7. What durable row/contract determines current READY vs INVALID vs superseded?

Grounding anchors:
- `workers/workers/summary_worker_impl.py::_do_enrichment`
- `shared/polymath_shared/latent/*`
- `control/control/scheduler.py::auto_enrich_on_chunks`
- `control/control/scheduler.py::apply_promotions`
- `orchestrator/orchestrator/api/ui.py::_mint_enrichment`
- `frontend/src/components/FilesView.tsx`

## 7.2 Required classification

Assign exactly one:
- **KEEP — required additive retrieval lane**
- **KEEP — optional additive retrieval lane**
- **BRIDGE during vNext migration**
- **SUPERSEDED — readers already migrated**
- **RETIRE after reader migration**

Do not classify it dead simply because newer profile/MAP stages exist.

## 7.3 Readiness policy

Unless the existing accepted migration authority is explicitly changed, do not make enrichment a surprise hard `query_ready` barrier. If it remains additive, display its own state separately:

```text
enrichment: READY / PARTIAL / FAILED_OPTIONAL / DISABLED
```

That preserves observability without turning a historical non-blocking retrieval aid into an accidental ingestion outage.

---

# 8. One canonical document-status contract

The UI should not independently reconstruct migration truth from several unrelated endpoints.

Graphify must choose the lowest-blast-radius compatibility path:
- extend `/status`, or
- extend `/documents`, or
- add `/documents/{doc_id}/status`,

but the actual count/state builder should be **one shared backend authority** reused by any compatibility endpoint.

## 8.1 Recommended response model

```text
identity
  doc_id
  run_id
  corpus_id
  source_name
  media_type

state
  run_status
  core_query_ready
  vnext_verdict / semantic_index_ready
  fully_ready
  blockers[]

chunks
  children_total
  parents_materialized
  parents_with_children

profile
  present
  valid
  vnext
  schema_version
  prompt_version
  compiler_version
  counts_by_field
  issues_summary
  projected

parent_map
  map_contract
  eligible
  excluded
  mapped_active
  unresolved
  batches_total
  batches_done
  batches_partial
  repair_or_error_summary
  projected

enrichment
  classification
  applicable
  ready
  invalid_unrecovered
  remaining

stages
  ticket/status/attempt/error for current run
```

## 8.2 Truth rules

- Every number comes from authoritative Postgres/artifact/projection-receipt state.
- Logs are diagnostics, not completion proof.
- Provider lane selection is not equivalent to HTTP dispatch.
- A queued ticket is not progress completion.
- Old/superseded contract rows do not count toward current generation.
- An advisory profile target miss is not automatically a blocker.
- A missing current required artifact is a blocker even if legacy `query_ready` is true.

## 8.3 Backend acceptance criteria

For one seeded document fixture/database state, the status builder must correctly distinguish:

1. no document yet;
2. chunks landed, profile missing;
3. valid profile but profile projection missing;
4. MAP partial with exact unresolved count;
5. all eligible parents resolved by active maps + exclusions;
6. optional enrichment partial;
7. full semantic-index ready;
8. stale historical rows under an old contract that must **not** satisfy current readiness.

**Test timing:** one targeted DB integration module for this aggregate. Do not duplicate all compiler edge cases here.

---

# 9. UI/UX migration

Grounded files:
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/components/FilesView.tsx`
- `orchestrator/orchestrator/api/ui.py`

The current Files page already owns upload, duplicate feedback, document rows, section expansion, enrichment, readiness, and retrieval visibility. Extend this surface rather than creating a parallel admin page unless Graphify shows a concrete ownership conflict.

## 9.1 Document row — fast operational answer

Each row should answer, without expanding it:

```text
Source
Type / size
Children
Parents
Profile state
MAP mapped/eligible
Enrichment state
Overall semantic-index state
Primary blocker if incomplete
```

Example conceptually:

```text
Book.pdf   4.2 MB   982 child   173 parent
Profile ✓ vNext
MAP 168/171 + 2 excluded · 1 unresolved
Enrich 160/169
Semantic index: BLOCKED — 1 parent MAP unresolved
```

Do not use the example numbers as test fixtures or target values.

## 9.2 Expanded document — quantitative contract

Expanded view should show:

### Profile counts
A compact table of actual counts, with target/aim only where defined:

```text
ONE             1
SUMMARY         1
TOPIC           8 / aim 10
TERM           11 / aim 10
Q              14 / aim 15
SEARCH         13 / aim 15
THEORY          8 / aim 10
CONCEPT         9 / aim 10
LATENT-PATTERN  2
ANCHOR          1
RECALLQ         3
TENSION         1
BRIDGE          2
INVERSION       1
BOUNDARY        1
SEEALSO         7 / aim 10
```

### Parent contract
- materialized
- MAP eligible
- excluded
- active mapped
- unresolved
- projected
- enrichment applicable / ready / failed / remaining

### Pipeline contract
- current generation/version
- current stage states
- exact blockers
- last durable error

Keep raw model output, hashes, provider lane, full compiler issue payload, and low-level receipts **collapsed/debug-only**. The normal UI is for operational truth, not forensic noise.

## 9.3 UI testing policy

`frontend/package.json` currently has no frontend unit/component test framework; it has `tsc --noEmit && vite build`.

Therefore:
- do not introduce Jest/Vitest solely for the migration status cards;
- put the correctness burden in the backend document-status contract tests;
- run `npm run build` after UI/types/API changes;
- visually/behaviorally prove the UI during the final production document E2E.

Introduce a frontend test framework only if new UI logic becomes sufficiently stateful that the backend contract + TypeScript build cannot isolate it.

---

# 10. Projection and retrieval-readiness wiring

The vNext migration authority already distinguishes build substrate from live readers. Finishing ingestion is not enough if the new artifacts are never consumed or projected.

Graphify must prove:

1. `doc_profile` artifact -> profile representation -> profile Qdrant projection;
2. parent MAP row -> parent-MAP vector text -> parent-MAP Qdrant projection;
3. projection reconciliation/receipts use the current embedding contract;
4. retrieval dual-read/shadow/current reader actually consumes the intended profile/MAP generation;
5. the final normal query path deepens back to source child evidence and does not cite routing hypotheses as evidence.

Grounding:
- `workers/workers/doc_profile_worker.py`
- `shared/polymath_shared/document_profile/projection.py`
- `workers/workers/doc_parent_map_worker.py`
- `shared/polymath_shared/document_profile/parent_map_projection.py`
- `shared/polymath_shared/semantic_readiness.py`
- current retrieval modules identified by Graphify, including the live `orchestrator/orchestrator/api/chat_retrieval.py` path.

**P0 failure condition:** a stage can say “complete” while its current required projection is missing and no readiness/status surface reports that gap.

---

# 11. Existing corpus reconciliation — repair, do not blindly re-ingest

`control/control/manifest_ingest.py` already implements deterministic I1-style plan / execute / status. Reuse its design principle: derive owed work from durable state, then enqueue only what is missing/stale.

## 11.1 Reconciliation classification

For each document, classify current generation state, e.g.:

- `CORE_NOT_READY`
- `CORE_READY_PROFILE_MISSING`
- `PROFILE_STALE_GENERATION`
- `PROFILE_READY_MAP_NOT_STARTED`
- `MAP_PARTIAL`
- `MAP_READY_PROJECTION_STALE`
- `VNEXT_READY_ENRICHMENT_PARTIAL`
- `FULLY_READY`
- `FAILED_REPAIRABLE`
- `RUNNING`

Names can change; the key is mutually understandable state derived from durable truth.

## 11.2 Migration rules

- Do not delete/re-ingest documents just to regenerate an additive semantic lane.
- Do not re-profile a current valid profile.
- Do not remap an active current-contract parent.
- Preserve partial MAP work and repair only unresolved parents.
- Do not treat optional enrichment gaps as current-generation MAP gaps.
- Do not mix old contract rows into “complete.”
- Every repair is resumable and idempotent.

## 11.3 Dry-run first

Before any corpus-wide mutation, produce a read-only reconciliation report with:

```text
documents_total
core_ready
profiles_current
profiles_missing_or_stale
map_eligible_parents
map_active
map_excluded
map_unresolved
docs_map_complete
docs_map_partial
enrichment_ready / partial / failed
projection_gaps
repairable_failures
estimated provider calls for owed work
```

The report becomes the bulk execution input. No “scan everything and hope idempotency saves us” migration.

---

# 12. Reconcile stale planning/checklist state only after runtime proof

Do not spend engineering time implementing historical “NOT STARTED” items that current code already provides.

At the end of the offline implementation pass:

1. compare `RAG_E2E_CHECKLIST.md` against current code/runtime evidence;
2. reconcile I1 with `control/control/manifest_ingest.py`;
3. update the retrieval migration ledger only where the authoritative runtime evidence changed;
4. append the required work log/continuity entry;
5. preserve prior history rather than rewriting it to look cleaner.

Documentation follows proven runtime state; documentation does not manufacture it.

---

# 13. Test economics — required timing and scope

## 13.1 Tier A — deterministic targeted tests

**When:** immediately after changing deterministic policy/logic.  
**Cost:** low; no provider/network spend.  
**Purpose:** isolate exact behavior.

Use for:
- profile compiler adversarial fixtures;
- MAP compiler adversarial fixtures;
- limiter/accounting/refusal logic;
- parent-count/readiness arithmetic;
- document-status builder logic;
- migration/reconciliation selection;
- current-contract/supersession semantics.

Run the smallest relevant test module(s). Do **not** run full integration/E2E here.

## 13.2 Tier B — coherent persistence/wiring integration tests

**When:** after a coherent backend boundary is assembled, not after each line edit.  
**Cost:** medium; local Postgres/fakes, no provider spend.  
**Purpose:** prove transaction/persistence/event wiring that unit tests cannot.

Use only where needed, e.g.:
- profile compiled artifact -> status aggregate;
- MAP maps/exclusions/batches -> status aggregate;
- current-contract projection receipt -> readiness transition;
- reconciliation plan -> correct re-arm/no-op behavior;
- new-upload ticket graph reaches the expected semantic stage with provider call stubbed.

Do not repeat every Tier-A malformed-output fixture through Postgres.

## 13.3 Tier C — frontend compile/build

**When:** after backend response shape and UI wiring settle.  
**Command authority:** `frontend/package.json` -> `npm run build`.  
**Purpose:** TypeScript/API/component integration and production bundle.

No new test framework by default.

## 13.4 Tier D — grouped offline acceptance suite

**When:** once the offline implementation is coherent and before any live provider canary.  
Run:
- affected backend/compiler/worker suites;
- Groq conservation regressions;
- one local DB status/readiness integration set;
- migration dry-run tests;
- frontend production build;
- repo governance/guards required by `AGENTS.md`/work-log policy.

This is the first reasonable point for a broader relevant suite. Do not repeatedly run it after each small commit.

## 13.5 Tier E — ONE bounded production fresh-document E2E

**When:** only after the offline acceptance gate in §15 is green.  
**Cost:** real provider/runtime spend.  
**Purpose:** prove actual production composition, not parser edge cases.

One representative new document should traverse the real production path. This replaces many redundant earlier live “smokes.”

If it fails, repair at the smallest layer that explains the failure. Repeat the entire E2E only if the fix changes cross-stage wiring or final behavior.

## 13.6 Tier F — bulk migration integrity

**When:** after the single fresh-document production E2E passes.  
Do not E2E every historical document. Use reconciliation counts, durable receipts, failure classes, and sampled normal queries.

---

# 14. Tests explicitly not worth running early

Do **not** spend time on these until the condition that makes them decision-relevant exists:

- live 15/20/30/40/60 MAP batch-size benchmark **unless** `MAP_RELIABILITY_CAP` is still unresolved and the result will change production configuration;
- full corpus backfill before the one fresh-document canary;
- repeated full repo suites after every logical patch;
- repeated live profile/model calls to test parser tolerance;
- new frontend unit framework for straightforward status rendering;
- live enrichment requalification just to discover whether retrieval reads it — Graphify/file/runtime trace comes first;
- destructive restart/recovery drills already proven by foundation gates unless new migration code introduces a new untested recovery boundary;
- unrelated MCP / model-catalog / UI-polish work that does not block fresh-document-to-query completion.

---

# 15. Offline acceptance gate — STOP before live provider calls

All of the following must be true before the final production canary begins.

## Runtime truth
- [ ] Graphify runtime graph captured against the execution worktree HEAD.
- [ ] Fresh `/upload` path traced to canonical intake and downstream semantic stages.
- [ ] `doc_profile` trigger/worker/persistence/projection path proven.
- [ ] `doc_parent_map` trigger/worker/persistence/projection path proven or missing edge implemented.
- [ ] `parent_enrichment` current reader/writer/trigger behavior classified.
- [ ] contradictory comments/checklists identified and not treated as runtime truth.

## Counts / state
- [ ] canonical parent populations named and implemented.
- [ ] profile actual field counts derive from persisted compiled artifact.
- [ ] profile targets remain advisory.
- [ ] MAP eligible/excluded/mapped/unresolved derive from current-contract durable rows.
- [ ] current-generation projection gaps are visible.
- [ ] document blocker list derives from durable state.
- [ ] legacy `query_ready` is not silently mistaken for vNext completeness.

## Compilers
- [ ] profile compiler adversarial fixture set green.
- [ ] MAP compiler adversarial fixture set green.
- [ ] no JSON/second-parser regression introduced.
- [ ] partial MAP work still persists and repairs only missing aliases.

## Groq/MAP control-plane prerequisite
- [ ] RPD/RPM/provider-header accounting defects closed offline.
- [ ] `LIMITER_REFUSED` proves zero HTTP dispatch/provider spend.
- [ ] actual HTTP dispatch is distinct from lane selection/local attempt.
- [ ] hidden mapping errors/partial compiler outcomes are surfaced.
- [ ] retry behavior cannot blindly burn quota on deterministic/local-refusal failure.

## UI / migration
- [ ] one canonical backend document-status builder exists.
- [ ] Files UI consumes authoritative counts/state.
- [ ] frontend `npm run build` passes.
- [ ] existing-corpus reconciliation dry-run is idempotent/read-only.
- [ ] targeted/grouped offline tests pass.

**STOP if any item above is false.** Do not compensate by “trying a real upload and seeing what happens.”

---

# 16. One bounded production fresh-document E2E

After §15 passes, authorize exactly one representative production ingestion proof.

## 16.1 Document choice

Use a real supported document that:
- is not already in the target corpus;
- is not a tiny toy with one parent;
- is not an extreme 400+ parent stress book for the first proof;
- has enough structure/content to exercise profile fields and multiple MAP batches;
- has a known source identity for retrieval verification.

## 16.2 Capture identifiers

Record:
- source name,
- upload sha/content identity,
- `run_id`,
- `doc_id`,
- corpus,
- active profile/map/projection contracts.

## 16.3 End-to-end acceptance

Prove in order:

1. UI `/upload` accepts the file and returns the canonical run.
2. duplicate guard behavior remains correct.
3. materialized document appears in Postgres.
4. `children_total`, `parents_materialized`, and `parents_with_children` reconcile with direct DB truth.
5. core extraction/projection chain settles.
6. intended profile generation runs (`vnext` state explicit).
7. profile is compiler-valid.
8. UI/API field counts equal persisted compiled profile counts.
9. MAP counts reconcile:
   - eligible,
   - excluded,
   - mapped active,
   - unresolved.
10. unresolved current eligible parents reach zero for this canary unless there is a specifically justified persistent failure that correctly blocks completion.
11. required MAP/profile projections reconcile with current durable source rows.
12. enrichment state is visible and behaves according to its final additive/required classification.
13. core `query_ready` and vNext/semantic-index readiness both display truthfully.
14. normal retrieval/chat — not a test-only path — can retrieve the new document for a query it should answer.
15. final answer cites underlying source evidence, not routing-inferred profile/MAP hypotheses as evidence.
16. Files UI values equal canonical status API values and direct DB truth.
17. re-reading/reconciling the document produces no duplicate current artifacts.

## 16.4 What not to cram into this E2E

Do not intentionally crash every worker, cycle every provider, run every retrieval mode, or repeat all parser malformed-output fixtures here. Those belong to cheaper targeted proofs unless this migration introduced a new recovery contract that has never been tested.

The purpose is one thing: **prove the finished production composition works for a genuinely new document.**

---

# 17. Existing-corpus migration / backfill

Only after §16 passes may the controlled profile/MAP migration resume at scale.

## 17.1 Resume from durable state

Use current contract state to select owed work:
- profile missing/stale only;
- MAP unresolved only;
- projection gaps only;
- enrichment only according to its classification.

Never restart from zero because a corpus is partially migrated.

## 17.2 Provider budgeting

For live MAP/profile work, request budgeting must be based on observed/conservatively reconciled provider capacity after the Groq forensic repair. Do not forecast from lane selection counts or unverified “accounts × advertised RPD” arithmetic.

## 17.3 Live migration dashboard/report

At minimum track:

```text
documents_total
core_query_ready_documents
vnext_profile_ready_documents
vnext_map_complete_documents
vnext_map_partial_documents
semantic_index_ready_documents

parents_materialized
map_eligible
map_excluded
map_active
map_unresolved

profile field-count distributions
profile invalid/stale
map failure classes
projection gaps
enrichment ready/partial/invalid
provider HTTP calls / valid maps persisted
```

Use document and parent denominators, not just “jobs processed.”

## 17.4 Completion arithmetic

For MAP coverage, the current migration authority’s generation invariant remains load-bearing: a partial generation is not complete. Use the current-contract equivalent of:

```text
unresolved eligible parents == 0
AND
all required documents have current qualified profiles
AND
required projections reconcile
```

Do not hide unresolved work by marking a batch/run complete.

---

# 18. Final pipeline acceptance / exit criteria

The RAG pipeline may be declared finished for the current migration when:

- [ ] a newly uploaded production document passes §16 end to end;
- [ ] current document profile generation is intentional, versioned, and observable;
- [ ] profile compiler has cheap-model formatting tolerance without semantic looseness;
- [ ] MAP compiler remains tolerant-format / strict-identity and is adversarially fixture-tested;
- [ ] all current required semantic stages are automatically reachable from a new upload;
- [ ] parent enrichment has an explicit current classification and is not accidentally lost;
- [ ] document-level counts are authoritative and unambiguous;
- [ ] Files UI shows profile/MAP/enrichment/readiness state and exact blockers;
- [ ] current vNext/semantic-index completion is distinct from legacy core readiness until an authorized cutover changes that contract;
- [ ] parent/profile/MAP projections reconcile to durable current rows;
- [ ] existing corpus migration is resumable/idempotent and no blind re-ingestion is required;
- [ ] bulk reconciliation reaches zero unexplained owed current-generation work;
- [ ] normal retrieval/chat samples use the migrated generation without source-evidence/citation regression;
- [ ] no hidden tickets/stalls/errors contradict the visible terminal state;
- [ ] `RAG_E2E_CHECKLIST.md`, migration ledger, and work logs are reconciled to the proven runtime state.

---

# 19. Critical-path work order

Execute in this order unless Graphify proves a dependency requires a small reorder:

### P0-A — Reconstruct runtime truth
Graphify + direct file verification; resolve stale docs/comments and identify all automatic trigger edges.

### P0-B — Finish the bounded offline Groq/MAP control repair
Close conservation/accounting/observability/retry defects. **No live call yet.**

### P0-C — Freeze canonical document-count/status contract
Name parent populations; build one backend status authority; add targeted DB tests.

### P0-D — Finalize document-profile production generation
Prove vNext enablement/rollback and expose actual compiled field counts.

### P0-E — Adversarially certify both compilers offline
Second-model scenario generation -> deterministic fixtures -> minimal proven compiler fixes only.

### P0-F — Finish new-document parent-MAP wiring
Prove/implement automatic stage + projection path and current-generation readiness accounting.

### P0-G — Resolve parent enrichment
Trace readers, classify it, preserve/additive-state or retire only by migration authority.

### P0-H — Wire projection/readiness contract
Current profile/MAP source rows -> current projections -> document/vNext readiness.

### P0-I — Migrate Files UI to the canonical backend contract
Operational counts/status first; forensic detail collapsed.

### P0-J — Run grouped offline acceptance (§15)
Targeted suites + DB integration + frontend build + guards. **Still no provider canary until green.**

### P0-K — Run one production fresh-document E2E (§16)
This is the composition proof.

### P1-L — Resume/reconcile existing corpus migration (§17)
Repair only owed work; budget live requests from provider truth.

### P1-M — Corpus integrity and retrieval sample
Reconciliation counters + sampled normal queries; no per-document E2E ceremony.

### P1-N — Reconcile documentation and declare finish
Update stale gates/ledgers only after production evidence exists.

---

# 20. Do-not-do list

Until this plan’s finish criteria require otherwise:

- do not redesign the chunker;
- do not create a second intake path;
- do not replace MAP DSL with JSON;
- do not add a new compiler/parser layer just for model formatting;
- do not make soft profile item targets hard quotas;
- do not make `parent_enrichment` blocking by accident;
- do not redefine legacy `query_ready` without the authorized retrieval cutover;
- do not count local limiter attempts as provider requests;
- do not treat logs as completion authority;
- do not use backfill scripts as evidence that automatic new-document wiring exists;
- do not rebuild already-current profiles/MAPs during migration;
- do not create a frontend test stack for basic status rendering;
- do not repeatedly run the full production E2E during intermediate implementation;
- do not resume a full corpus backfill before the single fresh-document canary passes;
- do not retire legacy readers/writers from comments or intuition — follow `RETRIEVAL-MIGRATION-DEPENDENCY-V1` reader-before-writer retirement ordering.

---

# 21. Required final evidence packet

At completion, leave one concise evidence packet/work-log entry containing:

1. execution HEAD / commit range;
2. Graphify runtime graph or reference to its generated graph artifacts;
3. canonical document-status contract example from the production canary;
4. direct DB reconciliation for the same canary document;
5. profile field counts and compiler/version identity;
6. parent MAP eligible/excluded/mapped/unresolved counts;
7. required projection reconciliation;
8. enrichment classification and canary state;
9. normal retrieval/chat query demonstrating source retrieval/citation;
10. frontend build result;
11. targeted/grouped test commands + results;
12. bulk migration/reconciliation totals;
13. remaining intentionally deferred work, if any, clearly separated from pipeline blockers.

The evidence packet should be short enough to audit. It is not a transcript of every command run.

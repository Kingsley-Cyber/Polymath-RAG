# RAG Pipeline Final Execution Plan — Unattended Agent Runbook

**Date:** 2026-09-09  
**Repository:** `Kingsley-Cyber/Polymath-RAG`  
**Status:** FINAL EXECUTION AUTHORITY for the RAG pipeline finish work  
**Purpose:** give an implementation agent enough architecture, ordering, stop conditions, diagnostics, and acceptance criteria to finish the pipeline unattended without rediscovering design decisions or wasting provider calls.

> This file is the ordered execution plan for finishing the current RAG pipeline. `docs/wiki/plans/RETRIEVAL-MIGRATION-DEPENDENCY-V1.md` remains authoritative for retrieval-generation retirement/cutover ordering. If current source code contradicts historical comments, source/runtime evidence wins. If this plan conflicts with a later explicit owner decision, the later owner decision wins.

---

# 0. Mission and finish line

The agent's mission is to finish the fresh-document ingestion path so that a normal new document flows through the real control plane, uses the intended provider pools efficiently, becomes fully observable, reaches current semantic-index readiness, and is retrievable through the normal chat/retrieval path.

The agent must not treat a worker starting, a ticket existing, a provider lane being selected, or legacy `query_ready` becoming true as proof of completion.

## 0.1 Final product invariant

For a valid new upload through the canonical production-style `/upload` path:

1. the upload is accepted and assigned a durable run/document identity;
2. materialization/chunking settle deterministically;
3. graph extraction work is drained by the `GRAPH_EXTRACTION` functional pool;
4. the deterministic document grounding context is compiled locally;
5. the document profile is produced by the `DOCUMENT_PROFILE` functional pool and compiler-valid;
6. all retrieval-eligible parents are mapped or explicitly excluded under the current pMAP contract;
7. pMAP work is drained by the `PMAP` functional pool without becoming pinned to a failed account/model lane;
8. required profile/pMAP projections reconcile;
9. current semantic-index/vNext readiness is explicit and truthful;
10. the backend exposes exact counts and exact blockers;
11. the Files/status UI consumes the same canonical backend truth;
12. normal retrieval/chat can retrieve the new document and cite underlying source evidence;
13. the same document/reconciliation operation remains idempotent;
14. a small 3–5 KB text canary completes from accepted upload to semantic terminal state in **less than 4 minutes** on a healthy warmed stack;
15. diagnostics are automatically captured for every canary and are sufficient to identify a >4-minute stall without reconstructing events from scattered logs.

## 0.2 Definition of "under 4 minutes"

The four-minute service-level expectation applies to the iterative micro-canary only.

Start the timer when:
- required services are already healthy/warmed;
- the canary upload has been accepted;
- a `run_id`/document identity exists.

Stop the timer when:
- the document has reached the current intended semantic terminal state;
- required profile/pMAP artifacts and projections reconcile;
- the canonical status builder reports no unexplained blocker.

Do **not** include Docker/service cold-start time in this timer.

If elapsed time reaches 4:00 and the document is not semantically complete, classify that iteration as **FAIL — PERFORMANCE/STALL**, capture diagnostics immediately, identify the exact blocking stage/lane, repair the smallest responsible layer, and run a new unique canary. Do not simply continue waiting and call the run successful later.

---

# 1. Frozen architecture — do not redesign while executing

These decisions are frozen for this finish work.

## 1.1 Four permanent API-backed functional pools

The provider control plane has four permanent functional classes:

```text
1. CHAT
2. GRAPH_EXTRACTION
3. DOCUMENT_PROFILE
4. PMAP
```

They are purposes, not providers.

| Functional pool | Purpose | Execution objective |
|---|---|---|
| `CHAT` | query-time compiler/planning/synthesis work managed by this provider plane | low interactive latency and reliable structured result |
| `GRAPH_EXTRACTION` | high-volume ingestion workhorse for entity/relation/object/fact extraction | drain extraction backlog at maximum compliant valid-work throughput |
| `DOCUMENT_PROFILE` | one document-level semantic/retrieval profile | drain pending documents; compiler-valid profiles with minimal retries |
| `PMAP` | parent-level semantic localization/routing maps | drain mapping batches at maximum valid-maps-per-call throughput |

`parent_enrichment` is **not** a fifth permanent pool. It remains a live legacy/bridge surface until its retrieval readers are migrated and the accepted migration authority permits retirement.

## 1.2 Three asynchronous ingestion work pools plus one latency pool

The three ingestion functions use independent shared queues:

```text
GRAPH_EXTRACTION_QUEUE
DOCUMENT_PROFILE_QUEUE
PMAP_QUEUE
```

`CHAT` uses the same account/model capacity concepts but is not a backlog-draining ingestion queue. Its policy is latency-oriented.

High-level target:

```text
                         INGESTION
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
          ▼                 ▼                  ▼
 GRAPH_EXTRACTION      DOCUMENT_PROFILE       PMAP
     shared queue          shared queue      shared queue
          │                 │                  │
     qualified         qualified account/ qualified account/
 account/model lanes     model lanes         model lanes
          │                 │                  │
          └─────────────────┼──────────────────┘
                            ▼
                  durable receipts/state
```

Every healthy qualified worker in a functional pool may claim eligible work from that pool. Work must not become permanently attached to the first lane that attempted it.

## 1.3 Job lifecycle

Use a durable equivalent of:

```text
PENDING
  -> CLAIMED / ASSIGNED
  -> PROCESSING
      -> DONE
      -> RETRYABLE -> PENDING
      -> TERMINAL_ERROR / DLQ
```

Required properties:
- claim/lease semantics are durable;
- retries are idempotent;
- successful work is never needlessly regenerated;
- provider/network failures return work to the functional pool;
- deterministic/source-invalid failures do not bounce forever;
- retry counts and failure classifications are visible.

## 1.4 Pool-drain invariant

Freeze this invariant:

> A retryable job belongs to its functional pool, not to the account/model lane that first attempted it. If any qualified healthy lane remains available, retryable work remains eligible for processing.

Examples:

```text
lane A -> 429      => lane A cooldown; job returns to pool
lane B -> timeout  => lane B health/retry state; job returns to pool
lane C -> 200 + valid compiler result => DONE
```

A lane-level outage must not manufacture a document-level failure while another qualified lane can perform the job.

Terminal/DLQ classification is appropriate only after the failure is proven non-transient or the functional pool has exhausted meaningful repair paths, for example:
- malformed deterministic input;
- unsupported payload;
- source corruption;
- deterministic compiler-invalid response reproduced across independent qualified attempts;
- explicit unrecoverable provider 4xx caused by the request contract.

Do not DLQ because one provider/account is exhausted or rate-limited.

## 1.5 API key = account lane by default

Freeze the resource hierarchy:

```text
FUNCTION
  -> API KEY / ACCOUNT LANE
      -> MODEL CAPACITY SUB-LANE
```

Rules:

1. Every API key is an independent account/capacity lane by default.
2. Provider name alone must never define a shared limiter/circuit.
3. RPM, TPM, RPD, concurrency, Retry-After, breaker state and adaptive limiter state must not cross API-key boundaries unless an explicit provider-specific shared-capacity contract is proven.
4. Different models under one key may have distinct model-capacity sub-lanes when the provider meters them separately.
5. Any shared quota inside one key must be represented explicitly, not inferred from provider branding.
6. Functional pools reference eligible account/model lanes; functional pools do not own provider quota truth.
7. Every cross-function credential reuse must be visible in inventory/status output.

### Explicit Groq exception

The current six Groq credentials may intentionally serve both:
- `DOCUMENT_PROFILE` through `groq/compound`;
- `PMAP` through `groq/compound-mini`.

This is an explicit owner-approved capacity optimization driven by free-token/account reality. It does not restore a general provider-family mental model.

## 1.6 Capacity has two contracts

Do not collapse provider capacity and workload reliability.

### Provider/account-model capacity

Per API key + model:

```text
rpm
tpm
itpm / otpm where relevant
rpd / tpd where relevant
max_concurrency
retry_after/reset observations
provider headers
account tier/source
```

### Functional workload capacity

Per function + API key + model:

```text
GRAPH_EXTRACTION
  qualified input/batch envelope
  expected output envelope
  valid extraction throughput

DOCUMENT_PROFILE
  qualified document-fingerprint/context envelope
  expected output ceiling
  compiler-pass rate

PMAP
  qualified aliases/request
  expected billed output density
  map completeness/reliability

CHAT
  latency envelope
  structured-output reliability
  output ceiling
```

The scheduler must optimize **valid durable work**, not nominal context-window size or raw request count.

## 1.7 Provider rate-limit catalog is a seed, not runtime authority

The agent should evaluate and, if low-risk, use `llerandi/llm-rate-limits-tracker` as a **seed/reference registry** for published provider/model/tier RPM/TPM/RPD metadata. The project publishes machine-readable JSON and updates weekly.

Do not make production request admission depend on live access to GitHub/jsDelivr.

Preferred integration pattern:

```text
external rate-limit catalog
        ↓ development/sync only
local versioned seed snapshot
        ↓
explicit account/config override
        ↓
observed provider headers / Retry-After / 429 evidence
        ↓
measured safe workload envelope
        ↓
effective scheduling capacity
```

Authority order:

```text
1. actual provider headers/response evidence for this key+model
2. explicit owner/account configuration
3. Polymath measured safe workload envelope
4. versioned external catalog seed
5. conservative unknown-provider default
```

Requirements:
- record catalog source URL/repository commit or retrieval timestamp;
- never write secrets to the catalog snapshot;
- null/unknown published limits remain unknown rather than guessed;
- a stale catalog may seed config but must never override newer runtime evidence;
- rate limits and workload qualification are separate concepts.

## 1.8 Universal deterministic document grounding compiler

pMAP must not depend on the LLM-generated `DOCUMENT_PROFILE` for basic document orientation.

Implement/freeze a CPU-only deterministic artifact, conceptually:

```text
DocumentGroundingContextV1
```

Target payload: **approximately 50–100 tokens**, hard bounded and deterministic.

It must work across all supported document classes, including:
- structured Markdown/text;
- HTML;
- EPUB;
- DOCX;
- native PDFs;
- scanned/OCR PDFs;
- transcripts;
- white papers/reports;
- books/manuals;
- sparse/poorly structured files.

Evidence precedence:

```text
1. explicit metadata/frontmatter
2. title-page/title metadata
3. author/byline/organization
4. explicit date/type when reliable
5. table of contents
6. high-level heading hierarchy
7. repeated high-confidence structural headings
8. filename only as a weak fallback
```

Reject/down-weight:
- page numbers;
- running headers/footers;
- navigation furniture;
- copyright/publisher boilerplate;
- generic `Contents`/`Index` labels without substance;
- repeated scanner artifacts;
- obvious OCR garbage;
- low-confidence tokens that consume the budget without orienting the document.

Rules:
- source-derived only;
- no LLM call;
- no invented summary;
- prefer omission to fabricated context;
- same source inputs + compiler version => same output/hash;
- token/character hard cap;
- persist/hash/version it so pMAP generation identity includes the grounding contract.

Conceptual output examples:

```text
TITLE: Benesh Movement Notation
AUTHORS: Rudolf Benesh; Joan Benesh
TYPE: technical manual
STRUCTURE: notation principles; signs and symbols; body positions; timing; examples
```

or, when weakly structured:

```text
TITLE: <reliable title or sanitized filename>
TYPE: scanned document
STRUCTURE: <only high-confidence headings if available>
```

## 1.9 pMAP input and batching architecture

pMAP receives:

```text
DocumentGroundingContextV1       # global 50–100 token orientation
+
ParentSkeleton[]                 # local source evidence
```

The current `ParentSkeleton` model-facing evidence remains:
- alias;
- heading path;
- headingless opening excerpt where applicable;
- salient excerpt;
- bounded key terms;
- exact deterministic identifiers.

Keep the frozen output DSL:

```text
MAP|<alias>|<routing signature>|<hook1>;<hook2>;<hook3>
```

No JSON-mode redesign, function-calling rewrite, second parser, or chunker redesign is authorized for this finish work.

### Restore original pMAP efficiency objective

The repo's original design objective remains:

> extract everything under one call whenever physically/reliably possible; batch only overflow.

`MAPPING_ONLY_TARGET = 60` is the architectural target.

The current `MAP_RELIABILITY_CAP = 15` is a measured **Groq Compound-Mini workload qualification result**, not a global pMAP architecture ceiling.

Therefore the effective pMAP batch size is per account/model lane:

```text
min(
  functional target,
  token envelope,
  provider/account capacity,
  qualified model reliability envelope
)
```

Examples:

```text
groq_key_1 / compound-mini -> qualified aliases may be 15
other_key / stronger model -> qualified aliases may be 40
other_key / proven model    -> qualified aliases may be 60
```

Do not force every pMAP lane to 15 because one model was flaky at larger structured outputs.

Persist workload qualification. Do not re-benchmark every ingestion.

Requalify only when:
- model/version changes;
- account tier materially changes;
- provider behavior materially changes;
- receipts show sustained degradation;
- the owner deliberately wants to raise the envelope.

## 1.10 pMAP batches are independently drainable jobs

A large document should produce durable pMAP batch jobs that can be processed by different healthy qualified lanes in the PMAP pool.

A 469-parent document should conceptually be:

```text
document
  -> deterministic grounding
  -> deterministic parent skeleton manifest
  -> lane-aware/contract-aware batches
  -> shared PMAP work pool
  -> healthy qualified account/model workers
  -> persist valid partial maps
  -> repair only unresolved parents
```

Do not serialize an entire large document behind one failed lane when independent batches can be drained safely.

Batch identity must include the grounding context/contract and relevant skeleton source identity so old skeleton-only maps do not silently count as current grounded maps.

## 1.11 Document profile and pMAP remain separate durable functions

`DOCUMENT_PROFILE` and `PMAP` are separate contracts even if the same provider key participates in both.

Reason:
- one document profile per document;
- potentially many pMAP batches per document;
- independent retries/backfills;
- pMAP should be able to run from deterministic grounding without waiting for LLM profile generation;
- repairing one missing pMAP batch must not regenerate a valid document profile.

Any dormant combined-call scaffold is an optimization candidate only after these contracts are correct. Single HTTP call does not imply one durable function.

## 1.12 Parent enrichment remains bridge/legacy until reader migration is proven

Current code still mints/reads `parent_enrichment` behavior. Do not delete it from intuition.

The agent must trace its actual retrieval readers and classify it against the migration authority. Do not invest major new provider architecture into this lane unless required to preserve current retrieval during migration.

Do not make parent enrichment a surprise hard readiness barrier unless the accepted migration contract explicitly requires it.

## 1.13 Legacy `query_ready` is not semantic-index completion

Preserve the distinction between:
- legacy/core `query_ready`;
- current/vNext semantic-index readiness.

The canonical document status must expose both until an authorized cutover changes the contract.

---

# 2. Unattended execution rules

The agent is expected to continue without asking routine clarification questions while the owner is away. When the repo/runtime gives enough evidence to choose safely, choose and document the decision.

## 2.1 Safety/worktree rules

Before edits:

1. inspect `git status --short`;
2. inspect current branch/HEAD;
3. run repository preflight/guard commands required by current `AGENTS.md` and repo policy;
4. preserve unknown dirty work;
5. never `git reset --hard`;
6. never mass-stage unrelated files;
7. do not delete user data to make tests pass;
8. do not expose API keys/Authorization headers in diagnostics, commits, logs, screenshots or reports;
9. make coherent commits by phase;
10. update work log/wiki/continuity artifacts required by the repository.

If the working tree contains unrelated owner work, isolate this task in a safe branch/worktree rather than overwriting it.

## 2.2 Graphify + source verification is mandatory

Before modifying runtime behavior, run Graphify against the actual execution HEAD and directly inspect the real files/symbols.

At minimum trace:

```text
/upload
 -> intake_submission
 -> materialization/chunks
 -> extraction tickets/workers
 -> profile_document/core projection
 -> doc_profile
 -> pMAP mint/worker/projection
 -> semantic readiness
 -> retrieval readers
 -> Files/status UI
```

For each functional pool/stage record:
- minting event/ticket;
- queue/work ownership;
- worker registration;
- account/model selection;
- limiter/circuit owner;
- durable artifact/table;
- retry/lease/idempotency path;
- projection path;
- readiness reader;
- API status exposure;
- UI consumer.

Comments are evidence, not authority, when they disagree with executable paths.

## 2.3 Evidence labels

Use concise labels in diagnostics/reports:

```text
MEASURED
CONFIRMED
INFERRED
DISPUTED
UNKNOWN
```

Do not convert guesses into architecture facts.

## 2.4 Testing economics

Use the cheapest proof that can fail for the behavior under test.

- deterministic compiler -> deterministic tests;
- queue routing -> fake provider/persistence tests;
- status aggregation -> local DB integration;
- frontend contract -> TypeScript production build;
- real provider composition -> tiny bounded canary;
- corpus migration -> only after tiny canaries are stable.

Do not repeatedly run whole-repo suites after every edit.

---

# 3. Exact execution order

Execute the following phases in order. A phase may contain small internal iterations, but do not jump ahead across a failed gate.

---

## PHASE 0 — Establish clean execution environment

### Actions

1. Capture:
   - execution branch;
   - HEAD SHA;
   - dirty worktree state;
   - running service/container state;
   - relevant environment/config presence without printing secret values.
2. Run repository preflight/guard commands.
3. Create or confirm a task branch/worktree.
4. Create a dated execution-log directory if repository policy does not already define one.
5. Record the starting architecture/config hashes for:
   - provider configuration;
   - limiter configuration;
   - ticket DAG;
   - profile prompt/compiler;
   - pMAP prompt/compiler/batcher;
   - semantic readiness.

### Gate

Proceed only when unknown owner changes are safe and preserved.

---

## PHASE 1 — Reconstruct runtime truth with Graphify

### Actions

1. Graphify the real current pipeline.
2. Directly verify all load-bearing symbols.
3. Produce a compact runtime-topology report.
4. Resolve stale comments/docs where they conflict with source.
5. Specifically prove:
   - how `GRAPH_EXTRACTION` work is minted and consumed;
   - how `DOCUMENT_PROFILE` is minted and consumed;
   - whether/how `PMAP` is automatically minted for fresh uploads;
   - how parent enrichment is minted/read;
   - what currently makes semantic readiness complete;
   - what the normal retrieval/chat reader consumes.

### Required output

A machine/auditor-readable inventory such as:

```text
function
queue/ticket
worker
lane selector
provider/account/model
limiter owner
artifact/table
projection
readiness reader
retry path
```

### Gate

Do not patch provider routing or stage ordering until this graph is complete enough to explain current behavior.

---

## PHASE 2 — Freeze and implement the account/model lane registry

### Objective

Make provider capacity explicit and stop provider-wide shared-family behavior.

### Actions

1. Build/normalize a lane registry where each lane identifies:
   - functional pool eligibility;
   - provider;
   - API-key environment reference/account identity;
   - model;
   - active/configured/reachable state;
   - provider capacity metadata;
   - functional workload qualification;
   - priority/fallback role.
2. Remove/replace broad provider-family limiter/circuit coupling where it violates the one-key-one-account rule.
3. Preserve explicit Groq account relationships where intentional.
4. Make shared credential use across functions visible.
5. Detect configured-but-unreachable lanes.
6. Fix the document-profile fallback reachability topology if current code still slices configured fallback lanes out of the attempt path.

### Required query views

The registry must be able to answer:

```text
function -> account/model lanes
account/key -> functions/models consuming it
model -> functions/accounts using it
lane -> configured / credential-present / active / reachable / cooldown
```

### Tests

Provider-free deterministic tests for:
- different API keys do not share limiter/circuit state by default;
- model sub-lanes under one key are represented distinctly;
- explicit shared quota relationships work only when configured;
- one lane cooldown does not disable unrelated keys;
- configured fallback lanes are actually reachable;
- no secret values are rendered in inventory output.

### Gate

All account-isolation tests green before live provider calls.

---

## PHASE 3 — Add versioned rate-limit seed/capability metadata

### Objective

Stop manually rediscovering common published RPM/TPM/RPD information while retaining runtime truth.

### Actions

1. Evaluate `llerandi/llm-rate-limits-tracker` schema and licensing/fit.
2. If suitable, create a versioned local seed/snapshot or small sync utility; do not add a hard runtime CDN dependency.
3. Store source metadata and retrieval timestamp/commit.
4. Map only exact known provider/model/tier identities; unknowns stay unknown.
5. Add explicit per-account overrides where the user's real account differs from generic published tiers.
6. Keep runtime provider headers and measured behavior higher authority.
7. Persist/compute an effective capacity view used by the scheduler.

### Tests

- catalog unavailable -> production/runtime still works from local config;
- null catalog values do not become zeros or guessed values;
- explicit account override beats catalog;
- observed provider limit beats stale seed;
- different keys remain isolated.

### Gate

The system can print a sanitized effective-capacity table without making a provider call.

---

## PHASE 4 — Establish durable functional work pools

### Objective

Make `GRAPH_EXTRACTION`, `DOCUMENT_PROFILE`, and `PMAP` true functional pools whose healthy lanes finish retryable work.

### Actions

1. Reuse the existing durable ticket/lease/control-plane substrate wherever possible; do not introduce an unnecessary second orchestration system.
2. Implement the functional equivalent of shared queues within the current control plane.
3. Ensure workers claim work by functional eligibility, not sticky provider ownership.
4. Ensure transient failures return work to the pool.
5. Preserve idempotency and existing receipts.
6. Define terminal/DLQ classification explicitly.
7. Add queue/pool metrics:
   - pending;
   - claimed/in-flight;
   - retryable;
   - terminal;
   - oldest age;
   - throughput;
   - healthy lane count.

### Tests

Using fake providers:

```text
A 429s, B succeeds                 -> job DONE through B
A times out, B/C healthy           -> job remains drainable
one lane breaker opens             -> other keys continue
all lanes transiently unavailable  -> job remains retryable, not DLQ
permanent deterministic failure    -> bounded retries then terminal classification
successful result already exists   -> no duplicate regeneration
```

### Gate

A fake-pool stress test proves working lanes drain the queue despite injected lane failures.

---

## PHASE 5 — Build `DocumentGroundingContextV1`

### Objective

Provide every pMAP request with compact, reliable document orientation without an LLM dependency.

### Actions

1. Identify canonical structural metadata already available from materialization/chunking/fingerprint code.
2. Implement one deterministic compiler rather than format-specific ad hoc prompt logic.
3. Support all currently supported document types using common normalized structural inputs where possible.
4. Enforce a hard context budget targeting 50–100 tokens.
5. Establish deterministic precedence and boilerplate/OCR-noise rejection.
6. Version/hash the compiler and output.
7. Persist or reproducibly derive the context so diagnostics can display it.
8. Include its identity in current pMAP generation/batch identity.

### Required deterministic fixtures

At minimum:
- structured Markdown with title/author/headings;
- plain text with title-like first lines;
- HTML metadata/headings;
- EPUB/TOC-derived structure fixture;
- DOCX heading fixture;
- native PDF metadata/heading fixture where supported by existing extraction;
- scanned/OCR fixture with noisy repeated headers;
- transcript fixture;
- almost-empty/poorly structured document;
- duplicate boilerplate-heavy document;
- non-English/Unicode title/heading fixture where existing parser supports it.

### Invariants

- source-derived only;
- deterministic output/hash;
- no invented summary;
- no API call;
- budget never exceeded;
- garbage does not crowd out high-confidence title/structure;
- missing metadata degrades gracefully.

### Gate

All document-context fixtures green before pMAP prompt integration.

---

## PHASE 6 — Integrate deterministic grounding into pMAP

### Actions

1. Extend the pMAP user prompt with `DocumentGroundingContextV1` ahead of local ParentSkeleton blocks.
2. Preserve the frozen MAP DSL/compiler.
3. Bump the appropriate prompt/map generation contract so old skeleton-only maps cannot satisfy the new grounded generation.
4. Keep partial valid MAP persistence and exact unresolved repair behavior.
5. Ensure prompt render is deterministic for the same grounding context + skeleton manifest.
6. Update diagnostics to capture the sanitized grounding header and a bounded pMAP prompt sample.

### Tests

- same document context + skeletons -> exact same rendered prompt;
- changed grounding source identity -> new mapping generation/batch identity;
- unknown/invented alias still rejected;
- valid partial MAPs persist;
- missing aliases remain exact repair set;
- context text cannot be interpreted as instruction/control data;
- no LLM document profile is required to render the pMAP prompt.

### Gate

Fake-inference pMAP flow passes end to end.

---

## PHASE 7 — Restore pMAP capacity to lane-specific qualification

### Objective

Prevent `MAP_RELIABILITY_CAP=15` from becoming a global functional limit.

### Actions

1. Refactor the effective pMAP batch cap so it can be qualified/configured per account/model lane.
2. Preserve architectural target 60.
3. Preserve measured Compound-Mini safe value unless new evidence justifies change.
4. Use measured density/receipts to guard token envelopes.
5. Persist lane workload capability separately from provider RPM/TPM.
6. Ensure large-document batches are independently drainable by the PMAP pool.
7. Do not run a new expensive 15/30/40/60 provider benchmark unless an actual model's qualified envelope is unknown and the answer changes configuration.

### Offline tests

Use synthetic manifests/fake inference to prove:
- lane qualified at 15 gets <=15 aliases;
- lane qualified at 40 gets <=40;
- lane qualified at 60 gets <=60 when token envelope permits;
- token envelope can lower the functional target;
- successful batches are not regenerated;
- multiple pMAP workers can drain independent batches from one large document.

### Metrics

Expose:

```text
aliases requested
valid maps persisted
maps/request
completion ratio
retries
qualified batch size
input/output/billed tokens
latency
```

Primary pMAP efficiency signal:

```text
valid current maps persisted / actual HTTP requests
```

### Gate

Lane-specific batch qualification works provider-free before live use.

---

## PHASE 8 — Normalize `DOCUMENT_PROFILE` as a functional pool

### Actions

1. Confirm the intended vNext profile generation is explicitly enabled by supported startup/config, not an accidental local environment value.
2. Route pending profile jobs through the `DOCUMENT_PROFILE` functional pool.
3. Make transient failures lane-independent and retryable by another qualified lane.
4. Preserve compiler validity and artifact identity.
5. Fix configured fallback reachability.
6. Keep provider/account/model receipt metadata.
7. Expose actual profile field counts and prompt/compiler/schema versions.

### Profile count contract

Source-anchored:
- ONE;
- SUMMARY;
- TOPIC;
- TERM;
- Q.

Routing-inferred:
- SEARCH;
- THEORY;
- CONCEPT;
- LATENT-PATTERN;
- ANCHOR;
- RECALLQ;
- TENSION;
- BRIDGE;
- INVERSION;
- BOUNDARY;
- SEEALSO.

Targets/aims remain advisory. Never turn soft count aims into validity quotas.

### Tests

- compiler adversarial fixtures;
- lane A failure -> lane B can complete same document;
- valid current profile -> no regeneration;
- fallback lanes reachable;
- status counts equal persisted compiled artifact.

### Gate

Fake-provider and deterministic profile tests green.

---

## PHASE 9 — Normalize `GRAPH_EXTRACTION` as the workhorse pool

### Actions

1. Inventory every currently eligible extraction lane.
2. Route extraction jobs through the shared functional pool using existing durable control-plane primitives.
3. Respect each account/model's provider capacity and qualified workload envelope.
4. Preserve output compiler/ontology contracts.
5. Ensure transient provider failures return jobs to the pool.
6. Maintain traceability:
   - chunk/job identity;
   - lane/account/model;
   - attempt;
   - provider response classification;
   - compiler/extraction outcome;
   - durable receipt.

### Efficiency metrics

At minimum:

```text
parents/chunks completed per minute
valid entities/objects/relationships persisted per request
tokens per valid completed unit
queue age/depth
retry rate
per-lane success rate
```

### Tests

Use fake lanes to prove free-for-all draining and deterministic result persistence before live canaries.

### Gate

No extraction job can remain stuck solely because its first selected provider/account is unavailable while another qualified lane is healthy.

---

## PHASE 10 — Keep `CHAT` latency-oriented and right-size its compiler lane

### Actions

1. Keep CHAT outside the ingestion backlog drainers.
2. Retain account/model isolation and capacity accounting.
3. Right-size the chat compiler/model based on its small structured-plan contract; do not use expensive capacity without measured benefit.
4. Preserve deterministic fallback for invalid structured plans.
5. Ensure ingestion backlog cannot starve interactive chat if credentials are intentionally shared.

### Gate

Chat routing remains functional after provider-control-plane changes and does not accidentally consume ingestion queue semantics.

---

## PHASE 11 — Trace/classify parent enrichment and migration dependency

### Actions

1. Graphify exact current `parent_enrichments` writers/readers.
2. Verify candidate/retrieval surfaces that still consume it.
3. Classify against the migration authority:
   - required bridge;
   - optional bridge;
   - readers migrated/superseded;
   - retire after explicit reader migration.
4. Do not build a new permanent provider pool for it.
5. Keep its visible status separate if still live.

### Gate

No current retrieval reader is silently broken by the functional-pool migration.

---

## PHASE 12 — Build one canonical document status + diagnostics authority

### Objective

A failed canary must explain itself.

### Canonical document status

The backend must expose one authoritative aggregate, reused by compatibility endpoints/UI where practical.

At minimum:

```text
identity
  run_id
  doc_id
  corpus_id
  source

state
  run_status
  core_query_ready
  semantic/vnext verdict
  fully_ready if retained
  blockers[]

chunks
  children_total
  parents_materialized
  parents_with_children

profile
  present
  valid
  generation/schema/prompt/compiler versions
  counts_by_field
  projected
  provider/account/model/attempt summary

pmap
  grounding_context_version/hash
  map_contract
  eligible
  excluded
  mapped_active
  unresolved
  batches total/done/partial
  projected
  provider/account/model/attempt summary

enrichment
  classification
  applicable/ready/invalid/remaining

functional_pools
  graph_extraction queue/healthy lanes/oldest age
  document_profile queue/healthy lanes/oldest age
  pmap queue/healthy lanes/oldest age

stages
  ticket/lease/status/attempt/error/last_progress
```

### Canary diagnostic packet

For every iterative canary, automatically write a run-scoped diagnostic folder. Use the repository's existing reporting convention if present; otherwise use a path conceptually like:

```text
reports/rag_pipeline_canaries/YYYY-MM-DD/<run_id>/
```

Minimum files/content:

```text
summary.md
canary_manifest.json
pipeline_timing.json
canonical_status.json
pool_state.json
lane_capacity.json
provider_receipts.jsonl
profile_status.json
pmap_status.json
grounding_context.txt
pmap_prompt_sample.txt          # sanitized/bounded
projection_status.json
retrieval_probe.json
errors.jsonl
```

Never include:
- raw API keys;
- Authorization headers;
- secret env values;
- unbounded copyrighted document text.

### Timing events

Capture at least:

```text
upload_accepted
intake_started/intake_done
chunks_ready
extraction_started/extraction_done
grounding_compiled
profile_started/profile_done
pmap_started/pmap_done
profile_projection_done
pmap_projection_done
semantic_ready
retrieval_probe_done
```

Where exact events do not exist yet, derive them from durable state and label them accordingly.

### Gate

A seeded local DB/status test can identify exact blockers without reading free-form logs.

---

## PHASE 13 — Reconcile projection/readiness wiring

### Actions

Prove current source rows/artifacts flow to current projections and readiness:

```text
doc_profile artifact -> profile representations -> Qdrant/profile projection
pMAP rows -> pMAP vector text -> Qdrant/pMAP projection
```

Then prove current retrieval readers consume the intended generation.

Required rule:
- routing/profile/pMAP hypotheses may route/deepen retrieval;
- final answer citations come from underlying source evidence, not from inferred routing text as if it were source evidence.

### Gate

A document cannot report semantic-ready while a required current projection is missing.

---

## PHASE 14 — Offline acceptance gate

Before the first timed provider canary, all items below must be green.

### Architecture/control plane
- [ ] Graphify runtime graph captured against current execution HEAD.
- [ ] four functional pools represented explicitly.
- [ ] one-key-one-account isolation implemented/tested.
- [ ] provider-wide family coupling removed except explicit proven relationships.
- [ ] configured lanes have active/reachable diagnostics.
- [ ] retryable work is functional-pool-owned, not sticky-lane-owned.

### Capacity
- [ ] local rate-limit seed/override/evidence precedence works.
- [ ] no runtime dependency on external catalog availability.
- [ ] per account/model provider capacity visible.
- [ ] per function/account/model workload qualification visible.
- [ ] pMAP batch capability is lane-specific.

### Grounding/pMAP
- [ ] `DocumentGroundingContextV1` deterministic fixtures green.
- [ ] grounding payload budget enforced.
- [ ] pMAP prompt includes deterministic grounding.
- [ ] pMAP contract/version invalidates old skeleton-only generation appropriately.
- [ ] MAP compiler remains tolerant-format / strict-identity.
- [ ] partial MAP persistence/repair remains correct.
- [ ] offline 15/40/60 lane-capability batch-planner tests green.

### Profile/extraction
- [ ] profile compiler adversarial tests green.
- [ ] vNext intended startup contract explicit.
- [ ] profile pool failover test green.
- [ ] graph extraction pool failover/drain tests green.

### Status/diagnostics
- [ ] canonical document status builder exists.
- [ ] exact blocker list derives from durable state.
- [ ] run-scoped canary diagnostics writer works locally.
- [ ] frontend/API types compile if changed.

### Repo quality
- [ ] targeted relevant tests green.
- [ ] affected persistence integration tests green.
- [ ] frontend `npm run build` green when frontend touched.
- [ ] repo guards/preflight green.

**STOP if this gate is not green. Do not use live provider calls to discover deterministic implementation defects.**

---

## PHASE 15 — Iterative 3–5 KB timed canary loop

This phase is explicitly authorized for unattended execution after Phase 14 passes.

### 15.1 Canary file specification

Generate a unique synthetic `.txt` file for each iteration.

Size:

```text
3 KB <= file size <= 5 KB
```

Target around 4 KB when convenient.

Each canary should be source-safe synthetic text and contain enough deterministic structure to test grounding and retrieval:
- clear title;
- clear author/organization;
- small `Contents` section or equivalent high-level outline;
- 3–5 meaningful headings/sections;
- at least one exact identifier/code/acronym;
- at least one numerical fact;
- at least one explicit negation (`X does not ...`) to exercise preservation;
- one cross-section relationship that can be queried later;
- no copyrighted copied text.

Example themes may vary per iteration so duplicate guards do not collapse runs.

Do not deliberately create an extreme stress document. This is a fast composition canary.

### 15.2 Canary environment

Prefer:
1. dedicated test/dev corpus/database if already supported;
2. dedicated canary corpus in the real stack if supported;
3. otherwise a clearly marked synthetic source name and safe cleanup/reconciliation path.

Never delete unrelated real user documents to clean canaries.

### 15.3 Timed run procedure

For each iteration:

1. confirm required services healthy;
2. capture pre-run pool/lane state;
3. create unique 3–5 KB canary file;
4. upload through the canonical `/upload` path, not a test-only shortcut;
5. record `run_id`, `doc_id`, source hash and start timestamp;
6. poll canonical status at a sane interval;
7. capture stage/pool transitions into the diagnostic packet;
8. at 4:00, if semantic completion is not reached, mark FAIL immediately and snapshot diagnostics;
9. if complete before 4:00, run a normal retrieval/chat probe against a fact intentionally present in the canary;
10. verify citation/source identity;
11. finalize diagnostic summary.

### 15.4 Canary success criteria

A run passes only if all are true:

- accepted through real upload path;
- expected chunks/parents exist;
- graph extraction settles;
- `DocumentGroundingContextV1` exists and reflects reliable title/author/structure;
- document profile exists and compiler-valid;
- pMAP eligible/excluded/mapped/unresolved arithmetic reconciles;
- current required pMAP/profile projections reconcile;
- semantic/vNext readiness is complete;
- no unexplained pending/retryable tickets remain for the document;
- elapsed accepted-upload -> semantic-ready < 4:00;
- normal retrieval/chat retrieves the canary for a relevant query;
- answer/source evidence is correctly attributable;
- diagnostic packet is complete and sanitized.

### 15.5 Required consecutive passes

Do not close the pipeline after one lucky run.

Require **3 consecutive unique 3–5 KB canaries** to pass the criteria above.

If provider quota/availability makes three impossible despite healthy failover, capture that as a capacity defect; the pool architecture is supposed to let healthy lanes finish the job.

### 15.6 Failure triage order

When a canary fails or exceeds four minutes, do not make broad speculative edits. Diagnose in this order:

```text
1. canonical blocker/status truth
2. stuck/oldest ticket or queue item
3. healthy lane count and reachability
4. limiter admission vs actual HTTP dispatch
5. provider response/Retry-After/headers
6. worker lease/retry behavior
7. compiler validity/yield
8. durable persistence
9. projection reconciliation
10. readiness aggregation
11. retrieval reader
```

Classify failure as one of:

```text
CONTROL_PLANE_STALL
NO_HEALTHY_LANE
LIMITER_FALSE_REFUSAL
PROVIDER_RATE_LIMIT
PROVIDER_TRANSPORT
DETERMINISTIC_INPUT
COMPILER_INVALID
PERSISTENCE
PROJECTION
READINESS
RETRIEVAL
UNKNOWN
```

Repair the smallest responsible layer.

### 15.7 Rerun policy

After a fix:
- run the smallest deterministic/integration test proving that fix first;
- then run a **new unique** 3–5 KB canary;
- reset consecutive-pass count after any canary failure that indicates a pipeline defect.

Do not use repeated live canaries as a substitute for local tests.

---

## PHASE 16 — pMAP efficiency sanity after the micro-canaries

The 3–5 KB canary proves composition, not 60-parent pMAP packing.

After three consecutive micro-canaries pass:

1. inspect measured pMAP receipts from canaries;
2. verify the selected lane's qualified batch size is being honored;
3. run provider-free synthetic planning/persistence tests for a 60-parent manifest;
4. only run a live larger pMAP qualification if an actual production lane's workload envelope remains unknown and the result will change configuration.

Do not automatically spend provider quota proving 60 live when the current model is already known to require 15.

---

## PHASE 17 — Existing corpus reconciliation/backfill

Only after the micro-canary gate passes may existing-corpus migration resume.

### Dry-run first

Produce read-only reconciliation counts:

```text
documents_total
core_ready
profiles_current
profiles_missing/stale
map_eligible
map_excluded
map_active
map_unresolved
docs_map_complete
docs_map_partial
projection_gaps
enrichment bridge state
repairable failures
estimated owed provider work by function/account/model capability
```

### Repair rules

- no blind re-ingestion;
- no regeneration of current valid profiles;
- no remap of current valid grounded maps;
- repair only unresolved/stale current-contract work;
- preserve partial valid MAPs;
- use functional pools so healthy lanes drain owed work;
- do not let optional parent enrichment gaps masquerade as pMAP gaps;
- old contracts never satisfy current-generation completion.

### Bulk execution

Use durable receipts and reconciliation counters. Do not E2E every historical document.

Sample normal retrieval queries after reconciliation.

---

## PHASE 18 — Frontend/status product closeout

If not already completed as part of Phase 12, ensure Files/status UI shows operational truth:

Per document row:

```text
source/type/size
children
parents
profile state
pMAP mapped/eligible/excluded/unresolved
semantic-index state
primary blocker
enrichment bridge state if still live
```

Expanded/debug view may expose:
- profile field counts;
- contract versions;
- pMAP batch counts;
- lane/provider summaries;
- last durable error;
- diagnostics link/reference.

Keep raw model output and forensic payloads collapsed/debug-only.

Do not introduce a frontend testing framework solely for basic status cards. Use backend contract tests + `npm run build` unless UI logic becomes sufficiently stateful to justify more.

---

## PHASE 19 — Final repo validation, commits, continuity and handoff

### Actions

1. run targeted affected tests;
2. run the grouped relevant acceptance suite once;
3. run frontend production build if touched;
4. run repo guards/preflight;
5. inspect `git diff` and working tree for unrelated changes;
6. commit coherent work in understandable slices;
7. update work log/wiki/continuity docs required by repo policy;
8. reconcile stale comments/checklists only after runtime proof;
9. leave no unexplained dirty files;
10. if branch protection/required checks permit and the owner's operating instructions authorize normal merge behavior, complete the normal PR/merge workflow; otherwise leave a clean ready-to-merge PR with exact blockers/check status. Never bypass failed required checks.

### Required final evidence packet

Create one concise final report containing:

```text
execution branch + final SHA/commit range
Graphify/runtime topology reference
frozen functional-pool inventory
account/model lane inventory
rate-limit seed source/version + effective precedence
workload qualification table
DocumentGroundingContextV1 version + fixture results
profile compiler/version + tests
pMAP contract/version + tests
canonical status contract
3 consecutive canary run IDs
each canary size + elapsed time
each canary profile/pMAP/readiness counts
retrieval probe result for each canary
diagnostics folder references
bulk reconciliation totals if executed
frontend build result
repo guard/test commands + results
remaining intentional deferred work
```

The final report must distinguish:
- finished/current;
- legacy bridge still intentionally present;
- deferred/non-blocking;
- blocked by an external condition.

---

# 4. Canonical quantitative contracts

These names should remain unambiguous throughout implementation/status/UI.

## 4.1 Parent populations

```text
children_total
parents_materialized
parents_with_children
map_eligible
map_excluded
map_active
map_unresolved
enrichment_applicable
enrichment_ready
enrichment_invalid_unrecovered
```

Do not assume these populations are equal until the actual policy proves it.

## 4.2 Current-generation scoping

Counts must scope to the current relevant:
- profile schema/compiler/prompt generation;
- pMAP contract/prompt/grounding-context generation;
- active/superseded state;
- input/content hashes;
- projection contract.

Historical stale rows must not satisfy current completion.

## 4.3 Functional-pool operational metrics

### Graph extraction

```text
queue depth/oldest age
healthy qualified lanes
completed units/min
valid objects/relationships per request
tokens per valid unit
retry rate
```

### Document profile

```text
queue depth/oldest age
healthy qualified lanes
valid profiles/request
compiler-pass rate
documents/min
tokens/profile
p50/p95 latency
```

### pMAP

```text
queue depth/oldest age
healthy qualified lanes
qualified aliases/request
requested aliases
valid maps persisted
maps/request
completion ratio
tokens/map
retry rate
p50/p95 latency
```

### Chat

```text
healthy lanes
p50/p95 latency
structured-plan compiler pass/fallback rate
error/retry rate
```

---

# 5. Deterministic compiler certification requirements

## 5.1 Document profile compiler

Use a different capable reviewer model to theorize edge cases, but convert only real risks into deterministic fixtures.

Cover:
- whitespace/CRLF/no final newline;
- markdown fences;
- small preamble/trailing text;
- bullets/numbering;
- label variants;
- duplicate fields;
- unknown labels;
- Unicode punctuation;
- below/above advisory counts;
- missing optional vNext tags;
- malformed optional tags;
- refusal/apology;
- truncation;
- semantically empty core.

Expected philosophy:
- tolerant to harmless presentation drift;
- strict about semantic core/identity;
- never invent missing content to hit a quota.

## 5.2 pMAP compiler

Cover:
- whitespace around `MAP` and separators;
- lowercase/zero-padded aliases;
- CRLF/no final newline;
- reordered valid lines;
- valid MAPs surrounded by prose;
- Unicode drift;
- hook count errors;
- empty/generic hooks;
- duplicate alias;
- unknown alias;
- empty signature;
- partial response;
- valid partial + garbage;
- refusal/empty;
- truncation.

Invariant:

> tolerant format, strict identity; valid partial persists; missing aliases become exact repair set.

## 5.3 Deterministic grounding compiler

Cover the universal document fixtures from Phase 5 and explicitly test:
- title/author precedence conflicts;
- repeated headers;
- TOC with page numbers;
- OCR mirrored/garbled tokens;
- boilerplate-heavy front matter;
- no author;
- no title;
- filename fallback;
- extremely long heading trees;
- token-budget clipping;
- deterministic ordering/tie breaks.

---

# 6. Do-not-do list

Unless a later explicit owner decision changes the plan:

- do not redesign the chunker;
- do not create a second upload/intake path;
- do not replace the MAP DSL with JSON mode;
- do not make pMAP depend on the LLM document profile for basic grounding;
- do not hard-code 15 as the global pMAP batch size;
- do not hard-code 60 for a model that has not qualified at 60;
- do not make provider name a shared failure/capacity domain;
- do not let one key's 429 suppress another key;
- do not let one lane's failure permanently own/stall retryable work;
- do not use external rate-limit catalog data as stronger authority than real account/runtime evidence;
- do not make production depend on the external catalog CDN being online;
- do not count limiter admission/selection as an HTTP provider call;
- do not count logs as completion authority;
- do not turn soft profile count aims into hard quotas;
- do not make legacy parent enrichment blocking by accident;
- do not silently redefine legacy `query_ready` as semantic completeness;
- do not blindly re-ingest the corpus;
- do not repeatedly run large live pMAP benchmarks when configuration will not change;
- do not repeatedly run whole-repo suites during small edits;
- do not use live canaries to debug deterministic parser/compiler defects that local tests can expose;
- do not expose secrets in diagnostics;
- do not delete unrelated user data or dirty work to obtain a green run;
- do not declare success after a single lucky canary;
- do not bypass failed required checks to merge.

---

# 7. Final completion checklist

The task is complete only when:

- [ ] Graphify/runtime topology is documented against final execution HEAD.
- [ ] Four permanent functional pools are explicitly represented.
- [ ] `GRAPH_EXTRACTION`, `DOCUMENT_PROFILE`, and `PMAP` operate as durable shared-work pools.
- [ ] Working qualified lanes finish retryable work when another lane fails.
- [ ] API key = independent account lane is the default control-plane rule.
- [ ] Provider-wide family failure/capacity coupling is removed unless explicitly proven.
- [ ] Provider/account/model capacity and workload qualification are separately visible.
- [ ] External rate-limit data is only a versioned seed/reference layer.
- [ ] `DocumentGroundingContextV1` works deterministically across supported document classes.
- [ ] pMAP receives bounded deterministic global grounding + local ParentSkeleton evidence.
- [ ] pMAP remains the frozen plaintext DSL/compiler contract.
- [ ] pMAP batch size is lane-qualified; architectural target 60 remains intact.
- [ ] current Compound-Mini reliability limit is treated as model-lane evidence, not global architecture.
- [ ] intended vNext document profile generation is explicit and observable.
- [ ] configured profile fallback lanes are reachable.
- [ ] graph extraction pool failover is proven.
- [ ] parent enrichment has an explicit migration classification.
- [ ] canonical document status exposes exact counts/blockers.
- [ ] run-scoped diagnostics exist for every canary.
- [ ] required profile/pMAP projections reconcile.
- [ ] semantic readiness is distinct from legacy `query_ready` until authorized cutover.
- [ ] **3 consecutive unique 3–5 KB `.txt` canaries complete in <4:00 each after upload acceptance.**
- [ ] every passing canary succeeds through normal retrieval/chat with source evidence.
- [ ] existing corpus reconciliation is dry-run-first and idempotent.
- [ ] final relevant tests/build/guards are green.
- [ ] worktree is clean of unexplained task changes.
- [ ] final evidence/continuity report is committed.

When all boxes above are satisfied, the agent may report the RAG pipeline finish work complete for this migration generation.
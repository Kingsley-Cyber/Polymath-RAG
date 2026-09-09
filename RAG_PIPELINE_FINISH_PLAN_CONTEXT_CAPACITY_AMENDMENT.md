# RAG Pipeline Finish Plan Amendment — Deterministic pMAP Context & Lane Capacity

**Date:** 2026-09-09  
**Status:** normative amendment to `RAG_PIPELINE_FINISH_PLAN.md` on the same branch  
**Scope:** correct the pMAP grounding design and formalize per-key/model lane efficiency without changing the frozen MAP DSL/compiler/chunker contracts.

> This amendment **supersedes any wording in the current finish plan that makes pMAP depend on the LLM-generated Document Retrieval Profile for its grounding context**. `DOCUMENT_PROFILE` and `PMAP` remain separate permanent functional lanes. pMAP receives a deterministic document-context header compiled from source/structure metadata, not from an LLM profile artifact.

---

# A. Frozen correction: deterministic document context, not profile-derived context

## A.1 Current repo truth

Current `shared/polymath_shared/document_profile/parent_skeleton.py` gives pMAP a compact local `ParentSkeleton` containing the parent alias, heading path, optional opening excerpt, salient excerpt, key terms and deterministic identifiers.

Current `shared/polymath_shared/document_profile/map_prompt.py` renders only those local fields. No curated document-level context is sent today.

This is too locally blind for ambiguous sections, OCR-heavy documents, repeated headings, appendices, tables and sections whose meaning depends on the document's global structure.

## A.2 Target architecture

Add a **deterministic, CPU-only Document Map Context compiler** whose sole purpose is to orient every pMAP batch to the document without spending another model call and without making pMAP wait for `DOCUMENT_PROFILE`.

Conceptual contract:

```text
DocumentMapContextV1
  title
  authors[]
  source/document type when deterministically known
  year/date when explicitly present
  structural anchors[]
  selected TOC/top-level headings[]
  repeated/boilerplate structural hints when useful
  language/format hint when deterministically known
  context_hash
  compiler_version
```

The rendered model-facing header should usually be **about 50–100 tokens**, bounded by a hard deterministic budget.

Example shape only:

```text
DOCUMENT CONTEXT
Title: Benesh Movement Notation
Author: Rudolf Benesh; Joan Benesh
Structure: introduction; movement notation principles; signs and symbols; body positions; timing; examples
Type: scanned technical manual
```

The exact formatting is implementation-owned and versioned. The point is deterministic orientation, not another summary.

## A.3 Allowed sources

The compiler may use only already-landed deterministic/source-authored information such as:

- normalized document title;
- explicit author metadata/frontmatter;
- explicit publication/year metadata;
- source filename only as a last-resort display hint, never as semantic truth;
- table of contents entries;
- top-level and second-level heading paths;
- heading frequency/order;
- region-role classification already owned by the repository;
- deterministic boilerplate/furniture classification;
- source/document media type;
- other source-authored structural metadata Graphify proves is already available before pMAP.

It must **not** use:

- LLM-generated `ONE`, `SUMMARY`, `TOPIC`, `THEORY`, `CONCEPT`, etc.;
- retrieval-time query information;
- invented authors, dates, subjects or document types;
- another model call;
- heuristic semantic claims that cannot be traced to source/structure metadata.

Missing fields are omitted rather than guessed.

## A.4 Deterministic selection under the token budget

The context compiler should prefer high-value global orientation in this order unless Graphify proves a better deterministic source ordering:

1. title;
2. author(s) / explicit bibliographic metadata;
3. explicit document type/year where present;
4. high-information TOC/top-level headings in document order;
5. additional structural anchors only while budget remains.

Boilerplate headings such as repeated page furniture, copyright headers, generic `Contents`, `Index`, page numbers and OCR garbage should be excluded using existing repository-owned region/noise rules wherever possible rather than inventing a second furniture taxonomy.

The compiler must be deterministic:

```text
same source metadata + same structure + same compiler version
    => same rendered context + same context_hash
```

## A.5 pMAP prompt composition

Every pMAP batch should become:

```text
SYSTEM
  frozen MAP contract

USER
  DOCUMENT CONTEXT            # deterministic 50–100-token orientation
  <DocumentMapContextV1>

  SECTIONS TO MAP
  <existing ParentSkeleton blocks>

  <existing exact-alias footer>
```

The MAP output contract remains unchanged:

```text
MAP|<alias>|<routing signature>|<hook1>;<hook2>;<hook3>
```

No JSON mode, second parser, schema replacement or chunker change is authorized by this amendment.

## A.6 Independence from Document Profile

`DOCUMENT_PROFILE` and `PMAP` remain separate durable functions:

```text
DOCUMENT
  ├─> deterministic DocumentMapContextV1 ─> PMAP
  └─> DocumentFingerprint ─> DOCUMENT_PROFILE
```

They may run concurrently once their deterministic prerequisites exist.

A failed/stale profile must not prevent pMAP from running. A failed pMAP batch must not force profile regeneration.

The existing `combined_global_profile_billed_tokens` / `is_combined` scaffold may be retired, repurposed or left dormant only after Graphify establishes its remaining readers/tests. It must not be mistaken for the target grounding design.

## A.7 Generation identity

Once `DocumentMapContextV1` enters the model input, its identity must participate in pMAP generation identity.

At minimum, Graphify must decide whether to bind `context_hash` into:

- batch/input hash;
- map contract/version;
- prompt version;
- completeness/reconciliation identity.

A map generated from skeleton-only input must never silently satisfy readiness for a generation that contractually requires deterministic document context.

---

# B. Restore pMAP efficiency as an architectural objective

## B.1 The current 15-parent cap is not the original architecture

Current `map_batches.py` explicitly states the owner objective:

> extract everything under ONE call whenever physically possible; batch only the overflow.

The same file still carries:

```text
MAPPING_ONLY_TARGET = 60
MAPPING_ONLY_PROVEN = 40
MAP_RELIABILITY_CAP = 15
```

The `15` cap was added after a measured `groq/compound-mini` behavior where 10–15 aliases were reliable, 20 was mostly complete and >=25 became flaky/empty despite small prompts.

Therefore:

> **15 is a model/deployment-specific reliability limit discovered during the current Groq campaign. It is not the permanent PMAP functional-lane batch size.**

The permanent architecture objective remains to pack as many parents as can be safely and reliably completed in one call, with **60 as the existing target** where the chosen model/deployment can actually support it.

## B.2 Consequence for the test document

A document with 9 eligible parents should require:

```text
1 pMAP provider call
```

before retries.

Its pMAP input should be approximately:

```text
one deterministic document-context header
+ 9 ParentSkeletons
+ frozen MAP instruction/footer
```

There is no architectural reason to split 9 parents across multiple provider calls.

## B.3 Do not globalize one model's weakness

The planner must evolve from:

```text
one global reliability cap for PMAP
```

toward:

```text
PMAP functional lane
  -> account/key lane
      -> model deployment capability
          -> qualified batch envelope
```

Each pMAP-capable deployment should have a capability record such as:

```text
provider
account_lane
model
qualified_aliases_per_call
max_request_chars/tokens
max_output_tokens
rpm
tpm
rpd
max_concurrency
structured/text mode
reliability evidence/version
last_qualified_at
```

`qualified_aliases_per_call` is a reliability envelope, not simply the provider context-window size.

Example:

```text
Groq key N / compound-mini
  qualified_aliases_per_call = 15   # current measured reality

future PMAP model/key X
  qualified_aliases_per_call = 60   # only after the cheap qualification proves it
```

The function planner can then choose the batch size supported by the **actual selected lane** rather than applying the weakest model's cap to every pMAP provider forever.

## B.4 Efficiency metric

The pMAP lane should optimize for useful durable output, not raw request count or theoretical tokens.

Primary metric:

```text
valid_current_maps_persisted / actual_provider_request
```

Supporting metrics:

```text
parents_requested
parents_valid
parents_missing
input_tokens
billed/output tokens
wall time
HTTP outcome
compiler rejects
retry count
maps persisted
```

For a 60-parent call that produces 15 valid maps, the effective yield is worse than a 15-parent call that produces 15 valid maps. Capacity qualification must optimize real map yield/request while preserving correctness.

---

# C. Four permanent API-backed functional lanes remain frozen

Permanent function classes:

```text
CHAT
GRAPH_EXTRACTION
DOCUMENT_PROFILE
PMAP
```

`parent_enrichment` remains a migration/legacy lane until its readers are replaced; it is not a fifth permanent provider pool.

Default capacity identity remains:

```text
API KEY = independent account lane
MODEL UNDER THAT KEY = model-capacity sub-lane
```

No limiter, circuit, Retry-After, RPM, TPM, RPD or concurrency state crosses API-key boundaries merely because the provider name is the same.

Groq's deliberate Profile/pMAP account sharing remains an explicit provider-specific exception.

---

# D. Provider-rate-limit registry: catalog seed + runtime truth

## D.1 Do not hand-maintain every provider limit from memory

Polymath should not require an operator to repeatedly search provider documentation simply to seed reasonable production envelopes.

A usable external seed source exists: `llerandi/llm-rate-limits-tracker` publishes a weekly-updated machine-readable catalog with provider/model/tier RPM, TPM and RPD, provider documentation links, historical snapshots and a static JSON API.

Use an external catalog only as **seed/reference metadata**, never as the final enforcement authority.

Reasons:

- some providers do not publish numeric limits;
- account tier changes limits;
- model quotas may be separate or shared;
- paid/project/org limits may differ from public tables;
- providers may return more current limits in response headers;
- dynamic providers can change capacity without the catalog changing first.

## D.2 Capacity-source precedence

For each account/model lane, record the source of every enforced capacity value.

Recommended precedence:

```text
1. provider response/header truth for this exact credential/model
2. explicit owner/config override for this exact account/model
3. measured safe envelope from Polymath receipts/canary
4. external catalog seed for provider/model/tier
5. conservative fallback when unknown
```

Do not let an external catalog overwrite a lower measured/provider-reported safe ceiling automatically.

## D.3 Local cached registry

Add a provider-capability registry or gateway-owned equivalent that can materialize, for every configured lane:

```text
account_lane
credential_env_name           # never secret value
provider
model
functional_lanes[]
rate_limit_source
rpm_seed / effective_rpm
tpm_seed / effective_tpm
rpd_seed / effective_rpd
max_concurrency_seed / effective
qualified_batch_envelope
last_provider_header_observation
last_429
last_success
last_catalog_refresh
```

External catalog refresh must be fail-open with respect to an already-known local snapshot: a CDN/GitHub outage cannot darken Polymath.

## D.4 Tolerance policy

Production should normally operate below the currently known ceiling rather than repeatedly discover it through 429s.

The exact reserve should be evidence-driven per provider/model, but the control concept is:

```text
known/provider ceiling
  -> safety/tolerance margin
  -> effective scheduling envelope
  -> runtime header/adaptive correction
```

Do not use a single provider-wide percentage if token and request quotas behave differently. TPM, RPM, RPD and concurrency are independent dimensions.

## D.5 Gateway/repository options

Two types of external projects are useful and should not be confused:

### Catalog/index

`llerandi/llm-rate-limits-tracker`
- weekly-updated RPM/TPM/RPD by provider/model/tier;
- machine-readable JSON;
- historical snapshots;
- provider-doc links;
- suitable as a seed/reference layer.

### Enforcement/gateway

LiteLLM / Bifrost-style gateways can own normalized provider transport, deployments, rate limiting, retry/fallback, usage and key routing.

If Polymath adopts a gateway, preserve Polymath's frozen semantics:

```text
Polymath chooses FUNCTION
Gateway chooses/limits ACCOUNT+MODEL DEPLOYMENT
```

The gateway must not collapse separate API keys into provider-wide failure/capacity families.

A gateway evaluation is worthwhile only if it removes more custom limiter/router complexity than it introduces. Finishing the RAG pipeline remains the priority.

---

# E. Efficient qualification/testing — no benchmark theater

## E.1 Deterministic context compiler

Provider-free tests only:

- same source/structure -> byte-identical context and hash;
- title/author/TOC/heading extraction uses real source fields;
- missing metadata is omitted, never fabricated;
- furniture/boilerplate does not consume the context budget;
- hard 50–100-token-class budget is respected;
- OCR garbage does not dominate structural anchors when existing repository noise rules can reject it;
- context hash changes when a load-bearing deterministic input changes.

No live model call is needed for these tests.

## E.2 pMAP prompt contract

Provider-free render tests:

- every batch includes exactly one deterministic document context header;
- existing ParentSkeleton payload remains intact;
- exact aliases remain unchanged;
- MAP DSL remains unchanged;
- context identity participates in current generation identity.

## E.3 Lane capability qualification

Do **not** rerun 15/20/30/40/60 against every provider on every change.

Run a bounded qualification only when:

- a new model is admitted to PMAP;
- the model/version changes;
- the provider behavior materially changes;
- current receipts show the stored envelope is no longer reliable;
- the result will actually change the batch planner configuration.

For a new pMAP deployment, a compact qualification may test candidate envelopes such as 15/30/40/60 on one or a few representative prepared payloads, stopping early when the decision is already clear.

Persist the resulting **qualified envelope** so normal production does not rediscover it.

## E.4 Full-production test timing

The final fresh-document E2E remains the composition proof.

Do not use it to discover deterministic context-compiler bugs or repeatedly tune request packing.

The E2E should prove, for one representative new document:

```text
deterministic document context compiled
PMAP batch plan selected from actual lane capability
provider requests attributable to exact key/model lanes
maps compile/persist/reconcile
profile runs independently
retrieval uses the resulting current generation
```

---

# F. Required plan corrections

When the main `RAG_PIPELINE_FINISH_PLAN.md` is next edited directly, fold this amendment into it and remove/supersede any conflicting language.

Specifically:

1. Replace `profile -> pMAP context` with `deterministic DocumentMapContextV1 -> pMAP`.
2. Remove any requirement that pMAP wait for a compiled Document Retrieval Profile.
3. Keep `DOCUMENT_PROFILE` and `PMAP` as separate permanent functional lanes.
4. Add `DocumentMapContextV1` to pMAP input/current-generation identity and UI/debug observability.
5. Treat `MAP_RELIABILITY_CAP = 15` as a current `groq/compound-mini` deployment envelope, not the PMAP architecture limit.
6. Preserve `MAPPING_ONLY_TARGET = 60` as the existing architectural target where a deployment is qualified for it.
7. Add per-account/model capability records and a lane-efficiency view.
8. Add external rate-limit catalog ingestion as seed metadata, with runtime/provider evidence taking precedence.
9. Do not introduce expensive tests earlier than the decision they inform.

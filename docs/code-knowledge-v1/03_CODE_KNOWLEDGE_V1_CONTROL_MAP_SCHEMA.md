---
title: "POLYMATH CODE-KNOWLEDGE-V1 — Control Map Schema"
date: 2026-09-18
status: "CONTROL-PLANE DESIGN CONTRACT"
---

# 0. Purpose

This document maps CODE-KNOWLEDGE-V1 into the existing Polymath control-plane model:

```text
runs
stage_tickets
outbox_events
stage_attempts
artifacts
projection_receipts
execution_contract
census
scheduler
reconciliation
promotion
```

It is designed to prevent an implementation agent from creating a second scheduler, bypassing ticket semantics, or allowing partially indexed code to appear fully ready.

# 1. Existing control-plane laws to preserve

From current repository architecture:

```text
control = census / scheduling / recovery / readiness
worker = one durable stage
Postgres = workflow authority
outbox = work delivery
stage ticket = explicit durable handoff
execution contract = compatibility pin
projection receipts = desired-vs-observed proof
```

A durable stage mutation must commit the repository-required artifact/receipt/status/outbox state in its prescribed transaction boundary.

# 2. New source metadata schema

Additive document metadata:

```yaml
source_classification:
  contract: code-source-detection-v1
  source_family: document | structured_data | low_code_app | source_code
  source_language: yaml | powerapps_yaml | powerfx | python | lua | luau | null
  semantic_family: document | structured_config | powerapps | code
  detection:
    extension: ".luau"
    mime: "text/plain"
    method: "extension+parser"
    confidence: deterministic
```

Persist as explicit columns or a versioned JSON surface according to current store conventions. Prefer queryable columns for fields used by retrieval filters/readiness.

# 3. Structure manifest schema

Recommended durable table:

```text
document_structure_manifests
```

Columns:

```text
manifest_id            PK, content-addressed
doc_id                 FK → documents
corpus_id
source_family
source_language
structure_contract
parser_name
parser_version
source_hash
manifest_hash
status                 complete | degraded | failed
symbol_count
edge_count
diagnostics            JSONB
active                 BOOLEAN
created_at
updated_at
```

Invariant:

```text
one active manifest per (doc_id, structure_contract)
```

Supersession deactivates; it does not erase history.

# 4. Symbol schema

Recommended:

```text
code_symbols
```

```text
symbol_id              PK content identity
manifest_id            FK
doc_id
corpus_id
symbol_kind
name
qualified_name
char_start
char_end
parent_symbol_id       nullable
heading_path           JSONB
signature              nullable
attributes             JSONB
source_hash
structure_contract
active
created_at
updated_at
```

Identity must include source-bound information so symbols from two documents cannot collide merely because they share a name.

# 5. Parent-link schema

Recommended:

```text
code_symbol_parent_links
```

```text
symbol_id
doc_id
parent_id              canonical chunks.chunk_id
relation               owns | contained_by | primary_parent
structure_contract

PRIMARY KEY(symbol_id, parent_id, relation, structure_contract)
```

This is the bridge from structure to Polymath evidence.

Every structure retrieval result must be able to resolve through this mapping.

# 6. Edge schema

Recommended:

```text
code_edges
```

```text
edge_id                PK content identity
manifest_id
doc_id
corpus_id
source_symbol_id
relation
target_symbol_id       nullable
target_external_name   nullable
resolution             resolved | unresolved | ambiguous | external
confidence             numeric
provenance             parser | static_analysis | powerfx_binding | ...
attributes             JSONB
structure_contract
active
created_at
updated_at
```

Partial unique/index rules should prevent duplicate active logical edges.

# 7. Projection receipts

Recommended projection name:

```text
code_structure
```

Postgres edge/symbol rows are authority.

Neo4j projection receipts prove corresponding graph state.

Desired count and actual count must reconcile.

# 8. Qdrant payload additions

Existing child/profile/pMAP collections remain.

Add optional payload metadata:

```yaml
source_family: source_code
source_language: luau
semantic_family: code
symbol_id: sym_...
symbol_kind: function
qualified_name: WeaponService.Fire
symbol_path:
  - ServerScriptService
  - Combat
  - WeaponService
  - Fire
structure_contract: code-structure-v1
```

Do not require a separate structural vector collection in V1.

# 9. Neo4j namespace

Code structure must not collide semantically with existing Entity/Fact topology.

Suggested:

```text
(:CodeDocument)
(:CodeSymbol)
(:CodeConfigPath)
```

Relationships:

```text
[:CODE_CONTAINS]
[:CODE_CALLS]
[:CODE_REQUIRES]
[:CODE_IMPORTS]
[:CODE_READS]
[:CODE_WRITES]
[:CODE_REFERENCES]
```

Power Apps optional:

```text
[:CODE_READS_CONTROL]
[:CODE_WRITES_DATASOURCE]
[:CODE_NAVIGATES_TO]
```

# 10. Execution-contract additions

Current `worker_contracts()` pins keys such as:

```text
query_policy
chunker
semantic_bundle
ontology_file_sha
extraction_gate
```

Add independent code keys:

```yaml
source_adapter_bundle: <hash>
code_structure_contract: <version/hash>
code_chunk_contract: <version/hash>
code_semantic_prompt_bundle: <hash>
code_query_policy: <version>
```

## Why independent keys

A Luau parser change should not pretend the semantic entity ontology changed.

A pMAP code prompt change should not require reparsing source.

A query-policy change should not require re-ingestion.

Independent keys enable selective regeneration.

# 11. Reconciliation dependency map

Target mapping:

```yaml
stage_contract_dependencies:

  intake:
    - chunker
    - source_adapter_bundle
    - code_structure_contract
    - code_chunk_contract

  extract:
    - semantic_bundle
    - chunker
    - extraction_gate
    - ontology_file_sha
    - code_chunk_contract

  profile_document:
    - semantic_bundle

  project_qdrant:
    - semantic_bundle
    - code_chunk_contract

  project_neo4j:
    - semantic_bundle
    - extraction_gate

  compile_objects:
    - semantic_bundle
    - extraction_gate
    - chunker

  doc_profile:
    - code_semantic_prompt_bundle
    - code_structure_contract

  doc_parent_map:
    - code_semantic_prompt_bundle
    - code_structure_contract
    - code_chunk_contract

  project_code_structure:
    - code_structure_contract

  code_readiness: []
```

The implementation agent must adapt this to the actual active reconciliation map and prove carry/regenerate behavior. Do not blindly insert keys.

# 12. Intake control path

## Non-code

```text
intake ticket
    ↓
existing materializer
    ↓
existing chunk provider
    ↓
existing transaction
    ↓
chunked.v1
```

No code parser should be imported/executed for non-code unless a cheap detector requires it.

## Code / structured source

```text
intake ticket
    ↓
materialize exact text
    ↓
source detect
    ↓
deterministic structure adapter
    ↓
structure manifest
    ↓
source-family chunk provider
    ↓
validate exact offsets
    ↓
persist:
  document
  chunks
  structure manifest
  symbols
  local/unresolved edges
  layout/diagnostics
    ↓
intake artifact + receipt
    ↓
chunked.v1
```

One transaction according to current stage doctrine.

# 13. pMAP trigger map

Current control already has:

```text
auto_map_parents_on_chunks
```

Reuse it.

Trigger condition remains:

```text
intake done
parents exist
feature/scope guards satisfied
no existing doc_parent_map ticket
```

Change only the worker's skeleton/prompt dispatch:

```text
document      → existing skeleton/prompt
code          → code skeleton/code prompt
powerapps     → Power Apps skeleton/prompt
structured    → structured skeleton/prompt
```

No new pMAP scheduler.

# 14. Document Profile trigger map

Current scheduler emits `doc_profile` early after intake in the pMAP rollout path.

Reuse that behavior.

Worker dispatch:

```text
semantic_family
    ↓
fingerprint builder
    ↓
profile prompt family
    ↓
same compiler/profile atom persistence/projection
```

# 15. Structure projection trigger

Add an idempotent auto-mint patterned after `doc_parent_map`.

Pseudo-condition:

```sql
intake ticket = done
AND document.source_family IN ('source_code','low_code_app','structured_data')
AND active structure manifest exists
AND no live project_code_structure ticket/event
AND corpus not archived
AND run not superseded
```

Recommended event:

```text
project_code_structure.v1
```

Recommended stage:

```text
project_code_structure
```

This stage may live outside `STAGE_DAG` initially to preserve compatibility.

If outside DAG, add it to `NON_BLOCKING_STAGES` **for legacy promotion only** and use `CODE_QUERY_READY_V1` as the stricter code retrieval floor.

# 16. project_code_structure worker

Inputs:

```text
run_id
corpus_id
doc_id
manifest_id
structure_contract
```

Effects:

1. resolve new/previously unresolved edges against corpus symbol table;
2. refresh affected edges idempotently;
3. project CodeSymbol/Code* edges to Neo4j;
4. write projection receipts;
5. artifact includes authoritative/projection counts and hashes.

Failure modes:

```text
TRANSIENT store unavailable → ticket returns according to standard hold/retry policy
DETERMINISTIC manifest invalid → failed receipt / code readiness false
Neo4j projection failure → Postgres truth retained; projection incomplete
```

# 17. Readiness schema

Do NOT overload generic run status immediately.

Create a derived view/function:

```text
code_query_readiness(doc_id)
```

Output:

```yaml
contract: code-query-ready-v1
ready: true
source_family: source_code
requirements:
  chunks:
    state: PRESENT
  structure_manifest:
    state: PRESENT
  structure_projection:
    state: PRESENT
  qdrant_children:
    state: PRESENT
  parent_maps:
    state: PRESENT
    eligible: 12
    active: 12
  parent_map_projection:
    state: PRESENT
  doc_profile:
    state: PRESENT
  profile_atoms:
    state: PRESENT
reasons: []
```

Readiness is computed from durable desired-vs-observed state.

Never from "worker said done" alone.

# 18. Query-time gating

When a compiled query has:

```text
code_task != NONE
```

and a corpus contains relevant code sources:

- prefer/require `code_query_ready` documents;
- exclude known incomplete code generations from code-aware lanes;
- if only incomplete code is available, return explicit degradation metadata;
- do not silently label partial code indexing as complete.

Non-code questions remain unaffected.

# 19. Query policy schema

Add orthogonal overlay:

```yaml
code_task:
  value: LOCATE | EXPLAIN | TRACE | IMPACT | DEBUG | CRITIQUE | REFACTOR | GENERATE | COMPARE | NONE
  contract: code-query-policy-v1

target:
  source_families: []
  languages: []
  doc_ids: []
  symbols: []

needs:
  implementation: true
  dependency: false
  reference: false
  config: false
  analog: false
  wildcard: false
```

This is compiled deterministically from existing query-plan signals plus code lexical signals.

# 20. Candidate-lane control schema

```yaml
lanes:

  direct_dense:
    evidence_capable: true

  sparse_exact:
    evidence_capable: true

  document_profile:
    evidence_capable: false
    output: doc_ids

  profile_atom:
    evidence_capable: false
    output: doc_ids/routes

  parent_map:
    evidence_capable: false
    output: parent_ids

  structure:
    evidence_capable: false
    output: parent_ids
    activates_for:
      - TRACE
      - IMPACT
      - REFACTOR
      - DEBUG
      - selected GENERATE/CRITIQUE

  graph_destination:
    evidence_capable: false
    output: doc/parent nominations

  latent:
    evidence_capable: false until source-hydrated
```

All routing-only lanes must converge to original child/source evidence before final citation.

# 21. Candidate roles

```yaml
candidate_roles:
  IMPLEMENTATION:
    source_families: [source_code, low_code_app, structured_data]
  DEPENDENCY:
    origin: structure expansion
  CONFIG:
    source_families: [structured_data]
  REFERENCE:
    source_families: [document]
  ANALOG:
    origin: related implementation
  TEST:
    origin: code structure/path classifier
  LATENT:
    origin: wildcard/latent
```

Roles are orthogonal to existing DIRECT/PRECISION/RELATIONAL/LATENT synthesis roles.

# 22. API control/trace schema

Additive metadata:

```yaml
query:
  intent: APPLICATION
  code_task: CRITIQUE

retrieval:
  code_policy_version: code-query-policy-v1
  structure:
    enabled: true
    seed_symbols: 2
    edges_traversed: 4
    parents_nominated: 3

  candidate_roles:
    before_rerank:
      IMPLEMENTATION: 8
      DEPENDENCY: 4
      REFERENCE: 12
    after_rerank:
      IMPLEMENTATION: 3
      DEPENDENCY: 2
      REFERENCE: 4

readiness:
  code_query_ready: true
```

Do not expose private model reasoning.

# 23. Failure control map

```yaml
failures:

  unsupported_source:
    owner: intake
    effect: typed refusal

  parser_missing:
    owner: intake
    effect: fail/hold; no fake code-ready

  parse_degraded:
    owner: intake
    effect: persist exact source + diagnostics; structure_status=degraded

  structure_projection_unavailable:
    owner: project_code_structure
    effect: source retrieval survives; code readiness false

  pmap_unavailable:
    owner: doc_parent_map
    effect: existing transient-hold semantics

  profile_unavailable:
    owner: doc_profile
    effect: existing hold/degraded semantics

  qdrant_unavailable:
    owner: retrieval/projection
    effect: current error/degradation doctrine

  neo4j_unavailable:
    owner: graph/structure
    effect: HYBRID source lanes survive

  validator_failed:
    owner: code-generation workflow
    effect: generated patch status invalid
```

# 24. Rollback map

Feature flags should allow independent rollback:

```text
CODE_SOURCE_SUPPORT
CODE_PMAP_PROMPTS
CODE_PROFILE_PROMPTS
CODE_STRUCTURE_PROJECTION
CODE_QUERY_POLICY
CODE_STRUCTURE_LANE
CODE_GENERATION_VALIDATION
```

Flag-off behavior:

- existing document behavior unchanged;
- code source may be refused rather than silently flattened if turning off full support;
- never downgrade a previously structure-aware code source to misleading generic prose without an explicit migration policy.

# 25. Control-plane proof checklist

Before merge, prove:

```text
ticket replay idempotency
outbox replay idempotency
contract compatibility refusal
contract drift successor
blue/green source availability
projection reconciliation
code readiness false-on-missing-surface
archived/superseded suppression
non-code zero-cost/no-op path
```

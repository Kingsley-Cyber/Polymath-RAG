---
title: "POLYMATH CODE-KNOWLEDGE-V1 — In-Depth Implementation Plan"
date: 2026-09-18
status: "EXECUTION PACKET — bootstrap repository before implementation"
owner: "@king"
repository: "Kingsley-Cyber/Polymath-RAG"
---

# 0. Mission

Extend Polymath so YAML/Power Apps, Luau/Roblox, and Python source code can be ingested, indexed, retrieved, reasoned over, critiqued, refactored, and used for source-grounded code generation **inside the existing Polymath retrieval architecture**.

This is not a new "Code RAG" product. It is a source-family extension of the existing knowledge system.

The target behavior is:

```text
SOURCE CODE
    ↓
deterministic structure
    ↓
canonical parent / child source evidence
    ↓
semantic pMAP representation
    ↓
global profile + abstract atoms
    ↓
dense + sparse + profile + pMAP + structural + graph + latent retrieval
    ↓
one candidate union
    ↓
one cross-encoder judgement surface
    ↓
exact-source hydration
    ↓
code + technical-corpus reasoning
    ↓
optional generated patch
    ↓
deterministic validation / impact check
```

The system must support mixed queries in which code and prose knowledge are equally first-class:

```text
implementation + documentation + technical books + theory + configs + notes
```

# 1. Non-negotiable architectural laws

## 1.1 One retrieval architecture

Do NOT create:

```text
CODE_FAST
CODE_HYBRID
CODE_GRAPH
CODE_WILDCARD
```

Keep:

```text
HYBRID
GRAPH
WILDCARD
```

Code contributes additional representations and one structural nomination primitive to the same modes.

## 1.2 Exact source is evidence

For every code-aware parent and child:

```python
source[row.char_start:row.char_end] == row.text
```

The existing offset/provenance doctrine remains load-bearing.

Never cite an LLM-generated code summary as proof of what code does.

## 1.3 Structure is deterministic

The following are deterministic/parser-owned:

- source type / language;
- YAML path;
- Power Apps screen/control/property identity;
- Power Fx parse tree;
- Python module/class/function identity;
- Luau function/local/module identity;
- symbol spans;
- exact references;
- statically resolvable calls;
- imports/requires;
- reads/writes when the parser/analyzer can prove them;
- source offsets;
- parent/child containment;
- structural edge provenance.

The LLM MUST NOT invent these.

## 1.4 LLM owns retrieval language, not syntax truth

The ingestion LLM may produce:

- purpose;
- behavior;
- concepts;
- semantic hooks;
- likely natural-language questions;
- design patterns;
- boundaries;
- tensions;
- bridges;
- abstractions.

These are routing surfaces.

The existing deterministic compiler remains the acceptance boundary.

## 1.5 Postgres authority remains

Authoritative durable state:

```text
Postgres
```

Rebuildable projections:

```text
Qdrant
Neo4j
```

Do not make a third-party code index the workflow authority.

## 1.6 Do not recreate parsers

Before implementing a parser or static analyzer, inspect existing mature tooling.

Preferred baseline:

```text
Power Fx:
  microsoft/Power-Fx

Power Apps source:
  microsoft/PowerApps-Tooling

Luau:
  luau-lang/luau
  OR tree-sitter-grammars/tree-sitter-luau for source spans

Python:
  Instagram/LibCST
  built-in ast where sufficient

Architecture/reference implementations:
  SylphxAI/coderag
  Aider-AI/aider
  einad5/codegraph
  ian000/graphify-go
```

If a library is unsuitable, document WHY before replacing it.

# 2. Current Polymath surfaces to preserve

## 2.1 Intake

Current:

```text
intake_worker
    → materialize
    → route_document
    → selected chunk provider
    → canonical document/chunk rows
    → chunked.v1
```

Current document chunk providers include:

```text
legacy_v1
semantic_v2
tier_v3
```

Do not modify `tier_v3` to become an AST parser.

## 2.2 Parent Map

Current pMAP contract:

```text
MAP|alias|routing signature|hook1;hook2;hook3
```

Preserve the compiler and durable map schema.

Code changes the **input skeleton/prompt representation**, not the map output DSL.

## 2.3 Document Profile / Atoms

Reuse:

```text
Document Profile
Profile Atoms
```

They already provide global abstraction / cross-domain routing.

Code-specific fingerprints should feed the existing compiler schema whenever possible.

## 2.4 Retrieval

Current chat retrieval already has:

- direct hierarchical/dense/sparse lanes;
- subqueries;
- Document Profile → pMAP → child;
- Profile Atoms;
- resolution lift;
- SEEALSO/BRIDGE/ANCHOR fan-out;
- graph destination;
- latent rescue;
- WILDCARD frontier;
- one cross-encoder judge.

Code must enter this funnel rather than bypass it.

# 3. End-state data model

A code-bearing document has four simultaneous layers.

```text
L0 SOURCE
    exact source bytes/text
    authoritative evidence

L1 STRUCTURE
    parser-derived hierarchy/symbols/edges
    deterministic routing/dependency truth

L2 SEMANTIC
    pMAP per canonical code parent
    natural-language meaning / hooks

L3 ABSTRACT
    Document Profile / Profile Atoms
    cross-domain concepts, theories, boundaries, bridges, tensions
```

All layers resolve back to:

```text
doc_id
parent_id
child chunk_id
```

# 4. Source classification

Introduce deterministic source-family detection before materialization/chunk dispatch.

Recommended durable fields:

```text
source_family:
    document
    structured_data
    low_code_app
    source_code

source_language:
    yaml
    powerapps_yaml
    powerfx
    python
    lua
    luau
    <future>

semantic_family:
    document
    structured_config
    powerapps
    code
```

Detection precedence:

```text
1. explicit upload metadata if trustworthy
2. filename extension
3. MIME
4. parser validation
5. deterministic structural signatures
```

LLM detection is forbidden.

Example:

```text
Screen_Main.pa.yaml
    ↓
.yaml
    ↓
valid YAML
    ↓
Power Apps source markers / source context
    ↓
source_family=low_code_app
source_language=powerapps_yaml
semantic_family=powerapps
```

Generic YAML remains generic unless the Power Apps detector proves otherwise.

# 5. Materialization design

## 5.1 Add code/text extensions

Extend the materializer registry for:

```text
.py
.lua
.luau
.yaml
.yml
```

Materialization itself should remain boring:

```text
bytes
→ BOM/CRLF/NFC normalization
→ exact normalized UTF-8 source
```

It must NOT rewrite source into synthetic Markdown.

## 5.2 Preserve current document behavior

A Markdown/PDF/HTML/DOCX/EPUB/TXT file MUST continue through its current path.

Acceptance requirement:

```text
existing document materialization fixture hashes unchanged
existing tier_v3 document chunks unchanged
```

unless a deliberately versioned migration is admitted.

# 6. Parser / analyzer adapters

Create a registry; do not create language conditionals across the codebase.

Conceptual contract:

```python
SourceAdapterPlan(
    source_family,
    source_language,
    semantic_family,
    analyzer,
    chunk_provider,
    validator,
)
```

## 6.1 Generic YAML

Use an existing YAML parser with location support. Do not write a YAML grammar.

Extract:

- mappings;
- sequences;
- scalar keys/values;
- full dotted paths;
- line/character spans where available;
- parent/child path relationships.

Canonical parents should be meaningful YAML subtrees, not arbitrary token windows.

## 6.2 Power Apps YAML

Power Apps YAML is two languages:

```text
Power Apps structure
+
embedded Power Fx
```

Use the Power Apps source structure to identify:

- app;
- screen;
- component;
- container;
- control;
- control properties;
- formulas;
- data sources;
- variables where structurally recoverable.

Use `microsoft/Power-Fx` for formula parsing/binding/type information where sufficient context exists.

Do not regex-parse Power Fx syntax.

Recommended parent levels:

```text
screen
control
component
large behavior formula group
```

Recommended children:

```text
individual property/formula blocks
```

Example heading path:

```text
MainScreen
→ btnSubmit
→ OnSelect
```

## 6.3 Luau

Prefer an existing parser:

```text
tree-sitter-grammars/tree-sitter-luau
```

for source-position extraction, with official `luau-lang/luau` tooling used for deeper validation/type analysis when useful.

Extract at minimum:

- functions;
- local functions;
- table/module methods;
- type aliases where useful;
- requires/import-like module references;
- calls;
- property reads/writes when statically obvious;
- returned/exported module table;
- Roblox idioms as an optional later analyzer:
  - `GetService`
  - RemoteEvent/RemoteFunction fire/invoke/handlers
  - ModuleScript `require`.

Do not overclaim dynamic calls.

Every structural edge carries:

```text
provenance
resolution state
confidence
```

## 6.4 Python

Use:

```text
LibCST
```

for source-preserving structure and metadata, plus standard `ast` where useful.

Extract:

- module;
- class;
- function/method;
- imports;
- definitions/references;
- qualified names;
- callers/callees where statically resolvable;
- reads/writes;
- decorators;
- type annotations;
- tests associated by file/symbol heuristics only when deterministic enough.

# 7. Common Structure Manifest

Persist a parser-neutral manifest.

Minimum object model:

```text
StructureManifest
    manifest_version
    parser_name
    parser_version
    source_family
    source_language
    parse_status
    source_hash
    symbols[]
    edges[]
    diagnostics[]
```

Symbol:

```text
symbol_id
doc_id
kind
name
qualified_name
char_start
char_end
parent_symbol_id
heading_path
signature
attributes
```

Edge:

```text
edge_id
doc_id
source_symbol_id
relation
target_symbol_id?
target_external_name?
resolution
confidence
parser_contract
```

Allowed baseline relations:

```text
CONTAINS
DEFINES
REFERENCES
CALLS
REQUIRES
IMPORTS
READS
WRITES
EXPORTS
```

Power Apps extensions:

```text
READS_CONTROL
WRITES_DATASOURCE
READS_DATASOURCE
READS_VARIABLE
WRITES_VARIABLE
NAVIGATES_TO
```

Roblox/Luau later extensions:

```text
FIRES_REMOTE
INVOKES_REMOTE
HANDLES_REMOTE
USES_SERVICE
```

The initial release does not need every relation. Add only relations that materially improve accepted queries.

# 8. Canonical code chunking

Create source-family chunk providers that emit the existing canonical chunk-row semantics.

Do NOT change `tier_v3`.

Suggested providers:

```text
ast_code_v1
structured_yaml_v1
powerapps_yaml_v1
```

## 8.1 Code parent rule

Preferred parent:

```text
top-level function
method
class
module-level cohesive block
Power Apps control/component
YAML meaningful subtree
```

For small source files, a file/module parent is allowed if it improves retrieval without collapsing unrelated code.

## 8.2 Child rule

If parent <= atomic budget:

```text
one exact child
```

If parent is oversized:

```text
split only on parser-owned statement/block/property boundaries
```

Children remain:

- ordered;
- non-overlapping;
- exact source substrings;
- inside exactly one canonical parent.

Nested AST nodes are metadata, not automatically overlapping evidence chunks.

## 8.3 Structural address

Reuse `heading_path`.

Examples:

```text
Python:
api → auth.py → AuthService → authenticate

Luau:
ServerScriptService → Combat → WeaponService → Fire

Power Apps:
MainScreen → btnSubmit → OnSelect

YAML:
weapons → shotgun → reload
```

# 9. Persistence

Add additive Postgres tables; exact names may be adjusted to repository conventions.

Recommended:

```text
document_structure_manifests
code_symbols
code_edges
code_symbol_parent_links
code_structure_projection_receipts
```

Postgres is authoritative.

Qdrant/Neo4j are rebuildable.

Document metadata should durably record:

```text
source_family
source_language
semantic_family
structure_contract
structure_hash
structure_status
```

Use additive migration(s). Never edit an applied migration.

# 10. Ingestion transaction boundary

The per-file deterministic parse needed for chunking should occur inside `intake`, because parent/child identity depends on the parse.

Required order for code/structured sources:

```text
raw bytes
→ deterministic materialization
→ source detection
→ parser/analyzer
→ structure manifest
→ source-family chunk provider
→ exact chunk validation
→ persist document + chunks + structure manifest/symbols
→ intake artifact/receipt
→ chunked.v1
```

Everything that defines canonical source/chunk identity commits atomically with intake.

No ingestion LLM call belongs inside `intake`.

# 11. Cross-file structure resolution / projection

Per-file parse can emit unresolved references.

Add an additive durable structure projection/resolution stage or equivalent existing control-plane extension.

Recommended name:

```text
project_code_structure
event: project_code_structure.v1
```

Its job:

1. read Postgres structure truth;
2. resolve references across current corpus where deterministic;
3. update resolved `code_edges`;
4. project code-only nodes/edges to Neo4j under a disjoint namespace;
5. write projection receipts;
6. never rewrite source chunks.

Suggested Neo4j labels:

```text
CodeDocument
CodeSymbol
CodeConfigPath
```

Suggested edges:

```text
CODE_CALLS
CODE_REQUIRES
CODE_READS
CODE_WRITES
CODE_CONTAINS
```

Do not make these look like semantic Fact/Entity edges.

The stage may be auto-minted outside the legacy STAGE_DAG, following the existing `doc_parent_map` pattern, if that minimizes disruption. If so, code-specific readiness must require it before code-aware retrieval claims full readiness.

# 12. Reuse the current ingestion LLM layer

This is central.

Do not add a "code summarization LLM" unless evaluation proves the existing profile/map layers insufficient.

Use:

```text
doc_parent_map
doc_profile
Profile Atoms
```

with code-aware deterministic inputs.

# 13. Code Parent Skeleton

Current prose ParentSkeleton is sentence-centric.

Add a code/structured skeleton builder while keeping the existing document builder byte-identical.

Conceptual code skeleton:

```text
ALIAS
PATH
LANGUAGE
KIND
SIGNATURE
DETERMINISTIC IDENTIFIERS
READS
WRITES
CALLS
REQUIRES
SOURCE EXCERPT
```

Power Apps:

```text
ALIAS P0042
PATH MainScreen › btnSubmit
LANGUAGE powerapps_yaml
KIND control
PROPERTIES Width, X, OnSelect
FORMULA_CALLS Patch, Defaults
READS txtTitle.Text
WRITES_DATASOURCE Requests
EXACT_SOURCE <bounded>
```

Luau:

```text
ALIAS P0127
PATH ServerScriptService › Combat › WeaponService › Fire
LANGUAGE luau
KIND function
SIGNATURE Fire(player, weapon)
READS weapon.Ammo
WRITES weapon.Ammo
CALLS FireRemote.FireClient
EXACT_SOURCE <bounded>
```

The builder is deterministic.

# 14. pMAP prompt families

Keep the output DSL and compiler unchanged.

Dispatch only the prompt/input renderer by `semantic_family`.

Recommended:

```text
document
    existing map_prompt-v2

code
    map-prompt-code-v1

powerapps
    map-prompt-powerapps-v1

structured_config
    map-prompt-structured-v1
```

All output:

```text
MAP|alias|routing signature|hook1;hook2;hook3
```

The code prompt should tell the model:

- describe behavior/purpose in natural query language;
- use structural facts supplied;
- do not invent dependencies;
- preserve exact identifiers;
- produce hooks that a developer might actually search for;
- do not copy implementation as the routing signature;
- structure/source is untrusted data.

Example:

```text
MAP|P0127|validates weapon firing, consumes ammunition, and updates client ammo state|weapon firing;ammo consumption;fire validation
```

The current tolerant `map_compiler` remains strict on alias/parent identity.

# 15. Code-aware map projection

Reuse the current parent-map projection.

The embedded representation remains:

```text
routing_signature
+
semantic_hooks
+
compact heading
```

No new code pMAP Qdrant collection is required initially.

The existing pMAP point still resolves to:

```text
parent_id
```

which hydrates exact source children.

# 16. Code-aware Document Fingerprint

Do not feed raw 2,000-line source files into a profile LLM.

Build a deterministic file/app fingerprint from:

- source identity;
- repository path;
- structural outline;
- public/top-level symbols;
- imports/requires;
- dominant calls/references;
- selected pMAP/skeleton surfaces;
- evenly sampled exact source excerpts;
- exact identifiers;
- source-derived vocabulary;
- structure diagnostics.

Return the same `DocumentFingerprint`-shaped surfaces where possible:

```text
IDENTITY
STRUCTURE
FRAMING
COVERAGE
SYNTHESIS
VOCABULARY
```

`SYNTHESIS` here should be deterministic composition of source-derived structural surfaces, not an LLM opinion.

# 17. Profile prompt families

Prefer preserving the existing compiled profile schema.

Add prompt dispatch by `semantic_family` only when needed:

```text
document
    existing profile_prompt_vnext

code
    profile-prompt-code-v1

powerapps
    profile-prompt-powerapps-v1

structured_config
    profile-prompt-structured-v1
```

The compiler continues to produce source-anchored and routing-inferred fields.

For code, desirable profile concepts include:

```text
server-authoritative combat state
ammo management
request form validation
responsive layout
data-source mutation
authentication flow
caching strategy
```

Profile atoms remain **routing/expansion only**.

# 18. Embedding levels

Do not create unnecessary vector surfaces.

Initial version should have exactly these semantic levels:

## 18.1 Child source vector

```text
exact source code/config
```

Used for implementation similarity and exact local evidence.

For code, consider embedding a short deterministic prefix with the source only if the current projection contract supports separate routing text without corrupting evidence identity. If not, leave child embedding unchanged and let pMAP carry natural-language semantics.

## 18.2 Parent pMAP vector

```text
natural-language routing signature
hooks
structural heading path
```

Primary natural-language localization door for code.

## 18.3 Document Profile vectors

Global file/screen/module purpose.

## 18.4 Profile Atom vectors

Abstract/cross-domain concepts.

## 18.5 No structure vector required initially

Exact symbol and dependency lookup should be deterministic.

Only add a separate code-symbol vector if evaluation proves pMAP + child vectors miss a documented class of queries.

# 19. Query compiler extension

Keep generic intent.

Add an orthogonal deterministic code-task overlay:

```text
LOCATE
EXPLAIN
TRACE
IMPACT
DEBUG
CRITIQUE
REFACTOR
GENERATE
COMPARE
NONE
```

This is NOT a public retrieval mode.

Inputs:

- resolved request;
- exact terms;
- detected file/symbol names;
- language names;
- code-oriented lexical patterns;
- requested action;
- corpus/source-family availability.

The overlay must be deterministic initially. Do not add a classifier LLM.

# 20. Query decomposition for code tasks

The overlay creates typed information needs.

## LOCATE

```text
implementation target
exact symbol/path
semantic behavior
```

## EXPLAIN

```text
implementation target
direct dependencies
relevant configs
```

## TRACE / IMPACT

```text
exact/semantic seed
structural graph expansion
source hydration
```

## CRITIQUE

```text
implementation target
dependency context
technical reference material
analogous implementation patterns
```

## REFACTOR

```text
implementation target
callers/callees
tests/configs
reference best practices
repository conventions
```

## GENERATE

```text
existing architecture
repository patterns
configs/interfaces
technical documentation
theory/design material
validation constraints
```

# 21. Structural retrieval lane

Add one additive primitive:

```text
STRUCTURE_NOMINATION
```

It should never return final evidence by itself.

Input may be:

- exact symbol;
- semantic seed parents;
- file/path;
- Power Apps control/property;
- resolved entity/symbol;
- pMAP winner.

Output:

```text
parent_ids
doc_ids
route reasons
```

Examples:

```text
CalculateDamage
→ callers
→ Fire
→ CombatHandler
```

```text
btnSubmit.OnSelect
→ READS_CONTROL
→ txtTitle
→ WRITES_DATASOURCE
→ Requests
```

The lane feeds the existing candidate union.

# 22. Candidate roles

Add an orthogonal candidate-role field; do not replace existing evidence roles.

Recommended:

```text
IMPLEMENTATION
DEPENDENCY
CONFIG
REFERENCE
ANALOG
TEST
LATENT
```

This allows critique/generation queries to retain the necessary mixture.

Example `CRITIQUE` desired bundle:

```text
IMPLEMENTATION: code being reviewed
DEPENDENCY: relevant connected code/config
REFERENCE: technical corpus principles
ANALOG: optional better pattern elsewhere in corpus
```

# 23. Fusion

Do not concatenate lane outputs and dump them to the LLM.

Use the existing funnel philosophy.

Recommended order:

```text
1. lane-local candidate generation
2. stable canonicalization to child/parent identity
3. provenance-preserving union
4. role-aware pre-rerank admission
5. ONE cross-encoder judgement
6. resolution lift / source hydration
7. final evidence selection
```

Never rerank pMAP text as if it were code evidence. pMAP nominates the parent; exact source is what is judged/cited whenever possible.

# 24. Role-aware pre-rerank admission

For normal code queries, relevance wins.

For mixed code+knowledge tasks, guarantee only the minimum evidence classes necessary to answer.

Example:

```text
CRITIQUE:
  if available:
    >=1 IMPLEMENTATION candidate
    >=1 REFERENCE candidate

GENERATE:
  if available:
    >=1 IMPLEMENTATION/ARCHITECTURE candidate
    >=1 REFERENCE or CONFIG candidate
```

These are candidate admission floors, not final citation quotas.

The reranker may still reject weak candidates.

# 25. HYBRID behavior

HYBRID for code should consist of:

```text
direct child dense
+
sparse/exact
+
Document Profile
+
Profile Atoms selected by intent
+
pMAP localization
+
resolution lift
+
optional STRUCTURE_NOMINATION based on code_task
+
one reranker
```

Examples:

```text
"where is ammo consumed?"
    exact/sparse + pMAP + dense
    structure optional

"what calls CalculateDamage?"
    exact symbol + structure mandatory
```

# 26. GRAPH behavior

GRAPH remains:

```text
HYBRID
+
relationship traversal
```

For code tasks, relationship traversal can include the code structure graph.

Keep semantic facts and code edges distinct.

Dispatch:

```text
semantic relation query
    → semantic Entity/Fact graph

TRACE/IMPACT/code dependency query
    → CodeSymbol graph

mixed query
    → bounded use of both
```

All graph routes hydrate original source before evidence.

# 27. WILDCARD behavior

WILDCARD remains:

```text
HYBRID baseline
||
divergent frontier
```

For code tasks, the HYBRID baseline includes the relevant structural nominations.

WILDCARD may surface:

- design theory;
- architectural analogy;
- cross-domain mechanism;
- alternative pattern;
- hidden constraint.

It MUST NOT displace the implementation evidence necessary to understand the current code.

A WILDCARD bridge is still routing/ideation, not proof.

# 28. API representation

Extend evidence metadata additively.

Recommended optional fields:

```text
source_family
source_language
semantic_family

symbol_id
symbol_kind
qualified_name
symbol_path

code_candidate_role
structural_route_reason
structure_contract

line_start
line_end
```

Do not break existing evidence consumers.

Suggested prompt legend:

```text
[S1][IMPLEMENTATION][Luau][WeaponService.Fire]
[S2][CONFIG][YAML][weapons.shotgun]
[S3][REFERENCE][Book]
```

`[S#]` remains the citation identity.

# 29. Retrieval trace / receipts

Code-aware turns should receipt:

```text
code_task
source_family filters
language filters

pmap_code_hits
structure_seeds
structure_edges_traversed
structure_parents_nominated

candidate_role_counts_before_rerank
candidate_role_counts_after_rerank

gold-like source hydration counts where eval instrumentation exists
```

This is necessary to diagnose "random code" retrieval.

# 30. Code-specific readiness

Do not let partial code indexing present itself as complete.

Introduce a derived readiness contract:

```text
CODE_QUERY_READY_V1
```

For a code/low-code source, require:

```text
canonical chunks durable
structure manifest durable
structure projection/reconciliation complete
pMAP eligible-parent floor complete
pMAP projection reconciled
Document Profile active
Profile Atoms active/projected where profile generated them
normal child Qdrant projection complete
```

This does NOT have to replace current run `query_ready`.

Recommended compatibility path:

```text
legacy query_ready
    remains unchanged

code_query_ready
    additive derived view/gate
```

Code-aware retrieval can:

- prefer/require `code_query_ready`;
- expose `code_index_degraded` if only partial surfaces are available;
- never silently call a partial index "fully indexed."

# 31. Control-plane trigger design

Use current control patterns.

## 31.1 Intake

Canonical structure/chunk identity is produced during the existing durable intake stage.

## 31.2 pMAP

Reuse existing `auto_map_parents_on_chunks`.

It already fires once intake parents exist.

Code-aware skeleton/prompt dispatch occurs in the worker, not the scheduler.

## 31.3 Doc Profile

Reuse existing early `doc_profile` emission.

Code-aware fingerprint/prompt dispatch occurs in the worker.

## 31.4 Structure projection

Add:

```text
auto_project_code_structure_on_chunks
```

or equivalent minimal scheduler hook.

Guard:

```text
only source_family in {source_code, low_code_app, structured_data where relationships exist}
```

It should follow the idempotent auto-mint pattern used by `doc_parent_map`.

## 31.5 Reconciliation

Add code contract keys to the execution contract so parser/chunker changes create a successor instead of mixing semantics.

Recommended keys:

```text
source_adapter_bundle
code_structure_contract
code_chunk_contract
code_semantic_prompt_bundle
code_query_policy
```

Do not overload `semantic_bundle` with parser versions.

## 31.6 Stage dependency mapping

Recommended reconciliation dependencies:

```text
intake:
  chunker
  source_adapter_bundle
  code_structure_contract
  code_chunk_contract

extract:
  existing dependencies
  + code_chunk_contract indirectly only if not already captured by intake carry logic

doc_profile:
  code_semantic_prompt_bundle
  code_structure_contract

doc_parent_map:
  code_semantic_prompt_bundle
  code_structure_contract
  code_chunk_contract

project_code_structure:
  code_structure_contract

project_qdrant:
  existing embedding/semantic dependencies
  + code_chunk_contract where projection text changed

verify_code_readiness:
  none; it verifies authoritative state
```

Adapt to actual current reconciliation conventions rather than copying this mechanically.

# 32. Blue/green migration

A code chunking/adapter contract change can change parent/chunk identities.

Therefore:

```text
never mutate a live generation in place
```

Use the existing generation-swap / shadow-successor pattern.

For additive new code support, existing non-code corpora must not be re-ingested unless a changed contract actually affects them.

# 33. Generation / refactoring execution

Retrieval should produce a structured evidence bundle before code generation.

Example:

```text
TARGET_IMPLEMENTATION
DEPENDENCIES
CONFIG
REFERENCE_KNOWLEDGE
REPOSITORY_PATTERNS
CONSTRAINTS
```

The generation LLM then receives:

- exact relevant code;
- exact technical evidence;
- structural facts;
- requested goal.

Do not feed it entire repositories.

# 34. Validation

Generated code is a proposal until deterministic tooling passes.

## Python

At minimum:

```text
parse
compile
configured formatter/linter where present
configured type checker where present
target tests
```

LibCST may be used for source-preserving patch generation.

## Luau

Use official Luau tooling where available:

```text
parse
type/static analysis
project-specific tests
```

## Power Apps / Power Fx

At minimum:

```text
YAML/source representation parse
Power Fx parse
binding/type checks when source context supports them
Power Apps source tooling validation where practical
```

Validation failures trigger one bounded repair pass in agent workflows, not silent acceptance.

# 35. Implementation slices

Do not implement this as one giant patch.

## Slice C0 — baseline/freeze

- bootstrap;
- freeze existing retrieval/code-free canaries;
- add no runtime behavior.

## Slice C1 — detection + exact text materialization

- extensions;
- source family/language metadata;
- fixtures;
- document regressions byte-identical.

## Slice C2 — structure manifest contract + DB

- schema;
- identities;
- deterministic adapters behind interfaces;
- no retrieval behavior.

## Slice C3 — Python structure + chunk provider

- LibCST adapter;
- exact chunks;
- tests.

## Slice C4 — Luau structure + chunk provider

- existing Luau parser integration;
- exact chunks;
- tests.

## Slice C5 — YAML / Power Apps structure + chunk provider

- generic YAML adapter;
- Power Apps detector;
- Power Fx parser integration;
- tests.

## Slice C6 — code ParentSkeleton + pMAP prompt dispatch

- keep compiler/output schema;
- map live/offline canaries;
- prove natural-language code localization.

## Slice C7 — code DocumentFingerprint/Profile/Atoms

- profile prompt dispatch only if necessary;
- projection reconciliation.

## Slice C8 — structural persistence/projection

- cross-file edge resolution;
- CodeSymbol graph namespace;
- receipts/reconciliation.

## Slice C9 — query code-task overlay

- deterministic task classifier;
- no new mode.

## Slice C10 — structural nomination lane + fusion

- lane returns IDs/provenance;
- one reranker;
- source hydration.

## Slice C11 — mixed implementation/reference candidate roles

- critique/refactor/generation bundles;
- synthesis prompt metadata.

## Slice C12 — code readiness + control integration

- derived readiness;
- auto-mint;
- reconciliation dependency keys;
- blue/green proof.

## Slice C13 — generation validators

- Python;
- Luau;
- Power Fx/Power Apps;
- bounded repair behavior.

## Slice C14 — qualification

- full acceptance matrix;
- existing document regression;
- code gold sets;
- mixed-corpus canaries;
- WILDCARD/GRAPH canaries.

# 36. Explicit anti-goals

Do NOT:

- rewrite `tier_chunker.py` to parse code;
- create a new vector DB for every code language;
- create one prompt schema per extension unless evaluation proves it;
- let the LLM choose symbol spans;
- let generated summaries become evidence;
- store overlapping every-AST-node chunks;
- dump entire call graphs into context;
- use Graphify/CodeGraph as a second workflow authority;
- fork an existing parser grammar just to avoid an adapter;
- add a CODE public mode;
- bypass the cross-encoder;
- weaken exact-source provenance;
- break current frozen retrieval tests to make code tests pass.

# 37. Definition of done

This phase is DONE only when:

1. Python, Luau, generic YAML, and Power Apps YAML are detected deterministically.
2. Each produces exact parent/child source chunks under source-specific structure.
3. pMAP natural-language queries reliably localize the correct code parent.
4. Document Profile/Atoms make code discoverable at global/abstract levels.
5. exact identifiers/symbols remain retrievable without semantic guessing.
6. deterministic structure queries return correct callers/dependencies.
7. HYBRID fuses code lanes without a new public mode.
8. GRAPH can use code structure while preserving semantic graph separation.
9. WILDCARD can add theory/ideas without displacing implementation evidence.
10. mixed "code + technical book" critique queries return both evidence classes.
11. generation queries retrieve repository constraints before writing code.
12. generated code passes the configured parser/validator in the canary suite.
13. code-specific readiness prevents partial indexes from being called complete.
14. existing non-code retrieval qualification does not regress.

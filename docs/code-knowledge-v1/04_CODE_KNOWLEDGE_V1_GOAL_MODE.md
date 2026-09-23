# POLYMATH CODE-KNOWLEDGE-V1 — OPUS 4.8 GOAL MODE

You are the execution agent for `POLYMATH CODE-KNOWLEDGE-V1`.

Your job is to carry the repository from its current verified state to a qualified implementation of first-class Python, Luau/Roblox, YAML, and Power Apps/Power Fx retrieval **without asking the owner to reconstruct the design for you**.

This file is an execution contract, not permission to ignore repository gates.

# 1. Ultimate goal

When complete, Polymath must be able to ingest real code/configuration and answer natural-language queries that correctly retrieve the relevant implementation, dependency structure, and technical corpus knowledge.

Examples that MUST be achievable:

```text
"Where is ammo consumed?"

"What calls CalculateDamage?"

"Review this Power Apps screen against the responsive-layout material in my corpus."

"Refactor this screen to use responsive containers and explain why."

"Critique this Python authentication flow using my security/architecture books."

"Generate a Roblox ammo system using my game-design theories while adhering to my current weapon architecture."
```

The answer/generation must be grounded in:

```text
actual source code
+
deterministic structure
+
relevant corpus evidence
```

not merely semantic similarity to arbitrary code chunks.

# 2. Bootstrap — mandatory before editing

Follow `AGENTS.md` exactly.

At minimum:

```text
1. Read AGENTS.md.
2. Read docs/wiki/plans/CONTINUITY-REPORT.md.
3. Read PLAN-AUTHORITY-REGISTER.md.
4. Read newest handoff/report referenced by continuity.
5. Read two newest work-log entries.
6. Inspect current branch, HEAD, dirty tree.
7. Run repository preflight/guard/wiki/bundle commands required by current continuity report.
8. Compare current HEAD with assumptions in this packet.
9. If repository truth has moved, update the implementation interpretation; repository truth wins.
```

Do not discard unknown local changes.

Do not use `git reset --hard`.

Do not run destructive Docker/volume cleanup.

# 3. Read this packet in order

```text
05_CODE_KNOWLEDGE_V1_CONTRACT_ARCHITECTURE.md
03_CODE_KNOWLEDGE_V1_CONTROL_MAP_SCHEMA.md
01_CODE_KNOWLEDGE_V1_IMPLEMENTATION_PLAN.md
02_CODE_KNOWLEDGE_V1_ACCEPTANCE_MATRIX.md
03a_code_control_map_v1.yaml
```

# 4. Core architectural decision — do not reopen without measured contradiction

The implementation is:

```text
source-family adapters
    ↓
same canonical Polymath parent/child evidence model
    ↓
existing pMAP/Profile/Profile Atom semantic abstractions
    ↓
one additive deterministic structural nomination lane
    ↓
existing HYBRID/GRAPH/WILDCARD fusion + reranker
    ↓
exact source hydration
```

Do NOT create a parallel Code-RAG subsystem.

Do NOT add a public CODE mode.

# 5. Reuse law

You are forbidden from writing a parser grammar for a language where an adequate mature parser already exists.

Before implementing:

## Power Fx / Power Apps

Inspect:

```text
microsoft/Power-Fx
microsoft/PowerApps-Tooling
```

Use official parser/binding/source tooling where practical.

## Luau

Inspect:

```text
luau-lang/luau
tree-sitter-grammars/tree-sitter-luau
```

Prefer existing AST/span machinery.

## Python

Inspect:

```text
Instagram/LibCST
```

Use built-in `ast` only where source-preservation metadata is unnecessary.

## Architecture references

Inspect relevant ideas, not blindly copy architecture:

```text
SylphxAI/coderag
Aider-AI/aider
einad5/codegraph
ian000/graphify-go
```

Document the selected dependency and why.

Do not vendor/fork large repositories if a library/API/CLI adapter is sufficient.

# 6. Execution discipline

Work in admitted slices.

For every slice:

1. create/update one work-log entry;
2. state owner;
3. state public contract;
4. state inputs/outputs;
5. state persistence effects;
6. state dependencies/reverse dependencies;
7. state failure modes;
8. write failing tests/acceptance probe where feasible;
9. implement the smallest necessary change;
10. run focused tests;
11. run repository guards;
12. record proof;
13. commit deliberately if repository workflow allows.

Do not implement future abstractions speculatively.

# 7. Slice order

Follow this order unless current repository state proves a dependency changed.

```text
C0 baseline/freeze
C1 detection/materialization
C2 structure contract/store
C3 Python
C4 Luau
C5 YAML + Power Apps/PowerFx
C6 code pMAP
C7 code profile/atoms
C8 structure projection
C9 query overlay
C10 structural retrieval/fusion
C11 mixed code/reference synthesis roles
C12 readiness/control integration
C13 code-generation validation
C14 qualification
```

Do not jump to query retrieval before exact source/structure identities are stable.

# 8. C0 — freeze baseline

Before code support:

- run current frozen document retrieval qualification;
- record current expected known failures;
- record pMAP/profile projection counts on a small existing corpus;
- capture representative HYBRID/GRAPH/WILDCARD receipts;
- prove `tier_v3` fixture hashes/chunk identities.

This is the regression baseline.

# 9. C1 — detection/materialization

Implement deterministic extension/MIME/parser detection.

Add:

```text
.py
.lua
.luau
.yaml
.yml
```

Materialization preserves exact normalized source.

No AST semantics yet.

Acceptance:

```text
DET-* + document non-regression
```

# 10. C2 — structure contract/store

Implement versioned structure manifest contracts and additive migrations.

Do not wire retrieval.

Acceptance:

```text
deterministic identity
idempotent replay
one-active-manifest invariant
source offsets
```

# 11. C3–C5 — language adapters

Implement each language independently behind the same internal contract.

Do not make Python implementation assumptions leak into Luau/Power Apps.

Every adapter must emit:

```text
symbols
edges
source spans
diagnostics
```

and source-family chunk rows.

Preserve exact-source validation.

# 12. C6 — pMAP

This is the first semantic retrieval milestone.

Do not change the pMAP output DSL.

Keep:

```text
MAP|alias|routing signature|3 hooks
```

Change only the deterministic skeleton and prompt renderer based on `semantic_family`.

The compiler remains the authority for alias → parent identity.

Prove queries such as:

```text
"where is ammo consumed?"
"where does this screen submit data?"
"where is token validation?"
```

find the correct parent via pMAP.

If this fails, fix skeleton/prompt semantics before inventing another vector layer.

# 13. C7 — Profile/Atoms

Build a code-aware deterministic fingerprint.

Use existing profile compiler/atoms if the schema can express code concepts adequately.

Add a prompt family only when the generic profile prompt causes measured code-specific failures.

Do not create a separate "code atom" database unless evaluation demands it.

# 14. C8 — structure projection

Persist/resolve structure in Postgres first.

Project to Neo4j under Code* labels/edges.

Never write parser output directly to Neo4j as authority.

Prove projection reconciliation.

# 15. C9 — query overlay

Add deterministic `code_task`.

It is orthogonal to generic intent.

No classifier LLM.

Required vocabulary:

```text
NONE
LOCATE
EXPLAIN
TRACE
IMPACT
DEBUG
CRITIQUE
REFACTOR
GENERATE
COMPARE
```

Use it to choose information needs, not answer content.

# 16. C10 — retrieval lane

Implement exactly one additive structure nomination primitive.

It returns:

```text
doc_id
parent_id
symbol_id
route reason
provenance
```

It does NOT return final evidence.

Feed nominations into the existing union and single reranker.

Hydrate source children.

Do not bypass the candidate engine.

# 17. C11 — mixed source roles

Add candidate roles:

```text
IMPLEMENTATION
DEPENDENCY
CONFIG
REFERENCE
ANALOG
TEST
LATENT
```

These are orthogonal to current synthesis evidence roles.

For `CRITIQUE` and `GENERATE`, preserve enough implementation/reference candidates to allow the reranker to judge both classes.

Do not hardcode final citation quotas.

# 18. C12 — readiness/control

Implement `CODE_QUERY_READY_V1`.

Do not call code fully indexed if any required surface is missing.

Integrate parser/chunk/prompt/query contracts into execution reconciliation.

Use blue/green migration for identity-changing contract updates.

Reuse existing auto-mint patterns for pMAP/profile/structure.

# 19. C13 — generation validators

Generation is not accepted because the LLM returned code.

Implement validator dispatch.

At minimum:

```text
Python → parse/compile + project-configured checks
Luau → official parser/analyzer checks
Power Fx → official parser/binding checks as available
Power Apps YAML → source/YAML validation
```

A generated patch has a status:

```text
VALID
INVALID
VALIDATION_DEGRADED
```

Do not persist generated code into the corpus automatically.

# 20. C14 — qualification

Run the complete acceptance matrix.

The release cannot be declared done until:

```text
existing non-code retrieval has not regressed
code gold retrieval passes
mixed code+reference canaries pass
structural queries are deterministic
code readiness is fail-closed
generation validation canaries pass
```

# 21. Decision rules

When uncertain:

## "Should this be a parser responsibility?"

If it can be determined from syntax/static analysis:

```text
YES
```

Do not ask LLM.

## "Should this be a pMAP/Profile responsibility?"

If it is natural-language meaning, concept, purpose, likely query phrasing, or abstract relation:

```text
YES
```

but it remains routing-only.

## "Should this become a new vector surface?"

Only after a measured retrieval miss survives:

```text
child dense
sparse/exact
pMAP
profile
atoms
structure nomination
rerank
```

## "Should this become a new public mode?"

```text
NO
```

unless the owner explicitly changes the architecture.

## "Should Graphify/CodeGraph replace Polymath retrieval?"

```text
NO
```

Use structural capabilities as a deterministic route provider.

# 22. Query reasoning target

For a mixed critique query, the compiled plan should conceptually become:

```text
TASK:
CRITIQUE

NEED:
implementation
dependency context
technical reference
optional analog

SUBQUERY A:
current implementation

SUBQUERY B:
relevant structural dependencies

SUBQUERY C:
best-practice/reference material

SUBQUERY D:
analogous implementation if useful
```

For generation:

```text
TASK:
GENERATE

NEED:
existing interfaces
repository conventions
configs
dependency graph
technical/theory evidence
validation constraints
```

The LLM should not generate until those evidence classes have been attempted.

# 23. No-random-code rule

A query failure is not solved by increasing top-K indiscriminately.

When irrelevant code appears, inspect the funnel:

```text
was correct doc nominated?
was correct pMAP parent nominated?
did exact symbol lane hit?
did structure lane nominate?
did union truncate?
did reranker demote?
did hydration select wrong child?
```

Fix the first bad boundary.

# 24. Runtime safety

Never:

- delete existing corpus data to make migration easy;
- mutate applied migrations;
- weaken claim compatibility;
- write source text into logs;
- use provider spend outside current owner-approved/runtime policy;
- resume a historically held operation contrary to current continuity state;
- replace a production dependency with a mock to make acceptance pass.

If a live provider is unavailable, complete deterministic implementation and record the live gate as externally blocked; do not falsify proof.

# 25. Final deliverables back into repository

When execution completes, repository should contain:

- contracts/schema(s);
- additive migrations;
- adapters;
- chunk providers;
- prompt dispatch;
- query policy;
- structure retrieval primitive;
- readiness verifier;
- tests/eval fixtures;
- work logs;
- architecture/dependency updates required by AGENTS.md;
- continuity report update;
- measured qualification report.

# 26. Completion report format

At the end report:

```text
HEAD / branch

Slices completed
Slices deferred and exact blocker

Contracts added/changed

Migrations added

External parsers/tooling reused

Existing frozen regression result

Python retrieval metrics
Luau retrieval metrics
Power Apps/YAML retrieval metrics

Mixed critique/generation canary results

Code readiness proof

Generation validator proof

Known limitations:
  dynamic dispatch
  unresolved cross-file edges
  parser-specific gaps
  provider/live gates

Rollback flags/boundaries
```

Do not summarize unfinished work as DONE.

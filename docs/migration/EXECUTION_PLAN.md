## Rule

Execute this plan.

Do not repeatedly redesign it.

Repository evidence may justify local adjustments.

Material changes are recorded in `AUTO_DECISIONS.md`.

---

## Phase 0 — Establish repository truth

Inspect:

- `polymath-v4`;
- `TRAIL_AGENT_AUTORESEARCH`;
- Trail A41;
- Hermes deployed skill.

Record:

- path;
- branch;
- HEAD;
- status;
- upstream;
- divergence;
- tags;
- user modifications.

Discover:

- Ponytail if available;
- Graphify;
- Graft;
- CodeGraph/equivalent.

Establish baseline tests once.

Create/update operational migration documents.

### Gate

No unresolved risk of overwriting user work.

---

## Phase 1 — Capability forensics

Before moving implementation, create the complete factual harvest map.

### AutoResearch

Map:

- graph nodes;
- executors;
- prompts;
- validators;
- schemas;
- state;
- dependencies;
- tools;
- tests;
- historical proof.

Cover:

- niche understanding;
- population discovery;
- VOI;
- evidence cards;
- lived situations;
- hypothesis generation;
- bridge/portfolio rules;
- semantic review;
- gap planning;
- channel planning;
- field research;
- product ideation;
- variations;
- product reality;
- sourcing;
- supplier normalization;
- price/MOQ;
- lead construction;
- reporting.

### Governed adapter

Map every current ecommerce step against existing AutoResearch capability and Trail checkpoint.

### Trail

Find the exact dependency closure required by the governed operations.

Determine whether any Trail function duplicates ecommerce-specific planning and assign one owner.

### Gate

Every major responsibility has:

- target owner;
- source implementation;
- migration action.

---

## Phase 2 — Import ecommerce implementation

Import the useful AutoResearch implementation into Polymath additively.

Do not redesign on import.

Preserve source organization where practical.

Exclude:

- secrets;
- private ledgers;
- DBs;
- `.env`;
- caches;
- private historical observations.

Migrate behavioral tests.

### Gate

Imported domain logic passes expected tests in its new location.

---

## Phase 3 — Domain binding seam

Extend the EXISTING adapter runtime minimally so an ecommerce adapter can invoke domain Python.

Possible mechanism depends on source inspection.

Requirements:

- no second scheduler;
- no second durable state machine;
- no second hypothesis ledger;
- existing adapters remain compatible;
- ecommerce domain failures map into existing typed adapter semantics.

### Gate

A real ecommerce domain operation executes through the existing adapter runtime.

---

## Phase 4 — EvidencePacket integration

Replace obsolete Polymath synthesis dependencies with current evidence contracts.

Preserve:

- EvidencePacket;
- provenance;
- CA4;
- utility roles;
- Corpus Explore;
- graph/wildcard lineage.

Adapt domain boundaries instead of deleting useful reasoning.

### Gate

Existing ecommerce understanding logic consumes current Polymath evidence and produces valid downstream structures.

---

## Phase 5 — Restore ecommerce intelligence

In dependency order restore:

### Population

- lenses;
- structural lookup;
- nomination;
- VOI;
- scouting;
- evidence cards;
- lived situations.

### Hypotheses

- bridge;
- portfolio constraints;
- generation;
- validators;
- challenge;
- advisory semantic review.

Use Polymath's durable hypothesis ledger.

Trail remains final deterministic judge.

### Field research

Reconnect:

- gaps;
- channel planning;
- source-specific queries;
- acquisition directives;
- observation normalization;
- curation.

Do not improvise queries that existing planners already know how to compile.

### Products

Restore:

- multiple product concepts;
- multiple variations;
- mechanism links;
- population/problem links;
- evidence links;
- assumptions.

### Product reality

Investigate real:

- competing products;
- prices;
- reviews;
- complaints;
- alternatives;
- missing features.

### Supply

Restore:

- sourcing plan;
- Exa;
- Alibaba;
- CJ;
- normalization;
- price parsing;
- MOQ parsing;
- lead assembly.

Capture stronger provenance at harvest time.

---

## Phase 6 — Embed required Trail core

Use deterministic dependency analysis.

Import minimum required core into Polymath.

Preserve:

- deterministic behavior;
- source registry;
- LAW 1;
- LAW 2;
- Trail logical ownership.

Write/update `ADR-TRAIL-EMBEDDING.md`.

### Gate

Embedded operations pass equivalence/contract tests.

---

## Phase 7 — Registry and authority consolidation

Ensure there is one authoritative registry.

In governed mode:

Trail owns:

- admission;
- judgement;
- qualification;
- score/refusal.

Polymath owns:

- runtime;
- state;
- transitions.

Ecommerce owns:

- domain research and product/sourcing intelligence.

Legacy AutoResearch score/admission logic may remain only as explicitly non-authoritative standalone compatibility until cleanup.

---

## Phase 8 — Reporting

Reuse existing AutoResearch renderer.

Do not build another renderer.

Expand the governed ReportModel/input mapping.

Clearly distinguish:

- POLYMATH KNOWLEDGE;
- LIVE-WORLD OBSERVATION;
- AGENT INFERENCE;
- TRAIL DETERMINATION;
- TRAIL REGISTRY.

### Gate

A fixture-driven report renders the complete product-oriented structure.

---

## Phase 9 — Hermes deployment

Determine why a physical deployed copy exists.

Test:

- filesystem permissions;
- macOS restrictions;
- service context;
- Hermes skill loading;
- supported source paths.

If physical deployment remains required, create deterministic deployment with:

- one source;
- version receipt;
- parity verification.

Do not manually maintain two sources.

---

## Phase 10 — Commerce corpus

Do not restore old indexes.

Fix/prove corpus isolation first.

Then ingest the smallest useful preserved ecommerce source set through current V4.

Verify:

- profiles;
- parents/chunks;
- embeddings;
- atoms;
- graph;
- provenance;
- corpus-scoped retrieval.

---

## Phase 11 — Acceptance ladder

### A. Targeted unit tests

### B. Contract tests

### C. Focused integration

### D. Historical behavioral parity fixture

Structural, not exact-output parity.

### E. Mechanical governed smoke

No expensive open-world research until internal contracts work.

### F. One real ecommerce E2E

Required path:

`seed`
→ knowledge
→ population
→ hypotheses
→ Trail judgement
→ real research
→ Trail admission
→ revision
→ multiple product concepts
→ variations
→ product reality
→ supplier research
→ qualification
→ score/refusal
→ HTML

### G. One negative control

System must be able to reject/withhold an unsupported opportunity.

---

## Phase 12 — Cleanup

Only after acceptance:

- retire external AutoResearch runtime dependency;
- retire external Trail runtime dependency if embedded;
- remove duplicated registry;
- retire duplicate governed ecommerce planners;
- remove manual Hermes mirroring;
- mark legacy authority paths non-governed/obsolete;
- update architecture docs.

Destructive deletion occurs separately from migration proof.

---

## Continuation contract

At every major phase update:

`docs/migration/CONTINUATION.md`

with:

- mission;
- current phase;
- repo state;
- completed work;
- architecture;
- migrated capabilities;
- authority map;
- auto decisions;
- tests;
- failures;
- blocker;
- next exact action;
- DO NOT REDO;
- commits.

A new session reads this and continues.

Do not restart discovery from zero unless repository state contradicts it.

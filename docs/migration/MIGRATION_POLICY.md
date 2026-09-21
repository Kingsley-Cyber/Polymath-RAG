## Mission

Consolidate the fragmented Polymath agent/research stack into `polymath-v4` without recreating functionality that already works.

The immediate product objective is:

> Make ecommerce research work end to end using the proven AutoResearch intelligence, the existing Polymath adapter runtime and knowledge system, and Trail's deterministic governance.

This is a migration and convergence mission.

It is NOT authorization to:

- redesign Polymath generally;
- create a second generic research runtime;
- create a speculative adapter SDK;
- generalize hypothetical future adapters before ecommerce proves the requirement.

Ecommerce is the first complete reference use case.

Generalize only after ecommerce demonstrates what is genuinely reusable.

---

## Authoritative codebases at migration start

### Destination

`~/Documents/polymath-rebuild/polymath-v4`

This becomes the authoritative repository for the distributable Polymath platform.

It already owns:

- knowledge/RAG;
- retrieval;
- EvidencePacket;
- Corpus Explore;
- graph retrieval;
- adapter runtime;
- adapter state;
- hypothesis ledger;
- loops;
- budgets;
- HarnessAction;
- typed stops;
- MCP servers;
- project-level lineage.

Do not build replacements for those systems.

### Ecommerce harvest source

`~/Documents/polymath-rebuild/TRAIL_AGENT_AUTORESEARCH`

Harvest useful ecommerce behavior rather than recreating it.

Expected high-value capability includes:

- ecommerce graph;
- prompts;
- population discovery;
- VOI ranking;
- evidence cards;
- lived situations;
- bridge/portfolio validation;
- advisory semantic review;
- gap compilation;
- channel-query planning;
- web/community research logic;
- product ideation;
- multiple concepts;
- product variations;
- sourcing planning;
- Exa integration;
- Alibaba/CJ handling;
- price/MOQ parsing;
- lead construction;
- ReportModel;
- HTML renderer;
- receipt/journal integrations.

Verify all capabilities against source before migration.

Do not copy private runtime/user evidence.

### Trail harvest source

`~/trail-signal-os-worktrees/A41`

Trail is the deterministic governance authority, not the ecommerce engine.

Harvest only the dependency closure required for:

- registry projection;
- evidence admission;
- hypothesis judgement;
- territory projection;
- qualification;
- deterministic score/refusal;
- required registry data;
- associated contracts/types/tests.

Do not import unrelated Trail platform code merely because it exists.

### Hermes

`~/.hermes`

Hermes is an execution/deployment host.

Its deployed `standalone/opportunity-research` copy is not authoritative source code.

Determine why that physical deployment exists before changing it.

---

## Locked logical ownership

### Polymath

Owns:

- knowledge;
- retrieval;
- generic workflow infrastructure;
- adapter runtime;
- durable state;
- hypothesis ledger;
- generic MCP surfaces.

### Ecommerce adapter

Owns ecommerce-specific intelligence:

- niche interpretation;
- population/lived-situation reasoning;
- ecommerce hypothesis structure;
- research planning;
- product ideation;
- product reality;
- sourcing;
- ecommerce reporting.

### Trail

Owns:

- deterministic evidence governance;
- registry/source policy;
- freshness;
- independence;
- deterministic judgement;
- qualification;
- commercial score/refusal.

Trail does NOT:

- browse;
- retrieve Polymath knowledge;
- generate hypotheses;
- generate products;
- generate suppliers;
- operate the harness.

### Agent host

Owns execution of agent/tool actions.

Possible hosts include:

- Hermes;
- Claude;
- Codex;
- OpenClaw;
- Grok-style agents.

Physical consolidation must not erase these logical boundaries.

---

## Constitutional invariants

### INV-1 — Ecommerce first

Do not implement abstractions for hypothetical adapters unless ecommerce requires them.

### INV-2 — Reuse before rewrite

Use:

`REUSE > WRAP > MOVE > ADAPT > REWRITE`

A rewrite requires evidence that existing code cannot reasonably satisfy the migrated contract.

### INV-3 — One authoritative implementation per responsibility

Do not maintain multiple live authorities for:

- adapter state;
- hypothesis ledger;
- evidence admission;
- hypothesis judgement;
- registry;
- qualification;
- commercial score.

Legacy paths may temporarily exist for parity testing, but they must be clearly non-authoritative.

### INV-4 — Preserve proven ecommerce behavior

Migration should preserve useful structural behavior including:

- population discovery;
- lived situations;
- hypotheses;
- real research;
- multiple product concepts;
- variations;
- supplier research;
- qualified/rejected outcomes;
- reporting.

Exact historical outputs are not required.

### INV-5 — Trail remains deterministic

Embedding Trail changes its deployment/process boundary only.

It does not authorize model-written governance decisions.

### INV-6 — Polymath remains evidence-first for agent workflows

Preserve:

- EvidencePacket;
- grounded retrieval;
- evidence provenance;
- `synthesis_performed=false` where appropriate.

Do not restore unnecessary nested synthesis.

### INV-7 — Privacy by default

Assume the unified repository could eventually be public.

Never migrate:

- credentials;
- API keys;
- cookies;
- browser profiles;
- `.env`;
- private runtime DBs;
- personal data;
- Reddit author/quote private ledgers;
- raw private observations;
- caches;
- machine-local state;
- secrets.

If uncertain, exclude and document.

### INV-8 — Minimal filesystem disruption

Do not reorganize existing `polymath-v4` packages for aesthetics.

Prefer additive integration.

### INV-9 — Reversible migration

Before destructive cleanup:

1. new path works;
2. parity is demonstrated;
3. provenance exists;
4. old path is deprecated/tagged;
5. deletion occurs separately.

---

## Autonomous governance policy

The coding agent is authorized to answer ordinary migration/governance questions itself.

Do not interrupt the user when the answer can be derived from:

1. mission;
2. invariants;
3. ADRs;
4. source code;
5. tests;
6. historical artifacts;
7. minimality;
8. reversibility.

For nontrivial decisions record:

- question;
- evidence;
- applicable invariants;
- decision;
- rejected alternatives;
- reversibility;
- validation.

in:

`docs/migration/AUTO_DECISIONS.md`

### Decision procedure

1. Identify the real owner of the behavior.
2. Search for an existing implementation.
3. Prefer the smallest reversible choice.
4. Check invariants.
5. Record and continue.

Do not ask the user merely because two reasonable implementations exist.

---

## Pre-authorized decisions

### Consolidation

Authorized.

`polymath-v4` is the destination/source-of-truth repository.

### Trail embedding

Authorized in principle, subject to dependency/license/source verification.

The agent may amend ADR-063 narrowly so the required deterministic Trail core may execute in-process within Polymath.

Logical ownership and Trail Laws remain intact.

### Commerce corpus

Do not restore old indexes.

Reconstruct from preserved sources using current V4 ingestion.

Prove corpus isolation before activating ecommerce beside other corpora.

### Repository privacy

Do not block on whether the current GitHub repository is private.

Apply public-safe migration rules.

### Hermes

Do not assume the deployed copy can simply disappear.

Verify its technical reason.

If a physical copy is required, replace manual mirroring with deterministic deployment plus version receipt.

---

## Genuine stop conditions

Stop and ask only when:

1. licensing prevents required consolidation;
2. migration risks publishing secrets/private data;
3. the only viable route requires destructive live-data/index migration;
4. authoritative policies directly contradict and evidence cannot resolve them;
5. required changes alter Trail's fundamental policy semantics without documented intent;
6. required credentials/payment/interactive authorization are unavailable;
7. continuing requires force-push/history rewrite;
8. unresolved user edits would need to be overwritten;
9. evidence proves the architecture cannot preserve an important capability;
10. proceeding requires weakening a security boundary.

These are NOT stop conditions:

- hard coding problem;
- failing test;
- large migration;
- ordinary naming/placement choice;
- multiple reversible implementation options.

---

## Tool policy

Before broad LLM reasoning prefer:

1. git/status;
2. Graphify;
3. deterministic dependency/code graph tooling;
4. Graft;
5. grep/AST/find;
6. targeted reads;
7. targeted tests;
8. model synthesis.

Use Graphify for structural mapping.

Use Graft for targeted traversal/integration.

Use CodeGraph or equivalent for callers, dependencies and blast radius.

If Ponytail is available, it may support long-horizon goal continuity, but it does not replace repository evidence or the migration ledger.

---

## Token discipline

A 1M context window is capacity, not a consumption target.

Do not:

- linearly read repositories;
- repeatedly summarize known architecture;
- regenerate existing plans;
- rerun unchanged full suites;
- use expensive reasoning where deterministic tools answer the question.

Maintain durable state in `docs/migration/`.

---

## Test discipline

Testing order:

`unit → contract → focused integration → mechanical smoke → real ecommerce E2E → negative control`

Run broad suites at meaningful phase gates, not after every edit.

Do not use live web research to debug elementary imports/contracts.

---

## Git discipline

Never overwrite user work.

Inspect:

- branch;
- HEAD;
- status;
- untracked files;
- upstream divergence.

Commit coherent migration phases.

Do not force-push.

Do not publish remote work unless authorized.

---

## Definition of success

One `polymath-v4` checkout contains everything required for the complete ecommerce reference implementation, excluding external credentials and agent-host-specific runtime access.

A real run must demonstrate:

`seed`
→ Polymath knowledge
→ niche/population analysis
→ grounded hypotheses
→ Trail judgement
→ live research
→ Trail admission
→ revision
→ multiple product concepts
→ variations
→ product reality
→ supplier research
→ qualification
→ Trail score/refusal
→ governed HTML dossier

A defensible rejection is success.

A software/runtime failure is not.


---

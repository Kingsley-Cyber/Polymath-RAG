# Polymath Semantic Transduction Restoration
## Agent Build Reference and Goal-Mode Implementation Specification

**Status:** OWNER-AUTHORIZED IMPLEMENTATION REFERENCE  
**Phase:** Post-migration semantic alignment / semantic transduction restoration  
**Canonical production adapter:** `ecommerce.product_research`  
**Compatibility adapter:** `trail.product_discovery`  
**Primary audit baseline:** `docs/migration/TRANSDUCTION_AUDIT.md`  
**Owner realignment:** `docs/migration/OWNER_REALIGNMENT_2026-09-21_LATENT_TRANSDUCTION.md`

---

# 0. Why this document exists

The consolidation migration succeeded.

Polymath now has a working execution architecture:

- arbitrary corpus retrieval;
- governed adapter execution;
- durable adapter state;
- durable hypothesis state;
- real external research;
- Trail admission;
- Trail judgement;
- hypothesis revision;
- product ideation;
- product reality;
- sourcing;
- qualification;
- scoring / refusal;
- hosted MCP;
- per-principal access;
- production deployment.

A real hosted run completed the complete production ecommerce workflow and reached a lawful Trail refusal after real research, competitor investigation, supplier research and qualification.

The problem discovered by that run is therefore **not** missing RAG, missing Trail, missing orchestration, missing persistence, missing hosted MCP, missing product concepts, missing sourcing, or a need for an entirely new opportunity engine.

The problem is narrower:

> **Polymath already creates rich latent-opportunity semantics, but subsequent consumer boundaries repeatedly reduce, flatten, ignore, disconnect or misroute those semantics.**

The implementation task is therefore:

> **Restore semantic continuity across the existing production architecture.**

This document is intended to be sufficiently detailed that a fresh coding agent can operate in goal mode without reconstructing the architecture from conversation history and without inventing another system.

---

# 1. Governing thesis

The product thesis is broader than ecommerce RAG.

The intended machine is:

```text
ARBITRARY KNOWLEDGE CORPUS
        ↓
POLYMATH RETRIEVAL
        ↓
SEMANTIC ABSTRACTION
        ↓
drivers
behaviors
adaptations
constraints
frictions
workarounds
latent values
physical jobs
causal mechanisms
transferable invariants
possible populations
        ↓
LATENT OPPORTUNITY STRUCTURE
        ↓
HYPOTHESIS PORTFOLIO
        ↓
TRAIL DETERMINISTIC NORMALIZATION / GOVERNANCE
        ↓
HYPOTHESIS-SPECIFIC REALITY RESEARCH
        ↓
SUPPORT / CONTRADICTION / MARKET REALITY
        ↓
SEMANTIC REVISION
        ↓
PRODUCT MECHANISMS
        ↓
TYPED PRODUCT CONCEPTS
        ↓
PRODUCT REALITY
        ↓
SUPPLY REALITY
        ↓
QUALIFICATION / LAW-1 SCORE OR LAWFUL REFUSAL
```

The source corpus does **not** need to be ecommerce knowledge. Cinema, fiction, military logistics, psychology, game design, engineering manuals, history, gardening or unrelated knowledge collections may all act as hypothesis-generating substrates.

The knowledge source and eventual market do not need to share a domain.

The system should be capable of:

```text
specific source observation
        ↓
generalized causal / behavioral structure
        ↓
transferable invariant
        ↓
candidate population
        ↓
earned bridge
        ↓
commercial hypothesis
        ↓
real-world falsification
```

Source knowledge is inspiration / prior structure. Only live-world evidence may establish that a market, friction, unmet need, product gap or supply reality actually exists. Trail preserves that epistemic boundary.

---

# 2. What the audit proved

The canonical production adapter, `ecommerce.product_research`, already contains a substantial semantic transformation architecture.

It is incorrect to claim that production has “no Opportunity IR” or “no semantic transformation layer.”

The current production workflow already creates and persists:

- transformation lenses;
- typed primitive families;
- drivers;
- behaviors;
- adaptations;
- constraints;
- workarounds;
- physical interactions;
- frictions;
- latent values;
- unresolved questions;
- shared predicates;
- transferable invariants;
- latent structures;
- possible populations;
- population leads;
- community leads;
- value-of-information ranking;
- seed-population discount;
- rich hypothesis ledger state;
- bridge paths;
- inference boundaries;
- alternatives;
- falsifiers;
- physical jobs;
- product mechanisms;
- market-facing `product_terms`;
- product concepts;
- product variations;
- real-world evidence;
- supplier leads.

These are durable in the existing architecture through:

- `adapter_steps.output`;
- `adapter_runs.outputs`;
- `adapter_hypotheses.state`;
- Trail/admission records;
- adapter harness receipts.

The failure is **reach**, not durability.

The recurring pattern is:

```text
RICH DURABLE STATE
        ↓
THIN PROJECTION
        ↓
CONSUMER
```

Examples:

```text
21-field hypothesis state
        ↓
{id, revision, status, statement}
        ↓
every later reasoning step

rich hypothesis state
        ↓
same 4 fields
        ↓
Trail

typed concepts + product_terms
        ↓
generic territory templates
        ↓
product reality

targeted later retrieval
        ↓
citable IDs only
        ↓
agent still reads old first-pass evidence
```

The implementation goal is to correct these boundaries while preserving the existing architecture.

---

# 3. Locked owner decisions

## 3.1 Staged correction; Trail remains the eventual mapping authority

Use a staged implementation.

### Stage A — Polymath-side corrections

Implement the semantic propagation and consumer fixes that genuinely belong to Polymath:

- derived semantic view;
- rich-state propagation;
- origin linkage;
- revision correctness;
- per-hypothesis gap propagation;
- semantic query compilation;
- query grammar binding where Polymath owns semantic vocabulary;
- product-reality planning and joining;
- later-evidence readability;
- dossier fidelity;
- retrieval need propagation.

These changes do not make Polymath a second Trail.

### Stage B — Trail-owned corrections

Correct defects that physically and semantically belong to Trail:

- real `knowledge_support_count`;
- meaningful returned coordinate semantics;
- removal of first-hypothesis fallback;
- hypothesis-relative evidence relation;
- field-aware deterministic registry mapping;
- registry data discriminators where proven necessary.

Then re-pin the embedded Trail core.

### Invariant

Do **not** create two permanent semantic registry authorities.

Final ownership remains:

```text
POLYMATH / LLM
interpret
abstract
generalize
generate semantic vocabulary
construct opportunity semantics
compile human-language research vocabulary

TRAIL
deterministically normalize
project registry coordinates
specify evidence requirements
govern source roles
admit / reject evidence
judge
qualify
score / refuse

HARNESS
execute live-world research
```

---

## 3.2 Derived semantic view, not a new durable IR

Do not create another durable state store such as `LatentOpportunityRepresentationV1` as a second source of truth.

Implement `OpportunitySemanticViewV1` as a **derived, read-only projection** over already-authoritative state.

It may combine:

- latest hypothesis ledger revision;
- originating lead IDs;
- originating latent-structure IDs;
- population;
- activity;
- task;
- context;
- mechanism;
- suspected friction;
- assumptions;
- falsifiers;
- contradictions;
- knowledge support;
- knowledge gaps;
- relevant primitives;
- transferable invariants;
- bridge state;
- physical jobs;
- product mechanisms;
- `product_terms`;
- product concepts;
- admitted evidence relations.

It is not independently persisted. It is not revised directly. It is not a second ledger. It is not the object Trail stores.

It exists so each consumer can receive the smallest semantically sufficient projection from state Polymath already owns.

---

## 3.3 Additive semantic restoration, not a rewritten migration

Do not rewrite migration history.

The consolidation migration succeeded.

Treat this as **Semantic Transduction Restoration** under the architecture produced by the completed migration.

Preserve migration doctrine:

- reuse before rewrite;
- one authority per responsibility;
- Trail deterministic;
- no second runtime;
- no second ledger;
- no speculative abstraction;
- evidence-first claims;
- smallest reversible implementation;
- targeted tests before broad suites;
- production safety;
- durable continuation.

---

# 4. Canonical workflows — do not confuse them

## 4.1 Canonical production workflow

The canonical product for this phase is `ecommerce.product_research`, the 54-step production adapter that completed the real E2E.

Important conceptual sequence:

```text
A_understand
        ↓
B_* knowledge planning / retrieval / graph / intake / lenses
        ↓
C_primitives
        ↓
C_lineage
        ↓
C_population
        ↓
C_hypotheses
        ↓
C_bridge
        ↓
C_bridge_law
        ↓
Trail projection / judgement
        ↓
research loop
        ↓
lived-world / situations / revision
        ↓
N_jobs
        ↓
N_concepts
        ↓
O_territory
        ↓
P_reality
        ↓
qualification
        ↓
supply planning / supply research / lead joining
        ↓
score / interpretation / compile
```

Typed product concepts **already exist before** `P_reality`.

Do not reorder product-concept generation as a first response. The defect is that product reality fails to consume those concepts correctly.

## 4.2 Compatibility workflow

`trail.product_discovery` is a smaller 28-step compatibility/governed workflow. It lacks many semantic capabilities present in `ecommerce.product_research`.

Do not infer production behavior from it.

Any implementation finding must be labeled:

- EPR — `ecommerce.product_research`;
- TPD — `trail.product_discovery`;
- BOTH — shared runtime or embedded Trail core.

---

# 5. Confirmed production defects

## 5.1 Ledger → issued-step semantic collapse

### Existing authoritative state

The hypothesis ledger contains fields including:

- statement;
- mechanism;
- population;
- activity;
- task;
- context;
- suspected friction;
- assumptions;
- falsifiers;
- contradictions;
- knowledge gaps;
- knowledge support;
- Trail priors;
- field evidence relationships / IDs where available.

### Current boundary

`context_view()` reduces a hypothesis to approximately:

```json
{
  "hypothesis_id": "...",
  "revision": 0,
  "status": "...",
  "statement": "..."
}
```

Historical run evidence showed every hypothesis-bearing issued step carrying this thin view.

### Consequence

Later reasoning repeatedly has less structured information than Polymath already knows. Consumers may need to infer population, task, mechanism or friction again from prose.

### Required direction

Do not blindly widen the universal context contract. Create the derived semantic view and allow relevant consumers to opt in. Where Trail receives hypothesis payloads, explicitly project only Trail's allowed wire fields.

---

## 5.2 Polymath → Trail knowledge-support bug

### Current behavior

Trail's `HypothesisView` is built from the thin statement-level representation. `knowledge_support_count` is forced to zero.

### Historical consequence

Real hypotheses with corpus support were seen by Trail as unsupported and weakened with `NO_KNOWLEDGE_SUPPORT`.

### Severity

P0 correctness.

### Required direction

Trail must receive the actual support fact it requires. This is a Trail wire/contract change. Do not fake support on the Polymath side merely to avoid changing Trail.

---

## 5.3 Registry semantic collapse into lexical overlap

### Registry structure

The registry has structured fields such as:

- participant;
- task;
- context;
- body / hand state;
- friction family;
- friction hypothesis;
- workaround hypothesis;
- product territory;
- shared predicates.

These fields can represent a transformation grammar.

### Current Trail behavior

Structured values are substantially flattened into text and matched against hypothesis-statement tokens.

### Real failure

An irrelevant seed may win because of accidental words while a semantically correct friction family has no token overlap with the hypothesis sentence.

This is not reliably fixable by stop-word tuning.

### Required direction

Polymath provides structured semantic candidates. Trail deterministically maps/validates field-to-field. Keep lexical matching as a compatibility fallback until the structured path is proven. Do not put an LLM in Trail.

---

## 5.4 Trail coordinates lose semantics on return

Trail computes useful coordinate information but downstream Polymath often receives opaque IDs.

Examples include:

- seed IDs without labels/sections;
- territory IDs while human-meaningful territory names are lost;
- constant `product_territory` rather than actual territory semantics.

### Required direction

Return enough deterministic coordinate information for later consumers to understand the registry result without separately guessing from IDs.

At minimum evaluate:

- record/coordinate ID;
- label/name;
- section/type;
- actual territory.

---

## 5.5 Trail grammar slots are never bound

Trail query templates contain slots such as:

- `{activity}`;
- `{task}`;
- `{friction_family}`;
- `{product_territory}`.

The hypothesis ledger already contains several of these semantic values. The harness can nevertheless receive unresolved template strings.

### Interpretation

The registry is shaped like grammar, but the production path is failing to bind the grammar to semantic state.

### Required direction

Bind deterministic values before harness execution.

Ownership split:

- Polymath supplies semantic values/vocabulary;
- Trail selects role/stage/source policy/template;
- Harness executes.

Missing semantic values must remain explicit rather than fabricated.

---

## 5.6 Rich primitives are produced and then under-consumed

`C_primitives` produces substantial semantic state.

Important families include:

- drivers;
- behaviors;
- adaptations;
- constraints;
- workarounds;
- physical interactions;
- frictions;
- latent values;
- unresolved questions;
- inferred structures;
- transferable invariants;
- shared predicates;
- physical jobs.

Many have no meaningful governed consumer after production.

Examples:

- `transferable_invariants` can have zero production consumers;
- free-text friction strings may fail exact friction-family matching;
- physical jobs produced from corpus semantics may never connect to later `N_jobs`;
- adaptations / workarounds / latent values may disappear before later reasoning.

### Required direction

Do not create new semantics. Restore existing semantics to steps that demonstrably require them. Use manifest `config.show`, domain-operation scope or the derived view.

---

## 5.7 Latent structure → population works; population → hypothesis lacks typed lineage

The production engine already creates:

- latent structures;
- `possible_populations`;
- NAMED leads;
- LATENT leads;
- VOI scores;
- seed-population discount;
- channel queries.

Historical evidence showed non-seed LATENT leads can rank ahead of seed-bound leads.

### Missing contract

No stable typed relation guarantees:

```text
latent_structure
        ↓
population_lead
        ↓
hypothesis
```

### Required direction

Add minimal origin linkage, likely optional IDs such as:

- `lead_ids[]`;
- `latent_structure_ids[]`.

Do not copy whole lead/structure payloads into the hypothesis ledger.

---

## 5.8 Revision silently drops semantic changes

The agent can propose semantic changes such as:

- `knowledge_gaps`;
- contradictions;
- assumptions;

while the runtime applies only a restricted subset of fields. Unsupported change keys can be silently discarded.

### Consequence

The model believes it revised the hypothesis. Durable state does not reflect the revision. Later research cannot see the intended uncertainty or contradiction.

### Required direction

Every intentionally supported revision field must either be applied or produce a typed validation failure. Never silently discard semantically meaningful revision content.

---

## 5.9 Per-hypothesis gaps are only partially preserved

A top-level gap path may preserve `hypothesis_id` while other gap sources disappear:

- ledger `knowledge_gaps`;
- bridge gaps;
- `K_revise.open_gaps`;
- revised gaps;
- other semantic uncertainty sources.

Trail additionally has a first-hypothesis fallback for gaps missing a hypothesis ID.

### Required architecture

```text
H1
  ↓
H1 gaps
  ↓
H1 research program

H2
  ↓
H2 gaps
  ↓
H2 research program
```

No silent assignment of an unowned gap to H1.

### Required direction

Polymath refuses an unbound hypothesis-specific gap before Trail. Trail eventually removes the fallback at the source.

---

## 5.10 Query compiler loses semantic intent

The production query compiler can reduce a rich research need into a small keyword fragment. Governance text can become literal search language.

### Correct ownership

Trail controls:

- evidence role;
- admissible source types;
- research stage;
- freshness;
- independence;
- budget;
- falsification requirement.

Polymath controls:

- population language;
- activity/task vocabulary;
- context;
- behavior;
- adaptation;
- friction language;
- workaround terminology;
- mechanism terminology;
- falsifier semantics;
- relevant corpus/domain vocabulary;
- product terms where stage-appropriate.

Harness executes the resulting search.

### Required direction

Compile human-language reality queries from semantic state, not governance phrases.

---

## 5.11 `K_questions` does not reach `K_retrieve`

The production workflow computes corpus questions / a new retrieval need. The evidence boundary later falls back to the original seed instead of using the computed need.

### Consequence

The iterative research cycle appears to perform second-pass corpus reasoning while retrieval can remain anchored to the initial seed.

### Required direction

Allow trusted domain-compiled retrieval needs to reach the retrieval boundary while preserving protections against unconstrained LLM reformulation.

---

## 5.12 Later retrieval becomes citable but not readable

The evidence boundary supports many citable IDs and a smaller readable-row window. Historical evidence showed later targeted retrieval results were not entering the readable window.

### Consequence

The intended loop:

```text
initial evidence
→ hypothesis
→ targeted retrieval
→ revise
```

can behave like:

```text
initial evidence
→ hypothesis
→ targeted retrieval
→ old evidence still dominates readable context
→ revise
```

### Required direction

Do not simply raise the cap. Use a bounded allocation policy that reserves space for later/hypothesis-specific evidence.

Possible deterministic strategies:

- pass quota;
- stage quota;
- recency quota;
- relevance + recency;
- explicit reservation for targeted retrieval.

Choose the smallest change consistent with the existing evidence-boundary contract.

---

## 5.13 Product reality consumes the wrong semantic object

Production ordering is correct: `N_concepts` occurs before `P_reality`.

`N_concepts` already creates useful:

- product concepts;
- variations;
- mechanisms;
- `product_terms`;
- buyer / target-moment / form-factor semantics.

### Current problem

The harness can receive generic Trail templates and unresolved territory slots while product concepts arrive only as surrounding reading material. Compiled search objects fail to use market vocabulary already available.

### Missing structural capability

There is no product-reality equivalent of the strong supply pattern:

```text
supply.plan
→ per-concept jobs
→ research
→ supply.leads join
```

### Required direction

Build:

```text
product_reality.plan
→ per-concept competitor / substitute jobs
→ harness
→ product_reality.join
```

Do not move concept generation. Do not create another product engine. Reuse the supply planning/join pattern.

---

## 5.14 Product reality lacks concept-level lineage

External product observations may not be deterministically linked back to the exact concept/variation that caused the search.

### Required direction

Every product-reality research job should retain:

- concept ID;
- optional variation ID;
- hypothesis ID;
- mechanism ID where relevant.

Every returned product/competitor observation should be joinable back to that origin.

Use an existing convention/pattern where possible. Do not infer concept ownership later from names.

---

## 5.15 Counterevidence is globally classified instead of hypothesis-relative

Current receipts/admission do not fully represent the relation:

```text
observation
→ hypothesis
```

A single observation can simultaneously:

- prove that a friction exists;
- disprove that the need is unmet;
- support a different mechanism.

A global observation polarity cannot represent this.

### Correct conceptual model

Keep evidence role:

```text
role = behavior | friction | competition | price | supply | ...
```

Add hypothesis-relative relation:

```text
observation O1 SUPPORTS H1
observation O1 CONTRADICTS H2
observation O1 NEUTRAL H3
```

These are independent concepts.

### Required direction

Minimum relational shape:

```text
observation_id
hypothesis_id
relation = SUPPORTS | CONTRADICTS | NEUTRAL
```

Trail remains the authority for admission and the relation used by governance/scoring.

---

## 5.16 First-hypothesis fallback is semantically unsafe

Trail may attach an unowned knowledge gap to the first hypothesis.

This is incompatible with a hypothesis portfolio.

### Required direction

Polymath should never send an unowned gap. Trail should ultimately remove the fallback and emit a typed refusal consistent with existing missing-link admission behavior.

No guessing.

---

## 5.17 Dossier fidelity is downstream of semantic loss

The renderer/reporting path may show empty:

- mechanism;
- population;
- activity;
- friction;
- support counts;

even though those values exist in authoritative state.

It can omit:

- primitives;
- latent structures;
- invariants;
- bridges;
- jobs;
- territories;
- qualification gates;
- existing products.

### Required direction

Reporting is not the first implementation slice. After semantic continuity is fixed, render from rich authoritative state rather than reconstructing meaning from the thin four-field view.

---

# 6. What NOT to build

This phase is vulnerable to accidental overengineering.

Do not build:

- a second adapter runtime;
- a second hypothesis ledger;
- a second Trail;
- a new graph database;
- a per-domain ontology;
- a cinema-specific registry;
- a commerce-specific Trail fork;
- an LLM-based Trail scorer;
- a giant `LatentOpportunityRepresentation` database;
- a new general research SDK;
- a new external agent protocol;
- a new product ideation engine;
- a new supplier engine;
- a new renderer.

Do not change stage ordering unless execution evidence proves ordering itself is wrong.

Do not restore old AutoResearch as another runtime.

Do not make Polymath permanently perform Trail's registry-governance mapping.

---

# 7. OpportunitySemanticViewV1 — detailed design intent

This object is the central Polymath-side restoration mechanism.

It is a **view**, not a store.

## 7.1 Identity

The view should be derivable for:

```text
run_id
hypothesis_id
latest_revision
```

Optional sub-identities may include:

- mechanism ID;
- concept ID;
- lead ID;
- latent-structure ID.

## 7.2 Candidate shape

Not every consumer gets every field.

The full internal view may conceptually expose:

```yaml
hypothesis:
  hypothesis_id:
  revision:
  status:
  statement:

origin:
  lead_ids: []
  latent_structure_ids: []
  source_population:
  seed_population:

semantics:
  population:
  activity:
  task:
  context:
  mechanism:
  suspected_friction:
  normalized_friction_candidates: []
  assumptions: []
  falsifiers: []
  contradictions: []

knowledge:
  supporting_evidence_ids: []
  knowledge_support_count:
  knowledge_gaps: []

transduction:
  relevant_drivers: []
  relevant_behaviors: []
  relevant_adaptations: []
  relevant_constraints: []
  relevant_workarounds: []
  relevant_physical_interactions: []
  relevant_latent_values: []
  relevant_transferable_invariants: []
  relevant_shared_predicates: []

bridge:
  bridge_id:
  path: []
  first_inference_at:
  target_mechanism:
  gaps: []
  alternatives: []
  falsifiers: []
  status:
  evidence_boundary:

jobs:
  physical_jobs: []

mechanisms:
  product_mechanisms:
    - mechanism_id:
      name:
      product_terms: []

concepts:
  - concept_id:
    name:
    form_factor:
    target_moment:
    buyer:
    differentiator:
    variations: []

field_evidence:
  - observation_id:
    role:
    source:
    relation:
    admitted:
```

This is illustrative. Actual field names must reuse existing contracts where possible. Do not duplicate data simply to match this presentation.

## 7.3 Construction

Build the view where the runtime already has access to:

- run state;
- latest ledger revision;
- outputs;
- bridge state;
- domain outputs;
- evidence relationships.

Use IDs and references to existing durable objects.

## 7.4 Consumer-specific projections

### Agent reasoning projection

May receive:

- rich hypothesis semantics;
- relevant primitives/invariants;
- bridge;
- current gaps;
- contradictions;
- recent readable evidence.

### Query planning projection

May receive:

- population;
- activity;
- task;
- context;
- friction;
- workaround;
- mechanism;
- falsifier;
- relevant vocabulary.

### Product-reality projection

May receive:

- concept;
- variation;
- product terms;
- buyer;
- target moment;
- job;
- mechanism;
- population;
- friction.

### Trail projection

Must be deliberately smaller and closed. Trail should receive only fields it can deterministically use.

Do not send arbitrary rich objects into Trail.

---

# 8. Implementation Slice 1 — Semantic Continuity

This slice repairs internal Polymath dataflow.

No live E2E is required yet.

## 8.1 Build OpportunitySemanticViewV1

### Requirements

- read-only;
- deterministic;
- derived from authoritative state;
- no side effects;
- no new table;
- no second ledger;
- stable IDs;
- explicit missing fields;
- bounded serialization size.

### Tests

Create tests proving:

1. latest revision wins;
2. origin IDs remain linked;
3. rich fields survive;
4. missing bridge does not fabricate bridge;
5. multiple concepts remain separate;
6. multiple evidence relations remain separate;
7. no mutation of underlying state;
8. deterministic output for identical state.

## 8.2 Restore governed semantic inputs

Compare governed `config.show` / domain-operation inputs with existing standalone/domain functions.

Restore only proven useful existing inputs.

Candidates:

- primitives;
- transferable invariants;
- latent structures;
- population leads;
- bridge state;
- physical jobs;
- product mechanisms.

Likely consumers:

- `C_hypotheses`;
- `C_bridge`;
- `G_mechanisms`;
- `N_jobs`;
- `N_concepts`.

### Rule

No “show everything everywhere.” Each field needs a consumer.

## 8.3 Add origin linkage

Extend the hypothesis proposal/state contract minimally.

Candidates:

```text
lead_ids[]
latent_structure_ids[]
```

These establish where the hypothesis came from and support lineage, benchmark evaluation and origin-aware research.

They must not duplicate full leads/structures into the ledger.

## 8.4 Fix revisions

Audit current `REVISABLE_FIELDS`.

For every field agents are contractually encouraged to update, either support it or reject it.

At minimum inspect:

- `knowledge_gaps`;
- contradictions;
- assumptions;
- falsifiers;
- mechanism;
- population;
- task/context fields.

Do not make every field mutable without thought.

## 8.5 Fix readable-evidence allocation

Preserve the existing row cap.

A reasonable evaluation order:

1. preserve admitted field evidence;
2. reserve a bounded portion for current-step targeted retrieval;
3. fill remaining slots from prior knowledge evidence by relevance;
4. maintain citable IDs beyond readable rows.

Test the exact historical failure where later retrieval existed but no later rows became readable.

## 8.6 Slice 1 acceptance

A synthetic or historical state must prove:

```text
rich state
→ OpportunitySemanticViewV1
→ reasoning consumer
```

without semantic collapse.

The consumer should receive hypothesis statement, population, task, context, mechanism, friction, current gaps, relevant invariant, bridge and newer targeted evidence when those values exist.

No Trail behavior needs to change yet.

---

# 9. Implementation Slice 2 — Hypothesis-Specific Research Fidelity

This slice repairs:

```text
hypothesis
→ uncertainty
→ research program
→ query
```

## 9.1 Gather legitimate gap sources

Audit and merge without duplication:

- ledger `knowledge_gaps`;
- top-level `G_mechanisms` gaps;
- bridge gaps;
- `K_revise.open_gaps`;
- Trail gate gaps.

Every gap should have, where supported:

```text
gap_id
hypothesis_id
question
role / evidence objective
source / origin
```

Stable IDs should survive rounds where practical.

## 9.2 Refuse unowned gaps

An unbound hypothesis-specific gap is malformed.

Do not map it to the first hypothesis.

Polymath must reject it before Trail. Later Trail should reject it too.

## 9.3 Semantic query compiler

Replace first-few-token behavior with an actual semantic query compiler.

Input:

```text
hypothesis semantic view
+
gap
+
Trail research policy
```

Output: research intents.

### Semantic vocabulary inputs

Potential inputs:

- population aliases;
- activity;
- task;
- context;
- behavior;
- adaptation;
- friction;
- workaround;
- mechanism;
- falsifier;
- source-domain vocabulary;
- candidate product terms if relevant;
- negative/contradiction concepts.

### Governance inputs

Trail continues to determine:

- role;
- stage;
- source classes;
- freshness;
- independence;
- budget.

### Critical rule

Never search governance text literally unless the governance term itself is the intended research object.

Example:

```text
BAD:
"corroborate second independent source"

GOOD:
"camera assistants lens cap temporary holder complaints"
```

when the evidence objective is corroboration of that specific friction.

## 9.4 Bind query-template slots

When Trail produces a template such as:

```text
{activity} {task} annoying
```

bind `activity` and `task` from authoritative semantic state.

Likewise evaluate friction family and product territory.

Missing semantic values should create a visible unresolved requirement, not a literal `{slot}` sent to search.

## 9.5 Repair `K_questions → K_retrieve`

Trace the computed need and allow trusted domain-operation outputs to become retrieval needs.

Preserve protections against arbitrary LLM-written retrieval rewrites.

Add a focused test proving the next retrieval is based on the computed corpus question/need rather than the original seed.

## 9.6 Repair governed field-record mapping

Correct the known mapping issue where semantic fields are assigned incorrectly.

Use current contracts. Do not redesign population evidence cards.

## 9.7 Slice 2 acceptance

Prove:

```text
H1 gap
→ H1 semantic query
→ H1 harness intent

H2 gap
→ H2 semantic query
→ H2 harness intent
```

Ensure:

- no unresolved template slots;
- governance phrases do not become user-language searches;
- hypothesis IDs survive.

---

# 10. Implementation Slice 3 — Product Reality Fidelity

This slice repairs:

```text
concept
→ marketplace research
→ competitor evidence
→ concept
```

## 10.1 Preserve stage order

Do not move `N_concepts`.

Concepts already exist before product reality.

## 10.2 Build `product_reality.plan`

Follow the architecture pattern of `supply.plan`.

Input:

- hypothesis semantic view;
- concept ID;
- concept name;
- variations;
- form factor;
- target moment;
- buyer;
- differentiator;
- physical job;
- mechanism;
- `product_terms`;
- friction;
- relevant territory;
- Trail policy / research requirements.

Output per-concept research jobs.

Potential job classes:

- direct competitor search;
- substitute search;
- price reality;
- review/complaint investigation;
- return/failure investigation;
- feature comparison;
- saturation check.

Trail continues to govern evidence roles/source classes.

## 10.3 Compile actual marketplace language

Use `product_terms`.

Use concept/mechanism semantics.

Use population/job vocabulary.

Do not use opaque registry territory IDs or generic ontology labels as the primary user-facing query when richer vocabulary exists.

## 10.4 Build `product_reality.join`

After harness research, deterministically associate observations/products with:

- concept ID;
- variation ID where applicable;
- hypothesis ID;
- research job ID.

The join should support:

- competitor;
- substitute;
- current solution;
- product validation;
- product contradiction.

## 10.5 Product reality must be able to kill a concept

A successful product-reality stage is not one that always confirms novelty.

It must be able to establish:

```text
existing product already solves this
```

and feed that contradiction into hypothesis/concept interpretation.

## 10.6 Slice 3 acceptance

Given two concepts, prove they produce distinct market-research jobs, returned competitor products join to the correct concept, and a competitor can invalidate one concept without automatically invalidating the other.

---

# 11. Implementation Slice 4 — Trail Contract and Mapping Correctness

This slice changes Trail-owned semantics.

Follow Trail governance/ADR/versioning rules.

Use an upstream Trail worktree as appropriate, then re-pin the embedded Trail core.

## 11.1 Add actual knowledge support

Extend the Trail wire so a hypothesis can carry the knowledge-support fact Trail actually needs.

Do not send a giant Polymath object.

At minimum:

```text
knowledge_support_count
```

Evaluate whether IDs/roles are actually required by Trail or only the count.

Use the smallest value Trail can deterministically judge.

## 11.2 Return coordinate semantics

Update Trail response types so registry projections return meaningful semantic information.

Candidate fields:

```text
record_id
label
section
prior_role
overlap / match basis where useful
```

For product territories:

```text
territory_id
territory_name
```

Do not force Polymath to resolve opaque IDs against a second copy forever.

## 11.3 Remove first-hypothesis fallback

Malformed gap ownership should produce a typed error/refusal.

Mirror admission's existing strict missing-link behavior.

No guessing.

## 11.4 Add hypothesis-relative evidence relation

Update the relevant receipt/admission contract.

Do not remove evidence role.

Model two dimensions:

```text
role:
  behavior
  friction
  competition
  price
  supply
  ...

relation_to_hypothesis:
  SUPPORTS
  CONTRADICTS
  NEUTRAL
```

An observation linked to multiple hypotheses may need multiple relation rows.

Prefer normalized relationship semantics over one global polarity value.

## 11.5 Field-aware registry mapping

### Input from Polymath

Structured semantic candidates such as:

- normalized friction-family candidates;
- activity/task;
- context;
- relevant predicates;
- workaround;
- mechanism / territory candidate.

### Trail behavior

Trail deterministically compares compatible fields.

Example:

```text
hypothesis semantic candidate
friction = object_retention
task = temporary staging during swap
predicates = access, retain, protect
mechanism = retained staging interface
```

against compatible registry dimensions.

### Do not

- add an LLM to Trail;
- infer semantics from free text inside Trail;
- permanently duplicate the registry mapper in Polymath.

### Compatibility

Keep lexical matching available as fallback during validation.

Record which mapping path produced the coordinate.

## 11.6 Registry discriminator repair

Do not start by rewriting the registry.

After structured mapping works, measure which fields actually help.

Known audit concerns include:

- constant participant values;
- constant shared predicates;
- undefined friction families;
- duplicated structural archetypes across many activities.

If these prevent structured mapping, repair deterministically, version the data and record provenance.

Do not casually hand-edit thousands of rows where a reproducible normalizer/generator can derive the change.

## 11.7 Slice 4 acceptance

Trail must prove:

1. supported hypotheses are not incorrectly weakened as unsupported;
2. field-aware mapping can find the appropriate primitive where lexical overlap fails;
3. coordinate meaning survives the wire;
4. unowned gaps are refused;
5. counterevidence relation can differ by hypothesis;
6. lexical fallback remains compatible for cases not yet structurally mapped.

Then re-pin.

---

# 12. Explicitly deferred — analogy stage / structural lookup

Do not add a new analogy subsystem now.

Current production already contains meaningful ingredients:

- transferable invariants;
- latent structures;
- possible populations;
- LATENT population leads;
- seed-population discount;
- VOI ranking;
- bridge inference boundary;
- exploratory portfolio limits.

Historical evidence showed non-seed latent leads can already rank first.

The immediate defect is that these semantics fail to survive into hypotheses/research.

First:

```text
extract
→ preserve
→ link
→ research
```

Then benchmark.

Only add or restore explicit `structural_lookup`, `signal_gate`, or a dedicated analogy stage if the post-restoration benchmark proves existing cross-domain mechanisms still cannot reliably consider transfer.

Execution evidence is required before adding that architecture.

---

# 13. Implementation Slice 5 — Reporting and auditability

After semantic correctness is established, make the dossier represent the actual system.

The report should explain:

```text
where did this hypothesis come from?
what structure was abstracted?
what population was nominated?
what bridge was earned?
what evidence supported it?
what evidence contradicted it?
what changed?
what product concepts resulted?
what real products competed?
what suppliers were found?
what did Trail decide?
```

## 13.1 Hypothesis table

Render real:

- population;
- activity;
- task;
- context;
- mechanism;
- friction;
- support counts;
- revision;
- status.

Do not read those fields from the thin context view.

## 13.2 Transduction section

Render where available:

- relevant primitives;
- latent structures;
- transferable invariants;
- origin leads;
- bridge path;
- inference boundary;
- alternatives;
- falsifiers.

Clearly distinguish:

- corpus evidence;
- inferred semantic structure;
- live-world evidence;
- Trail determination.

## 13.3 Product reality section

Show:

- generated concepts;
- variations;
- linked existing products;
- competitors;
- substitutes;
- price;
- relevant reviews/complaints;
- product URLs;
- concept-level contradiction.

Generated concept and existing product must never be visually conflated.

## 13.4 Governance section

Show:

- Trail priors / coordinates;
- evidence admissions/rejections;
- hypothesis-relative support/contradiction;
- qualification gates;
- score/refusal reasons.

## 13.5 Journal fidelity

If the dossier depends on the journal, ensure the journal captures enough governed materials/semantic projection to reconstruct what the agent actually received.

Do not dump hidden model reasoning. Record bounded execution semantics and IDs.

---

# 14. Benchmark — non-presupposing arbitrary-corpus test

Run only after implementation slices are coherent.

Cinema remains the first benchmark corpus because it already has a real baseline and is deliberately not ecommerce knowledge.

## 14.1 What the seed must NOT contain

Do not provide:

- target market;
- target population;
- product category;
- desired product;
- known consumer problem;
- expected niche.

The seed may describe source material or ask for latent-opportunity discovery.

## 14.2 Example benchmark seeds

Use one first.

Source-situation seed:

```text
How a camera crew keeps equipment working through a shooting day — who handles what, what is moved between setups, and what repeatedly goes wrong in hand-offs.
```

Mechanism-oriented seed:

```text
Moments in the material where one person has to accomplish with two hands what is normally divided among several people.
```

Open seed:

```text
Recurring physical handling problems described in this material.
```

Do not automatically run all three.

Run one and expand only if it leaves a specific architectural question unanswered.

## 14.3 Benchmark stages

### T1 — abstraction

Require:

- at least one transferable invariant;
- at least one latent structure;
- valid evidence references;
- semantic structure genuinely derived from corpus evidence.

Do not require an out-of-domain population yet.

### T2 — population nomination

Confirm:

- seed-bound and non-seed candidates are possible;
- VOI ranking operates;
- seed-population discount operates;
- origin remains traceable.

### T3 — hypothesis origin

At least one useful hypothesis should be traceable to:

```text
latent structure / lead
→ hypothesis
```

If all surviving hypotheses remain source-domain, that is allowed only if transfer candidates were actually considered.

### T4 — bridge

The bridge should:

- start from corpus evidence;
- contain multiple reasoning hops;
- declare the first inference boundary;
- preserve speculative gaps;
- preserve alternatives/falsifiers.

No direct seed→product jump.

### T5 — Trail normalization

Compare structured mapping and lexical fallback where both are available.

Record which coordinates are semantically appropriate.

Do not require structured mapping to win every case.

### T6 — research fidelity

For each hypothesis:

```text
hypothesis-specific uncertainty
→ semantically meaningful query
→ real external research
```

Queries must not be generic governance phrases.

### T7 — evidence relation and revision

Require:

- admitted observations;
- hypothesis linkage;
- support/contradiction relation;
- actual revision / weakening / split / kill / strengthening where warranted.

A zero-admission round is lawful if governance rejects the evidence.

### T8 — product concepts

Concepts must be:

- typed;
- linked to hypothesis/mechanism;
- multiple where appropriate;
- not directly copied from the seed.

### T9 — product reality

Queries must derive from concepts, mechanisms, product terms, jobs and market vocabulary.

Existing products must be joined to the concept they test.

### T10 — supply

Use the existing working supply planner and lead join.

Do not rewrite them for this phase.

### T11 — outcome

Valid terminal states include:

- score;
- provisional opportunity;
- lawful hard-gate refusal;
- no defensible bridge;
- market already solved;
- supply not proven.

A runtime/software error is not a valid product result.

---

# 15. Benchmark non-goals

The benchmark does NOT require:

- positive Trail score;
- out-of-domain product;
- predetermined niche;
- novelty for novelty's sake;
- a product in cinema;
- a product outside cinema.

The actual test is:

> Can the system derive, preserve, transfer, investigate and revise latent-opportunity structure without the human seeding the target opportunity?

---

# 16. Testing strategy

Do not build an enormous matrix.

Use the smallest test capable of falsifying each change.

## 16.1 Slice tests

Each slice should have:

1. unit test;
2. contract test where a contract changes;
3. nearest focused integration test;
4. historical fixture/replay where available;
5. guards.

## 16.2 Historical run fixtures

Use run-5 artifacts where they expose exact defects.

Good targets:

- `knowledge_support_count=0`;
- lexical bad match;
- unresolved query templates;
- governance query fragments;
- later retrieval invisible to readable evidence;
- product terms ignored by product reality;
- counterevidence misclassified.

Do not require exact model-output parity. Test structural behavior.

## 16.3 Trail changes

For Trail:

- targeted unit tests;
- wire contract tests;
- deterministic equivalence where appropriate;
- structured-vs-lexical comparison;
- embedded-copy parity;
- re-pin verification.

Do not run unrelated broad suites after every edit.

## 16.4 Full E2E timing

Do not run a paid/live E2E after every slice.

Run the benchmark when:

- Polymath semantic path is coherent;
- Trail contract changes are integrated;
- product reality plan/join works;
- targeted tests are green.

---

# 17. Git and production discipline

This work touches live architecture.

Use worktrees/branches.

Before implementation:

- verify production HEAD;
- verify clean status;
- verify semantic branch/worktree;
- verify open adapter runs;
- verify ingestion state if fenced components are involved;
- verify fleet health.

Do not modify fenced live code while runs are active.

Commit coherent slices separately.

Suggested conceptual boundaries:

```text
semantic-view + propagation
research-fidelity
product-reality
trail-contracts
reporting
benchmark fixtures
```

Do not combine all changes into one unreviewable commit.

---

# 18. Continuation discipline

At every major slice boundary update the active continuation record with:

- branch;
- HEAD;
- exact slice;
- files changed;
- confirmed defect addressed;
- tests;
- unproven behavior;
- known defects;
- next exact action;
- DO NOT REDO.

Do not let semantic-alignment state live only in model context.

---

# 19. Evidence vocabulary

Use:

- `EXECUTED`;
- `INTEGRATION_EXECUTED`;
- `UNIT_EXECUTED`;
- `STATICALLY_VERIFIED`;
- `READ`;
- `HISTORICAL_RUN_EVIDENCE`;
- `INFERRED`.

Do not claim “fixed” when only code was read.

Do not claim “benchmark passed” from a scripted fixture.

Do not claim “Trail maps semantics correctly” because a Polymath-side test passed.

---

# 20. Failure classification

Classify failures before redesigning.

Possible classes:

- semantic propagation defect;
- contract mismatch;
- Trail correctness defect;
- query translation defect;
- retrieval visibility defect;
- product-reality planning defect;
- evidence-relation defect;
- reporting defect;
- fixture defect;
- provider failure;
- expected governance refusal.

Do not treat every failure as evidence that another architecture layer is needed.

---

# 21. Key architectural invariants

## One source of truth

No duplicate:

- hypothesis ledger;
- adapter state;
- registry authority;
- evidence admission authority;
- scoring authority.

## Trail deterministic

No LLM in Trail governance/scoring.

## Polymath semantic

Polymath/LLM may interpret, abstract and generate semantic candidates.

## Harness observational

Harness executes research. It should not substitute for missing domain reasoning by inventing a better opportunity plan.

## Evidence boundary

Corpus inspiration is not market evidence. Live-world evidence must establish real market claims.

## Cross-domain is allowed, not forced

A source-domain opportunity is valid if it survives the same process. Do not reward cross-domain novelty for its own sake.

---

# 22. Detailed target dataflow

```text
INPUT
 seed + corpus_ids
        │
        ▼
POLYMATH KNOWLEDGE
 retrieval / graph / evidence boundary
        │
        ▼
C_PRIMITIVES
 drivers
 behaviors
 adaptations
 constraints
 workarounds
 frictions
 physical interactions
 latent values
 transferable invariants
 latent structures
 possible populations
        │
        ▼
C_POPULATION
 NAMED / LATENT candidates
 VOI
 seed discount
        │
        ▼
C_HYPOTHESES
 rich typed proposal
 + lead_ids
 + latent_structure_ids
        │
        ▼
HYPOTHESIS LEDGER
 rich authoritative revision state
        │
        ├─────────────────────────────────────┐
        │                                     │
        ▼                                     ▼
OpportunitySemanticViewV1              C_BRIDGE
 derived read-only projection           earned reasoning path
        │                                     │
        └────────────────┬────────────────────┘
                         ▼
TRAIL PROJECTION
 bounded semantic payload
 field-aware deterministic mapping
 lexical fallback
                         │
                         ▼
TRAIL JUDGEMENT
 correct knowledge support
                         │
                         ▼
HYPOTHESIS-SPECIFIC GAPS
 explicit owner
 stable lineage
                         │
                         ▼
POLYMATH QUERY COMPILER
 semantic vocabulary
 + Trail evidence objective / source policy
                         │
                         ▼
HARNESS
 real-world research
                         │
                         ▼
TRAIL ADMISSION
 role
 + hypothesis-relative relation
                         │
                         ▼
SEMANTIC REVISION
 preserve gaps
 contradictions
 assumptions
 mechanism / population changes
                         │
                         ▼
N_JOBS
                         │
                         ▼
N_CONCEPTS
 mechanisms
 product_terms
 concepts
 variations
                         │
                         ▼
PRODUCT_REALITY.PLAN
 per-concept jobs
                         │
                         ▼
HARNESS
 competitors / substitutes / prices / reviews
                         │
                         ▼
PRODUCT_REALITY.JOIN
 concept ↔ existing product
                         │
                         ▼
QUALIFICATION
                         │
                         ▼
SUPPLY.PLAN
                         │
                         ▼
SUPPLY / LEADS
                         │
                         ▼
TRAIL SCORE / REFUSAL
                         │
                         ▼
DOSSIER
 full semantic + evidence lineage
```

---

# 23. Authoritative implementation queue

Use this queue unless repository evidence proves a dependency is different.

## NOW — Slice 1

Semantic continuity:

- OpportunitySemanticViewV1;
- rich governed inputs;
- origin linkage;
- revision correctness;
- readable later evidence.

## NEXT — Slice 2

Research fidelity:

- gap propagation;
- gap ownership;
- semantic queries;
- query-template binding;
- K_questions retrieval;
- record mapping.

## NEXT — Slice 3

Product reality:

- plan;
- per-concept jobs;
- join;
- concept-linked competitors.

## NEXT — Slice 4

Trail correctness:

- knowledge support;
- returned semantics;
- fallback removal;
- relation;
- structured mapping;
- registry discriminators only as required;
- re-pin.

## NEXT — Slice 5

Reporting.

## THEN

Non-presupposing cinema benchmark.

## ONLY IF BENCHMARK REQUIRES

- explicit analogy / structural lookup restoration;
- signal-gate restoration;
- broader multi-corpus benchmark.

---

# 24. Stop conditions

The coding agent should not ask routine questions.

Stop for owner input only if:

1. implementation requires a second durable authority;
2. a Trail semantic change materially conflicts with established law;
3. the audit is disproven by repository truth;
4. a required contract change would break a supported external consumer with no compatible migration;
5. a security/privacy boundary must be weakened;
6. irreversible live-data migration is required;
7. licensing prevents the change;
8. hidden user work would be overwritten;
9. benchmark design must materially change the product thesis.

Otherwise:

```text
INSPECT
→ DECIDE
→ IMPLEMENT
→ TEST
→ RECORD
→ CONTINUE
```

---

# 25. Definition of done

The restoration phase is complete when all of the following are true.

## Semantic continuity

A hypothesis's rich meaning survives from creation through reasoning, Trail normalization, research planning and revision.

## Origin lineage

A useful cross-domain or non-seed hypothesis can prove which latent structure / population lead caused it.

## Trail correctness

Trail does not falsely classify supported hypotheses as unsupported.

Trail can deterministically map structured semantic candidates.

Trail does not guess gap ownership.

## Research fidelity

Research queries reflect the hypothesis's semantic vocabulary and Trail's epistemic objective.

## Evidence relation

Counterevidence can contradict one hypothesis while supporting another.

## Product reality

Marketplace research is driven by actual product concepts/mechanisms/product terms and joins findings back to concepts.

## Iterative knowledge

Later targeted retrieval can actually be read by the reasoning model.

## Dossier

The final report explains the latent-opportunity path and real evidence that changed it.

## Benchmark

A non-presupposing cinema seed can proceed:

```text
knowledge
→ latent structure
→ candidate population
→ earned hypothesis
→ real-world research
→ revision
→ concept
→ product reality
→ supply
→ score or lawful refusal
```

without the operator supplying the target market/problem/product.

A lawful refusal passes.

A software failure does not.

---

# 26. Goal-mode kickoff prompt

After this reference file is committed into the repository, use a short goal prompt rather than pasting the architecture again.

```text
You are executing the Polymath Semantic Transduction Restoration phase.

Your controlling technical build reference is:

<PATH>/SEMANTIC_TRANSDUCTION_RESTORATION_REFERENCE.md

Read it in full after the normal Polymath bootstrap, current CONTINUATION, owner realignment and audit documents.

The consolidation migration is complete.

Do NOT re-plan Polymath.
Do NOT build a new runtime, new ledger, new Trail, new domain registry or new durable latent-opportunity database.

The production ecommerce.product_research workflow already creates most of the intended semantic architecture. Your job is to restore semantic continuity through the existing production path.

Execute the implementation slices in dependency order:

1. semantic continuity;
2. hypothesis-specific research fidelity;
3. product-reality plan/join;
4. Trail contract/mapping correctness and re-pin;
5. reporting;
6. non-presupposing cinema benchmark.

Use repository truth over assumptions.
Preserve one authority per responsibility.
Use OpportunitySemanticViewV1 only as a derived read projection over existing authoritative state.

Polymath owns semantic interpretation and human-language vocabulary.
Trail remains the deterministic mapping/admission/judgement/qualification/scoring authority.
Harness executes real-world research.

For every slice:
- inspect the exact current implementation first;
- reuse existing components before adding code;
- make the smallest reversible change;
- add the smallest falsifying tests;
- run focused integration tests;
- run guards;
- commit coherently;
- update continuation evidence;
- continue without asking routine questions.

Do not run a paid/full real E2E after every slice.
Run the non-presupposing cinema benchmark only after the semantic path is coherent and Trail changes are integrated.

The final benchmark must not be seeded with a target market, population, product category or specific product problem.

The target is not a positive Trail score.
The target is to prove that Polymath can earn an opportunity from arbitrary knowledge through semantic abstraction, governed reality testing and revision rather than being handed the opportunity in the seed.

If repository evidence materially disproves this reference, record the contradiction with exact code/test evidence and stop only if it changes an owner-level architectural decision.

Otherwise:
INSPECT → IMPLEMENT → PROVE → RECORD → CONTINUE

until the restoration acceptance criteria are satisfied.
```

---

# 27. Final reminder to the implementing agent

The audit did not find a missing machine.

It found a working machine that repeatedly throws away information it already computed.

Do not solve that by building another machine.

Solve it by preserving, projecting, normalizing and consuming the semantics that already exist.

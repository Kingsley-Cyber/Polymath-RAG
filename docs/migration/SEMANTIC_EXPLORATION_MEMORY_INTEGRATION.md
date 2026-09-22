# Polymath Semantic Exploration Memory
## Implementation Contract for Cross-Run Redundancy Control and Compound Ideation

**Status:** Agent implementation reference  
**Owner:** Polymath  
**Purpose:** Implement persistent memory of semantic work attempted across runs without creating a second hypothesis ledger, second RAG runtime, or second governance authority.

---

# 1. Mission

Polymath must remember **what semantic work it has already attempted**, not merely which chunks were retrieved.

The system must be able to recognize:

```text
same objective
+ same semantic operation
+ same versioned inputs
+ same input roles
+ unchanged relevant conditions
        ↓
already explored
```

while still allowing:

```text
old evidence + new evidence
old evidence + different role
old evidence + different population
old evidence + changed constraint
old evidence + new market reality
        ↓
new legitimate exploration
```

Do **not** implement a global `chunk_used=true` mechanism.

Old evidence remains reusable.

The architecture must reduce redundant semantic work while preserving compounding possibility.

---

# 2. Architectural placement

Semantic Exploration Memory belongs to **Polymath**.

It does not belong to Trail.

Existing ownership remains:

```text
POSTGRES
authoritative Polymath workflow/run/hypothesis/receipt/provenance state

QDRANT
rebuildable semantic/vector projections

NEO4J
permitted graph retrieval/projections

POLYMATH ADAPTER RUNTIME
current run state and reasoning orchestration

TRAIL
evidence admission, judgement, qualification, score/refusal
```

Exploration history may influence what Polymath investigates next.

It must never:

- admit evidence;
- promote hypotheses;
- change Trail scores;
- count as market evidence;
- act as a second hypothesis lifecycle.

---

# 3. Relationship to OpportunitySemanticViewV1

Keep these separate.

## OpportunitySemanticViewV1

Answers:

> What does Polymath currently know about this hypothesis?

Properties:

- derived;
- read-only;
- current hypothesis/run oriented;
- assembled from existing authoritative records.

## Semantic Exploration Memory

Answers:

> What semantic work has Polymath attempted across previous runs?

Properties:

- cross-run;
- historical;
- persistent at the provenance layer;
- queried through a derived index.

Relationship:

```text
authoritative existing records
        ↓
OpportunitySemanticViewV1
        ↓
current semantic state
        ↓
compare against
        ↓
Exploration history/index
        ↓
select next semantic operation
```

Do not persist a mutable copy of `OpportunitySemanticViewV1`.

---

# 4. Core rule: distinguish exposure from exploration

Track these separately:

```text
retrieved
reference_available
offered_to_harness
included_in_model_input       # only if observable
declared_support
cited
```

Do not record "read" or "understood" as factual states.

A retrieved chunk is not automatically explored.

A citable reference is not automatically explored.

Only an actual semantic operation should create an exploration attempt.

---

# 5. Central durable object: ExplorationAttempt

The smallest useful cross-run memory unit is an attempted semantic operation.

Logical shape:

```yaml
ExplorationAttempt:
  attempt_id:
  scope_id:
  run_id:
  step_issuance_id:
  objective_ref:
  operation:
  operation_spec:
  input_bindings:
    - input_ref:
      role:
  exposure_refs:
  output_refs:
  disposition:
  disposition_reason:
  predecessor_attempt_refs:
  producer_version:
  recorded_at:
```

Initial operations:

```text
INTERPRET
CORROBORATE
COMPOSE
PROJECT
CHALLENGE
```

Initial dispositions:

```text
PRODUCED_OUTPUT
REDUNDANT
INCONCLUSIVE
NO_SUPPORTED_INTERACTION
REJECTED_BY_GOVERNANCE
TECHNICAL_FAILURE
BUDGET_STOP
SUPERSEDED
```

Do not collapse software failure, business failure, governance refusal, and inconclusive research.

---

# 6. Composition identity is role-sensitive

Do not identify a composition by sorted member IDs alone.

These are different semantic attempts:

```text
A = observed problem
B = corroborating evidence
```

versus:

```text
A = observed problem
B = candidate mechanism
```

Attempt identity must include:

- operation;
- canonical objective/question;
- versioned inputs;
- role of every input;
- relevant semantic conditions;
- operation/normalization version.

---

# 7. Postgres storage

Use the existing Postgres control plane.

Do not create a new memory service.

Minimum new durable schema:

```text
exploration_attempts
exploration_attempt_inputs
evidence_exposures
evidence_exposure_items
```

Anything else should be derived unless proven necessary.

---

# 7.1 exploration_attempts

Recommended logical columns:

```sql
attempt_id                  primary id
scope_id                    not null
run_id                      not null
step_issuance_id            nullable
objective_ref               jsonb not null
operation                   text not null
operation_spec              jsonb not null
attempt_signature           text not null
semantic_signature          jsonb nullable
evidence_version_signature  text nullable
producer_version            jsonb not null
disposition                 text not null
disposition_reason          jsonb nullable
predecessor_attempt_ids      jsonb/array nullable
output_refs                 jsonb not null
created_at                  timestamptz not null
updated_at                  timestamptz not null
```

Recommended indexes:

```text
BTREE(scope_id, attempt_signature)
BTREE(scope_id, run_id)
BTREE(scope_id, operation)
BTREE(scope_id, created_at)
GIN(semantic_signature)
```

Use repo-standard types/IDs/migration style.

---

# 7.2 exploration_attempt_inputs

Recommended logical columns:

```sql
attempt_id
input_ordinal
scope_id
corpus_id
input_kind
input_id
input_revision_or_hash
locator_json
role
semantic_facets_json
created_at
```

Indexes:

```text
(input_kind, input_id)
(scope_id, corpus_id)
(role)
```

Purpose:

- exact-attempt matching;
- attempts-by-input lookup;
- role-sensitive composition history.

---

# 7.3 evidence_exposures

Recommended logical columns:

```sql
exposure_id
scope_id
run_id
step_issuance_id
request_attempt_id nullable
stage
payload_ref
observed_by
created_at
```

Initial stages:

```text
OFFERED_TO_HARNESS
INCLUDED_IN_MODEL_INPUT
```

Only emit `INCLUDED_IN_MODEL_INPUT` when actual request instrumentation exists.

---

# 7.4 evidence_exposure_items

Recommended logical columns:

```sql
exposure_id
item_ordinal
scope_id
corpus_id
evidence_kind
evidence_id
revision_or_content_hash
locator_json
representation_kind
presented_content_hash
truncated
created_at
```

Prefer IDs/hashes/locators over copying source text.

The original evidence remains authoritative in existing stores.

---

# 8. Attempt signature

Exact repeat detection requires a deterministic content signature.

Build a canonical object containing:

```json
{
  "operation": "COMPOSE",
  "objective": "...canonical objective...",
  "inputs": [
    {
      "kind": "latent_structure",
      "id": "...",
      "revision": "...",
      "role": "observed_interruption"
    },
    {
      "kind": "transferable_invariant",
      "id": "...",
      "revision": "...",
      "role": "placement_mechanism"
    }
  ],
  "conditions": {
    "population": "...",
    "context": "...",
    "mechanism": "..."
  },
  "operation_version": "...",
  "normalization_version": "..."
}
```

Canonicalize deterministically.

Hash with the repository's standard content-hash convention; otherwise use SHA-256.

Do not hash only free-form prose.

Retries/replays must not count as distinct semantic work unless the logical signature changes.

---

# 9. Semantic signature

Use semantic signatures for near-duplicate candidate lookup, not exact identity.

Recommended structure:

```yaml
activity_task:
frictions:
causal_interventions:
constraints:
expected_consequences:
applicability_conditions:
population:
setting:
buyer_or_user_context:
```

Preserve:

- causal direction;
- negation;
- constraints;
- applicability conditions;
- material units/quantities where relevant.

Do not allow product names or wording alone to dominate.

---

# 10. Derived ExplorationIndex

Build a **rebuildable** read model over authoritative attempts.

Logical shape:

```yaml
ExplorationIndexEntry:
  source_attempt_id:
  scope_id:
  projection_version:
  structural_signature:
  evidence_version_signature:
  family_candidates:
  population_context_facets:
  mechanism_constraint_facets:
  outcome_refs:
  dependency_refs:
  indexed_through:
```

The index should answer quickly:

```text
Has this exact attempt happened?
What similar attempts exist?
Which populations were already tested?
Which mechanism variants already exist?
What unresolved work is nearby?
What prior attempt should this revisit link to?
```

The index is not authoritative.

---

# 11. Where the index lives

## V1

Use Postgres.

Use:

- exact hash lookup;
- structured columns/JSONB;
- indexed candidate filtering.

No new infrastructure.

## Optional later Qdrant projection

Only add if semantic-history candidate lookup needs vector similarity beyond structured blocking.

Qdrant remains rebuildable.

Store:

```text
attempt_id
scope_id
projection_version
```

Do not duplicate mutable state.

## Neo4j

Do not change Neo4j for V1.

Later derived edges may include:

```text
ATTEMPT_USED_STRUCTURE
ATTEMPT_PRODUCED_HYPOTHESIS
ATTEMPT_PRECEDED
FAMILY_RELATED_TO
```

only if graph traversal proves useful.

---

# 12. Scope/isolation

Every history lookup must enforce current access scope.

At minimum:

```text
principal/project scope
authorized corpora
relevant adapter-purpose boundary
```

Unauthorized history must not influence:

- retrieval;
- novelty;
- ranking;
- duplicate detection;
- exploration choice.

No cross-user novelty leakage.

---

# 13. Write path

Do not write exploration memory on raw retrieval.

Write provenance at existing accepted workflow boundaries.

Recommended integration events:

```text
evidence/materials assembled for reasoning
semantic operation issued
semantic output accepted
hypothesis transition accepted
Trail outcome linked
```

Use existing transaction boundaries where possible.

Do not introduce a standalone background memory writer.

---

# 14. Evidence exposure hook

At the point readable evidence/materials are assembled:

record:

```text
EvidenceExposure
+
EvidenceExposureItems
```

This records what representation was actually offered.

If the connected harness can attest the exact request payload:

add:

```text
INCLUDED_IN_MODEL_INPUT
```

Otherwise stop at `OFFERED_TO_HARNESS`.

Never infer request inclusion from retrieval.

---

# 15. ExplorationAttempt write lifecycle

Recommended lifecycle:

```text
semantic operation authorized
        ↓
attempt created/idempotency key reserved
        ↓
reasoning executes
        ↓
accepted output OR typed stop/failure
        ↓
disposition finalized
        ↓
output refs linked
```

Idempotency key should include:

```text
run_id
step_issuance_id
logical operation key
```

A retry may have physical execution metadata without becoming a second logical exploration attempt.

---

# 16. Read path

Do not consult exploration history on every low-level chunk lookup.

Use semantic planning boundaries such as:

```text
before hypothesis generation
before explicit composition
before cross-population projection
before spending a full downstream research cycle
before reopening old/rejected work
```

This keeps the feature fast.

---

# 17. Internal API

Add a small shared interface in the existing shared Polymath layer.

Logical API:

```python
class ExplorationHistory:
    def exact_attempt(signature, scope): ...
    def similar_attempts(query, scope, limit): ...
    def attempts_using(ref, scope, limit): ...
    def predecessors_for(change_set, scope, limit): ...
    def unresolved_neighborhood(query, scope, limit): ...
```

Do not expose this over public MCP in V1.

Do not let adapters run raw history SQL.

---

# 18. Exact repeat behavior

Classify as `EXACT_REPEAT` when all materially relevant parts are unchanged:

```text
operation
objective
versioned inputs
roles
conditions
producer/normalization contract
```

Initial behavior:

```text
reuse prior semantic result
OR
skip duplicate synthesis
```

Do not automatically reuse freshness-sensitive market/supplier facts.

Stable semantic reasoning may be reused while:

```text
price
supplier availability
current competition
```

can require refresh under existing freshness rules.

---

# 19. Reopen behavior

Reopen prior work only when a material dependency changes.

Examples:

```text
new evidence addresses old gap
new evidence contradicts assumption
new constraint appears
new population matches predicates
market reality changes
supplier reality changes
source content revision changes
semantic normalizer changes materially
```

Create a **new attempt** linked through:

```text
predecessor_attempt_ids
```

Record:

```text
what changed
why reconsideration is justified
```

Never erase the prior outcome.

---

# 20. Duplicate classification

Do not let semantic duplicate classification control execution immediately.

## Phase 1: observation only

Classifications:

```text
EXACT_REPEAT
SEMANTIC_DUPLICATE
POPULATION_VARIANT
MECHANISM_VARIANT
NEW_FAMILY_CANDIDATE
POSSIBLE_DUPLICATE
```

Processing:

```text
exact signature
        ↓
structured facet blocking
        ↓
semantic candidate retrieval
        ↓
comparison/classification
```

Embeddings may nominate candidates.

Embeddings must not merge hypotheses.

## Phase 2: selection influence

Only after evaluation:

- exact repeats may reuse/skip;
- high-confidence semantic duplicates may be deprioritized;
- population/mechanism variants remain eligible;
- possible duplicates remain eligible.

---

# 21. Compound ideation

Do not compose by brute-forcing raw chunks.

Preferred composition units:

```text
latent structures
transferable invariants
normalized primitives
constraints
hypothesis gaps
mechanisms
```

Chunks/parents remain grounding evidence.

---

# 22. Directed composition frontier

Future COMPOSE behavior should use:

```text
objective
        ↓
anchor semantic structure
        ↓
identify missing role / relation / constraint
        ↓
retrieve candidates that can fill it
        ↓
bind role
        ↓
check history + known constraints
        ↓
retain promising partial composition
        ↓
extend until interaction is reasoning-ready
```

Do not enumerate pairs/triples.

---

# 23. Partial compositions

Support higher-order ideation without requiring each pair to independently produce an idea.

Logical object:

```yaml
PartialComposition:
  objective_ref:
  member_bindings:
    - input_ref:
      role:
  unresolved_roles:
    - role:
      question:
  constraints:
  search_cursors:
  predecessor_attempt_refs:
```

Persist only when:

- it survives meaningful selection;
- it consumes material reasoning budget;
- it must resume across runs.

Ephemeral candidate sets remain run state.

---

# 24. Marginal contribution rule

For every composed output ask:

```text
What does each member contribute?
```

If removing a member leaves the proposed implication essentially unchanged:

that member is:

```text
corroborating/contextual
```

not a necessary composition member.

This prevents decorative evidence stacking.

---

# 25. Exploration intentions

Add later, not in provenance V1:

```text
EXPLOIT
EXPLORE
COMPOSE
CHALLENGE
```

These are policy intentions above existing retrieval modes:

```text
Fast
Hybrid
Graph
```

Examples:

```text
EXPLOIT → strongest direct evidence
EXPLORE → relevant under-investigated semantic alternatives
COMPOSE → complementary structures
CHALLENGE → evidence capable of breaking a key assumption
```

Do not replace the retrieval stack.

---

# 26. No weighted novelty score initially

Do not immediately implement:

```text
relevance + novelty + diversity - saturation
```

The scales are not calibrated.

Start with constrained policy:

1. enforce permissions;
2. enforce objective/evidence requirements;
3. preserve necessary direct evidence;
4. consult history;
5. choose according to exploration intention.

Learn weights only later if evidence justifies it.

---

# 27. Saturation

Do not mark chunks saturated.

Saturation applies to a scoped semantic neighborhood:

```text
objective
population/context
mechanism/friction
operations attempted
evidence versions
coverage
```

A valid conclusion is:

```text
conditionally saturated under current evidence and explored operations
```

Never:

```text
this chunk is exhausted forever
```

---

# 28. New ingestion / dependency reopening

Do not replay all exploration after ingestion.

Maintain dependencies from attempts to:

- evidence;
- latent structures;
- gaps;
- assumptions;
- semantic facets.

New evidence should nominate affected attempts through:

```text
shared dependency
resolved gap
contradicted assumption
new population match
new mechanism/constraint
```

Only affected neighborhoods reopen.

---

# 29. Retention

Recommended:

```text
ExplorationAttempt             durable
EvidenceExposure               durable under existing audit policy
ExplorationIndex               rebuildable
Qdrant projection              rebuildable
temporary frontier candidates  ephemeral unless resumable
```

Do not invent TTLs before measuring volume.

Historical failures remain useful exploration memory.

---

# 30. Versioning

Record enough to interpret old work after system changes:

```text
model/producer identity where observable
operation contract version
normalization version
semantic projection version
source content version/hash
```

A new model version does not automatically create a novel idea.

Version change affects comparison confidence.

---

# 31. Performance strategy

Lookup sequence:

```text
exact signature/hash lookup
        ↓
structured facet blocking
        ↓
small candidate set
        ↓
semantic/expensive comparison
```

Never deserialize all prior runs per request.

Never scan every attempt to find novelty.

---

# 32. What must never be materialized

Do not create:

- all chunk pairs;
- all chunk triples;
- embeddings for theoretical combinations;
- global unexplored-combination inventory;
- copied mutable OpportunitySemanticView records.

Persist **actual work performed**, not theoretical possibility space.

---

# 33. Integration with current Semantic Transduction Restoration

Do not derail restoration with full exploration policy.

During restoration, add only provenance that cannot be safely reconstructed later.

IMPLEMENT NOW:

```text
stable origin/version refs
exact evidence exposure
input role bindings for semantic operations
output refs
disposition/outcome/gap refs
producer/contract version
```

DEFER UNTIL RESTORATION IS GREEN:

```text
ExplorationIndex
duplicate policy
history-aware selection
directed composition frontier
adaptive learning
```

Reason:

```text
semantic continuity
        ↓
reliable provenance
        ↓
cross-run exploration memory
        ↓
selection policy
```

Do not build exploration memory over broken semantic propagation.

---

# 34. Integration points to inspect

Confirm actual call paths before editing.

Known relevant areas from prior Polymath inspection:

```text
shared/polymath_shared/adapter/service.py
shared/polymath_shared/adapter/store.py
shared/polymath_shared/adapter/evidence_boundary.py
shared/polymath_shared/retrieval_lineage.py
shared/polymath_shared/corpus_explore.py
adapters/ecommerce/python/memory.py
```

Also inspect:

- schema migrations;
- hypothesis transition cause records;
- harness receipt models;
- accepted-output transaction boundary;
- OpportunitySemanticViewV1 once implemented.

Use repository tools/CodeGraph/grep before deciding exact file placement.

---

# 35. Suggested shared module location

Prefer existing shared Polymath package conventions.

Conceptually:

```text
shared/polymath_shared/exploration/
```

Potential modules:

```text
models.py
store.py
signatures.py
history.py
projection.py     # when index is implemented
policy.py         # later
composition.py    # later
```

Do not create all of these mechanically.

Initial provenance phase may need only:

```text
models
store
signatures
history
```

Follow actual repo conventions.

---

# 36. Feature flags

Behavior-changing capabilities must be reversible.

Suggested logical flags:

```text
EXPLORATION_PROVENANCE_ENABLED
EXPLORATION_INDEX_ENABLED
EXPLORATION_DUPLICATE_OBSERVE
EXPLORATION_EXACT_REUSE
EXPLORATION_POLICY_ENABLED
EXPLORATION_COMPOSE_ENABLED
```

Use actual configuration conventions.

When policy flags are off:

existing Polymath behavior must remain unchanged.

Provenance may continue recording.

---

# 37. Trail boundary

Trail must not receive novelty or saturation as evidence.

Do not feed:

```text
novelty_score
exploration_count
saturation
```

into LAW-1.

Exploration history does not make a claim true.

Trail continues to govern evidence truth/qualification.

---

# 38. Hypothesis ledger boundary

Do not duplicate hypothesis state.

ExplorationAttempt records:

```text
this semantic operation produced/revised/challenged H7
```

through `output_refs`.

The existing hypothesis ledger remains authoritative for H7.

Do not store a second copy of its state.

---

# 39. Retrieval lineage boundary

Do not duplicate:

```text
query → retrieval path → evidence
```

if retrieval lineage already captures it.

Exploration memory should reference that lineage.

Its missing fact is:

```text
what semantic operation was attempted with this evidence?
```

---

# 40. Adapter boundary

Keep exploration substrate generic.

Adapters define relevant semantic facets and operation semantics.

Ecommerce can use:

```text
population
friction
mechanism
product concept
commercial outcome
```

Other adapters may use different outcome semantics.

Do not encode Trail score or ecommerce-specific "success" into generic exploration history.

---

# 41. Rollout phases

## Phase 0 — provenance audit

Create a matrix:

```text
required fact
existing source
complete?
reconstructible?
new persistence required?
```

Persist only missing facts.

## Phase 1 — provenance substrate

Add:

- exposures;
- attempts;
- input roles;
- output refs;
- predecessor refs;
- dispositions;
- versions.

No selection behavior changes.

## Phase 2 — read-only history projection

Support exact lookup and indexed history queries.

No suppression.

## Phase 3 — duplicate observation mode

Annotate duplicates/variants.

Measure errors.

## Phase 4 — exact-repeat reuse

Only unchanged exact attempts can skip/reuse.

Feature-flagged.

## Phase 5 — history-aware exploration

Add EXPLORE / CHALLENGE.

## Phase 6 — directed composition

Add COMPOSE frontier.

## Phase 7 — adaptive learning

Only if measured evidence justifies it.

---

# 42. Acceptance tests

## Exact repeat

A+B with same objective, roles, versions:

```text
recognized as prior exact attempt
```

## Reuse

A+C after A+B:

```text
A remains eligible
```

## Role sensitivity

Same A+B but different roles:

```text
different attempt signatures
```

## Higher-order composition

A+B incomplete, C resolves missing role:

```text
A+B+C allowed
no brute-force enumeration
```

## Semantic duplicate

Different wording, same causal claim/conditions:

```text
candidate duplicate
no automatic ledger merge
```

## Mechanism variant

Same friction, different intervention:

```text
MECHANISM_VARIANT
remains eligible
```

## Population variant

Same mechanism, materially different population/context:

```text
POPULATION_VARIANT
remains eligible
```

## Reopening

New evidence resolves old gap:

```text
new attempt
predecessor link
old outcome preserved
```

## Exposure accounting

100 retrieved, 60 offered, 40 actually included if observable:

history must preserve distinct counts.

## Retry idempotency

Three retries:

```text
one logical semantic attempt
```

## Scope isolation

Unauthorized corpus history:

```text
no influence
```

## Scale

No all-history scan, pair enumeration, or per-request payload deserialization.

---

# 43. Metrics

Collect in observation mode:

```text
exact repeat rate
semantic duplicate candidate rate
false duplicate rate
missed duplicate rate
reused evidence rate
reopened attempt rate
attempts per supported useful hypothesis
distinct supported mechanism families
distinct supported population variants
history lookup cost
storage growth per run
```

Do not optimize raw novelty count.

---

# 44. Failure modes and protections

## Novelty chasing
Grounding/objective requirements come first.

## Strong evidence starvation
Penalize repeated semantic work, not the evidence itself.

## False duplicate collapse
Classification does not merge lifecycle records.

## Runaway composition
Role-directed frontier + existing budgets.

## Stale penalties
Use versioned attempts and explicit reopen rules.

## Concept laundering
Compare mechanisms/conditions, not names.

## History treated as evidence
Never satisfies Trail evidence requirements.

## Technical failure treated as refutation
Typed dispositions.

## Missing history treated as novelty
Return "not found in indexed history," not "globally novel."

---

# 45. Definition of done

The integration is correct when:

1. semantic attempts survive across runs;
2. exact repeated work is identifiable;
3. old evidence remains reusable;
4. same members with different semantic roles remain distinct;
5. retries do not inflate exploration history;
6. cross-run lookup is indexed and bounded;
7. new evidence can reopen prior attempts explicitly;
8. history respects principal/corpus scope;
9. exploration memory cannot alter Trail truth authority;
10. the ExplorationIndex can be rebuilt from authoritative records;
11. existing Polymath behavior is preserved when behavior flags are disabled;
12. the system can explain why an attempt was reused, skipped, reopened, or explored.

---

# 46. Goal-mode implementation prompt

```text
You are implementing Polymath Semantic Exploration Memory.

Read the current Polymath bootstrap, continuation, Semantic Transduction Restoration reference, and this file before modifying code.

Mission:

Add persistent cross-run memory of semantic work attempted without creating a second hypothesis ledger, second RAG runtime, second registry authority, or new memory microservice.

Core rule:

DO NOT mark chunks permanently used.

Remember semantic attempts:

objective
+ operation
+ versioned inputs
+ input roles
+ relevant conditions
+ outputs
+ disposition.

Postgres owns authoritative exploration provenance.

The ExplorationIndex is derived/rebuildable.

Qdrant is optional later for semantic candidate lookup.

Neo4j requires no V1 change.

Trail does not own novelty/exploration and must not receive novelty as evidence.

Execution order:

1. audit which required provenance fields already exist;
2. persist only missing provenance;
3. implement EvidenceExposure and ExplorationAttempt using existing transaction boundaries;
4. implement deterministic attempt signatures and scope-safe indexed lookup;
5. build a read-only derived history projection;
6. add duplicate classification in observation-only mode;
7. validate false/missed duplicate behavior;
8. stop before enabling behavior-changing novelty policy unless specifically authorized.

During the current Semantic Transduction Restoration phase, only add provenance hooks that cannot be reconstructed later. Do not derail restoration with the full exploration controller.

Use existing repository conventions, migration patterns, IDs, scopes, receipts, hypothesis ledger, retrieval lineage, and guards.

Do not:
- brute-force combinations;
- materialize chunk pairs;
- randomize retrieval for novelty;
- permanently suppress old evidence;
- treat history as evidence;
- duplicate Trail;
- duplicate hypothesis state.

Prove:
- exact repeated attempts are identifiable;
- A remains reusable in A+C after A+B;
- A+B with different roles is a different attempt;
- retries are idempotent;
- scope isolation holds;
- lookup remains indexed and bounded;
- the derived index can be rebuilt from authoritative records.

Proceed autonomously under repository truth and stop only for an owner-level architectural conflict.
```

---

# 47. Final principle

Do not build memory of:

```text
"which chunks were used?"
```

Build memory of:

```text
"what semantic work did Polymath attempt
with which versioned knowledge,
under what objective,
with what input roles,
what did it produce,
and what happened?"
```

That prevents repetition without destroying recombination.

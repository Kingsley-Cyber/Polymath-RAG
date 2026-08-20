---
owner: governance
status: draft
last_reviewed: 2026-08-18
last_touched: 2026-08-18
---

# REFERENTIAL-ADMISSION-V2 — author's plan (verbatim)

Recorded as authored 2026-08-18. Gap analysis follows in the work log;
this file is the source text and is not edited to match findings.

## Posture

Freeze the semantic architecture where it is. Keep legacy_v1 as
production. Do not promote kimi_v1, semantic_v2, new GLiNER labels, more
VerbNet/FrameNet/SemLink coverage, or more recall rescues.

> THIS IDEA MAY CHANGE OR BE REMOVED IF WE INCORPORATE A STAGED/PHASED
> ENTITY HARBOR LAYER

Attack admission next, because it has real authority over current noise.
Specifically qualify rejection/demotion of definite descriptions and bare
plurals: `the system`, `the application`, `the process`, `users`,
`servers`, `databases`. These should generally become MENTION_ONLY unless
there is discriminative identity evidence. This removes false graph
assertions without touching predicate semantics. Measure only one thing:
which current FPs disappear, and which legitimate TPs are lost. If
admission removes 3-4 FPs while losing 0 useful facts, that is real
progress.

## Mention retention

Keep a mention when it has downstream value:
- participated in a relation candidate
- OR was rejected by admission
- OR was linked/resolved to an entity
- OR provides evidence for an accepted fact
- OR is needed for evaluation/observability

## Admission gate: REFERENTIAL-ADMISSION-V2

Constrained to exactly these mechanisms:

1. spaCy head extraction + lemmatization
2. mention form: named-like / nominal / bare plural / pronoun-deictic
3. generic-head classification by LEMMA
4. identity signals: acronym / version-model identifier / established
   alias / discriminative named compound / previous resolved entity
5. definite-description resolution: resolve existing identity OR remain
   noncanonical
6. no token-count promotion
7. corpus uniqueness = weak supporting evidence only
8. GLiNER confidence = never identity authority

### Required outcomes

MENTION_ONLY: `system`, `application`, `workers`, `background workers`,
`invoicing system`, `container platform`, `regional dispatchers`,
`two new surgeons`

Admitted: `QuickScale`, `QuickScale platform` (admitted/resolved
appropriately), `PostgreSQL`, `TLS 1.3`, `Harbor Gateway`

...while ensuring legitimate multiword technical identities do not
disappear.

The entity pipeline currently has a specific defective rule:
`descriptive compound ~= identity`.

## Storage split

Mentions live in Postgres, never as Neo4j nodes:

```
Mention { mention_id, document_id, chunk_id, sentence_id,
          start, end, surface, proposed_type, proposal_score,
          admission_class, admission_reason,
          canonical_entity_id: nullable }
```

Neo4j contains only CANONICAL ENTITY, CANONICAL FACT, and the
PROVENANCE/EVIDENCE needed for accepted facts.

```
RAW TEXT -> MENTIONS (permissive evidence)
         -> ADMISSION
         -> CANONICAL ENTITY (strict identity)
         -> FACT
         -> NEO4J (extremely strict knowledge)
```

## Target

Rerun the frozen precision evaluation immediately after admission. The
target is not more relations. It is **FP -> 1 or 0 while preserving
useful TP**. If P >= .95 with acceptable recall is reached, STOP
precision surgery. A system can have incomplete lexical coverage and
still be production-quality if the incompleteness does not create wrong
knowledge.

## Sequence

```
NOW
├── Admission precision gate            -> rerun frozen eval
├── Canonicalization (only if remaining errors justify) -> rerun
├── Heading/context promotion test      -> rerun
└── If P>=.95 / R>=.70 + safety green
        -> FREEZE -> SEALED MULTI-DOMAIN EVAL
           PASS -> extraction is done
           FAIL -> first-loss evidence chooses ONE next gate
```

No new extraction work is authorized unless it points to an existing FP
or qualification failure and explains how the work changes that outcome.

## Explicitly deferred

Do NOT resolve the I3R <-> ADR-0016 compiler-authority collision now. It
is real, but there is no evidence that wrong predicate selection is the
dominant source of bad graph facts. I3R already delivered a large
precision win by constraining trigger semantics. Reopening it so
VN/PB/FN/SemLink can "truly choose" would be architecture-driven rather
than evidence-driven engineering.

Semantic path stays conceptually:
GLiNER -> typed trigger -> UD/PropBank role + direction evidence ->
predicate candidate -> lexical resources as validation/provenance ->
type/signature/safety gates -> entity admission -> FACT
...until an actual false positive proves predicate selection is wrong.

## Division of labor

**spaCy NER will not be used in Polymath.**

```
GLiNER      "What spans are meaningful?"
ADMISSION   "Is this allowed to become durable identity?"
spaCy / UD  "Who is grammatically doing what to whom?"
PropBank    "Which semantic argument is ARG0 / ARG1?"
```

## Identity lane

```
GLiNER MENTION -> ADMISSION
   ├── MENTION_ONLY --X
   ├── DOCUMENT_SCOPED
   ├── CORPUS_SCOPED
   └── GLOBAL
          -> IDENTITY CANDIDATE GENERATION
             (exact name | alias table | fuzzy candidate)
          -> OPTIONAL GLinker evidence
          -> DETERMINISTIC MERGE GATE
             (SAME_ENTITY | ABSTAIN)
          -> CANONICAL ENTITY
```

## Entity dedup

RapidFuzz (MIT, fast Levenshtein/Jaro-Winkler) for cheap candidate
generation: `Postgres` ~ `PostgreSQL` -> very high similarity.
Reference: https://github.com/DerwenAI/strwythura

```
MENTIONS          = permissive evidence world
CANONICAL ENTITIES = stricter identity world
FACT GRAPH        = strictest truth world
```

## Generic-head inventory

Do not delete it. Change it from an exact surface blacklist to a
**lemmatized semantic head inventory**: user, server, database, device,
team, company, method, algorithm.

Then `worker` / `workers` / `the workers` / `background workers` /
`regional workers` all share `head_lemma = worker`, and the question
becomes: is there genuine identity information modifying "worker"?

- `background workers` -> generic description -> MENTION_ONLY
- `Harbor Gateway workers` -> "Harbor Gateway" is an established identity
  anchor -> perhaps DOCUMENT/CORPUS scoped group

## Definite descriptions

Do not automatically kill `the company` / `the application` / `the
system` — they can be resolvable.

```
QuickScale launched a billing platform.
The platform processes invoices.
```

"the platform" is not name-bearing, but if deterministic local resolution
establishes `the platform = QuickScale billing platform`, it inherits
that identity.

- unresolved definite description -> MENTION_ONLY / DOCUMENT_SCOPED
- resolved definite description -> reference existing entity

**Resolving a mention must reuse an existing entity, never create
"the platform" as a new entity.**

---

# REVISION 1 — agreed in discourse 2026-08-18

This section supersedes conflicting text above. Where REVISION 1 and the
original differ, REVISION 1 governs. New sessions: read this section
first, then `docs/wiki/refactors/0011-pipeline-cleanup-ledger.md`.

## Core correction

**"Not a named identity" does not mean "noise."** Polymath holds useful
canonical concepts (`vector index`, `retrieval system`, `transactional
outbox`, `language model`) as well as named entities. The frozen
admission gold was right; the rule we were about to introduce was wrong.

Three distinct things, not two:

| expression | kind |
|---|---|
| `the system` | unresolved textual reference |
| `retrieval system` | potentially canonical technical concept |
| `PostgreSQL` | identifiable named entity |

The admission question is therefore NOT "named vs common noun" but:

> A. an identifiable instance?
> B. a stable canonicalizable concept?
> C. merely a contextual/generic reference?

**RETRACTED:** the earlier requirement that `invoicing system` and
`container platform` become MENTION_ONLY. They require contextual
classification as potential concept terms, not automatic rejection.
`regional dispatchers` and `two new surgeons` remain correct MENTION_ONLY
targets (generic / existential group).

## Entity Harbor — formalized (no longer a vague future option)

```
GLiNER -> MENTION (permissive evidence) -> REFERENTIAL ANALYSIS
   ├── IDENTITY BEARING -> ENTITY HARBOR ─────┐
   ├── CONCEPT TERM     -> CANONICAL CONCEPT HARBOR ─┤
   └── LOCAL REFERENCE / GENERIC -> MENTION_ONLY     │
                                                     ▼
                                            CANONICALIZATION
                                                     ▼
                                             GRAPH-ELIGIBLE
                                                     ▼
                                               FACT GATE
                                                     ▼
                                                  NEO4J
```

## Admission data model — two axes, not one

Scope classes stay as SCOPE only. Add:

```
anchor_kind    : IDENTITY | CONCEPT | LOCAL_REFERENCE | GENERIC
referentiality : SPECIFIC | GENERIC | UNRESOLVED
graph_eligible : bool
```

| surface | anchor_kind | referentiality | scope | graph_eligible |
|---|---|---|---|---|
| `PostgreSQL` | IDENTITY | SPECIFIC | GLOBAL | true |
| `retrieval system` | CONCEPT | GENERIC | CORPUS_SCOPED | true |
| `the application` | LOCAL_REFERENCE | UNRESOLVED | DOCUMENT_SCOPED | false |
| `workers` | GENERIC | GENERIC | MENTION_ONLY | false |

The error class to eliminate is `"the system"` becoming a standalone
canonical identity named "the system" — NOT the existence of multiword
common-noun concepts.

## Canonical Fact Gate — replaces per-class _REFERENTIAL_FRAMES

Do NOT add evidence classes to `_REFERENTIAL_FRAMES` one at a time; that
guarantees one gets forgotten. Make endpoint safety a single central
invariant:

```
RELATION CANDIDATE   (may use mentions freely)
        ▼
FACT PROPOSAL        (compiler believes the relation exists)
        ▼
CANONICAL FACT GATE
   ├── subject graph_eligible?
   ├── object graph_eligible?
   ├── predicate/signature valid?
   └── assertion/scope valid?
        ▼
CANONICAL FACT
```

A MENTION_ONLY endpoint MAY still participate in candidate generation,
diagnostics, syntax binding, evaluation and provenance. It MAY NOT
produce a canonical asserted fact.

Three durable tiers, all retained in Postgres; Neo4j gets only the third:

```
RelationCandidate = hypothesis / evidence
FactProposal      = compiler believes the relation exists
CanonicalFact     = legally admissible knowledge
```

## Decisions taken

1. **Fix the admission qualification harness FIRST.** `qualify_admission.py`
   imports a stale fork, does not test production code, and overwrites
   its own frozen artifact. No admission measurement is trustworthy until
   repaired. Infrastructure repair, not tuning. (ledger row 37)
2. **Re-author the admission gold BEFORE touching production rules.** Do
   not flip `retrieval system` / `vector index` to MENTION_ONLY. Annotate
   each gold expression with `anchor_kind`; let the existing scope values
   describe scope only.
3. **Admission becomes a distinct durable STAGE:**
   `extract_mentions -> syntax -> admit_mentions -> resolve/canonicalize`.
   No more `allocate_entity_id()` as an inline side effect. Changing an
   admission contract must not require re-running GLiNER.
4. **Admission consumes the existing spaCy syntax artifact** as an
   explicit prerequisite. It must not call spaCy opportunistically. If
   `syntax-evidence-v1` is unavailable, FAIL CLOSED / pending — never
   silently change admission behaviour. spaCy is a structural evidence
   provider for binding AND referential admission. **spaCy NER stays
   disabled.**
5. **"Discriminative named compound" is removed** as an escape hatch.
   Replaced by explicit evidence categories: proper-name structure,
   acronym / model / version identifiers, established aliases,
   deterministic antecedent resolution, canonical-concept evidence.
   "Looks discriminative" is not a category.
6. **RapidFuzz and GLinker are OUT of this gate.** They are later
   identity-candidate providers, are not required to close the current
   false positives, and would contaminate the experiment.
7. **Mention-retention behaviour is FROZEN during this work.** The
   current OR-clause retains effectively everything; that is fine.
   Storage optimisation is unrelated to graph precision and must not be
   combined with REFERENTIAL-ADMISSION-V2.
8. **Canonicalization is no longer conditional.** At least one remaining
   FP has legitimate endpoints that admission cannot touch. Sequence is
   admission precision -> identity/canonicalization precision.
9. **Boundary vs canonicalization qualifier.** A contracted mention is a
   canonicalization case ONLY if sufficient identity evidence exists to
   resolve it. If the full form never appeared and GLiNER simply
   contracted the span, that is a BOUNDARY error and canonicalization
   must NOT invent the missing text.

## Phases

```
PHASE 0  Repair admission qualification harness
PHASE 1  Freeze Entity Harbor contract (anchor_kind; scope separate)
PHASE 2  REFERENTIAL-ADMISSION-V2
         spaCy head/lemma · mention form · referential status ·
         identity signals · concept-term evidence ·
         no token-count promotion · no GLiNER-score authority
PHASE 3  CANONICAL FACT PROMOTION GATE  -> rerun frozen precision eval
PHASE 4  IDENTITY / CANONICALIZATION    -> rerun
THEN     heading/context (recall)
```

Program order is **precision closure first, recall closure second**:

```
PRECISION PHASE  remove unjustified graph assertions without losing legitimate TP
                 ↓  (only once P >= .95)
RECALL PHASE     address known FN classes while P MUST remain >= .95
```

## Measured forecast against the 5 current FPs (CONTROL arm)

Re-derived under REVISION 1. Full forms verified present in-document.

| # | FP | owner under REVISION 1 |
|---|---|---|
| 1 | `associated_with(crestline -> vision system)` | **neither** — wrong PAIR. Gold wants `associated_with(vision system, quality database)`; this is the deferred ditransitive/binding error |
| 2 | `founded(crestline -> robotics vendor)` | Phase 3 — `the robotics vendor` is an unresolved definite description |
| 3 | `depends_on(mentor engine -> qbank item database)` | Phase 4 — relation correct, subject contracted; `Mentor assessment engine` present 1x in-document |
| 4 | `member_of(regional dispatchers -> ...)` | Phase 3 — generic/existential group |
| 5 | `developed(crestline -> cobalt assembly cell)` | Phase 4 — relation correct, subject contracted; `Crestline Automation` present 2x in-document |

Forecast: Phase 3 removes 2 (FP 5->3, P 0.800). Phase 4 removes 2 more
(FP 3->1, P 0.923). FP #1 needs the deferred binding fix.

**Consequence: P >= .95 is NOT reachable at TP 12 unless either FP #1 is
also removed, or TP rises to >= 19.** See OPEN-1.

## OPEN — must be settled before Phase 2 writes code

**OPEN-1. What deterministically separates CONCEPT from LOCAL_REFERENCE?**
This is the whole gate, not a detail. Both of these are definite
descriptions of unnamed things in the same corpus:

```
"the vision system"      appears 2x, doc 03   -> CONCEPT or LOCAL_REFERENCE?
"the robotics vendor"    appears 1x, doc 03   -> CONCEPT or LOCAL_REFERENCE?
```

Determiner does not separate them — both are definite. Yet the frozen
gold requires `retrieval system` / `vector index` (same shape) to be
graph-eligible CONCEPTs.

The classification decides whether the precision target is reachable:

- `vision system` = LOCAL_REFERENCE -> FP #1 dies in Phase 3 -> P can reach 1.000
- `vision system` = CONCEPT         -> FP #1 survives both phases -> P caps at 0.923

Recurrence is the obvious candidate signal, but mechanism 7 says corpus
uniqueness is *weak supporting evidence only*, so it cannot be the
primary rule. Either mechanism 7 is relaxed for concept-hood, or CONCEPT
requires cross-document recurrence, or concept terms are graph-eligible
only in defined roles. UNRESOLVED.

**OPEN-2. `graph_eligible` must have exactly one authority.**
`neo4j_eligibility.py` currently derives eligibility from
`admission_class != 'MENTION_ONLY'` and is shared by projector, census
and verifier — the three that must agree. REVISION 1 adds an explicit
`graph_eligible` field. Decide: computed from (anchor_kind, scope), or
stored and authoritative? Two sources will drift (see ledger rows 25-26
for this exact failure class).

**OPEN-3. Adding a stage changes the control-plane contract.**
Production is eight stages (`EXPECTED_STAGES` in `verify_i4.py`, control
census, outbox event types, receipts). Inserting `admit_mentions` means a
migration, a new event type, census expectations, verifier updates, and
an ADR. This is real control-plane work, not a refactor. Confirm scope.

**OPEN-4. Does re-authoring the admission gold invalidate downstream
frozen evidence?** The E2/C1.1 admission qualification and the G4
downstream checkpoint were qualified against the current gold. Changing
the gold's semantics may require re-running both.

**OPEN-5. What is the relationship between CANONICAL CONCEPT HARBOR and
the E5 concept work?** `concept-inventory-v1` was QUALIFIED as an
experimental derived-metadata primitive but explicitly NOT promoted, and
concept-enriched routing was REJECTED. If CONCEPT terms now become
graph-eligible, that posture needs restating.

---

# REVISION 2 — settled in discourse 2026-08-18

Supersedes REVISION 1 where they differ. **New sessions read this first.**

## Attribution discipline (binding rules on this whole program)

1. **Do not manipulate admission to eliminate an error that is actually a
   binding error.**
2. **Do not increase recall to enlarge the precision denominator.** At
   TP 12, FP 1 gives .923. The fix is to correct that one binding error,
   not manufacture seven more TPs so the metric passes.
3. **Do not classify a mention based on which answer removes an FP.**
   That is tuning admission to the evaluation. Ask what the expression
   actually IS linguistically and epistemically. If it is a CONCEPT and
   the relation is still wrong, the BINDING layer owns that FP.

## OPEN-1 SETTLED — four anchor kinds

| kind | definition | examples |
|---|---|---|
| **IDENTITY** | a particular identifiable thing | Crestline Automation, PostgreSQL, Mentor Assessment Engine, TLS 1.3, Harbor Gateway |
| **CONCEPT** | a reusable kind / type / technical abstraction | retrieval system, vector index, transactional outbox, language model, **container platform, invoicing system** |
| **LOCAL_REFERENCE** | discourse-specific thing whose identity was never independently established | the system, the application, the vendor, the vision system, the robotics vendor, this platform, our database |
| **GENERIC_GROUP** | class/group reference rather than one entity | regional dispatchers, two new surgeons, workers, servers, users, applications |

`invoicing system` and `container platform` are **CONCEPTs**, not
MENTION_ONLY. The earlier requirement is fully retracted. The defect was
never "common-noun compound = bad"; it is "common-noun compound != an
identifiable instance".

### Definite-description rule

```
definite / demonstrative / possessive common-noun description
         ↓
   deterministically resolves to an existing anchor?
      yes -> REUSE that identity (never create Entity("the platform"))
      no  -> LOCAL_REFERENCE, noncanonical
```

### Bare concepts vs bare groups

`vector index` and `regional dispatchers` both lack proper names, but the
first is a stable technical concept and the second an unspecified group.
Morphology cannot separate them — admission needs **referentiality AND
anchor_kind**. spaCy supplies shape only (head, lemma, number,
determiner, POS, compound structure); it never decides concept status.
That is Polymath policy.

### Recurrence

Frequency/uniqueness stays **supporting evidence only** (mechanism 7
upheld). `the system` can occur 100x and remain generic; `transactional
outbox` can occur once and be a real concept.

## OPEN-2 SETTLED — no stored `graph_eligible`

`neo4j_eligibility.py` already owns that decision and is shared by
projector, census and verifier. Do NOT add a boolean column. Mentions
store `anchor_kind`, `referentiality`, `admission_class`,
`admission_reason`, `canonical_entity_id`; ONE function computes
`graph_eligible(mention)` and every consumer — projector, census,
verifier, fact promotion — calls that exact contract.

## OPEN-3 SETTLED — admission is NOT a new control-plane stage yet

Reversal of the earlier recommendation. A real stage costs a migration,
event type, outbox/census changes, EXPECTED_STAGES, verifier and an ADR —
too much operational surface for something still being qualified.

Instead: a **logical, versioned pure transformation**.

```
raw mention artifact + syntax artifact
        ↓  admission-v2 pure function
   persisted admission result   (admission_contract = referential-admission-v2)
```

The harness replays admission against persisted mentions without
re-running GLiNER. Promote to a first-class stage only if independent
re-admission later proves it necessary.

## OPEN-4 SETTLED — version the gold, never overwrite

`admission_gold_v1` preserved forever. Create `admission_gold_v2` with
Harbor semantics. Mark E2/C1.1 v1 explicitly as **historical
qualification**; REFERENTIAL-ADMISSION-V2 **requires new qualification**.
Do not pretend the previous gate certifies the changed contract.

## OPEN-5 SETTLED — E5 stays closed

To be stated in the ADR verbatim: **CONCEPT anchor_kind does NOT promote
`concept-inventory-v1`, does NOT enable concept-enriched routing, and
does NOT modify retrieval behaviour.** An admission-ontology distinction
is not the E5 project.

## Mention storage

Frozen. Keep permissive retention until extraction is stable. Storage is
not the precision blocker. Compaction rules come later.

## Roadmap

```
PHASE 0  Repair qualify_admission harness
         production imports · immutable frozen artifacts · trustworthy baseline
PHASE 1  Define ENTITY-HARBOR-V1 contract (anchor_kind / referentiality / scope)
         Create admission_gold_v2; do not overwrite v1
PHASE 2  REFERENTIAL-ADMISSION-V2  -> rerun frozen development eval
PHASE 3  CANONICALIZATION-PRECISION (only where full forms actually exist) -> rerun
PHASE 4  FIRST-LOSS THE LAST FP
         if it is the demonstrated wrong-pair binding error, authorize
         BINDING-PRECISION-CLOSURE-V1 for THAT ERROR FAMILY ONLY.
         No recall rescue. No lexical expansion. No kimi promotion.
         -> rerun -> FP = 0 -> PRECISION CLOSED
THEN     Recall >= .70 ?  yes -> SEALED MULTI-DOMAIN
                          no  -> ONE demonstrated FN class,
                                 precision floor stays >= .95
```

## OPEN-6 — NEW, blocking Phase 1

**Does Polymath assert facts between document-scoped unnamed referents?**

Five of the 26 I4 gold supported-positive facts have endpoints that are
first-mention definite descriptions with no proper name and no
antecedent — LOCAL_REFERENCE under the settled rule:

```
part_of(radiology review board -> Lakeshore General Hospital)   currently FN
created(engineering group -> load-testing harness)              currently FN
created(analytics team -> shift scheduling model)               currently FN
associated_with(vision system -> quality database)              currently FN
causes(pump failure -> production stoppage)                     CURRENTLY TP
```

Under LOCAL_REFERENCE => not graph-eligible, all five become structurally
unassertable, and one is a TP today.

| | Scenario A: LOCAL_REFERENCE never graph-eligible | Scenario B: first-mention definites get DOCUMENT_SCOPED identity |
|---|---|---|
| after Phase 3 | TP 11, FP 2 -> P .846 | TP 12, FP 3 -> P .800 |
| after Phase 4 | TP 13, FP 0 -> **P 1.000, R .500** | TP 14, FP 1 -> P .933, R .538 |
| after binding closure | n/a — FP already 0 | TP 14, FP 0 -> **P 1.000, R .538** |
| recall ceiling | 21/26 = **.808** | 26/26 = 1.000 |
| the wrong-pair binding FP | **masked** by admission | **preserved** for honest attribution |

Scenario A reaches precision closure sooner but does so by making the
binding error disappear for the wrong reason — which rule 1 and rule 3
above forbid. Scenario B keeps the binding error visible, ends at the
same precision, and has a higher recall ceiling.

Scenario B requires deciding that a first-mention definite naming a
specific event or artifact ("the pump failure") carries DOCUMENT_SCOPED
identity, while a definite naming an unresolved third party ("the
robotics vendor") does not. That distinction is not yet specified.
UNRESOLVED.

---

# REVISION 3 — OPEN-6 SETTLED 2026-08-18

No fifth anchor kind. The four kinds stay frozen. LOCAL_REFERENCE gains a
sub-axis:

```
anchor_kind      : LOCAL_REFERENCE
reference_basis  : ANTECEDENT_RESOLVED | DOCUMENT_CONSTITUTED | EXTERNAL_UNRESOLVED
```

The single eligibility authority derives behaviour from that.

## OPEN-6 SETTLEMENT (policy text)

A first-mention definite description is **NOT** automatically
DOCUMENT_SCOPED and **NOT** automatically MENTION_ONLY. Classify
LOCAL_REFERENCE by `reference_basis`:

**1. ANTECEDENT_RESOLVED** — deterministically resolves to an existing
admitted anchor. Reuse that anchor. Never create a new entity from the
descriptive surface.

**2. DOCUMENT_CONSTITUTED** — the document itself establishes a
particular local event/object/group as a stable discourse referent. No
external real-world identity is required for the supported relation to be
meaningful. May receive a deterministic DOCUMENT_SCOPED identity.

**3. EXTERNAL_UNRESOLVED** — the phrase denotes a particular externally
existing participant whose identity is withheld or unresolved. Retain as
mention/reference. `canonical_entity_id = null`. Not eligible for
canonical facts.

**Do not infer `reference_basis` from definiteness, recurrence, GLiNER
score, capitalization, or gold-label consequences alone.** The
classification must be explainable from textual/discourse evidence.

**Do not demote a valid DOCUMENT_CONSTITUTED endpoint merely to remove an
FP owned by binding.**

## Worked distinction

| surface | anchor_kind | reference_basis | scope | canonical_entity_id |
|---|---|---|---|---|
| `the pump failure` | LOCAL_REFERENCE | DOCUMENT_CONSTITUTED | DOCUMENT_SCOPED | document-local deterministic id |
| `the robotics vendor` | LOCAL_REFERENCE | EXTERNAL_UNRESOLVED | DOCUMENT_SCOPED | **null** |

Typically DOCUMENT_CONSTITUTED: `the pump failure`, `the production
stoppage`, `the migration`, `the outage`, `the training run`,
`the review board` (only where the document establishes it as its local
object).

Typically EXTERNAL_UNRESOLVED: `the robotics vendor`, `the company`,
`the supplier`, `the surgeon`, `the customer`, `the application`.

GENERIC_GROUP is unchanged: `regional dispatchers`, `two new surgeons`,
`workers`, `servers` -> MENTION_ONLY.

## Re-annotation requirement

The five gold facts with definite common-noun endpoints
(`radiology review board`, `engineering group`, `analytics team`,
`vision system`, `pump failure`) must each be **re-annotated
independently** under this rule. Do NOT admit them because the gold
happens to contain a relation over them. For each ask: *does this
document establish a stable local referent that can safely participate in
facts, or is this a description of an externally existing but
unidentified participant?* This prevents designing the rule backward from
a desired TP count.

## Consequence for `vision system`

If the document genuinely establishes a document-local vision system, it
stays graph-eligible — and `associated_with(crestline -> vision system)`
therefore **remains visible as a binding error**. That is desirable. The
correct fact is `associated_with(vision system -> quality database)`;
erasing `vision system` at admission would give FP=0 for the wrong reason
and permanently hide a real candidate-binding defect.

## Forecast

Scenario-B behaviour is now the expected path:

```
Phase 0 harness repair
Phase 1 Entity Harbor contract incl. reference_basis
Phase 2/3 admission precision
Phase 4 canonicalization precision
        remaining FP = wrong-pair binding
        -> narrow BINDING-PRECISION-CLOSURE-V1
```

Phase 0 is UNBLOCKED and authorized to start immediately: it is
independent, non-semantic, and required before any number above is
trustworthy.

## REVISION 3a — bounded discourse individual vs generic plurality

The distinguishing axis is **not** "named vs unnamed". It is **one
bounded discourse participant vs a class/plurality**.

> A common-noun collective may be DOCUMENT_CONSTITUTED when the document
> treats it as ONE BOUNDED DISCOURSE PARTICIPANT capable of accumulating
> properties, actions and relations. **Proper naming is not required.**
>
> e.g. `the engineering group`, `the analytics team`, `the review board`,
> `the committee`
>
> These differ from GENERIC_GROUP expressions, which denote an unbounded
> class, plurality or existential set rather than one stable participant.
>
> e.g. `workers`, `regional dispatchers`, `two new surgeons`, `servers`,
> `users`

**Operational test:** can later text sensibly refer back to it as the
SAME participant?

```
"The engineering group created a load-testing harness.
 The group later extended it."          -> one stable discourse entity

"Regional dispatchers joined the consortium.
 Dispatchers frequently work overnight."-> a class/population, no bounded identity
```

`the robotics vendor` is also singular and definite, so morphology alone
cannot reject it. It differs because it is a **description standing in
for an externally existing organization** — a particular company exists,
the document simply has not said which. Treating that description as the
organization's identity would overclaim.

### Evidence hierarchy (mandatory)

Do NOT implement as `singular definite collective noun ->
DOCUMENT_CONSTITUTED`; that recreates the same defect one level deeper.
Require evidence that the document treats it as a bounded participant.

**Strong (may establish DOCUMENT_CONSTITUTED):**
- introduced as one syntactic argument
- subsequently referred to as the same participant
- receives multiple predicates/properties
- appositional/local description establishes it
- definite singular collective whose local identity suffices for the
  asserted facts

**Not sufficient alone:**
- the determiner `the`
- singular number
- appears twice
- GLiNER confidence
- **a gold relation exists over it**

**The gold tests the rule; it must never define the rule.** Whether
admitting a phrase recovers a gold TP is not evidence for its
classification.

### Seven cases settled

| surface | reference_basis | reason |
|---|---|---|
| `the pump failure` | DOCUMENT_CONSTITUTED | specific event constituted by the document |
| `the production stoppage` | DOCUMENT_CONSTITUTED | specific resulting event/state |
| `the vision system` | DOCUMENT_CONSTITUTED | stable local artifact established by the document |
| `the robotics vendor` | EXTERNAL_UNRESOLVED | particular external party, identity withheld |
| `the radiology review board` | DOCUMENT_CONSTITUTED | one bounded institutional collective |
| `the engineering group` | DOCUMENT_CONSTITUTED | one bounded collective actor, not a plurality |
| `the analytics team` | DOCUMENT_CONSTITUTED | same |

## REVISION 3b — seven rulings + the CONTEXT_REQUIRED invariant

**Rename: `GENERIC_GROUP` -> `GENERIC`.** `system`, `model`, `platform`,
`workers` and `regional dispatchers` can all be generic, but only some
are groups. GENERIC names the epistemic category correctly.

### Rulings

| surface | anchor_kind | note |
|---|---|---|
| `component D6L11` | **IDENTITY** | `D6L11` is a discriminative identifier. The old MENTION_ONLY scope is legacy policy, not evidence that it lacks identity. |
| `the ingestion system` | **CONTEXT_REQUIRED** | could be a specific local system, a previously introduced one, or generic terminology |
| `this service` | **LOCAL_REFERENCE** | deictic reference is clear; `reference_basis` needs context |
| `our recommendation engine` | **LOCAL_REFERENCE** | possessive reference is clear; DOCUMENT_CONSTITUTED vs ANTECEDENT_RESOLVED needs context |
| `Model 3` | **IDENTITY** | numbered identifier creates a particular referent; usually document/corpus scope, not necessarily GLOBAL |
| `Polymath retrieval system` | **IDENTITY** | `Polymath` is an explicit identifying anchor modifying a generic head |
| `Qwen3 embedding model` | **CONTEXT_REQUIRED** | named anchor is strong, but the surface alone cannot say whether this is one deployed model or the Qwen3 family/category |

### Do not encode "proper token + concept head -> IDENTITY"

That rule would eventually misclassify named families and categories.
Record the structural feature instead —

```
named_anchor_present = true
```

— and let context decide whether the whole NP denotes a particular
referent. `Polymath retrieval system` is one system because `Polymath`
identifies *which* system. `Qwen3 embedding model` may be one deployed
model or a family. The phrase alone does not settle it.

### THE INVARIANT

> If the required classification depends on discourse context, the system
> MUST consume discourse context or return **CONTEXT_REQUIRED**. It must
> NEVER infer the answer from morphology because the test harness happens
> to expect one.

### Two fixture classes, not one

Surface-only fixtures can qualify what is deterministically observable
from the span: surface, POS/head/lemma, proper-name structure, acronym,
version/model identifier, number, determiner, plurality, generic head,
named anchor.

They CANNOT qualify `ANTECEDENT_RESOLVED`, `DOCUMENT_CONSTITUTED` or
`EXTERNAL_UNRESOLVED` — those are discourse properties. Context-bearing
fixtures are therefore required, or a sophisticated context resolver
could be built with no qualification test for it.

### CONCEPT vs GENERIC is NOT solved

Morphology does not reliably separate `vector index` / `retrieval system`
/ `transactional outbox` from `system` / `platform` / `workers`.

PHASE 2 must NOT invent a concept classifier. CONCEPT admission requires
**defensible, auditable evidence**: an established canonical
vocabulary/ontology entry, a previously admitted concept, deterministic
terminology evidence, or another explicit source. **Otherwise abstain.**

```
unsure whether stable concept -> do NOT manufacture a canonical concept
```

not

```
technical-looking compound -> CONCEPT
```

which would recreate the two-token bug in a more sophisticated form.

### PHASE 2 authorized scope

1. Harbor enums / contracts
2. GENERIC rename
3. context-fixture schema
4. context-bearing qualification fixtures
5. explicit named_anchor / identifier / generic-head evidence fields
6. pure admission-v2 function interface

**NOT authorized:** a final CONCEPT-vs-LOCAL_REFERENCE classifier from
surface strings.


## CROSS-DOMAIN INVARIANT (formal acceptance criterion, added 2026-08-18)

For any well-formed textual document:

1. ingestion does not require a domain-specific admission algorithm;
2. the same deterministic Harbor contract executes;
3. unsupported semantic knowledge causes ABSTENTION, never guessed graph truth;
4. domain vocabularies are versioned evidence providers, not executable rule changes;
5. absence of concept recognition never prevents text retrieval;
6. every promoted identity/concept/fact has an auditable evidence chain;
7. replaying the same document + same contracts/resources produces the same result.

This replaces "every book gets every entity", which is unachievable
without sacrificing precision. The deterministic engine is universal; the
knowledge sources vary by corpus.

---

# REVISION 4 — governing roadmap as of 2026-08-19

Supersedes the REVISION 2 roadmap. **New sessions: this is the plan.**

## Completed

```
Phase 0      Harness repair                          DONE
Phase 1      Entity Harbor contract + gold_v2        DONE
Phase 2A/B   Discourse reference                     DONE
Phase 2B.1   Versioned discourse policy pack         DONE
Phase 2C     Harbor attribution                      DONE
Phase 2C.1/2 Envelope + routing integration repair   DONE
Phase 2D     Cross-domain concept evidence           DONE
IDENTITY-V2  Cross-register identity precision       QUALIFIED, NOT WIRED
CONCEPT-DEFINITION-COVERAGE-V1                       DONE
```

IDENTITY-PRECISION-V2 and CONCEPT-DEFINITION-COVERAGE-V1 were NOT in the
REVISION 2 roadmap. Both were authorized in response to a measured failure
on two real out-of-corpus documents, per the governing rule.

## Remaining

```
1. PHASE 3 CANONICALIZATION
      crestline     -> Crestline Automation
      mentor engine -> Mentor assessment engine
      Reuse an EXISTING admitted in-document identity. Never invent a
      plausible longer name. Preserve the original mention. Record why the
      merge occurred. No GLinker / embeddings / learned linker / broad
      fuzzy merge — two demonstrated failures do not justify them.

2. RERUN FROZEN I4        FP 0 expected; TP is MEASURED, not targeted

3. IF FP REMAINS          first-loss attribution -> identify the exact owner
                          -> authorize exactly ONE narrow gate
                          (e.g. BINDING-PRECISION-CLOSURE-V1)
                          otherwise STOP extraction surgery

4. WIRE QUALIFIED WORK INTO PRODUCTION            <-- NEW, was never in the plan
      IDENTITY-V2 + Entity Harbor + discourse reference + concept evidence
      -> the production admission path.
      Must preserve: 55/55 old admission regression · the new identity
      qualification · discourse qualification · concept qualification ·
      deterministic replay · graph_eligible as the SINGLE authority ·
      never classify from normalized_surface.

5. FULL FROZEN DEVELOPMENT GATE
      P >= .95 · R >= .70 · MUST-NOT green · 0 unexplained outcomes ·
      0 new admission losses · deterministic replay · provenance intact

6. FREEZE EXTRACTION SEMANTICS      no further development tuning

7. SEALED MULTI-DOMAIN EVAL                        <-- untouched documents
      technical · academic/scientific · business/organizational ·
      transcript/conversational · general prose · new domain terminology
      RULE: a sealed FAIL is diagnosed by first-loss. NEVER tune against
      the sealed corpus. A pass means extraction is DONE.

8. OPERATIONAL QUALIFICATION                       <-- NEW, was never in the plan
      bulk ingestion / scale · worker supervision (CP2.1) ·
      kill worker -> auto restart -> re-register -> resume ·
      bounded restart/quarantine · replay/idempotency ·
      Qdrant destruction -> exact reconstruction ·
      Neo4j destruction -> exact reconstruction ·
      orphan detection/removal · corpus authorization/isolation ·
      large integrity run converges

   This is the difference between "the extraction algorithm works" and
   "Polymath can be left running with a real corpus."

-> PRODUCTION READY
```

## Governing rule (unchanged)

> No new extraction work is authorized unless an existing MEASURED failure
> identifies its owner and you can explain exactly how the proposed change
> could correct that outcome.

The architecture search is over. What remains is closing measured defects,
integrating already-qualified pieces, and proving the whole on untouched
data.

---

# REVISION 5 — 2026-08-19. Supersedes REVISION 4's ordering.

## The major correction: qualified semantics are NOT production semantics

Everything from Harbor onward is a **shadow implementation** until the
wiring gate lands:

```
QUALIFIED                              LIVE PRODUCTION
IDENTITY-PRECISION-V2                  entity_admission.decide() = v1.1
ENTITY-HARBOR-V1                       (admits `I`, `That`,
DISCOURSE-REFERENCE-V1                  `When attention shifts`)
CONCEPT-EVIDENCE-V1
CONCEPT-DEFINITION-COVERAGE-V1
```

The wiring step cannot be skipped, and it moves EARLIER — to step 3,
immediately after the I4 rerun, so that the full frozen qualification
measures the production path rather than a shadow one.

## Evaluation hierarchy — development evidence vs sealed evidence

```
DEVELOPMENT / REGRESSION          (may be inspected, may drive rules)
├── I4 corpus
├── 04_transcript_local_rag_build.md
├── 01_psychology_working_memory.md
├── admission golds (v1, v1.1, v2)
├── Harbor fixtures
├── discourse context fixtures
└── concept cross-domain fixtures

SEALED QUALIFICATION              (never inspected while tuning)
└── entirely untouched documents
```

**The transcript and psychology files are now DEVELOPMENT probes**, because
their failures directly caused IDENTITY-PRECISION-V2 and
CONCEPT-DEFINITION-COVERAGE-V1 to exist. They stay as regression fixtures.
They must NEVER be cited as multi-domain generalization evidence —
otherwise generalization would be claimed using documents whose failures
authored the rules.

## Roadmap

```
1. PHASE 3 CANONICALIZATION PRECISION
2. FROZEN I4 RERUN            classify every residual FP by owner
                              FP 0 -> precision closure
                              FP remains -> exactly ONE first-loss gate
3. PRODUCTION WIRING GATE     raw mention -> identity-v2 -> Harbor ->
                              discourse reference -> concept evidence ->
                              single graph_eligible authority.
                              NO parallel old/new truth paths.
4. FULL FROZEN DEVELOPMENT QUALIFICATION
                              old regressions + I4 + transcript +
                              psychology + Harbor/discourse/concept fixtures
                              P>=.95 · R>=.70 · MUST-NOT green ·
                              deterministic · unexplained = 0
5. FREEZE SEMANTICS
6. FRESH SEALED MULTI-DOMAIN EVAL   untouched documents only, no tuning
                                    PASS -> extraction semantics DONE
                                    FAIL -> first-loss identifies ONE owner
7. OPERATIONAL QUALIFICATION  bulk ingest · CP2.1 automatic worker
                              supervision · replay · crash recovery ·
                              Qdrant reconstruction · Neo4j reconstruction ·
                              corpus isolation/auth · convergence
-> PRODUCTION READY
```

## PHASE 3 constraint — contraction resolution, NOT fuzzy dedup

The demonstrated problem is narrow:

```
short/contracted mention
+ existing LONGER identity in the SAME document
+ compatible type/context
-> resolve to the existing identity
```

```
"Crestline Automation uses Siemens PLCs..."   then   "Crestline developed..."
-> the Crestline mention may resolve to the existing Crestline Automation
```

That is NOT:

```
Crestline  ~=  Crestview Automation      (high string similarity)
-> MUST ABSTAIN
```

Rules: the full anchor must ALREADY exist in-document · never synthesize
missing name text · preserve the original mention · record exact merge
evidence · deterministic SAME_ENTITY or ABSTAIN.

**Start with deterministic in-document alias/contraction resolution.**
RapidFuzz and GLinker remain optional candidate generators for LATER, only
if real identity errors justify them. Two demonstrated failures do not.

## Note on step 7

Most destructive-reconstruction and replay behaviour is already exercised
and green from the I4 acceptance. **CP2.1 worker supervision is the
conspicuous remaining operational gap**: a worker death should become
`death detected -> bounded automatic restart -> health -> registration ->
leases resume -> corpus converges`, rather than requiring a human to
notice and restart it.

---

# PHASE 3 SETTLEMENT — 2026-08-19

**Policy B is promoted.** SAME_ENTITY resolution merges canonical identity
ONLY.

Phase 3 was supposed to answer *"are these two mentions the same entity?"*
It was never supposed to answer *"which textual surface should be the
preferred canonical label?"* Those are different problems, and conflating
them is what produced the CareChart regression.

```
MENTION SURFACE  "Crestline"
      -> IDENTITY RESOLUTION  SAME_ENTITY?
            no  -> ABSTAIN
            yes -> CANONICAL ENTITY ID
                     ├── "Crestline"            local member
                     └── "Crestline Automation" local member
```

Rules:

- It MUST NOT rewrite evidence/fact surfaces merely to select a preferred
  canonical label.
- Original mention surfaces remain **immutable provenance**.
- Canonical display-label selection is OUTSIDE Phase 3 and has **no
  authority over fact truth**.
- The historical frozen surface scorer remains UNCHANGED. Its artifacts
  are not overwritten and it is not retroactively called wrong.
- A separately versioned identity-aware evaluation may be added, comparing
  `predicate(canonical(subject), canonical(object))`. It supplements, never
  replaces, the frozen surface metric.
- **No longer/shorter-form preference may be selected from the I4 score.**
  Policy C scored 0.765 vs 0.706 and was REJECTED: `CareChart EMR` /
  `CareChart EMR platform` is a proven counterexample to "longer is
  canonical", so C had no semantic justification and choosing it would
  have been eval-driven policy selection.

## Evaluation representation mismatch (recorded, not repaired)

Once endpoints share canonical IDs, a surface-matching scorer reports
"different string -> wrong" where the production graph holds "same
canonical IDs -> same assertion". That is an evaluation representation
mismatch, not an extraction error. Two metrics now coexist:

```
I4 surface score            historical metric, frozen, unchanged
I4 canonical-identity score graph-semantic metric, separately versioned
```

## Scope limit

Contraction resolution keeps exactly: exact tokens · prefix containment ·
head-preserving elision · unique in-document anchor · type compatibility.
**No RapidFuzz, no GLinker, no universal entity linker.** `IBM` /
`International Business Machines` is an ACRONYM/ALIAS problem and
`Postgres` / `PostgreSQL` is an ALIAS/NORMALIZATION problem; each earns
its own demonstrated gate later, if ever.

## Ownership after Phase 3

```
founded(... -> robotics vendor)          Harbor      EXTERNAL_UNRESOLVED
crestline -> Crestline Automation        Phase 3     identity resolved
mentor engine -> Mentor assessment engine Phase 3    identity resolved
associated_with(... -> vision system)    BINDING     wrong pair, still wrong
```

Phase 3 is NOT asked to eliminate the Harbor-owned or binding-owned FPs.

---

# PRODUCTION-WIRING-GATE-V1 — SCOPE (2026-08-19)

Integration gate. **No new classification rules, thresholds, entity/concept/
discourse/contraction policies, predicate logic, binding logic or recall
work are authorized.**

## Real integration surface (measured, not estimated)

Admission is called INLINE at five sites, never as a stage:

```
workers/candidates.py:194      decide()              trigger-time slot check
workers/candidates.py:397      allocate_entity_id()  _allocate(), HAS SentenceSlice
workers/extract_worker.py:273  allocate_entity_id()
workers/extract_worker.py:729  allocate_entity_id()
workers/extract_worker.py:814  decide()
```

`admission_class` consumers that must all move to the single authority:

```
shared/neo4j_eligibility.py   5 refs   (projector + census + verifier share this)
workers/extract_worker.py     3 refs
workers/canonicalize_worker.py 2 refs
workers/candidates.py         2 refs
```

Good news: `_allocate()` already receives the `SentenceSlice`, so
`sl.syntax` is reachable at the exact point the new stack needs it. No
call-graph restructuring is required.

## The three risks that dominate this gate

### R1. IDENTITY-V2 is inert unless spaCy is ON in production

`syntax_provider` defaults to `disabled`. Without tokens,
`identity_evidence()` runs in DEGRADED mode, which is precisely the old
capitalization behaviour. **Wiring without enabling syntax gains nothing.**

Enabling it makes spaCy a HARD dependency of identity, not just of
binding: sidecar down = admission cannot decide = must fail closed/pending
rather than silently reverting to degraded evidence. That failure mode is
a control-plane behaviour change and needs its own decision.

### R2. Changing admission INVALIDATES existing entity and fact ids

`entity-identity-v2` derives the id FROM the admission class:

```
GLOBAL          entity_id(type, normalized)
CORPUS_SCOPED   entc_ + hash(corpus, type, normalized)
DOCUMENT_SCOPED entd_ + hash(corpus, doc, type, normalized)
MENTION_ONLY    mention_ + hash(doc, chunk, offsets, type)
```

IDENTITY-V2 demotes many surfaces (`I`, `That`, `Researchers`, ...), so
their ids change PREFIX. Every fact referencing them changes `fact_id`,
and every Qdrant/Neo4j projection keyed on those ids is stale.

**This is a re-ingest, not a code swap.** It is the largest item in the
gate and it is absent from the flow diagram. Stage 1 must MEASURE the
blast radius (how many entities change class, how many facts change id)
before anything is promoted.

### R3. Replay determinism requires contract pinning

`execution_contract` currently pins chunker, rule pack, query policy,
syntax contract, rescue policy. It does NOT pin: `identity-precision-v2`,
`entity-harbor-v1`, `discourse-reference-v1` + its policy-pack sha256,
`concept-evidence-v1`, `contraction-resolution-v1`. Without those, a
replay cannot reproduce an admission decision and invariant 6 of the
frozen gate ("deterministic replay") is unprovable.

## Schema — migration 0015

`mentions` has none of the Harbor state. Eight columns to add:

```
proposal_surface · referential_surface · anchor_kind · reference_basis
decision_status · canonical_entity_id · admission_reason · admission_contract
```

`surface` stays as-is and becomes the raw provider output;
`normalized_surface` stays for lookup/candidate generation ONLY.

## Staged plan

```
S1  BLAST-RADIUS MEASUREMENT (no promotion)
    re-run admission over the current corpus under both policies;
    report entities changing class, facts changing id, projections
    invalidated. Decide re-ingest strategy from the number.

S2  MIGRATION 0015 + contract pinning
    columns added, execution_contract extended, no behaviour change yet.

S3  SINGLE-PATH SWITCH
    one composed entry point replaces the 5 inline call sites;
    every admission_class consumer moves to graph_eligible().
    Old path DELETED, not flagged off — invariant 1 forbids parallel
    truth paths, and a feature flag IS a parallel path.

S4  SYNTAX DEPENDENCY DECISION (R1)
    enable spacy in production + define the fail-closed behaviour.

S5  RE-INGEST + FULL FROZEN DEVELOPMENT QUALIFICATION
```

## Acceptance, mapped to the six invariants

```
1 one truth path      old admission code path DELETED; grep proves no
                      second interpretation reaches facts
2 immutable surfaces  proposal/referential/normalized distinct; test asserts
                      admission never reads normalized_surface
3 one authority       no stored graph_eligible column; projector, census,
                      verifier, fact promotion all call the same function
4 no evidence rewrite mention surface, offsets and fact evidence byte-identical
                      before/after contraction resolution
5 fail closed         CONTEXT_REQUIRED / ABSTAINED / GENERIC /
                      EXTERNAL_UNRESOLVED / AMBIGUOUS never graph-eligible
6 retrieval intact    text, child chunks, parent summaries and retrieval
                      eligibility unchanged when admission abstains
```

Plus the regression floor: **55/55 admission gold · 31/31 identity
cross-register · 14/14 discourse fixtures · 16/16 concept cross-domain ·
10/10 contraction · deterministic replay byte-identical**.

## Explicitly OUT of scope

Tuning any rule after seeing the wired result · new admission/concept/
discourse rules · RapidFuzz/GLinker/embeddings · predicate, binding or
recall work · display-label policy · modifying the frozen surface scorer
or its artifacts.

## WIRING GATE — R1/R2/R3 SETTLED 2026-08-19

### R1 — spaCy is MANDATORY for entity-admission-v2. No degraded fallback.

```
syntax available    -> admission executes
syntax unavailable  -> RETRYABLE / PENDING infrastructure state
                       no admission decision, no facts
NEVER               -> quietly fall back to capitalization logic
```

Missing syntax is an **infrastructure failure, not semantic uncertainty**.
It must NOT become UNKNOWN or ABSTAINED, because that would make the graph
depend on whether spaCy happened to be healthy during extraction. The
DEGRADED path in `identity_evidence()` is therefore not reachable from a
v2 production run. Execution preflight must REJECT a v2 run whose required
syntax provider is disabled.

### R2 — semantic contract migration, not an in-place upgrade

If admission class changes, the entity id, fact id and projection identity
legitimately change. **Do not mutate the existing graph in place.**

```
existing corpus under admission-v1.1
   -> new extraction contract (entity-admission-v2 / Harbor stack)
   -> REDERIVE authoritative semantic records
        new entity ids · new fact ids · canonical memberships
   -> rebuild derived Qdrant/Neo4j state
```

S1 determines **where the rederive can START** (persisted chunks? persisted
raw GLiNER mentions? persisted syntax? or must the provider re-infer?).
S1 does NOT determine whether stale ids may remain — they may not.

### R3 — pin every authority capable of changing identity, eligibility or fact identity

```
identity_precision_contract        entity_harbor_contract
referential_envelope_contract      discourse_reference_contract
discourse_reference_policy_sha256  concept_evidence_contract
concept_resource_manifest_hash     contraction_resolution_contract
graph_eligibility_contract         canonical_fact_gate_contract
syntax contract / provider / model
```

Same source + same pinned contract MUST reproduce the same identities and
facts.

### Revised sequence — syntax readiness moves BEFORE cutover

```
S1  BLAST-RADIUS MEASUREMENT   (read only)
S2  MIGRATION + CONTRACT PINNING
S3  SYNTAX HARD-DEPENDENCY / READINESS
S4  SINGLE-PATH CUTOVER
S5  RE-DERIVE CORPUS + FULL QUALIFICATION
```

Syntax readiness must exist BEFORE the production path starts requiring
it. The earlier ordering had the dependency decision after cutover.

### Old path: retained for pinned replay, NEVER as fallback

The v1.1 implementation is **not deleted**. Historical deterministic replay
requires it.

```
execution_contract
   ├── contract = v1.1  -> v1.1 interpreter      (historical replay/audit only)
   └── contract = v2    -> Harbor/V2 interpreter (all new ingestion)
```

For ONE execution exactly one contract is authoritative — that is not a
parallel truth path. What is forbidden:

```
try v2; on failure silently use v1.1          FORBIDDEN
POLYMATH_USE_NEW_ADMISSION=0/1 changing truth FORBIDDEN
```

New ingestion accepts ONLY the current v2 semantic contract. Rollback is
an explicit deployment/contract rollback plus reconstruction — never a
runtime boolean flipped against existing records.

## S4 SETTLEMENT — evaluation hierarchy after cutover (2026-08-19)

**The 55-item gold becomes an explicitly HISTORICAL contract regression.**
Once S4 flips the live path to V2, calling it "the production regression"
would be misleading: it no longer exercises the production authority.

```
entity-admission-v1.1   -> HISTORICAL INTERPRETER
55-item gold            -> HISTORICAL CONTRACT REGRESSION
                           proves old pinned runs remain reproducible
                           does NOT certify current production admission
```

**The new production regression is the frozen COMPOSITION of the already
qualified V2 gates**, not another monolithic hand-authored gold:

```
PRODUCTION-ADMISSION-V2 REGRESSION
  IDENTITY-PRECISION-V2       31/31 · 0 false IDENTITY · 0 identity loss
  ENTITY-HARBOR               anchor/status/scope invariants
  DISCOURSE-REFERENCE-V1      frozen fixtures · 0 confident wrong · AMBIGUOUS abstains
  CONCEPT-EVIDENCE-V1         cross-domain fixtures · forbidden shortcuts abstain
  CONCEPT-DEFINITION-COVERAGE simple + hedged definitions
  CONTRACTION-RESOLUTION-V1   SAME_ENTITY positives/negatives
  REAL-REGISTER REGRESSION    transcript · psychology
  GRAPH AUTHORITY             graph_eligible() single authority
  DEPENDENCY BEHAVIOUR        syntax unavailable -> NO DECISION, never degraded
```

### Bridge test, with an explicit non-goal

Every case from the historical 55-item gold that remains semantically
applicable under V2 must produce a **documented** V2 outcome.

**Do NOT require `V2 output == v1.1 output`.** V2 intentionally changes
the semantics: a phrase v1.1 called CORPUS_SCOPED may correctly become
GENERIC and ineligible. Forcing backward equivalence would defeat the
migration.

### Single live authority, no generically named footgun

```
interpret_admission(contract_version=...)
    current ingestion        -> V2 ONLY
    explicit historical replay -> v1.1 ONLY
    unknown/unpinned contract  -> FAIL
```

Never `if V2 fails: try v1.1`.

`entity_admission.decide()` must not remain a generic name that secretly
means historical semantics — that is precisely how a future agent calls it
from production six months from now. It becomes
`decide_v1_1_historical()`.

### Consumer audit

Every site reading `admission_class` directly is audited. Some may
legitimately STORE or REPORT the class; **truth decisions must route
through the single Harbor authority** rather than re-deriving
`if admission_class != MENTION_ONLY` in several places. The consumers that
must agree: canonical fact promotion · Neo4j projector · control census ·
verifier · canonicalization.


---

# S4 CUTOVER — BLOCKED, reported 2026-08-19

The cutover is NOT a mechanical substitution. Two of the five call sites
cannot reach the syntax V2 hard-requires, and a PARTIAL cutover would
create precisely the parallel truth path wiring invariant 1 forbids. So it
is all-or-nothing, and it cannot be all until these are resolved.

## Site readiness

```
READY (syntax reachable)
  candidates.py:194   _admission_class_of(span, sl, ...)   has sl.syntax
  candidates.py:397   _allocate(span, sl, ...)             has sl.syntax
  extract_worker:814  _persist_decision(...)  called at 681 inside the
                      slice loop where `sl` is in scope

BLOCKED
  extract_worker:729  _persist_mentions(...)
  extract_worker:273  _allocate_parse_entity(...)
```

## BLOCKER A — stage ordering: mentions are persisted BEFORE syntax exists

```
line 589   _persist_mentions(...)        <- per-chunk, right after GLiNER
line 618   syntax_runtime = _syntax_evidence(ordered_slices)
                                          <- AFTER the whole chunk loop
```

Mentions are committed with their admission class before syntax exists for
any of them. Cutting this site to V2 requires reordering the extract
stage — batch GLiNER discovery across chunks, fetch syntax, THEN persist
mentions with V2 admission.

That changes the stage's commit ordering, which is control-plane-visible.
It is plumbing rather than semantics, but it exceeds a mechanical
substitution and was not authorized.

## BLOCKER B — `_allocate_parse_entity` has no token syntax, and must not

The parse record carries `voice / subject / agent / object / temporal /
weak` — the compiler's SEMANTIC record, with no tokens. Its ids must be
IDENTICAL to the candidate ids because `_oriented_pair` compares them.

The correct repair is NOT to give it its own V2 admission call (two
independent admissions of one span is a second truth path). It is to
THREAD the id already allocated at `_allocate` instead of recomputing it.
Also plumbing, also beyond mechanical substitution.

## Recommended follow-on, for authorization

```
S4a  EXTRACT-STAGE ORDERING
     move syntax acquisition before mention persistence
     no semantic change; commit ordering only
S4b  PARSE-ENTITY ID THREADING
     _allocate_parse_entity consumes the allocated id rather than
     re-deriving admission
S4c  CUTOVER  all five sites at once
```

Nothing was changed. Production remains v1.1; the V2 stack remains
qualified and inert.

---

# S4 CUTOVER — EXECUTED AND GREEN, 2026-08-19

Supersedes the BLOCKED section above. Both blockers were cleared by the
authorized S4a/S4b steps, then S4c cut all sites at once.

## What each step did

```
S4a  EXTRACT-STAGE ORDERING
     mention persistence deferred past `_syntax_evidence`
     BEHAVIOUR-NEUTRAL: I4 reproduced the frozen baseline exactly
S4b  SINGLE ALLOCATION AUTHORITY
     `_allocate_identities` allocates each proposed span ONCE at the
     post-syntax boundary; `_allocate_parse_entity` became a consumer
     BEHAVIOUR-NEUTRAL: I4 reproduced the frozen baseline exactly
S4c  CUTOVER
     all sites now read that one decision; the boundary calls
     interpret_admission(contract_version=admission-harbor-v2)
```

`_slices()` no longer allocates at all — it runs BEFORE syntax exists and
therefore cannot be an authority under a syntax-dependent contract.

## Sites, after the cutover

```
extract_worker  _allocate_identities   THE authority — one interpret_admission call
extract_worker  _allocate_parse_entity consumer
extract_worker  _persist_mentions      consumer (writes the V2 columns)
extract_worker  _persist_decision      consumer
candidates      _allocate              consumer
candidates      _admission_class_of    consumer
kimi_candidates _allocate (shared)     consumer
```

A consumer with no entry for a span RAISES. It never allocates a second
identity, so the failure mode is a loud stage failure rather than two
representations of one span quietly disagreeing.

## Boundary placement: after syntax AND after rescue

Rescue rebuilds `sl.entities` (boundary correction, type reconciliation),
so a pre-rescue snapshot holds superseded spans. The boundary therefore sits
after rescue, and mentions persist the FINAL proposal set.

This closed a pre-existing divergence: mentions were previously written from
the pre-rescue snapshot while candidates used post-rescue spans, so a mention
row could describe a span no fact endpoint referred to.

## Result — frozen I4, reproduced twice

```
                    TP  FP  FN     P       R     envelope  must-not  provenance
v1.1 baseline       12   5  14   0.706   0.462     7/8      18/18      16/16
V2 cutover          12   4  14   0.750   0.462     7/8      18/18      15/15
```

Recall, envelope and must-not are unchanged; one false positive is gone.
Provenance is 15/15 because there are 15 accepted facts, not 16 — every
accepted fact is still exact-span verified. 82/82 mentions carry
`semantic_contract = admission-harbor-v2`.

## Defect found and fixed during the cutover (plumbing, not semantics)

Identity was first keyed on `referential_surface`. That SPLIT one referent in
two: `the CareConnect portal` and `CareConnect portal` hashed differently and
produced two entity rows, so gold facts stopped matching (P fell to 0.375).

The envelope is an INTERPRETATION artifact — it keeps the determiner so a
definite description reaches the discourse consumer. It is not an identity
key. Identity is keyed on the proposal surface; the entity row's lookup
column carries the entity's own surface, never a reference to it.

This was found by the frozen gold and fixed in the allocator, not by
adjusting any rule to fit the gold.

## Development-document probes, live path

```
                             proposals  eligible  IDENTITY  GENERIC  ABSTAIN/CTX-REQ
04_transcript_local_rag       29         12        12        8        7
01_psychology_working_memory  39          8         1       20       10
03_research_notes_sleep       40          3         2       25       11
```

No durable identity was granted to a determiner-bearing surface in any of
the three.

## Open semantic questions — NOT actioned, cutover step is closed to tuning

1. **Title-case headings manufacture proper-noun evidence.** `Working Memory`
   admits as IDENTITY/GLOBAL on `POS=PROPN`, while `working memory` in body
   prose admits as CONCEPT/CORPUS_SCOPED (DOCUMENT_DEFINED). One concept,
   two identities, decided by capitalization in a heading. Same cause for
   `Attention` and `Research Notes`.
2. **Resolved local references earn durable document-scoped ids.**
   `these notes` (E3 repeated named anchor) and `new concept` (E4 single
   compatible antecedent) both become durable DOCUMENT_SCOPED entities. This
   is what `graph_eligible()` currently specifies for ANTECEDENT_RESOLVED,
   and it is inherited eligibility rather than manufactured identity — but
   whether a phrase like `these notes` should hold a durable id is a
   semantic decision that belongs to the evaluator, not to this step.

Both require authorization before any change.

---

# PRE-S5 SETTLEMENTS — executed 2026-08-19

Authorized after S4 so S5 does not rederive the corpus under semantics with
known identity defects.

## HEADING-IDENTITY-PRECISION-V1 (closes row 47)

> In a recognized heading/title context, title capitalization and
> heading-induced PROPN tagging are not sufficient positive identity
> evidence.

```
layout-induced capitalization  !=  semantic identity evidence
```

Mechanism, in `layout_evidence.py` + `identity_evidence.py`:

- Heading regions are read from CHUNK text, which still has line structure.
  Sentence text does not — a heading and the paragraph under it can land in
  one sentence — so asking the sentence would mean inferring typography from
  the phrase, which is the heuristic being removed.
- Recognized forms are narrow and syntactic: ATX headings and setext
  underlines. A short capitalized PROSE line is NOT a heading; guessing there
  would suppress real identity in body text, the more costly error.
- In heading context, PROPN evidence is kept only where capitalization is
  UNEXPLAINABLE by title-casing — an uppercase after the first character, or
  an all-caps token. Title-casing produces `Xxxxx` and nothing else.

Nothing is lowercased and no heading entity is rejected wholesale:

```
Working Memory   heading  ->  identity withdrawn (title-case explains it)
PostgreSQL       heading  ->  IDENTITY  (internal capitals survive lowercasing)
GLiNER           heading  ->  IDENTITY
NIST Cyber...    heading  ->  IDENTITY  (acronym evidence)
TLS 1.3          heading  ->  IDENTITY  (identifier evidence)
Working Memory   prose    ->  unchanged
```

**Preferred outcome achieved.** On the psychology document, `Working Memory`
now falls through to the concept authority and admits DOCUMENT_DEFINED,
identical to `working memory` in prose. Was 1 GLOBAL identity + 6 concepts;
now 7 concepts on one id.

## ANTECEDENT-IDENTITY-INHERITANCE-V1 (closes row 48)

Treated as a contract bug, not an open choice. Eligibility already inherited
from the antecedent; identity did not, which asserted:

```
same referent = yes
same identity = no
```

Now, in `allocate_identity()`, ahead of all scope routing:

```
reference_basis == ANTECEDENT_RESOLVED
    antecedent holds durable identity  ->  reuse that entity_id
    antecedent holds none              ->  mention id, NOT eligible
```

A resolved reference can no longer mint `entd_<hash(its own surface)>`. When
nothing durable is inherited, `graph_eligible` is corrected to False on the
record too, so the stored class never contradicts the decision.

## SEMANTIC-BUNDLE-WORKER-FENCE-V1

```
worker dies            -> supervision (CP2.1, later)
worker alive but stale -> refused the claim, HERE
```

`worker_contracts()` advertises `semantic_bundle`; `compatible()` requires
equality when the run pinned one. Runs pinned before the fence carry no
bundle and are unaffected.

**The bundle had to be strengthened to be worth anything.** It hashed only
declared contract IDs, and the incident's change (`identity_allocation.py`)
bumped no version string — so the fence as-then-written would not have caught
the very incident that motivated it. `semantic_authorities()` now also
carries `authority_code_sha256`, a content hash over the eleven semantic
authority modules.

The claim gate uses `semantic_authority_sha256()`, which is the bundle MINUS
the probed `syntax_model`. That value is read from a live sidecar and goes
None on a blip; including it would let one hiccup change every worker's
advertised bundle and stall the queue with tickets nothing can claim. The
syntax dependency is already gated, and better, by `claim_eligible()` against
fresh capability.

## SEMANTIC-RESIDUE-RECONCILIATION-V1

`entities` and `facts` are not corpus-scoped, so a wipe left them behind and
a failed run's rows survived every later wipe. Authority is the provenance
chain, never age or run label:

```
evidence  authoritative while its document exists
fact      authoritative while it has evidence
entity    authoritative while a mention or fact refers to it
```

Deletion is ordered along the chain and re-evaluated after each step, because
removing an orphan fact orphans the entities it alone held up. Dry run is the
default. Applied once:

```
entities 863 -> 728      facts 462 -> 385      mentions 585 (untouched)
residual: 0 dangling evidence, 0 unsupported facts, 0 unreferenced entities
```

24 determiner-prefixed entity rows remain. They are NOT residue: each has an
intact provenance chain in an older corpus (i3, e3, kimi-dev, quality-probe).
Zero are in the live corpus.

## Regression after all four

```
frozen I4            TP 12  FP 4  FN 14  P .750  R .462  envelope 7/8  must-not 18/18
historical 55-gold   accuracy 1.0, zero errors  (v1.1 replay intact)
test suite           541 passed, 53 skipped
transcript           12 eligible — unchanged
psychology            7 eligible — the split is closed
research notes        0 eligible — see below
```

I4 is unchanged by both rulings, so neither cost a true positive.

## New finding — a THIRD identity-fragmentation vector, needs a ruling

`working memory` still yields TWO ids on the psychology document:

```
entc_d870861a2df55d9  <- 'Working Memory' [Concept], 'working memory' [Concept]
entc_d994a987feadb3f  <- 'working memory' [Technology]
```

Identical normalized surfaces, so the split is `core_type`: GLiNER typed one
occurrence `Technology` and the rest `Concept`, and core_type is part of the
identity key. This is extractor type instability, distinct from typography
(row 47) and from reference minting (row 48), and outside both authorizations.
Logged as ledger row 51.

## Research notes now admits nothing — reported, not adjusted

0 of 40 proposals eligible, from 3. The three withdrawn were `Attention` and
`Research Notes` (title-case headings, row 47) and `these notes`, whose
antecedent was `Research Notes` — once that stopped being durable there was
nothing to inherit, so row 48 correctly refused to manufacture it.

The cascade is coherent and each step is individually correct. Whether a
document of this kind SHOULD yield zero graph entities is a coverage question
for the evaluator; nothing was tuned to avoid the answer.

---

# HARBOR-TYPE-IDENTITY-ALIGNMENT-V1 — executed 2026-08-19 (closes row 51)

## The frozen principle

```
Provider type helps DESCRIBE an identity;
it does not by itself DEFINE identity.
Qualified Harbor evidence owns canonical identity semantics.
```

## The defect

`core_type` was part of the identity key, so a provisional neural label
fragmented one referent:

```
working memory  normalized "working memory"  Concept     -> entc_d870...
working memory  normalized "working memory"  Technology  -> entc_d994...
```

Model typing is never stable across a diverse corpus — `transformer` alternates
Technology/Model/Architecture, `Python` Technology/Product/Language — so this
would have compounded across every book.

## The rule, and its deliberate limit

Precedence is inverted only where a stronger authority has actually settled
the kind:

```
qualified semantic authority  ->  canonical identity namespace
provider type                 ->  retained as evidence
```

```
CONCEPT          the document defined the term; that authority outranks a
                 competing provider guess     -> canonical type = CONCEPT
IDENTITY         provider type RETAINED       -> homonyms stay apart
LOCAL_REFERENCE  inherits the antecedent (row 48, unchanged)
```

Type is NOT removed from the key globally. That would overmerge, which is the
more damaging error:

```
Java    Technology / Location      stay separate
Apple   Organization / Product     stay separate
Mercury Concept / Location         stay separate
```

Nor does the gate merge on string equality: `Mercury` as a DOCUMENT_DEFINED
concept and `Mercury` as a named identity remain distinct, because the gate
keys off Harbor evidence rather than matching surfaces.

**This is not GLiNER type arbitration.** Nothing here adjudicates between
competing neural labels. It decides only whether a provisional label may
fragment an identity a qualified authority already settled.

## Result

```
psychology   'Working Memory' [Concept]   ┐
             'Working memory' [Concept]   ├─> entc_77ae3db105b8c6e   ONE identity
             'working memory' [Concept]   │   (was two)
             'working memory' [Technology]┘

transcript   7 distinct named identities, unchanged — no overmerge
frozen I4    TP 12  FP 4  P .750  R .462  envelope 7/8  must-not 18/18
55-gold      accuracy 1.0, zero errors
suite        554 passed, 53 skipped
```

Live corpus audit: no surface maps to more than one entity id. The only two
ids spanning multiple surfaces are row 48 inheritances behaving correctly —
`patient portal` -> `careconnect portal`, `invoicing system` ->
`quickscale invoicing system`. No IDENTITY-to-IDENTITY merge occurred.

# ROW 52 — CLOSED AS EXPECTED ABSTENTION

A document may produce chunks, embeddings, mentions, syntax and retrieval
while producing zero canonical entities and zero canonical facts. That is the
precision-first design working, not a coverage failure.

`03_research_notes_sleep_and_attention.md` discusses sustained attention,
working-memory updating, subjective fatigue and executive control without
establishing named identities or defining those terms as canonical concepts.
Forcing every document to contribute graph nodes would violate the design.

```
chunks ✓  embeddings ✓  mentions ✓  syntax ✓  retrieval ✓
canonical entities 0    canonical facts 0     <- expected
```

---

# S6A / S6B — FORENSIC ATTRIBUTION, 2026-08-19 (diagnostic only)

Semantics frozen. Nothing changed. Both waterfalls are closed and both
reported UNEXPLAINED = 0.

## S6A — canonical endpoint coverage (52 gold endpoint instances)

```
DURABLE                      38
DISCOVERY_MISS                7   provider never proposed the span
LOCAL_REFERENCE_UNRESOLVED    4   contract-correct refusal
HEADING_SUPPRESSED            2   row 47 working as designed
SPAN_BOUNDARY                 1   proposed with a different extent
UNEXPLAINED                   0
```

The 7 discovery misses were verified by listing every proposal in the
affected documents. `Nimbus Cloud` really is absent: GLiNER proposed
`Nimbus API gateway` and `Nimbus postmortem report` and never the company
itself. These are provider recall failures, not admission failures.

The 4 local-reference refusals are correct: `pump failure`,
`production stoppage` and `vision system` have no antecedent
(EXTERNAL_UNRESOLVED), and `engineering group` resolved to an antecedent that
itself holds no durable identity — row 48 refusing to manufacture one.

## S6B — canonical false positives (6)

```
WRONG_CANONICAL_IDENTITY      3   right referent, wrong extent
UNSUPPORTED_FACT              3   no gold relation between these referents
WRONG_PREDICATE               0
WRONG_ARGUMENT_PAIR           0
WRONG_DIRECTION               0
OVERMERGE                     0
UNEXPLAINED                   0
```

**BINDING-PRECISION-CLOSURE-V1 is NOT justified.** The earlier suspicion that
argument binding was the residual defect is refuted by evidence: zero wrong
pairs, zero wrong directions, zero wrong predicates, zero over-merges. The
three that first classified as WRONG_ARGUMENT_PAIR were re-examined and are
identity-extent mismatches — `developed: crestline -> cobalt assembly cell`
against gold `Crestline Automation -> Cobalt assembly cell` is the right
argument with a shorter identity. Conflating the two would have manufactured
a binding defect and sent the next gate at the wrong component.

## Verdict — the dominant mechanism is span discovery and extent

```
span discovery / extent   11   7 DISCOVERY_MISS + 1 SPAN_BOUNDARY
                               + 3 WRONG_CANONICAL_IDENTITY
admission behaving as designed  6   4 LOCAL_REFERENCE + 2 HEADING_SUPPRESSED
relation over-generation        3   UNSUPPORTED_FACT
```

Neither Harbor nor binding is the bottleneck. The graph cannot hold a
relation whose endpoint was never proposed, and 11 of 20 residual defects
trace to which spans the provider produced and with what extent.

This is the shape the original design anticipated — "keep the extractor broad,
treat outputs as candidates, enforce admission deterministically" — with the
first half currently under-delivering rather than the second half
over-refusing.

## Open question for a ruling, not a defect

`Crestline Automation` appears ONLY in its document's heading, so row 47
withdraws its identity and the document's own subject never becomes a node.
The rule is correct as written — title capitalization is not identity
evidence — but a heading is also where a document names what it is about.
Whether a heading-only proper name should be recoverable by other means is a
semantic decision, not a bug, and is not actioned.

---

# V4 SEMANTIC FREEZE — 2026-08-20

Semantic development is CLOSED for this release. The accepted state is the
last one that passed its qualification contract, reproduced and verified.

```
main / accepted/v2-semantic-freeze
    I4        TP 13  FP 3  FN 13  P .812  R .500  envelope 7/8  must-not 18/18
    provenance 15/15 · historical 55-gold 1.0, 0 errors · census no divergences
    S6A       DURABLE 38 · DISCOVERY_MISS 7 · SPAN_BOUNDARY 1
              HEADING_SUPPRESSED 2 · LOCAL_REFERENCE_UNRESOLVED 4
    S6B       WRONG_CANONICAL_IDENTITY 3 · UNSUPPORTED_FACT 3 · UNEXPLAINED 0
    569 tests pass

candidate/rescue-discourse-v1-failed   (tag v4-candidate-rescue-discourse-FAILED)
    A+B+67+69 · 602 tests pass · FAILED its acceptance bar
```

**A failed candidate does not become production because it fixed real bugs.**
Otherwise every acceptance bar in this programme becomes decorative.

## Why the accepted state keeps a known coverage defect

The accepted state deletes valid provider spans on refused widening; the
candidate fixes that but introduced wrong canonical identities and
unsupported facts. For a precision-first graph:

```
NO EDGE  is preferable to  A WRONG EDGE
```

A coverage defect is the safer release limitation than a truth defect, and
the underlying text stays reachable through the non-graph retrieval path — a
suppressed graph candidate does not erase the document from Polymath's
knowledge surface. This is a serious known limitation, not correct behaviour.

## KNOWN LIMITATIONS — V4

1. **Failed boundary widening can suppress valid semantic spans.** 13 per I4
   run, `Nimbus Cloud` at 0.91 among them (ledger 63).
2. **Deterministic discourse/coreference is deliberately conservative.** E3
   resolves on shared content words, which is lexical relatedness rather than
   identity (ledger 69); E4b never fires in production because
   `admitted_anchors` carries an entity id where a core type is expected
   (ledger 70).
3. **Identity extent can differ**: `Crestline` vs `Crestline Automation`,
   `Nimbus` vs `Nimbus billing service` (ledger 73). This is the unsolved
   axis, and the residual failures are extent, not discourse.
4. **Heading-only identity/alias recovery is incomplete** (ledger 61).
5. **Corpus-scoped concept homonyms remain possible** — two documents
   defining one term in different senses would share an id. Not observed.
6. **Some valid relationships therefore never enter the canonical graph.**

These are release limitations. They are NOT an invitation to open six more
gates. Row 64 (rescue label-vocabulary dilution) stays frozen. E4b stays out
of the composition. The failed candidate stays available for a future
redesign of identity extent.

## Next, without semantic tuning

```
fresh untouched multi-domain qualification   <- DO NOT TUNE
        ↓
measure actual generalization
        ↓
CP2.1 operational hardening
        ↓
large corpus ingest
        ↓
release decision
```

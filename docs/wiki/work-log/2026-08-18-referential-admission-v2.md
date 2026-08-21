---
change_id: referential-admission-v2
owner: worker
date: 2026-08-18
status: in-progress
architecture_impact: entity-harbor-admission-contract
last_reviewed: 2026-08-18
---

# REFERENTIAL-ADMISSION-V2

Plan: `docs/wiki/plans/REFERENTIAL-ADMISSION-V2-PLAN.md` — **REVISION 3
governs**. Ledger: `docs/wiki/refactors/0011-pipeline-cleanup-ledger.md`.

## Contract

Close graph precision at the identity layer, not by adding capability.
Entity Harbor separates IDENTITY / CONCEPT / LOCAL_REFERENCE /
GENERIC_GROUP, with `reference_basis` beneath LOCAL_REFERENCE
(ANTECEDENT_RESOLVED / DOCUMENT_CONSTITUTED / EXTERNAL_UNRESOLVED). A
single `graph_eligible()` authority governs canonical fact promotion.
Semantic architecture stays frozen: legacy_v1 production, no kimi_v1, no
semantic_v2, no new GLiNER labels, no lexical expansion, no recall
rescue. Precision closure first, recall second.

Binding attribution rules: do not manipulate admission to erase a
binding error; do not inflate recall to enlarge the precision
denominator; do not classify a mention by which answer removes an FP.

## Changes

### PHASE 0 — repair the admission qualification harness (DONE)

Non-semantic. **Zero production behaviour changed.** Three silent
defects, each of which independently invalidated admission measurement:

1. **Tested a fork, not production.** `qualify_admission.py` and
   `downstream_g4.py` imported `eval/admission/entity_admission.py`, a
   194-line frozen v1.1 snapshot, instead of the 228-line shipped module.
2. **Superseded gold.** It loaded `admission_gold.json` (44 items, v1),
   whose umbrella label `SCOPED` the policy has been unable to emit since
   v1.1 split it into CORPUS_SCOPED/DOCUMENT_SCOPED under identity
   contract v2 — so every scoped item scored WRONG. The matching 55-item
   `admission_gold_v1.1.json` existed and was never loaded.
3. **Destroyed its own evidence.** Every run unconditionally overwrote
   the committed `artifacts/admission_metrics.json`.

Net: the harness reported **0.773** for a policy that scores **1.000**,
while the committed artifact recorded 0.909 from an older contract —
three numbers, none reproducible.

Repair:

- **D1** both harnesses import `polymath_shared.entity_admission`. The
  fork carries a `HISTORICAL SNAPSHOT — DO NOT IMPORT` banner and is kept
  only to reproduce historical evidence byte-for-byte.
- **D2** default gold `admission_gold_v1.1.json`, overridable via
  `POLYMATH_ADMISSION_GOLD`. A gold whose labels the policy cannot emit is
  **refused with an explanation** rather than scored — a wrong number is
  worse than no number. Output records `gold_file`, `gold_version`,
  `policy_version`.
- **D3** artifact writes require `POLYMATH_WRITE_ARTIFACTS=1`; otherwise
  stdout only and committed evidence is untouched.

### PHASE 1 — ENTITY-HARBOR-V1 gold contract (DONE)

`eval/admission/admission_gold_v2.json`, 65 items. **v1 (44) and v1.1
(55) preserved byte-identical.**

Two axes, deliberately separable:
- `scope` carried forward UNCHANGED from v1.1, so the existing policy
  regression stays independently checkable.
- `anchor_kind` / `referentiality` / `reference_basis` are the NEW Harbor
  contract, present as SPECIFICATION. No policy implements them yet.

Annotation: IDENTITY 18 · GENERIC_GROUP 20 · LOCAL_REFERENCE 14 ·
CONCEPT 13. Ten items carry `context_document` (the seven REVISION 3a
cases plus three GENERIC_GROUP contrasts from the same corpus).

**Structural finding:** `reference_basis` CANNOT be determined from a
surface string — it requires document context. The 7 LOCAL_REFERENCE
items inherited from v1.1 (`the system`, `the model`, `the platform`,
`the real system`, `our recommendation engine`, `this service`,
`component D6L11`) are therefore marked `CONTEXT_REQUIRED` and assert no
basis. A surface-only gold cannot qualify the LOCAL_REFERENCE branch of
the contract; PHASE 2 needs context-bearing fixtures for it.

### PHASE 2 (scaffolding only) — ENTITY-HARBOR-V1 contract (DONE)

Authorized scope only. **No classifier was implemented** — REVISION 3b
withholds that authorization because PHASE 1 proved some Harbor decisions
are impossible from surface text alone.

- **Rename** `GENERIC_GROUP` -> `GENERIC`. Only some generics are groups;
  GENERIC names the epistemic category.
- **Seven rulings applied** to `admission_gold_v2.json`: `component D6L11`
  / `Model 3` / `Polymath retrieval system` -> IDENTITY;
  `the ingestion system` / `Qwen3 embedding model` -> CONTEXT_REQUIRED;
  `this service` / `our recommendation engine` -> LOCAL_REFERENCE with
  `reference_basis = CONTEXT_REQUIRED`.
- **`CONTEXT_REQUIRED` promoted to a first-class `anchor_kind`**, not
  merely a `reference_basis` value.
- **Structural evidence recorded, never decisive**
  (`named_anchor_present`, `identifier_present`, `determiner`,
  `multiword`). `Polymath retrieval system` and `Qwen3 embedding model`
  carry IDENTICAL structural evidence and receive DIFFERENT anchor kinds —
  pinned by test, so "proper token + concept head -> IDENTITY" cannot be
  encoded later.
- **`shared/polymath_shared/entity_harbor.py`**: `AnchorKind`,
  `Referentiality`, `ReferenceBasis`, `StructuralEvidence`,
  `HarborDecision`, and `graph_eligible()` as THE single eligibility
  authority (OPEN-2). `classify()` exists as an interface and **raises
  NotImplementedError**: shipping a guess is worse than shipping nothing.
- **`admission_context_fixtures_v1.json`**: 10 discourse fixtures
  covering all three reference bases, including three adversarial
  same-surface/opposite-outcome pairs (`The company` resolvable vs not;
  `Polymath retrieval system` vs `Qwen3 embedding model`).

### PHASE 2A — decision state separated from referent type (DONE)

`CONTEXT_REQUIRED` was a peer of IDENTITY/CONCEPT/LOCAL_REFERENCE/GENERIC,
which conflated *what kind of referent is this* with *do I have enough
evidence yet*. It made `CONTEXT_REQUIRED -> IDENTITY` look like a change of
entity type rather than the arrival of evidence. Corrected before any
production logic depended on the enum:

```
anchor_kind      IDENTITY | CONCEPT | LOCAL_REFERENCE | GENERIC | UNKNOWN
decision_status  RESOLVED | CONTEXT_REQUIRED | ABSTAINED
reference_basis  ANTECEDENT_RESOLVED | DOCUMENT_CONSTITUTED
                 | EXTERNAL_UNRESOLVED | AMBIGUOUS
```

`UNKNOWN` + `RESOLVED` is refused by the dataclass. `graph_eligible()`
returns False for anything not `RESOLVED`.

### PHASE 2B — DISCOURSE-REFERENCE-V1 (DONE)

`shared/polymath_shared/discourse_reference.py`. Not coreference: it
answers one question for a LOCAL_REFERENCE mention and records the
evidence that produced the answer.

Allowed evidence, all deterministic: E3 repeated named anchor · E4 exactly
one compatible local antecedent by shared head · **E4b type-noun head
naming exactly one admitted anchor of that core_type** · E5 event
nominalization with an unambiguous source event · E6 recurrence AND a
discriminating modifier.

Two defects were found by running the fixtures BEFORE trusting the code:

1. **E4 matched the target against itself.** A first-mention participant
   looked anaphoric, so `the engineering group` resolved to itself instead
   of being DOCUMENT_CONSTITUTED. Self-match now excluded.
2. **E6 was literally the forbidden "appears twice -> same entity"
   inference.** `The system` x3 and `the vendor` x2 were both promoted to
   DOCUMENT_CONSTITUTED. E6 now requires a head that is neither a generic
   head nor an external-party noun (`vendor`, `company`, `supplier`,
   `customer`, ...), plus a discriminating modifier. A party existing
   independently of the document cannot be constituted by it.

A third defect was in the **fixture**, not the code: ctx-01 asserted
`resolves_to = "QuickScale recommendation engine"`, a canonical surface
that never appears in the discourse. The resolver correctly returned the
existing admitted anchor `recommendation engine`. Inventing the fuller
name is the boundary-invention error REVISION 2 decision 9 forbids;
the fixture was corrected and a test now enforces that `resolves_to`
always names a surface that actually occurs.

Fixtures are now self-contained (`admitted_anchors` lives in the fixture,
not the test) so the qualification set cannot be reshaped by its harness.

### PHASE 2B.1 — policy pack freeze + E4b hardening (DONE)

**The tables are now policy DATA with an owner.**
`resources/discourse/discourse-reference-policy-v1.json` — versioned,
**sha256 hash-pinned** in the module, separate from executable logic,
every entry carrying a stated `purpose`. Drift raises rather than
silently changing behaviour. Owner: DISCOURSE-REFERENCE-V1 and its frozen
fixture suite. 21 type-noun entries, 12 external-party entries.

`type_noun` and `external_party` overlap deliberately — they answer
different questions. `company` is a type-noun (may anaphorically
reference a named Organization) AND an external-party noun (if
unresolved, never manufacture a document-constituted entity). Order:
resolve antecedence first; external_party applies only on failure.

**E4b was unsafe and is now an anaphoric resolver, not a type resolver.**
The counterexample: `Acme Systems negotiated with the company.` has
exactly one admitted Organization and must still not resolve — the
definite may denote an unnamed second party.

```
exact-one type match = NECESSARY SUPPORTING evidence
                     ≠ SUFFICIENT identity evidence
```

E4b now additionally requires: the candidate occurs in a STRICTLY PRIOR
sentence (a candidate sharing the target's sentence is a co-participant,
not an antecedent); and NO competing unnamed party was introduced by an
indefinite marker before the target. Otherwise AMBIGUOUS or
EXTERNAL_UNRESOLVED.

Of the four counterexamples, three already behaved correctly; only the
competing-unnamed-party case (`Acme hired a supplier. The company later
changed the specification.`) was wrong — it forced `Acme`. Now AMBIGUOUS.

Four adversarial fixtures added (ctx-11..14) using the required pattern:
**same surface, same type universe, opposite resolution.** ctx-11
resolves; ctx-12 and ctx-14 do not; ctx-13 abstains. That trio is the
structural protection against E4b decaying back into a type lookup.

### PHASE 2C — Harbor authority wiring + attribution (MEASUREMENT — STOP)

`canonical_fact_admissible()` added to `entity_harbor.py`. It calls the
SAME `graph_eligible()` contract that projection, census and the verifier
use; **no `graph_eligible` value is stored anywhere.** One authority, four
consumers.

Attribution harness: `eval/doc_audit/harbor_attribution.py`. Harbor
decisions built from QUALIFIED sources only — gold_v2 annotations where
they exist, DISCOURSE-REFERENCE-V1 on real document text for definite
descriptions, existing admission signals for surface-determinable cases,
and ABSTAIN for concept-dependent cases.

### Headline: the precision number is NOT a Harbor result

```
before   TP 12  FP 5   P 0.706
after    TP 11  FP 1   P 0.917

PRESERVED 12 · REMOVED_BY_HARBOR 1 · MASKED_ERROR 3 · NEW_LOSS 1
genuine Harbor removals: 1 of 5
```

Only `member_of(regional dispatchers -> west coast logistics consortium)`
was removed by a settled Harbor judgment (GENERIC, from a qualified gold
annotation). **Three removals are MASKED_ERROR** — the endpoint became
ineligible through ABSTENTION (UNKNOWN / CONTEXT_REQUIRED), not through a
Harbor decision. Per the phase contract these are NOT counted as
precision repairs, and P 0.917 must not be reported as a Harbor gain.

### STOP — integration defect (not a 2B qualification defect)

**Extracted spans carry no determiner; Harbor keys and the class-B
trigger both require one.**

```
gold key "the vision system"   ->  extracted surface "vision system"
gold key "the pump failure"    ->  extracted surface "pump failure"
gold key "the robotics vendor" ->  extracted surface "robotics vendor"
```

So the qualified discourse result is never consulted for ANY of them: the
gold lookup misses, the `startswith("the ")` class-B trigger does not
fire, and every one falls through to ABSTAIN. Consequences:

- `causes(pump failure -> production stoppage)` — **NEW_LOSS**, a
  protected definite. Both endpoints are DOCUMENT_CONSTITUTED in gold_v2
  and should have been eligible.
- `associated_with(crestline -> vision system)` — MASKED. `vision system`
  is DOCUMENT_CONSTITUTED in gold_v2 and should have stayed eligible,
  leaving the wrong-pair FP visible and **owned by binding**. Instead
  Harbor hid it for an unrelated reason — exactly the masking the phase
  contract warns against.
- `founded(crestline -> robotics vendor)` — right outcome, wrong reason.
  `robotics vendor` should be EXTERNAL_UNRESOLVED (a genuine Harbor
  removal); it abstained instead.
- `depends_on(mentor engine -> qbank item database)` — MASKED; this is a
  canonicalization case (contraction of `Mentor assessment engine`).

A second integration defect was found and fixed inside the harness
before any result was trusted: `entities.normalized_surface` is
lowercased while admission's proper-name signal is case-bearing
(`Oakland` -> GLOBAL, `oakland` -> MENTION_ONLY). Recomputing admission
from the normalized form demoted every proper noun and produced a first
run in which ALL 17 facts were lost. The harness now uses the STORED
`admission_class` and the raw case-bearing surface from `mentions`.

**Nothing was fixed in this phase.** Per the branch rule, the
determiner mismatch is an integration defect and PHASE 2D is not
authorized until it is resolved.

### PHASE 2C.1 — referential-span integration repair (DONE) + 2C rerun (STOP)

`shared/polymath_shared/referential_span.py`. Two surfaces are kept and
neither overwrites the other:

```
proposal_surface     exactly what GLiNER proposed — immutable provenance
referential_surface  deterministic syntactic envelope in the SOURCE TEXT
```

Expansion requires a spaCy noun chunk that CONTAINS the proposal AND whose
head token IS the proposal head. Not "grab the previous token": containment
plus head alignment is what stops the envelope wandering. No aligned chunk
means no expansion — fail closed. Determiners, demonstratives, possessives
and case are preserved, because `system` / `the system` / `this system` /
`our system` are not referentially equivalent and normalising them away
would undo PHASE 2B.

Verified against the required cases: `vision system` -> `the vision system`,
`pump failure` -> `The pump failure`, `service` -> `This service`,
`recommendation engine` -> `our recommendation engine`, with
`proposal_surface` unchanged in every case.

Two invariants pinned permanently in
`tests/determinism/test_referential_span_v1.py`: the envelope recovers
determiners; and admission/Harbor evidence is never recomputed from a
normalized surface (lowercasing DEMOTES every case-bearing signal —
`Oakland` GLOBAL -> `oakland` MENTION_ONLY, `Model 3` CORPUS_SCOPED ->
`model 3` MENTION_ONLY).

### 2C rerun — all three objectives met, one new defect exposed

| fact | before 2C.1 | after 2C.1 |
|---|---|---|
| `causes(pump failure -> production stoppage)` | NEW_LOSS | **PRESERVED** |
| `associated_with(crestline -> vision system)` | MASKED_ERROR | **PRESERVED** — binding defect now visible and owned by binding |
| `founded(crestline -> robotics vendor)` | MASKED_ERROR | **REMOVED_BY_HARBOR** — a legitimate Harbor precision improvement |
| `developed(crestline -> cobalt assembly cell)` | PRESERVED | MASKED_ERROR |
| `leads(maria kowalski -> Crestline automation team)` | PRESERVED | NEW_LOSS |
| `uses(corval logistics -> freightnet routing platform)` | PRESERVED | NEW_LOSS |
| `member_of(regional dispatchers -> ...)` | REMOVED_BY_HARBOR | MASKED_ERROR |

```
before   TP 12  FP 5   P 0.706
after    TP 10  FP 1   P 0.909
PRESERVED 11 · REMOVED_BY_HARBOR 1 · MASKED_ERROR 3 · NEW_LOSS 2
```

### STOP — new integration defect (single cause, four symptoms)

**A determiner-bearing PROPER NAME is being routed as a definite
description.** The attribution harness tests `startswith("the ")` BEFORE
testing identity signals, so once the envelope supplies the determiner
these all divert to the discourse consumer:

```
the FreightNet routing platform    admission = GLOBAL / proper_name_identity
the Crestline automation team      admission = GLOBAL / proper_name_identity
the Cobalt assembly cell           admission = GLOBAL / proper_name_identity
the West Coast logistics consortium admission = GLOBAL / proper_name_identity
```

Inside the consumer, E3 then reports `multiple named anchors match`
(`Crestline automation team` matches both `Crestline` and
`Crestline Automation`) and abstains. Every one of the four regressions
has this single cause. Contrast the genuine definite descriptions, which
route correctly:

```
the vision system   admission = CORPUS_SCOPED / discriminative_descriptive_reference
the pump failure    admission = CORPUS_SCOPED / discriminative_descriptive_reference
```

The fix is class-A-before-class-B routing precedence in the harness —
identity signals must be tested before the definite-description trigger.
Per the phase contract (**NO RULE CHANGES AFTER SEEING THE RESULT**) this
was NOT applied. PHASE 2D remains blocked.

### PHASE 2C.2 — routing precedence repair (DONE) + 2C rerun

Identity is now evaluated on the RAW case-preserving `proposal_surface`
BEFORE the determiner-bearing envelope is inspected, so envelope recovery
cannot demote an already-qualified identity-bearing mention.

The predicate is the EXISTING frozen admission identity rule — reasons
`acronym_identity` / `versioned_identity_structure` /
`proper_name_identity`. Deliberately NOT `named_anchor_present`, which
REVISION 3b defined as structural evidence and explicitly not authority;
using it would make "proper token somewhere in the envelope -> IDENTITY"
and reopen the Qwen3 problem. No signal added or widened.

Routing precedence:

```
1. qualified gold_v2 annotation / explicit REVISION 3b ruling
2. decisive identity evidence on the raw proposal_surface
3. definite/deictic/possessive envelope -> DISCOURSE-REFERENCE-V1
4. bare or generic -> GENERIC
5. otherwise ABSTAIN (concept status is PHASE 2D)
```

Step 1 outranks step 2 by design. `Qwen3 embedding model` SATISFIES the
identity predicate (`versioned_identity_structure`), so without that
precedence identity-first routing would silently overturn the REVISION 3b
CONTEXT_REQUIRED ruling. Pinned as the adversarial regression.

### 2C rerun — the four questions

```
before   TP 12  FP 5   P 0.706
after    TP 12  FP 2   P 0.857
PRESERVED 14 · REMOVED_BY_HARBOR 2 · MASKED_ERROR 1 · NEW_LOSS 0
```

1. **Identity regressions restored — yes.** All four
   (`FreightNet routing platform`, `Crestline automation team`,
   `Cobalt assembly cell`, `West Coast logistics consortium`) route as
   IDENTITY via `identity on proposal: proper_name_identity`, with the
   envelope retained as context. **Zero NEW_LOSS; TP back to 12.**
2. **`associated_with(crestline -> vision system)` still visible — yes.**
   PRESERVED. Harbor does not own it; the wrong-pair binding defect
   remains attributable to binding.
3. **`founded(crestline -> robotics vendor)` still legitimately
   REMOVED_BY_HARBOR — yes**, object ruled EXTERNAL_UNRESOLVED.
   `member_of(regional dispatchers -> ...)` is also REMOVED_BY_HARBOR
   (subject GENERIC). Two genuine removals of three.
4. **One MASKED_ERROR remains**: `depends_on(mentor engine -> qbank item
   database)`. Branch: subject `mentor engine` entered the discourse
   consumer and abstained on `E3 multiple named anchors match`. This fact
   is a canonicalization case (contraction of `Mentor assessment engine`)
   — Harbor does not own it, and its removal must not be credited as a
   precision repair.

**P 0.857 is the trustworthy figure**: TP unchanged at 12, and both FP
removals are attributable to executed Harbor judgments.

An unrelated defect surfaced and was fixed: the new test inserted
`eval/doc_audit` on `sys.path`, shadowing the `harness` module the Q1
qualification regression imports and failing two unrelated contract
tests. Several `eval/*` directories contain a module named `harness.py`;
the test now loads by explicit file path. Production was never affected.

### PHASE 2D — CONCEPT-EVIDENCE-V1, cross-domain (DONE)

`shared/polymath_shared/concept_evidence.py`. Two layers, evidence world
kept separate from truth world:

```
2D.1 concept_candidate()  "could this denote a reusable concept?"
                          permissive, NO graph authority
2D.2 admit_concept()      "is there AUDITABLE evidence?" -> CONCEPT | ABSTAIN
```

Authorities, any one sufficient: **DOCUMENT_DEFINED** (the document
establishes the term) · **GLOSSARY_DECLARED** (glossary / terminology /
definition list) · **EXISTING_CANONICAL** (admitted earlier under a valid
chain) · **CURATED_LEXICON** (exact entry in a versioned auditable
vocabulary, carrying `source_id` + `source_version`).

Supporting evidence only, never sufficient: multiword form, frequency,
corpus uniqueness, capitalization, provider confidence, technical-looking
morphology.

**The definitional patterns are properties of English exposition, not of
any subject matter** — genus-differentia copula (requiring an article, so
"X is slow" is not a definition while "X is the process by which..." is),
"refers to", "is defined as", "means/denotes", appositive. That is why the
same patterns fire on a pattern catalogue, a physiology text and a novel.

### Cross-domain acceptance: 16/16

| domain | admitted | abstained |
|---|---|---|
| technical | `transactional outbox`, `write-ahead log` (DOCUMENT_DEFINED) | `message broker`, `the system` |
| medical | `acute respiratory distress syndrome`, `photosynthesis` (DOCUMENT_DEFINED) | `oxygen saturation` |
| narrative | `the Ember Rite`, `Soulbinding` (DOCUMENT_DEFINED) | `the old bridge` |
| business | `chargeback`, `run rate` (GLOSSARY_DECLARED) | `the committee` |

`the Ember Rite` is the load-bearing case: vocabulary the engine has never
seen, no lexicon, no registry — admitted purely because the book defines
it. A whitelist tuned to the current corpus would fail all four domains.

Three adversarial forbidden-shortcut cases all abstain: `vector index`
(two technical-looking words), `retrieval system` (twelve occurrences),
`quality database` (present in the evaluation corpus but never defined).

A test strips docstrings and asserts **no domain phrase appears in
executable policy** — the illustrative examples in prose are not a lookup
table.

### Measurement on I4

```
endpoints currently abstaining on concept status : 0
concept promotions on I4                         : 0
false concept promotions                         : 0
```

I4 is a business-brief corpus with no definitional sentences and no
glossary, so CONCEPT admission correctly changes NOTHING there — while
the same unchanged engine admits 10 concepts across the four cross-domain
fixtures. That is the invariant working: **unknown knowledge reduces graph
COVERAGE, never graph CORRECTNESS.**

### REAL-BOOK PROBES — cross-domain identity defect found

Two genuinely different registers, run through the unchanged stack:
a spoken transcript (`04_transcript_local_rag_build.md`) and an academic
psychology text (`01_psychology_working_memory.md`).

`entity-admission-v1.1` — which scores 55/55 on its own gold — promoted
ordinary prose to GLOBAL identity in both:

```
transcript   I · That · What · We · It · Workers · Retrieval ·
             Earlier versions · Two documents · Every accepted fact ·
             two John Smith                                   (16 admissions)
psychology   Researchers · One influential account · These findings ·
             Several laboratory studies · Worked examples ·
             Performance · This · When attention shifts        (12 admissions)
```

`When attention shifts` is a subordinate CLAUSE. ~69% of identity
admissions were false. The 55-item gold is technical noun phrases from one
self-referential corpus: no pronoun, no wh-word, no sentence-initial
quantifier, no clause. Conversational and academic register were never
exercised. Ledger rows 38-40.

### IDENTITY-PRECISION-V2 (DONE)

`shared/polymath_shared/identity_evidence.py`. Conceptual correction:

```
capitalization is NEVER sufficient identity evidence
IDENTITY requires POSITIVE evidence, not the absence of generic evidence
```

The mechanism is SYNTACTIC, never a phrase blacklist — a larger
`GENERIC_HEAD` would be defeated by the next book's fifty new nouns.
spaCy POS separates sentence-initial `Postgres/PROPN` from sentence-initial
`Researchers/NOUN` for any document, and `syntax-evidence-v1` is already
qualified.

Structural exclusions, applied before any positive test: non-nominal head
(PRON/DET/SCONJ/VERB/AUX...) · pronoun anywhere · bare determiner ·
leading quantifier or NUM. Positive evidence, closed set: PROPER_NAME
(POS=PROPN anchor) · ACRONYM · IDENTIFIER · ESTABLISHED_ALIAS (exact).

`two John Smith` is rejected by the quantifier rule while `John Smith` is
admitted — a quantified named surface does not inherit singular identity.

### Gate result

```
cross-register fixtures      31/31
false IDENTITY admissions    0
legitimate identities lost   0
clause -> identity           0
pronoun/WH -> identity       0
quantified NP -> identity    0
deterministic (20 replays)   byte-identical
frozen 55-item regression    55/55 (production decide() untouched)
```

All four adversarial pairs diverge on the anchor, not the register:
`Workers` / `Workers United` · `Researchers` / `Researcher Technologies` ·
`two documents` / `Document D6L11` ·
`When attention shifts` / `Attention Shift Protocol`.

### Rerun of the two real documents

| document | v1.1 | v2 | removed | lost |
|---|---|---|---|---|
| transcript | 16 | **5** | 11 | 0 |
| psychology | 12 | **0** | 12 | 0 |

Every real technical entity survives (`Postgres`, `Qdrant`, `Neo4j`,
`GLiNER`). **27 of 28 false admissions removed.**

One residual: `Exact` in the transcript. spaCy tags the sentence-initial
adjective in *"Exact normalized names ... are relatively safe"* as PROPN,
so the predicate honours it. This is a tagger error, not a rule error —
recorded rather than special-cased, because adding `exact` to a list is
exactly the blacklist approach this gate rejects.

**The psychology result also unblocks the concept lane**: `Working
memory`, `Cognitive load` and `Sleep deprivation` were previously stolen
by identity-first routing and now proceed to CONCEPT evaluation, as
predicted.

### CONCEPT-DEFINITION-COVERAGE-V1 (DONE)

Authority unchanged — still `DOCUMENT_DEFINED`. Only the GRAMMATICAL
realization of an explicit definition broadens, because academic prose
rarely writes "X is a Y"; it hedges.

Added forms:

```
hedged copula      X is often described as the Y
                   X can be defined as a Y
                   X is generally understood as the Y
                   X has been characterized as the Y
author-declared    We define X as ...   |   By X we mean ...
alias declaration  X, also known as Y, ...
eventive           X occurs when ...
classificatory     X is another condition that ...
```

The hedge slot admits up to three adverbs before a closed set of
definitional participles (`described`, `defined`, `understood`, `known`,
`characterized`, `conceived`, `regarded`, `viewed`, `treated`,
`referred to`), and **still requires an article before the genus noun**.
That requirement is what separates definition from predication, so
`X is widely used` and `X is known to fail` remain non-definitions.

`another` was added to the genus-determiner set as a classificatory
variant (`Sleep deprivation is another condition that...`). `some` and
`any` were deliberately NOT added — they hedge existence rather than
assign a genus, and `X is some component` / `X is any process` must stay
non-definitions.

### Rerun of the two real documents

| document | before | after |
|---|---|---|
| psychology | 0 concepts | **`working memory`**, **`sleep deprivation`** (DOCUMENT_DEFINED) |
| transcript | 0 concepts | 0 concepts |

`working memory` is admitted on the document's own sentence: *"Working
memory is often described as the limited mental workspace used to hold and
manipulate information."*

Still abstaining, correctly: `cognitive load` (the document states its
effects, never defines it), `long-term memory` (mentioned only in
contrast), `central control process` (a negative claim about it),
`performance`.

**The transcript admitting zero concepts is the right result, not a
failure** — it is a conversation between people who already know the
vocabulary, and it defines none of its terms. Coverage tracks what the
document actually establishes.

### PHASE 3 — CONTRACTION-RESOLUTION-V1 (measured, DECISION REQUIRED)

`shared/polymath_shared/contraction_resolution.py`. Deterministic
in-document contraction only. No RapidFuzz, no GLinker, no embeddings —
two demonstrated failures do not justify them.

Two shapes, both by EXACT TOKEN identity, never character similarity:

```
A anchor prefix        Crestline      -> Crestline Automation
B head-preserving      Mentor engine  -> Mentor assessment engine
  elision              Cobalt cell    -> Cobalt assembly cell
                       Coachlight app -> Coachlight review app
```

Shapes B found two instances beyond the two target cases, which is
evidence the rule generalizes rather than fitting the failures.

The defining negative holds: `Crestline` vs `Crestview Automation` is very
similar as a STRING and shares no TOKEN -> ABSTAIN. Ambiguity abstains.
Incompatible type abstains. A bare shared head (`engine`) abstains.

### Both target FPs convert — but a TP regressed

```
developed(crestline -> cobalt assembly cell)         FP -> TP
depends_on(mentor engine -> qbank item database)     FP -> TP
depends_on(careconnect portal -> carechart emr)      TP -> FP   <-- regression
```

`founded(crestline -> robotics vendor)` and
`associated_with(crestline -> vision system)` correctly stay FP: Harbor
owns the first (EXTERNAL_UNRESOLVED) and binding owns the second.

### The regression exposes a real limit: label direction is undecidable

**Sameness resolution is correct in all five cases.** What is NOT
determinable from in-document evidence is which surface should be the
canonical LABEL. The frozen gold canonicalizes in OPPOSITE directions for
identical grammatical shapes:

```
CareChart/PROPN EMR/PROPN platform/NOUN      -> gold keeps "CareChart EMR"          (drops the NOUN)
FreightNet/PROPN routing/NOUN platform/NOUN  -> gold keeps the whole phrase          (keeps the NOUNs)
```

POS does not separate them. Neither does length, determiner or position.
The gold author made a judgement call, and **no deterministic in-document
signal reproduces it**. A rule that recovered both would be tuned to the
evaluation, which the governing rules forbid.

### Four labelling policies, measured

| policy | TP | FP | P |
|---|---|---|---|
| A. no contraction resolution (baseline) | 12 | 5 | 0.706 |
| B. merge nodes, never rewrite fact surfaces | 12 | 5 | 0.706 |
| C. rewrite toward the LONGER form | **13** | **4** | **0.765** |
| D. rewrite toward the SHORTER form | 12 | 5 | 0.706 |

B is architecturally the most honest — it fixes the duplicate-node defect
(which is what was actually demonstrated) and leaves fact surfaces alone —
but the I4 scorer matches on surface, so it registers no change.

C scores best and is defensible for the two demonstrated cases, at the
cost of one gold-disagreeing rewrite.

**STOP for decision. Nothing wired.** Choosing C purely because it scores
higher would be selecting a labelling policy from the evaluation.

### PHASE 3 SETTLEMENT — policy B promoted (DONE)

Identity resolution merges **canonical identity only**. It never rewrites
a mention or fact surface to select a preferred label. Original surfaces
remain immutable provenance; `canonical_id` is what the graph joins on.

Policy C (rewrite toward the longer form) scored better — 0.765 vs 0.706 —
and was **REJECTED**. `CareChart EMR` / `CareChart EMR platform` is a
proven counterexample to "longer is canonical", so C had no semantic
justification and adopting it would have beenselecting a labelling policy
from the evaluation score.

`build_memberships()` returns a `CanonicalMembership` per admitted
surface: every surface retained, contracted forms joined to the anchor's
canonical id, basis recorded. Nothing is rewritten and nothing dropped.

### Two coexisting metrics

The frozen surface scorer and its artifacts are UNTOUCHED and not
retroactively called wrong. A separately versioned diagnostic supplements
it: `eval/doc_audit/i4_identity_score.py`
(`i4-canonical-identity-score-v1`).

```
SURFACE   TP 12  FP 5  P 0.706  R 0.462    historical, frozen, unchanged
IDENTITY  TP 14  FP 3  P 0.824  R 0.538    graph-semantic
```

The two assertions the graph gets right but surface matching scores wrong
are exactly the two demonstrated identity defects:

```
developed(crestline -> cobalt assembly cell)
depends_on(mentor engine -> qbank item database)
```

### Generalization evidence

7 canonical clusters formed, **5 beyond the two motivating cases**:

```
carechart emr        + carechart emr platform
nimbus               + nimbus cloud
cobalt cell          + cobalt assembly cell
crestline            + crestline automation      <- demonstrated
coachlight app       + coachlight review app
mentor engine        + mentor assessment engine  <- demonstrated
freightnet           + freightnet routing platform
```

The same two token-structural shapes found all seven. No RapidFuzz, no
GLinker, no similarity scoring.

### Residual FPs, all attributed

```
founded(crestline -> robotics vendor)                HARBOR   EXTERNAL_UNRESOLVED
member_of(regional dispatchers -> west coast ...)    HARBOR   GENERIC
associated_with(crestline -> vision system)          BINDING  wrong pair
```

**Zero unattributed FPs.** The two Harbor-owned ones are already removed
by the qualified Harbor stack once wired; the binding-owned one is the
single candidate for a narrow first-loss gate, and only after wiring
proves it survives.

### S1 — BLAST-RADIUS-V1 (READ ONLY, DONE)

`eval/doc_audit/blast_radius_v1.py`. Current v1.1 interpretation compared
against the fully qualified V2 stack over the entire persisted corpus. No
writes, no migrations, no rule changes.

```
MENTIONS (69)      unchanged 42 · scope changed 21 · newly ineligible 19
                   newly eligible 1 · abstained 8 · missing syntax 0
                   kinds: IDENTITY 40 · LOCAL_REFERENCE 21 · UNKNOWN 8

ENTITIES           admitted v1.1 65 -> v2 47   (18 demotions)
                   canonical entities 39 · merged clusters 7

FACTS (17)         ALL fact_ids change — endpoint ids are admission-derived

DOCUMENTS          5 of 5 require semantic reprocessing

PROJECTIONS        Neo4j  ALL stale (entity + fact ids change)
                   Qdrant UNAFFECTED — chunk-keyed, not entity-keyed
                   receipts re-derived on reprocess
```

### The decisive operational finding

**GLiNER does not need to re-run.** Every reconstruction input is
persisted and complete:

```
raw case-preserving surface   69/69
exact offsets                 69/69
core_type                     69/69
provider score                69/69
chunk_id                      69/69
source chunk text             present
syntax                        NOT persisted -> regenerate, deterministic
                              under the pinned spaCy model
```

So the rederive boundary sits **downstream of provider inference**:

```
persisted mentions + chunk text
  -> regenerate syntax (pinned model, deterministic)
  -> V2 stack -> new entities/facts
  -> rebuild Neo4j + canonical projections
```

This is a semantic reprocessing run, not an ingest from original files.

**Qdrant being unaffected also satisfies wiring invariant 6 structurally**:
text retrieval is chunk-keyed and survives the migration untouched, so
admission churn cannot degrade retrieval.

### Known imprecision in this report

The FACT section matches endpoints by lowercase SURFACE across all
decisions rather than per-document entity id, because v2 entity ids do not
exist until S2 adds the columns. `endpoints still eligible 10 / removed 7`
is therefore INDICATIVE, not exact. Mention- and entity-level counts are
exact. A precise fact-level delta requires S2.

**STOP after report**, per the S1 authorization.

### S2 — SEMANTIC CONTRACT MIGRATION + PINNING (DONE, capacity only)

**Zero production semantic behaviour changed.**

#### Migration 0015

Eight nullable columns on `mentions`, two on `runs`. **No backfill.**
Historical v1.1 rows remain historical v1.1 evidence until S5 rederives
them — verified: 0 of 69 rows populated after apply.

```
proposal_surface     raw provider evidence (case-bearing)
referential_surface  source-faithful discourse envelope
anchor_kind · decision_status · reference_basis · admission_reason
canonical_entity_id  nullable — resolving to no canonical entity is normal
semantic_contract    NULL == historical v1.1
runs.semantic_contract + runs.semantic_bundle_sha256
```

Inferring `anchor_kind` from `normalized_surface` would have been exactly
the normalized-surface classification the contract forbids, and would
fabricate provenance for decisions never made. A test asserts the
migration contains no `UPDATE`.

**No `graph_eligible` column** — eligibility keeps its single derived
authority (wiring invariant 3). Its absence is documented in the migration
rather than silent.

#### Semantic authority bundle

`execution.semantic_authorities()` pins **14 authorities** — everything
capable of changing mention interpretation, entity identity, graph
eligibility, canonical membership or fact identity:

```
identity-precision-v2 · entity-harbor-v1 · referential-span-v1 ·
discourse-reference-v1 + policy sha256 · concept-evidence-v1 ·
contraction-resolution-v1 · graph-eligibility · canonical-fact-gate ·
syntax contract / provider / model
```

`semantic_bundle_sha256()` hashes the whole surface; a test proves the
hash moves when any single authority changes, and is otherwise
deterministic across 20 calls.

The syntax MODEL is pinned now (`en_core_web_sm@3.8.0`) precisely so
reprocessing is deterministic: old rows parsed with model X and new rows
with model Y under one execution contract would defeat replay. The
provider remains `disabled` — S2 records the dependency, S3 makes it
operational.

Historical and V2 contracts stay distinguishable
(`admission-v1.1` vs `admission-harbor-v2`); old execution contracts are
never rewritten to claim V2.

#### Acceptance

11 tests in `test_semantic_contract_v2_migration.py` assert the
no-behaviour-change property as hard as the new capacity: production
admission untouched and still 55/55, no backfill, all new columns
nullable, no `graph_eligible` column, no INSERT/DELETE/DROP, bundle-hash
sensitivity and determinism, contract distinguishability, syntax pinned
but not live.

### S3 — V2 SYNTAX READINESS CONTRACT (DONE)

`syntax-evidence-v1` is now a HARD runtime prerequisite for every
`admission-harbor-v2` interpretation. No semantic rules changed.

Three layers, because they protect against different failures — and
because a health check cannot eliminate TOCTOU, so C is required even
with B:

```
A RUN PREFLIGHT       check_run_configuration()   impossible configuration
B CLAIM ELIGIBILITY   claim_eligible() wired into compatible()
C EXECUTION ASSERTION assert_syntax_available()   race after claim
D DEGRADED PATH       physically unreachable under V2
```

#### Two failure classes, never conflated

```
INCOMPATIBLE_RUN_CONFIGURATION    V2 requested, syntax disabled/mismatched.
                                  No retry fixes it; never enqueue work.
RETRYABLE_DEPENDENCY_UNAVAILABLE  V2 correct, sidecar down.
                                  Pending until capability returns.
```

A test asserts neither is a subclass of the other, so an operator cannot
accidentally retry a configuration error forever.

#### B is the primary dynamic gate

`compatible()` — the existing lease-time check — now refuses a V2 ticket
unless the worker's CURRENT, FRESH capability satisfies the run's pinned
syntax contract and model. Capability is probed at most every 15s and
goes stale after 60s. Tickets stay PENDING rather than being claimed and
repeatedly released. Contracts carrying no `semantic_contract` are
entirely unaffected — verified.

No new pipeline stage was created. `_allocate()` already receives the
`SentenceSlice`, so the dependency is expressed to the CONTROL PLANE while
the semantic pipeline keeps its shape.

#### THE INVARIANT, pinned

> A failed required dependency may INTERRUPT a run. It may NEVER alter its
> semantics.

```
"Researchers generally distinguish..."

healthy syntax  -> is_identity = False          (GENERIC)
syntax outage   -> RETRYABLE_DEPENDENCY_UNAVAILABLE   (NO DECISION)
NEVER           -> GLOBAL
```

`identity_evidence(..., require_syntax=True)` RAISES rather than returning
capitalization-based evidence. The degraded path survives only for
surface-only historical evaluation — the frozen 55-item gold has no syntax
and must still evaluate — and is unreachable from any V2 decision.

#### Acceptance

17 tests in `test_syntax_readiness_v3.py`: preflight rejects disabled
provider / wrong contract / unpinned model and accepts a valid V2 config ·
historical v1.1 carries no dependency · healthy capability claimable ·
unhealthy, stale, model-mismatched and unregistered all leave the ticket
pending · the claim gate is genuinely wired into `compatible()` · post-claim
death is retryable · the two failure classes are distinct · the pinned
production defect cannot recur · V2 never reaches the capitalization
fallback.

### S4 (part 1) — single admission authority built; CUTOVER NOT PERFORMED

`shared/polymath_shared/admission_interpreter.py`:

```
interpret_admission(contract_version=...)
    admission-harbor-v2  -> qualified V2 stack   (current ingestion)
    admission-v1.1       -> historical replay ONLY
    anything else        -> UnknownAdmissionContract
```

No fallback exists. `entity_admission.decide` is renamed
`decide_v1_1_historical`; the old name survives only as an explicitly
documented historical alias, because a generic `decide()` that secretly
means "old semantics" is how a future caller reaches for it from
production.

Verified composition (real spaCy):

```
Postgres              IDENTITY         eligible      (POS=PROPN, not capitalization)
Researchers           not IDENTITY     not eligible
regional dispatchers  not IDENTITY     not eligible
the vision system     LOCAL_REFERENCE  not eligible
v1.1 historical       GLOBAL           eligible      <- intentional disagreement
```

The v1.1/V2 disagreement is pinned as a TEST, not a defect: backward
equivalence is an explicit non-goal.

### COMPOSITION GAP FOUND — reported, not patched

The qualified components do not compose to produce **GENERIC**:

```
Researchers          -> UNKNOWN / CONTEXT_REQUIRED   (contract says GENERIC)
regional dispatchers -> LOCAL_REFERENCE              (gold_v2 says GENERIC)
```

`identity_evidence()` correctly REFUSES both, but nothing downstream
assigns GENERIC. Today GENERIC comes only from (a) the 32-word
`GENERIC_HEAD` single-token check — the very list the identity gate
deliberately avoided depending on — or (b) a hand annotation in gold_v2,
which production does not have.

**Graph truth is unaffected**: UNKNOWN, LOCAL_REFERENCE/EXTERNAL_UNRESOLVED
and GENERIC are all non-eligible, so every one of these is correctly
refused. What is wrong is the RECORDED anchor_kind, which matters for
attribution honesty and for anything downstream reasoning about kind.

Assigning GENERIC would be a new classification rule, which S4 explicitly
forbids. **Reported for authorization, not invented.**

### Cutover status

The five inline call sites are UNCHANGED and still reach v1.1:

```
extract_worker.py  allocate_entity_id x2 · decide x1
candidates.py      decide x1 · allocate_entity_id x1
```

`test_cutover_is_not_yet_performed_and_the_remaining_sites_are_known`
documents that exact surface and fails if it drifts, rather than passing
silently. It becomes the no-production-callers assertion once the cutover
lands.

### GENERIC-CLASSIFICATION-V1 (DONE) — attribution gate, closes the S4 composition gap

`shared/polymath_shared/generic_classification.py`. Corrects the system's
EXPLANATION, not its behaviour.

```
before   Researchers -> UNKNOWN            -> not eligible
after    Researchers -> GENERIC            -> not eligible
```

Structural, never a noun blacklist — a test parses the module, strips
docstrings and asserts none of `researcher`, `dispatcher`, `worker`,
`server`, `database`, `study`, `finding`, `document` appears in executable
policy. Four evidence families: PLURAL_COMMON_NOUN · QUANTIFIED_PHRASE ·
BARE_KIND_TERM · GENERIC_DETERMINER.

Plurality is derived deterministically from the pinned tagger — a NOUN
whose surface differs from its lemma is inflected — so no hand list of
plural forms is needed and the rule behaves identically on a psychology
text and a cybersecurity manual.

#### Precedence

```
IDENTITY  >  LOCAL_REFERENCE(resolved | document-constituted)  >  CONCEPT  >  GENERIC  >  UNKNOWN
```

GENERIC is reached only after the others decline, so it can never override
an established interpretation. One refinement: a LOCAL_REFERENCE whose
basis is EXTERNAL_UNRESOLVED or AMBIGUOUS establishes NOTHING, so a plural
class expression may still be attributed GENERIC there — `The regional
dispatchers` is a population, not a withheld particular party. A
DOCUMENT_CONSTITUTED or ANTECEDENT_RESOLVED reference is protected
absolutely.

#### End-to-end through the production interpreter

```
Researchers            GENERIC           not eligible
regional dispatchers   GENERIC           not eligible
Postgres               IDENTITY          eligible
the engineering group  LOCAL_REFERENCE   eligible     (document-constituted)
Working memory         CONCEPT           eligible     (DOCUMENT_DEFINED)
the vision system      LOCAL_REFERENCE   not eligible
```

**Zero graph-eligibility changes** for the motivating cases: `Researchers`
and `regional dispatchers` were refused before and are refused now. Zero
IDENTITY, CONCEPT or DOCUMENT_CONSTITUTED losses.

#### Known limitation, recorded not patched

spaCy tags `PostgreSQL` as **ADV** in `PostgreSQL databases`, so no
proper-noun anchor is visible in the span and the phrase reads as a plural
common noun. The `has_identity_anchor` parameter exists for exactly this:
when the caller knows `PostgreSQL` is an admitted entity, the span is
protected. Pinned as a test in both directions. Same class as the
`Exact/PROPN` case — the gate honours its evidence source, and the source
is occasionally wrong.

### E4 BOUNDARY REPAIR (DONE) — from a real-document probe

`03_research_notes_sleep_and_attention.md` (research notes, heavy hedging,
zero proper nouns) exposed a CONFIDENT WRONG resolution — the failure mode
DISCOURSE-REFERENCE-V1 explicitly forbids:

```
the second group  ->  ANTECEDENT_RESOLVED
                  ->  'recurring methodological issue is that sleep
                       restriction studies often compare group'
```

A 12-word fragment spanning most of a sentence. E4's regex allowed SPACES
in its non-greedy span, so it crossed verbs and clause boundaries hunting
for the head word. All 14 frozen fixtures passed because none contained a
head word appearing mid-clause after an indefinite article.

Repair, as authorized: candidates now come from **bounded spaCy noun
chunks** — one NP each, no finite verb inside, max 6 tokens, matching
nominal head. The regex survives only as a tight fallback (max 3 tokens)
when syntax is absent, never as the authority. The interpreter now passes
`discourse_syntax` through so production takes the authoritative path.

#### Resolution does not manufacture identity

Second half of the authorization, and the more important half.
`HarborDecision.resolved_anchor_eligible` was added and
`graph_eligible()` now INHERITS it for ANTECEDENT_RESOLVED: resolving
`the second group` to a generic population such as `others` yields no
canonical entity. Correct anaphora and graph eligibility are separate
questions.

#### Result

```
fabricated antecedent      eliminated
14/14 frozen fixtures      green
research-notes document    138 candidates, 1 eligible (unchanged, no increase)
0 confident wrong resolutions
deterministic
```

#### Remaining, NOT patched (ledger row 43)

After the repair `the second group` falls through to E6 and is judged
DOCUMENT_CONSTITUTED, so it stays eligible. An ORDINAL modifier partitions
a set — it does not name a bounded actor the way `the engineering group`
does — but E6 requires only "recurs + discriminating modifier", which an
ordinal satisfies. Changing E6 exceeds the authorized boundary repair, so
it is reported rather than fixed.

#### What the document got right

Zero IDENTITY (it contains no proper nouns) and zero CONCEPT (it discusses
`sustained attention`, `working-memory updating`, `subjective fatigue`,
`psychomotor vigilance tasks` without defining any of them — there is not
one genus-differentia sentence in the file). Abstaining preserved
correctness at the cost of coverage, exactly as the cross-domain invariant
requires.

### SET-PARTITION-REFERENCE-V1 (DONE) — closes ledger row 43

E6's "recurs + discriminating modifier" was too broad: an ordinal IS
discriminating but is NOT identity-bearing.

```
the engineering group  one bounded collective actor      -> DOCUMENT_CONSTITUTED
the second group       partition of an introduced set    -> LOCAL_REFERENCE, noncanonical
```

**E6 is guarded, not weakened** — it still serves `the engineering group`,
`the analytics team`, `the review board`. A check runs BEFORE it.

Detection is structural, no `if modifier == "second"`. spaCy tags
`second`/`2nd` as ADJ but `engineering` as NOUN, so the shape alone
separates them and **no head-noun list is needed** — the rule generalizes
to `the third cohort`, `the latter case`, and anything else of that form.
Ordinals are a genuinely CLOSED grammatical class in English, unlike
nouns, so enumerating them is policy data of the same kind as the
determiner and quantifier sets; a test asserts no NOUN appears in that set.

No new Harbor anchor kind. The attribution rides as a reason —
`ordinal_set_partition` — on the existing LOCAL_REFERENCE.

An identity anchor outranks the guard: a PROPN in the span disables it.

#### Result on the research-notes document

```
138 candidates
  0 IDENTITY        (no proper nouns in the file)
  0 CONCEPT         (constructs discussed, none defined)
  0 GRAPH-ELIGIBLE
GENERIC 91 · UNKNOWN 37 · LOCAL_REFERENCE 10
```

Not because the system blindly rejects everything — 91 mentions carry a
positive GENERIC attribution and 10 are recognised as local references —
but because **no mention in this document earns durable identity or
concept authority**. That is the correct reading of the file.

14/14 discourse fixtures green, all Harbor tests green, suite 489.

## Proof

- Trustworthy baseline through production imports:
  **entity-admission-v1.1 = 55/55 = 1.000** on `admission_gold_v1.1.json`.
- Superseded gold now raises instead of reporting 0.773.
- `eval/admission/artifacts/` clean after repeated runs (`git status`).
- 6 new tests in `tests/determinism/test_admission_harness_integrity.py`
  pin: production imports in both harnesses, the DO-NOT-IMPORT banner,
  gold/policy label-vocabulary agreement, the 55/55 baseline, refusal of
  superseded gold, artifact opt-in.
- Suite **489 passed / 53 skipped** (was 322). `make guards` ok.
- PHASE 3 settlement: 4 further tests pin that surfaces are immutable, that
  merged forms share one canonical id, that no admitted surface is dropped,
  and that label selection is NOT part of identity resolution.
- `eval/i4/verify_i4.py`, `eval/i4/gold/` and `eval/admission/artifacts/`
  verified untouched by `git status`.
- PHASE 3: 10 tests pin both contraction shapes, the similarity-vs-containment
  negative, ambiguity/type/bare-head abstention, never-synthesise, mention
  preservation, evidence recording and determinism.
- CONCEPT-DEFINITION-COVERAGE-V1: 5 further tests pin the hedged forms, the
  author-declared/eventive/alias forms, the classificatory determiner, that
  broadened grammar admits no non-definitions, and both real documents.
- IDENTITY-PRECISION-V2: 16 tests in `test_identity_precision_v2.py` pin
  every defect class, the positive-evidence families, determinism,
  evidence recording, and that no qualification surface leaks into
  executable policy.
- PHASE 2D: 13 tests in `test_concept_evidence_v1.py` pin cross-domain
  acceptance (16/16 over four unrelated domains), the forbidden shortcuts
  (two-words, frequency), exact-not-fuzzy lexicon matching, registry
  auditability, candidacy-has-no-authority, deterministic replay, and the
  no-domain-phrase-in-executable-policy invariant.
- PHASE 2C: attribution recorded per fact in
  `eval/doc_audit/harbor_attribution.json` with old endpoint state, new
  anchor_kind / decision_status / reference_basis / scope, per-endpoint
  eligibility, retention, classification and reason.
- PHASE 2B.1 gate rerun: **10/10 LOCAL_REFERENCE context fixtures** correct;
  **0 confident wrong resolutions** (a wrong ANTECEDENT_RESOLVED fabricates
  identity and is treated as the worst failure mode); AMBIGUOUS abstains and
  is never graph-eligible; **byte-identical across 20 identical runs**; every
  resolution carries evidence.
- Both adversarial same-surface pairs diverge correctly: `The company`
  resolves with an antecedent (ctx-06) and stays EXTERNAL_UNRESOLVED without
  one (ctx-07) — evidence that discourse, not the surface string, decides.
- 14 tests in `test_discourse_reference_v1.py`, five of which assert the
  FORBIDDEN inferences do not occur.
- PHASE 2: 13 tests in `test_entity_harbor_contract.py` pin the
  vocabulary, the eligibility authority (CONTEXT_REQUIRED and GENERIC are
  never eligible; LOCAL_REFERENCE eligibility follows `reference_basis`,
  not scope), the contract violations that must raise, and agreement
  between every context fixture's expectation and `graph_eligible()`.
- Prior golds and `eval/admission/artifacts/` untouched
  (`git status` clean). **Production `entity_admission.py` unchanged.**
- PHASE 1: production policy scores **55/55 on v2's carried-forward
  scope**, so v2 does not invalidate the existing regression; and
  **0/10 on the new Harbor items**, all collapsing to CORPUS_SCOPED via
  the token-count rule. That 0/10 is the PHASE 2 target, pinned as a
  documented gap rather than asserted away.
- 8 tests in `tests/determinism/test_entity_harbor_gold_v2.py`.

## Rejected claims

- No claim admission behaviour improved. Phase 0 changed no production
  semantics; 0.773 -> 1.000 is a measurement repair, not a quality gain.
- No claim the 55/55 baseline certifies REFERENTIAL-ADMISSION-V2. Per
  REVISION 2 decision 4, v1 is **historical qualification**; the new
  contract requires `admission_gold_v2` and its own gate.
- No claim the forecast in REVISION 2 (P 1.000 / R .538 after binding
  closure) is achievable. It is arithmetic over the current FP set, not a
  measured configuration.

## Open contract gaps

- **`classify()` is unimplemented by design.** It needs (a) an auditable
  concept source — canonical vocabulary/ontology entry, previously
  admitted concept, or deterministic terminology evidence — and (b) a
  discourse consumer for `reference_basis`. Neither exists.
- **CONCEPT vs GENERIC is unsolved.** Morphology does not separate
  `vector index` from `platform`. Until an auditable source exists the
  contract must ABSTAIN, never infer from compound shape. This is PHASE 2D
  (CONCEPT-SOURCE-V1) and is the remaining blocker.
- **RESOLVED by PHASE 2C.1**: the determiner mismatch. Envelope recovered
  from source text via qualified spaCy syntax; provenance preserved.
- **RESOLVED by PHASE 2C.2**: identity/definite routing precedence.
- **Remaining MASKED_ERROR (1)**: `depends_on(mentor engine -> qbank item
  database)`. Owned by canonicalization, not Harbor. Its removal is not a
  precision repair and PHASE 4 still owns the contraction.
- **`eval/*` module-name collisions**: several directories define
  `harness.py`. Any sys.path insertion of an eval directory shadows the
  others. Tests must load eval modules by explicit file path.

- PHASE 1 not started: ENTITY-HARBOR-V1 contract and `admission_gold_v2`
  (`anchor_kind`, `reference_basis`, scope) are undefined in code.
- The five gold facts with definite common-noun endpoints
  (`radiology review board`, `engineering group`, `analytics team`,
  `vision system`, `pump failure`) still require independent
  re-annotation under REVISION 3 before Phase 2 can be measured.
- `graph_eligible()` is still derived solely from
  `admission_class != MENTION_ONLY` in `neo4j_eligibility.py`; it does not
  yet consider `anchor_kind`/`reference_basis`.
- Canonical Fact Gate does not exist. Endpoint safety is still the
  per-class `_REFERENTIAL_FRAMES = {"association"}` at `candidates.py:60`.

## 2026-08-19 — S4a/S4b/S4c: production wiring cutover

### Contract
`admission-harbor-v2` is now the live semantic contract for new ingestion.
`entity-admission-v1.1` remains, reachable only by explicit pin, for
historical replay. `identity-allocation-v1` is new: it routes a settled
admission to an identity, with durability decided by `graph_eligible()`
alone.

### Changes
- `shared/polymath_shared/identity_allocation.py` — new. `MentionIdentity`,
  `allocate_identity()`, `span_identity_key()`, `normalized_for_lookup()`.
- `workers/workers/extract_worker.py` — `_allocate_identities()` is the one
  admission authority per document; runs after syntax and after rescue.
  `_slices()` no longer allocates. `_persist_mentions` writes the eight
  V2 columns and now persists the post-rescue proposal set.
  `_persist_decision`, `_allocate_parse_entity` are consumers.
- `workers/workers/candidates.py` — `_allocate` and `_admission_class_of`
  are consumers; `identities_for()` added for harness callers.
- `workers/workers/kimi_candidates.py` — threads the same map.
- `shared/polymath_shared/neo4j_eligibility.py` — docstring states why the
  SQL predicate is a materialization of `graph_eligible()`, not a rival.
- `tests/historical_boundary.py` — new. Pre-V2 tests pin v1.1 explicitly.
- `tests/determinism/test_s4b_single_allocation.py` (5),
  `tests/determinism/test_s4c_single_path.py` (15) — new gates.
- `test_cutover_is_not_yet_performed_...` flipped to
  `test_the_cutover_is_performed_and_no_worker_calls_the_historical_authority`,
  exactly as that test promised it would.

### Proof
- 508 tests pass, 53 skipped, 0 failures.
- Frozen I4, reproduced twice: TP=12 FP=4 FN=14 P=0.750 R=0.462,
  envelope 7/8, must-not 18/18, provenance 15/15.
  v1.1 baseline was P=0.706 with FP=5 — one FP removed, nothing lost.
- S4a and S4b were each verified behaviour-neutral against the frozen
  baseline BEFORE S4c changed any semantics.
- 82/82 mentions stamped `admission-harbor-v2`.
- Three development documents run clean on the live path.

### Rejected claims
- **"S4a/S4b are behaviour-neutral" was not assumed.** Each was run against
  frozen I4 and reproduced 0.706/12/5/14 exactly before proceeding.
- **The first V2 run scored P=0.375 and that number was NOT reported as a
  V2 regression.** It had two causes, both mine: identity keyed on the
  referential envelope (splitting one referent in two), and a stale worker
  process that never loaded the fix. Neither was a semantic result.
- **No rule was adjusted to fit the gold.** The gold surfaced the keying
  defect; the fix was argued from the contract (the envelope is an
  interpretation surface, not an identity key) and independently locked by
  `test_identity_does_not_fragment_on_a_determiner`.
- **Two of my own new gates were wrong and were corrected, not deleted:** one
  asserted the migration contains no `graph_eligible` string when the file
  merely explains in a comment why no such column exists; another enumerated
  `scope=MENTION_ONLY` with `graph_eligible=True`, a state the predicate
  cannot produce.

### Open contract gaps
1. Title-case headings manufacture proper-noun evidence: `Working Memory`
   admits IDENTITY/GLOBAL while `working memory` admits CONCEPT/
   CORPUS_SCOPED. One concept, two identities, decided by capitalization.
2. `graph_eligible()` grants durable DOCUMENT_SCOPED ids to
   ANTECEDENT_RESOLVED local references (`these notes`, `new concept`).
   Inherited rather than manufactured eligibility, but it deserves a ruling.
3. Orphaned `entities` rows from the failed intermediate runs remain in the
   dev database (57 determiner-prefixed rows, none referenced by any live
   mention). Not cleaned — deleting rows was not authorized.
4. CP2.1 worker supervision remains the conspicuous operational gap: the
   cutover was briefly invisible because long-running workers held stale
   code, and nothing detected it.

## 2026-08-19 — pre-S5 settlements (rows 47/48, worker fence, residue)

### Contract
Four new/changed authorities: `layout-evidence-v1` (new),
`identity-precision-v2` (heading context added), `identity-allocation-v1`
(antecedent inheritance), `semantic-residue-reconciliation-v1` (new). The
claim gate gains `semantic_bundle`.

### Changes
- `shared/polymath_shared/layout_evidence.py` — new. `heading_regions()`,
  `in_heading()`, `independently_capitalized()`.
- `identity_evidence.py` — `heading_context` parameter; PROPN evidence in a
  heading survives only where capitalization is not title-case-explicable.
- `admission_interpreter.py` — threads `heading_context`.
- `extract_worker.py` — computes heading regions from CHUNK text (line
  structure survives there, not in sentence text); resolves antecedent
  identity and passes it to the allocator.
- `identity_allocation.py` — ANTECEDENT_RESOLVED inherits or gets nothing,
  ahead of all scope routing.
- `execution.py` — `authority_code_sha256` over 11 authority modules,
  `semantic_authority_sha256()`, `semantic_bundle` in `worker_contracts()`,
  equality check in `compatible()`.
- `verify_worker.py` — `reconcile_semantic_residue()`, dry run by default.
- New gates: `test_layout_and_inheritance.py` (11),
  `test_semantic_bundle_fence.py` (16), `test_semantic_residue.py` (5).

### Proof
- 541 pass, 53 skipped, 0 failures.
- Frozen I4 unchanged by both rulings: TP=12 FP=4 P=0.750 R=0.462,
  envelope 7/8, must-not 18/18. Neither ruling cost a true positive.
- Historical 55-item gold: accuracy 1.0, zero errors — v1.1 replay intact.
- Psychology: `Working Memory`/`Working memory`/`working memory` converge on
  one DOCUMENT_DEFINED concept id. The typography split is closed.
- Residue reconciliation applied: entities 863->728, facts 462->385,
  mentions untouched, residual zero in all three classes.

### Rejected claims
- **The worker fence was NOT delivered as first specified.** Advertising
  `semantic_bundle_sha256()` would not have caught the incident that
  motivated it: the bundle hashed declared contract IDs only, and
  `identity_allocation.py` changed without bumping a version. The bundle now
  hashes authority source. Reporting the fence as done without this would
  have been false assurance.
- **The claim gate deliberately excludes `syntax_model`.** It is probed from
  a live sidecar and returns None on failure; a gate depending on it would
  let one blip change every worker's bundle and stall the queue. The syntax
  dependency is already gated by `claim_eligible()` against fresh capability.
- **Heading detection does not infer "looks like a title" from the phrase.**
  That would reintroduce the capitalization heuristic the rule removes. Only
  ATX and setext forms count; capitalized prose lines do not.
- **Research notes dropping to 0/40 eligible was not softened.** Each
  withdrawal is individually correct; the coverage question is the
  evaluator's, and no threshold was adjusted to avoid it.
- **The 24 remaining determiner-prefixed entity rows were not deleted.** They
  have intact provenance chains in older corpora, so they are not residue.
  Deleting them would have been cosmetic, which is what was ruled out.

### Open contract gaps
1. **Row 51 — `core_type` fragments identity.** `working memory` yields two
   `entc_` ids from identical normalized surfaces because GLiNER typed one
   occurrence `Technology` and the rest `Concept`. A third fragmentation
   vector, outside both authorizations. Needs a ruling before S5.
2. **Row 52 — research notes admits nothing.** Coverage question.
3. CP2.1 supervision still handles the dead-worker case; the fence only
   covers alive-but-stale.

## 2026-08-19 — HARBOR-TYPE-IDENTITY-ALIGNMENT-V1 (row 51); row 52 closed

### Contract
`harbor-type-identity-alignment-v1`, declared in the semantic bundle.
Frozen principle: provider type helps DESCRIBE an identity; it does not by
itself DEFINE identity. Qualified Harbor evidence owns canonical identity.

### Changes
- `identity_allocation.py` — `canonical_type()`. CONCEPT anchors key on
  CONCEPT; IDENTITY anchors retain provider type; LOCAL_REFERENCE unchanged.
- `execution.py` — contract declared in `semantic_authorities()`.
- `tests/determinism/test_harbor_type_identity_alignment.py` — 13 gates.

### Proof
- 554 pass, 53 skipped, 0 failures.
- Frozen I4 unchanged: TP=12 FP=4 P=0.750 R=0.462, envelope 7/8, 18/18.
- Historical 55-gold: accuracy 1.0, zero errors.
- Psychology: 2 canonical identities -> 1. All four surface/type variants of
  `working memory` converge on `entc_77ae3db105b8c6e`.
- Transcript: 7 distinct identities, unchanged — no overmerge.
- Live corpus audit: no surface maps to >1 entity id; the only ids spanning
  multiple surfaces are row 48 inheritances behaving correctly.

### Rejected claims
- **Type was NOT removed from the identity key globally.** That would merge
  Java the language with Java the island. The gate is scoped to kinds a
  qualified authority settled; IDENTITY deliberately keeps provider type.
- **The gate does not merge on string equality.** `Mercury` as a
  DOCUMENT_DEFINED concept and `Mercury` as a named identity stay distinct.
- **This is not GLiNER type arbitration**, and the failed type-arbitration
  work was not reopened. Nothing adjudicates between competing neural labels.
- **Provider type is retained, not discarded** — it remains on the record as
  extraction evidence; only the identity NAMESPACE changed.

### Open contract gaps
1. Residual homonym risk for CONCEPTS specifically: two documents in one
   corpus that each define the same term differently would share a
   CORPUS_SCOPED concept id. Not observed; named so it is not mistaken for
   solved.
2. CP2.1 supervision still owns the dead-worker case.

## 2026-08-19 — S5 HALTED at invariant 3 (row 53 regression)

### Contract
`semantic-reprocess-v1` built and verified. No semantic rule changed.

### Changes
- `workers/workers/reprocess_worker.py` — new. Re-derives V2 semantic state
  from persisted mentions + chunks + pinned syntax + the V2 bundle. Imports
  no GLiNER and no Qdrant client (asserted statically).
- Slice reconstruction keeps EVERY sentence. A mentions-only reconstruction
  produced a smaller discourse context and silently lost an antecedent
  (`The engineering group`: ANTECEDENT_RESOLVED during extraction,
  EXTERNAL_UNRESOLVED on re-derivation). It is a superset of the extract
  stage's slice set and so cannot be PROVEN identical in general; making
  them provably agree means persisting the slice set at extraction.

### Proof
- Invariant 1: re-derivation reproduces live extraction byte-identically —
  mentions 82, entities 10, facts 16, canonical memberships 5, all identical.
- Invariant 10: replay idempotent, state hash stable across three runs.
- Invariants 2, 4, 5, 6, 9: pass. Fact deltas: 16 UNCHANGED_SEMANTICS,
  UNEXPLAINED=0, endpoints unresolved=0.
- **Invariant 3: FAILS.** 15 of 16 facts carry a MENTION_ONLY endpoint.

### Rejected claims
- **The earlier `Working Memory` convergence does not hold in production.**
  That probe built chunks by splitting on blank lines, preserving newlines.
  Production chunks have none, so heading detection never bounds correctly.
  Reporting row 47 as delivered was wrong.
- **P=.750 was not evidence that row 47 was safe.** The I4 fact score
  compares endpoint SURFACES, not eligibility, so a change that parks 42 of
  55 eligible identities leaves it unmoved. A green surface score is not
  coverage of the identity model.
- **S5 did not cause the failure and was not adjusted to hide it.** The
  reprocessor reproduces extraction exactly; it surfaced a defect that
  extraction already had.

### Open contract gaps
1. Row 53 — heading regions cannot be derived from normalized chunk text.
   Options: (A) require a real line terminus, which makes the rule abstain
   and therefore inert under the current chunker; (B) preserve line structure
   through chunking, which changes chunk content hashes and so embeddings;
   (C) persist a heading map at intake and consult it from admission.
   All three need authorization.
2. Row 54 — S5 halted; canonicalization, Neo4j reconstruction and both
   metric scores not run.

## 2026-08-19 — rows 53/54 closed, S5 COMPLETE

### Contract
`layout-evidence-v1` (persisted, option C), `sentence-slice-manifest-v1`,
`graph-residue-reconciliation-v1`, admission census regression. Migration
0016. No semantic admission rule changed.

### Changes
- `stores/postgres/migrations/0016_layout_and_slice_manifest.sql` — new:
  `document_layout`, `chunks.layout_map`, `sentence_slices`. No backfill.
- `layout_evidence.py` — `project_regions()`; `heading_regions()` documented
  as source-text-only.
- `chunker.py` — detects layout on materialized source, projects it
  character-exactly per sentence as chunks are assembled. `buf_len` keeps its
  original meaning so packing, chunk text, chunk ids and embeddings are
  bit-for-bit unchanged.
- `intake_worker.py` — persists `document_layout` and `chunks.layout_map`.
- `extract_worker.py` — READS `layout_map`; abstains when NULL. Writes the
  slice manifest. Inheriting references no longer describe borrowed entities.
- `reprocess_worker.py` — consumes the manifest; refuses without it.
- `verify_worker.py` — `reconcile_graph_residue()`.
- `eval/census/verify_census.py`, `eval/i4/canonical_identity_score.py` — new.
  `verify_i4.py` untouched.

### Proof
All ten S5 invariants pass. Re-derivation reproduces extraction byte-identically
(mentions 82, entities 40, facts 16, canonical memberships 24); replay
idempotent; fact deltas 16 UNCHANGED_SEMANTICS with UNEXPLAINED=0 and 0
unresolved endpoints; residue zero in Postgres and Neo4j; Neo4j holds exactly
the 11 eligible facts with 0 missing and 0 ineligible; Qdrant untouched.

```
A. historical surface   TP 13  FP 3  FN 13  P .812  R .500
B. canonical identity   TP 10  FP 6  FN 16  P .625  R .385
                        10 of 26 gold endpoints hold no durable identity
```

569 tests pass. Historical 55-gold accuracy 1.0. Census: no divergences.
Development probes: transcript 7 genuine identities, psychology ONE
working-memory concept, research notes zero — all as expected.

### Rejected claims
- **The census was re-baselined, and that is recorded rather than quiet.**
  It was frozen once before the row-57 ownership fix and re-frozen after
  (canonical_entities 23 -> 24). Re-baselining follows a ruling; it is never
  how a divergence gets resolved.
- **The canonical-identity score is LOWER than the surface score, and that is
  the point.** P .625 vs .812 is not a regression: 10 of 26 gold endpoints
  never earned a durable identity, which the surface score cannot see. Two
  metrics are kept because neither is sufficient alone.
- **Invariant 3's "15 contradictions" was a mis-framing in the halt report.**
  Parked facts are by design; the genuine defect was row 53 suppressing the
  identities, plus row 57's ownership bug. Verified separately: 0 rows where
  an id prefix disagrees with its admission class.
- **All-sentence reconstruction was abandoned, not kept.** It reproduced
  extraction on I4 but is a superset of the interpreter's view and could
  invent antecedents elsewhere. The manifest replaced it.

### Open contract gaps
1. Corpus-scoped concept homonyms: two documents in one corpus defining the
   same term in different senses would share a CORPUS_SCOPED id. Frozen as a
   known limitation; do not solve until a wrong merge is actually observed.
2. 36 corpora remain on v1.1 by design (historical replay state). Migrating
   any of them needs authorization.
3. CP2.1 supervision still owns the dead-worker case; the bundle fence covers
   alive-but-stale only.

## 2026-08-19 — S6A/S6B forensic attribution (diagnostic only)

### Contract
None changed. Two new read-only diagnostics:
`eval/i4/endpoint_coverage_attribution.py`,
`eval/i4/canonical_fp_attribution.py`. Both waterfalls are closed and both
require UNEXPLAINED = 0.

### Proof
```
S6A  52 endpoint instances   38 DURABLE · 7 DISCOVERY_MISS
                             4 LOCAL_REFERENCE_UNRESOLVED · 2 HEADING_SUPPRESSED
                             1 SPAN_BOUNDARY · 0 UNEXPLAINED
S6B  6 false positives       3 WRONG_CANONICAL_IDENTITY · 3 UNSUPPORTED_FACT
                             0 wrong pair / direction / predicate / overmerge
                             0 UNEXPLAINED
```
Discovery misses verified by listing every proposal in the affected
documents rather than trusting the classifier.

### Rejected claims
- **Binding is not the residual defect.** The earlier suspicion is refuted:
  zero wrong argument pairs, directions, predicates or over-merges.
  BINDING-PRECISION-CLOSURE-V1 was not opened.
- **My first FP attribution was wrong and was corrected before reporting.**
  Three FPs bucketed as WRONG_ARGUMENT_PAIR are identity-EXTENT mismatches —
  the right argument with a shorter identity. Left uncorrected it would have
  manufactured a binding defect and aimed the next gate at the wrong stage.
- **My first S6A run was also wrong.** It re-derived identity WITHOUT heading
  context and so reported two IDENTITY_FALSE_NEGATIVEs that do not exist. A
  diagnostic must ask the live authority under the same conditions, or it
  invents defects. Corrected to HEADING_SUPPRESSED.
- **Recall .385 is not a single failure.** It is 7 provider misses, 6
  contract-correct refusals and 1 extent mismatch. Treating it as one number
  would have justified weakening Harbor, which the evidence contradicts.

### Open contract gaps
1. Row 60 — span discovery/extent is the dominant residual mechanism.
2. Row 61 — heading-only proper names never become nodes. Needs a ruling.
3. Row 62 — 3 unsupported relations; bounded, revisit on the sealed set.

## 2026-08-20 — row 60 diagnosis: the gate targets the wrong mechanism. STOPPED.

### Contract
Nothing changed. Investigation only.

### What was authorized vs what the evidence shows
RELATION-ENDPOINT-SPAN-RECOVERY-V1 was authorized on the premise that the
provider fails to emit an endpoint span and syntax should supply one. That
machinery ALREADY EXISTS and works: `missing_argument_candidates()` derives
the trigger-governed argument NP from the dependency parse, excludes
quantified NPs, skips anything an entity already covers, and re-queries
GLiNER on the exact phrase. It produced correct candidates for 5 of the 7
gold misses. Building the gate as scoped would add machinery beside working
machinery and leave the actual defects untouched.

### The actual mechanisms
1. **Span deletion on refused widening** (`rescue.py:327`). 13 original
   provider spans deleted in the last I4 run. `Nimbus Cloud` at 0.91 is
   discarded because the speculative `Postmortem Review Nimbus Cloud` failed.
2. **Re-query sensitivity coupled to profile vocabulary size.** 20-label
   profile -> nothing for all 7 probes; 12-label core -> 2 accepted. Rescue
   recall degrades as a profile activates more domains.
3. **Heading contamination of noun chunks** — the row 53 root cause again,
   now in the discovery path rather than the identity path.

### Rejected claims
- **"The provider never proposed the span" was wrong.** S6A measured absence
  from `mentions` and named the bucket after a cause it had not established.
  GLiNER proposes `Nimbus Cloud`, `load-testing harness` and
  `radiology review board` at 0.69-0.91; the pipeline discards them.
- **My first rescue diagnostic was invalid and was discarded.** It rebuilt
  slices through the manifest, which sets `evidence=[]`, so it reported
  "triggers: NONE" for every sentence — an artifact of my reconstruction,
  not a finding. Re-run against the real pass-2 proposer, triggers exist
  everywhere.
- **Nothing was fixed.** The counterfactual was executed read-only, in a
  patched module copy, and the tree is unchanged.

### Open contract gaps
Rows 63, 64, 65 (mechanisms) and 66 (the corrected attribution).

## 2026-08-20 — RESCUE-SPAN-PRESERVATION-V1: objective met, qualification failed

### Contract
`rescue-span-preservation-v1`. Two mechanical fixes in `workers/rescue.py`.
No admission, binding, predicate or canonicalization rule changed.

### Changes
- (A) A refused boundary widening now KEEPS the original provider span.
- (B) `layout_of()` / `crosses_layout_boundary()`; both candidate lanes refuse
  any noun chunk straddling a persisted heading edge.
- `test_apply_boundary_refused_marks_unresolved` renamed and inverted — it
  pinned the superseded contract.
- New `tests/determinism/test_rescue_span_preservation.py` (10), including
  both pinned adversarial cases and the positive control.

### Proof
```
                        before   after
DURABLE endpoints          38      41
DISCOVERY_MISS              7       4
HEADING_SUPPRESSED          2       0
SPAN_BOUNDARY               1       3
LOCAL_REFERENCE_UNRESOLVED  4       4
surface TP / FP         13 / 3  14 / 10
recall / envelope    .500 7/8  .538 8/8
canonical FP                6      11
```
Both pinned cases recovered. Zero endpoints moved durable -> non-durable;
zero previously-matched facts lost. 579 tests pass.

### Rejected claims
- **The gate is NOT accepted.** Criteria 8 and 9 are violated:
  WRONG_CANONICAL_IDENTITY 3->6, UNSUPPORTED_FACT 3->4, one new OVERMERGE.
  Reporting "recall and envelope improved" as success would ignore the
  criteria that were set precisely to prevent that reading.
- **The new false positives are not caused by A or B.** Preserving spans
  gives the discourse resolver more antecedent candidates and it makes some
  wrong ones. The deletion bug was masking a discourse-precision defect;
  removing a mask is not a regression, but the exposed defect is real.
- **The vocabulary-dilution finding was NOT acted on**, per the hold. Noted
  for the record: `apply_boundary` already issues single-label queries
  (GLINER-QUERY-VOCAB-v2, "multi-label rescue queries dilute scores
  (measured)"); `apply_missing_arguments` does not. The remedy already
  exists in the codebase and is simply not applied to that lane.

### Open contract gaps
Row 67 (discourse antecedent type-compatibility) blocks acceptance.
Row 64 (vocabulary dilution) remains on hold.

## 2026-08-20 — E4 type compatibility; combined stack FAILS qualification. STOPPED.

### Contract
`e4-antecedent-type-compatibility-v1`. Three-valued `type_compatible()`;
E4's co-occurrence branch now requires POSITIVE compatibility before the
exactly-one count. Head-sharing candidates are deliberately not filtered.
Also corrected `admitted_anchors` to carry core types.

### Proof — required vs actual
```
DURABLE endpoints        >= 41   ->  41   PASS
DISCOVERY_MISS           <=  4   ->   4   PASS
HEADING_SUPPRESSED        =  0   ->   0   PASS
prior TP lost             =  0   ->   0   PASS
prior durable lost        =  0   ->   0   PASS
UNEXPLAINED               =  0   ->   0   PASS
WRONG_CANONICAL_IDENTITY <=  3   ->   6   FAIL
UNSUPPORTED_FACT         <=  3   ->   4   FAIL
OVERMERGE                 =  0   ->   2   FAIL
surface precision                 .560    did not recover
```
593 tests pass, including 14 new ones covering every pinned adversarial and
positive case.

### Rejected claims
- **The stack is NOT accepted and NOT promoted.** Three criteria fail.
- **Row 67 fixed only its named case.** `company` -> `raleigh` is gone. The
  surviving bad merges all carry `E3 repeated named anchor`, and E3 matches on
  ANY shared content word with no type or head constraint. The defect class is
  larger than E4, and constraining E4 was never going to close it.
- **My E4b wiring fix made the measurement worse, and I am not hiding it.**
  Correcting `admitted_anchors` revived a rule that had been dead in
  production, and it promptly resolved `vision system` -> `Siemens PLCs` —
  type-compatible, same type, wrong referent. Type compatibility cannot
  separate two same-typed co-occurring entities.
- **No further tuning was attempted**, per the ruling.

### Open contract gaps
Rows 69 (E3 shared-word matching), 70 (E4b revival), 71 (the failed
qualification record). Row 64 remains on hold.

## 2026-08-20 — E3-ANCHOR-CONTINUITY-V1 + E4b exclusion. Stack FAILS. STOPPED.

### Contract
`e3-anchor-continuity-v1`. E3 resolves only on exact normalized anchor
repetition; lexical overlap proposes, it does not prove. Contraction/alias
identity belongs to the contraction resolver, descriptive anaphora to E4.
E4b is explicitly excluded from admission-harbor-v2 (row 70), retained in
code with correct input representation and component-only tests.

### Proof — acceptance bar
```
DISCOVERY_MISS            <= 4  ->  4   PASS
HEADING_SUPPRESSED         = 0  ->  0   PASS
previous TP loss           = 0  ->  0   PASS
OVERMERGE                  = 0  ->  0   PASS
wrong predicate/direction/pair = 0 -> 0 PASS
UNEXPLAINED                = 0  ->  0   PASS
DURABLE endpoints        >= 41  -> 40   FAIL
WRONG_CANONICAL_IDENTITY  <= 3  ->  6   FAIL
UNSUPPORTED_FACT          <= 3  ->  5   FAIL
```
602 tests pass. The three surviving multi-surface identities are exactly the
correct inheritances: `outage`/`september outage`,
`careconnect portal`/`patient portal`,
`mentor engine`/`mentor assessment engine`.

### Rejected claims
- **The stack is not accepted.** Three criteria fail and the ruling is STOP.
- **I am not arguing the bar down.** The characterisation below explains the
  failures; it does not excuse them, and no criterion was reinterpreted to
  manufacture a pass.
- **DURABLE 41 -> 40 is not purely a loss.** The endpoint removed was
  `analytics team` inheriting from `crestline automation team`, one of the
  merges identified as WRONG. The >=41 target counted a defect as coverage.
  Reporting this as a clean regression would be as misleading as hiding it.
- **The residual failures are not discourse.** All 6 WRONG_CANONICAL_IDENTITY
  are extent mismatches (row 61, deferred); all 5 UNSUPPORTED_FACT are
  relation over-generation (row 62). Discourse work could not have closed
  either, and no further discourse work was attempted.

### Open contract gaps
Rows 72 (failed qualification), 73 (known limitation: identity EXTENT is the
unsolved axis), 74 (no VCS isolation for the unpromoted candidate stack).
Row 64 remains frozen.

## 2026-08-21 — SUBTOKEN-SPAN-ADMISSION-V1: qualified on candidate branch

### Contract
`subtoken-span-admission-v1`, inside `_interpret_v2`. The three-way
distinction ruled: syntax truly unavailable -> RETRYABLE (unchanged); syntax
present + span covers no complete token -> settled abstention on THAT span
(UNKNOWN/ABSTAINED/MENTION_ONLY, never eligible, surface preserved verbatim,
containing token recorded as evidence only); sentence with zero tokens ->
RETRYABLE (outage shape). Authority hash moved 8241bf94 -> 3981fcff — a
candidate semantic change, NOT on main.

### Proof
```
unit gates                6/6 (outage path, nested, zero-overlap,
                          no-token sentence, surface preservation, ordinary spans)
previously-crashing call  COMPLETES: 60 spans, `instagram` abstains
I4 state hash             byte-identical (P .812 R .500 envelope 7/8 exact)
smq1 stamped hashes       reproduced across TWO independent re-ingests
historical 55-gold        accuracy 1.0, 0 errors
suite                     575 passed
URL transcripts           ingest end-to-end, 0 stage failures (subtoken-probe-v1)
```

### Rejected claims
- **The production probe's convergence does NOT by itself prove the fix
  fired in production.** No abstention rows were persisted, and the reason is
  ledger 63: boundary rescue DELETED the `instagram`/`youtube` spans before
  admission saw them. The fix was proven instead on the exact configuration
  that crashed in the forensics bench, plus unit gates.
- **My earlier severity claim was overstated and is corrected (row 76).**
  "Deterministic production crash on any URL-bearing document" holds only for
  sub-token spans that ESCAPE boundary widening; the current deletion bug
  masks the two probe documents' triggers.
- **New gate dependency recorded:** row 75 is a prerequisite for ever
  promoting the rescue-preservation fix — without it, fixing deletion
  unmasks the crashes it was hiding.

### Open
Promotion to main (a semantic-freeze change) is the evaluator's call.

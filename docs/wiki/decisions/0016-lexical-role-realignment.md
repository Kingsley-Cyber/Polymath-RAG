---
owner: governance
last_reviewed: 2026-08-17
last_touched: 2026-08-17
status: accepted
---

# ADR-0016: Lexical-Role Realignment — the Kimi architecture restored

## Context

ADR-0015 identified that entity typing carries too much authority over
relation discovery. LEXICAL-COMPILER-ALIGNMENT-V1 (experiment 0007)
confirmed: types are an early hard veto (Q9=C), the compiler receives
candidates only after type filtering (Q10=AFTER), and PropBank ARG0/
ARG1 roles are never assigned (Q4=none).

This ADR records the CORRECT architecture, realigned to the original
Kimi design rather than the debugging-era approximation that drifted
in during Phase H / I3R / I4R.

## What went wrong

The current implementation starts from positional left/right pairing
with type-compatibility filtering, and only THEN consults lexical
resources. The Kimi design says candidate arguments should be derived
from the UD dependency tree (entities whose head tokens are syntactic
dependents of the predicate head), with a bounded linear window only
as a recall net.

The drift:
```
CURRENT (wrong):
GLiNER type → _slot_compatible → left/right positional filter →
candidate → lexical resources (too late)
```

The correct ordering:
```
KIMI (right):
evidence trigger → UD structure → possible grammatical arguments →
PropBank semantic roles → role-oriented candidate pair →
cheap type compatibility → lexical compiler
```

## The corrected architecture

```
SOURCE SENTENCE
      │
      ├──────────────────────┐
      ▼                      ▼
GLiNER PASS 1          GLiNER PASS 2
entity/object spans    coarse evidence classes (~18)
      │                      │
      └──────────┬───────────┘
                 ▼
             spaCy UD
    lemma / dependency / voice /
       coordination / negation
                 ▼
        COMPILED LEXICON
   ┌─────────┼──────────┐
   ▼         ▼          ▼
PropBank   VerbNet    FrameNet
   └─────────┬──────────┘
          SemLink
             ▼
     SEMANTIC ROLES
     ARG0 / ARG1 / ...
             ▼
     ARGUMENT BINDING
             ▼
   TYPE-PAIR PRECHECK
  (cheap / deterministic)
             ▼
   PREDICATE COMPILER
             ▼
   ONTOLOGY VALIDATION
             ▼
ACCEPT / QUALIFY / REJECT /
AMBIGUOUS / UNSUPPORTED
             ▼
    FACT + EVIDENCE
```

## Division of labor

| Component | Answers |
|---|---|
| GLiNER Pass 1 | What things are here? |
| GLiNER Pass 2 | What kind of relational evidence is here? |
| spaCy / UD | How is the sentence structurally connected? |
| PropBank | What semantic roles does this event have? |
| VerbNet | What argument structures are licensed? |
| FrameNet | What semantic frame is being evoked? |
| SemLink | Which PB/VN/FN interpretations line up? |
| Predicate compiler | Given all evidence, which canonical predicate? |
| Ontology signatures | Is that interpretation allowable? |

## Pass 2: evidence classes, NOT predicates

GLiNER Pass 2 asks for ~18 coarse evidence classes (creation,
employment_membership, ownership_control, leadership_governance,
composition, causation, usage_application, location, temporal,
comparison, measurement, association, dependency,
reference_attribution, transformation, classification,
influence_affect, communication_expression) — NOT graph predicates.
The deterministic compiler expands coarse evidence into the final
predicate using trigger lemma + roleset + type features.

Example:
```
"Steve Jobs founded Apple."
Pass 1: Steve Jobs → Person, Apple → Organization
Pass 2: founded → creation (evidence class)
spaCy: Steve Jobs = nsubj, Apple = obj
Lexical: find → found.01 → create-26.4 → Creating → SemLink
PropBank: ARG0 = founder, ARG1 = thing founded
Compiler: creation + found.01 + ARG0/ARG1 + Person/Organization → FOUNDED
```

## PropBank role assignment — the largest missing piece

The compiled resource already contains use.01, found.01, create.01,
lead.02, etc. But the runtime never assigns ARG0/ARG1/ARG2 to spans.
For "A robust implementation uses bounded leases":

Desired interpretation:
```
use.01:
  ARG0 = user → robust implementation (from nsubj → uses)
  ARG1 = thing used → bounded leases (from dobj → uses)
```

This happens BEFORE arguing about whether robust implementation is
Method vs Technology. Syntax provides the argument structure;
PropBank provides the semantic role labels; the compiler then uses
types as one disambiguating feature among several.

## Types still matter — but differently

The compiler uses types as one feature in semantic compilation:
```
creation + "found" + Person→Organization → FOUNDED
creation + "develop" + Person→Technology → DEVELOPED
```

Types are NOT collapsed to TechnicalConcept everywhere. They are one
signal among several, applied AFTER structural argument candidates
exist, not as a substitute for argument structure.

## The 12 realignment invariants

1. GLiNER never decides a graph relation.
2. Pass 1 extracts entities / semantic objects.
3. Pass 2 extracts coarse evidence classes, not predicates.
4. spaCy/UD provides structural argument evidence.
5. PropBank roles must actually be assigned to endpoints.
6. VerbNet + PropBank + FrameNet + SemLink are active compiler
   inputs, not decorative metadata.
7. Candidate generation is evidence-anchored and UD-bounded, not
   left×right Cartesian pairing.
8. Type compatibility is allowed as a cheap pair filter, but only
   AFTER structural argument candidates exist.
9. Direction is role-based, not surface-order-based.
10. The deterministic compiler is the semantic mapping authority.
11. Ontology signatures validate the compiled interpretation.
12. UNSUPPORTED means abstain, never guess.

## What this does NOT authorize

This ADR records architectural direction. Implementation requires its
own named gate with full qualification. No production change is
authorized by this document alone. The type-pair pre-check is
retained (per Kimi), but only after structural argument candidates
exist — the correction is ordering, not elimination.

## Speed implications

The expensive neural pieces remain GLiNER Pass 1 and Pass 2.
Everything after is spaCy + in-memory O(1) lexical lookups + small
deterministic rules. The architecture is compatible with future
GLiNER2-MLX substitution in the neural stages without changing the
deterministic pipeline underneath.

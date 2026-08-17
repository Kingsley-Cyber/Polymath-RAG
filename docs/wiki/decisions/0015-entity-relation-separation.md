---
owner: governance
last_reviewed: 2026-08-17
last_touched: 2026-08-17
status: accepted
---

# ADR-0015: Entity–Relation Separation — architectural lessons from five failed gates

## Context

Five controlled qualification gates (QUERY-VOCAB-v2, TYPE-ARBITRATION-v1,
EXTRACTION-CONTEXT-v1, SIGNATURE-AUDIT-v1, MODEL-QUALIFICATION-v1) each
attempted to repair the same downstream failure: entity canonical types
blocking relation candidates at the predicate-signature gate. All five
failed to produce a qualifying fix. The convergent finding is that the
architecture itself asks the entity layer to carry too much semantic
authority.

## Five identified design mistakes

### 1. Overly fine entity types

The current 12-type ontology asks the neural model to distinguish
Technology / Method / Process / Product / Document / Concept —
categories that are often semantically overlapping for abstract
technical noun phrases:

- "execution contract" — a document, a mechanism, a concept, or a method?
- "reconciliation process" — obviously a Process, also a Method used by a system

Forcing exactly one label before relation extraction creates
unnecessary failure at the type gate.

**Coarser entity classes are more robust:**
Person, Organization, Location, Product/System, Document, Event,
TechnicalConcept, OtherConcept — with original GLiNER hypotheses
preserved as metadata.

### 2. Entity typing controls relation discovery (backwards)

Current flow:
```
GLiNER span → canonical type → predicate slot check → candidate killed
```

"robust implementation" → Technology prevents the USES candidate from
even reaching the lexical compiler. The noisy zero-shot type vetoes
before the strong lexical evidence (VerbNet/PropBank/FrameNet/SemLink)
gets to speak.

**Better flow:**
```
GLiNER → endpoints → spaCy → subject/object structure
→ VN/PB/FN/SemLink → semantic relation evidence
→ compiler → candidate predicate
→ THEN ontology sanity validation (late, not gating)
```

### 3. Confusing entity classification with semantic role

"Kubernetes" → Technology is an entity classification.
"Kubernetes uses etcd" — Kubernetes occupies the semantic role USER/AGENT.

These are not competing facts. An endpoint has BOTH:
- entity class = Technology
- semantic role in this relation = USER

PropBank/FrameNet/VerbNet are better suited to the role question.
The current architecture asks entity class to answer both.

### 4. Judging entity quality by graph output

The probe showed 123 NPs → 42 mentions → 10 durable → 0 facts. The
0-fact result triggered entity-model investigation, but the entity
layer was actually working well (good spans: "bounded leases",
"deterministic stage contracts", "transactional claim operations",
"graph databases", "vector index", "workflow database"). The failure
was downstream.

**Entity quality and relation quality must be scored independently:**

ENTITY QUALITY: span discovery, boundary quality, meaningfulness,
generic rejection, coarse semantic class.

RELATION QUALITY: trigger, role binding, lexical semantics, predicate
mapping, evidence validity.

Don't punish GLiNER for a compiler failure. Don't change the compiler
because GLiNER missed an entity.

### 5. Demanding GLiNER recognize every noun phrase

GLiNER does not need to find every NP — spaCy already provides
structural coverage (123 NPs). GLiNER's value is: which spans look
semantically meaningful? 42 semantic proposals from 123 NPs is a
reasonable architecture, not a deficit.

## Revised architecture (target)

```
DOCUMENT
  ↓
semantic_v2 structure
  ↓
┌───────────────┴────────────────┐
↓                                ↓
GLiNER                         spaCy
semantic spans               syntax + NPs
│                                │
└──────────────┬─────────────────┘
               ↓
      MENTION RECONCILIATION
               ↓
      coarse entity classes
               ↓
      admission / identity
               ↓
    lexical trigger + lemma
               ↓
  VerbNet / PropBank / FrameNet / SemLink
               ↓
      semantic roles (PropBank ARG0/ARG1, VN thematic, FN frame elements)
               ↓
      role binding
               ↓
    canonical predicate
               ↓
    late sanity checks (ontology validation — not a gate)
               ↓
      FACT
```

**The entity model answers:** What meaningful things are in the text?
**The lexical compiler answers:** What is happening between them?
**The ontology answers:** Is the proposed assertion ridiculous or acceptable?

## Design invariants

1. **Entity typing should help relation extraction, not control it.**
2. **Fine semantic roles belong to the lexical/syntactic relation layer
   unless the distinction is genuinely intrinsic to entity identity.**
3. **Score entity quality and relation quality independently.**

## Implications for future gates

- MODEL-QUALIFICATION should primarily judge: span recall, span
  boundaries, generic-vs-meaningful discrimination, coarse type
  accuracy, throughput — NOT perfect Method/Technology/Process
  distinction.
- The rule pack's type signatures should move from pre-candidate
  gating to post-compiler sanity checking.
- The 12-type ontology may collapse to ~8 coarse types with original
  hypotheses as metadata.
- spaCy's syntactic evidence (dependency heads, argument positions)
  should feed role binding directly, not just rescue.

## What this does NOT authorize

This ADR records architectural direction. Implementation requires its
own named gate with full qualification. No production change is
authorized by this document alone.

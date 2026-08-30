---
change_id: POLYMATH-V5-EVIDENCE-FIRST-PLAN
owner: governance
date: 2026-08-21
status: reference
architecture_impact: none (documentation; front matter added 2026-08-29 governance cleanup)
last_reviewed: 2026-08-29
---

# POLYMATH V5 — EVIDENCE-FIRST SEMANTIC PIPELINE

**Status: DIRECTIVE — no phase started.**
Authored by the evaluator, 2026-08-21. This document is the governing plan;
implementation happens on this branch (`architecture/evidence-first-v5`),
never on `main` (`v4-semantic-freeze`, 43209aa), which stays frozen and
reproducible throughout.

## The central change

> **V4 interprets while extracting. V5 extracts evidence losslessly first,
> then interprets the completed document evidence set.**

This is an architectural transition, NOT a semantic tuning cycle.

```
DO NOT improve extraction quality during this migration.
DO NOT switch GLiNER.            DO NOT change thresholds.
DO NOT change label inventories. DO NOT add admission rules.
DO NOT alter predicate semantics.
```

## Governing principle

```
Collect broadly.
Preserve losslessly.
Interpret deterministically.
Commit graph truth conservatively.
```

> **Filtering may decide what becomes canonical knowledge.
> Filtering must never decide whether observed evidence survives.**

The boundary that stays: entity admission precedes relation compilation.
"Evidence first" never means "create all relations first and clean the graph
afterward" — that yields garbage combinatorics. Pass-2 trigger evidence is
CAPTURED early; facts are COMPILED only from settled endpoints.

## The three-layer picture

```
                  SOURCE DOCUMENT
                         |
             1. EVIDENCE COMPILATION      permissive / lossless
        entity spans - provider types - scores
        syntax - layout - aliases - definitions
        predicate/trigger evidence - discourse signals
                         |
                2. SEMANTIC HARBOR        conservative
           durable knowledge  |  evidence-only
           (identity/concept) |  (generic/unknown/...)
                         |
                3. GRAPH COMPILER         canonical only
```

## Known architectural problems this solves (all previously paid for)

1. Raw provider evidence is not immutable before rescue (ledger 63: a valid
   0.91 span deleted by a failed speculative widening).
2. Admission happens too close to extraction — document-wide evidence
   arrives after identity has already influenced allocation.
3. Provider type/span choices exert structural influence before the whole
   document is visible (ledger 51, 73: `Crestline` vs `Crestline
   Automation`; `Techne Writing` split across types).
4. Rescue acts as mutation; it must become hypothesis generation.
5. Relation evidence is coupled to whether endpoints survived processing.
6. Provider bake-offs are hard because a provider change immediately changes
   semantic state (ENTITY-PROVIDER-FORENSICS-V1 had to hold rescue out of
   both arms for exactly this reason).
7. Reprocessing must reconstruct context (row 54 existed because slice
   membership wasn't persisted; V5 persists everything replay needs).
8. Raw evidence / interpretation / canonical truth lack an explicit
   lifecycle boundary.

## Target data layers

```
L0  SOURCE                immutable source identity + offsets
L1  RAW EVIDENCE          append-only, immutable, content-addressed
      RawEntityProposal   (id, doc, chunk, sentence, offsets, surface,
                           provider_type, score, provider contract/model/rev)
      RawPredicateEvidence (trigger offsets, evidence class, score, contract)
      SyntaxEvidence · LayoutEvidence · SentenceSliceManifest
L2  INTERPRETATION        SpanHypothesis (source_proposal_ids[], mechanism,
      EVIDENCE             status ACCEPTED/REJECTED — never a mutation of L1)
                          AdmissionDecision · DiscourseResolution
                          ConceptEvidence · IdentityEvidence
L3  CANONICAL SEMANTICS   CanonicalEntity · CanonicalIdentityMembership
                          (only settled evidence creates these)
L4  FACT EVIDENCE         RelationCandidate — may exist WITHOUT eligible
                          endpoints; predicate + syntax + endpoint proposal
                          references + provenance
L5  CANONICAL FACTS       created only after settlement + canonical identity
                          + predicate compilation + eligibility
L6  PROJECTIONS           Neo4j / Qdrant — rebuildable; Postgres authoritative
```

## Target execution pipeline

```
intake -> materialize -> chunk
   -> extract_entity_evidence -> extract_syntax_evidence
   -> extract_predicate_evidence -> assemble_document_evidence
   -> settle_entities -> canonicalize_entities
   -> compile_facts -> project -> verify
```

Text retrieval stays independent of semantic settlement; Qdrant text/chunk
projection must not wait for graph settlement.

## Critical invariants

```
I1   Raw provider evidence is immutable.
I2   No rescue or semantic rule deletes raw evidence.
I3   Every derived span names the exact raw evidence it derives from.
I4   Admission runs against the COMPLETED document evidence view.
I5   A canonical identity is allocated exactly once, from the settled decision.
I6   Provider type remains attributable evidence, never silently rewritten.
I7   Relation evidence may exist without canonical endpoints.
I8   Canonical facts require graph-eligible settled endpoints.
I9   Same source + contracts + providers -> hash-identical ledger and state.
I10  Provider replacement changes L1 only; Harbor/compiler contracts unchanged.
I11  V4 accepted semantics remain reproducible during migration.
I12  No V5 stage silently falls back to V4 semantics.
```

## Implementation plan

**PHASE 0 — repo reality / design map.** READ-ONLY. Stage graph, persistence
graph, every semantic write location, every point raw evidence can be
transformed or deleted, every entity-id allocation site, control-plane
ticket/receipt implications, migrations required. No code until this report
exists. STOP if repository reality contradicts this plan.

**PHASE 1 — raw evidence ledger.** L1 schema + writer, DUAL-WRITE only; V4
stays authoritative. Deterministic evidence ids, exact raw pass-1/pass-2
persistence. Acceptance: V4 metrics and entity/fact ids byte-identical;
ledger deterministic; zero raw-evidence loss.

**PHASE 2 — rescue becomes hypotheses.** SpanHypothesis records; a failed
widening records REJECTED and PRESERVES the original; an accepted widening
records ACCEPTED without mutating L1. No production cutover. Acceptance:
every current rescue decision attributable; raw proposal counts invariant.

**PHASE 3 — document evidence assembler.** Deterministic
DocumentEvidenceBundle — a **manifest/versioned view** (hashes of member
sets), NOT a deserialized blob. Same source/contracts -> same bundle hash;
missing evidence -> fail closed; no reconstruction heuristics.

**PHASE 4 — shadow entity settlement.** Run qualified V4 Harbor semantics
against the completed bundle, SHADOW ONLY. Classify every delta:
`ORDERING_ONLY · CONTEXT_DIFFERENCE · RAW_EVIDENCE_PRESERVED ·
RESCUE_DIFFERENCE · IDENTITY_DIFFERENCE · CONCEPT_DIFFERENCE ·
DISCOURSE_DIFFERENCE · UNEXPLAINED`. UNEXPLAINED must be 0. Do not tune
semantics to eliminate differences.

**PHASE 5 — canonical entity settlement.** One document-level settlement
authority: bundle in, immutable AdmissionDecisions + CanonicalEntities +
provenance out. Current qualified V4 contracts only. Order-independent,
deterministic, no first-mention-wins state, no provider-type fragmentation,
no reference-minted duplicates.

**PHASE 6 — fact compilation after settlement.** Compiler consumes settled
endpoints + persisted predicate evidence + syntax. RelationCandidate may
exist without a CanonicalFact. No predicate semantics change. Parked
evidence stays attributable; no edge from an unresolved endpoint.

**PHASE 7 — V5 reprocessing/reconstruction.** raw evidence -> bundle ->
settlement -> facts -> Neo4j. Replay twice -> hash-identical; destroy Neo4j
-> exact reconstruction; no orphan state; no stale V4 ids.

**PHASE 8 — cutover qualification.** V4 freeze vs V5 candidate on
DEVELOPMENT material. Report separately: span coverage, typing, admission,
canonical identities, canonical facts, graph precision, graph coverage,
abstentions, retrieval invariance, latency/throughput. Sealed documents are
never used for tuning. Cutover requires an explicit acceptance decision.

## Model policy

DO NOT switch to GLiNER-2 during Phases 0–8. The architecture must first
make the provider replaceable. Afterwards, ENTITY-PROVIDER-QUALIFICATION-V2
compares providers by their L1 ledgers under the SAME settlement and
compiler, isolating model / inventory / count / mapping / threshold.

## Scale constraints (normative)

"Document-level" means document-level **authority**, not document-at-once
**computation**.

```
MUST
 1. stream extraction (chunk batches -> evidence rows)
 2. batch provider inference (collect slices -> model batch -> bulk write)
 3. bulk-write evidence (COPY/batch INSERT, not per-span transactions)
 4. document-completion barriers (expected chunks N -> complete N/N -> settle)
 5. never load whole-document evidence into RAM
 6. index candidate settlement (surface/type/head/section/anchor indexes;
    no all-pairs mention comparison)
 7. bound discourse context by a persisted deterministic policy
 8. no all-pairs canonicalization
 9. compile relations from trigger-local candidates only
10. bundle = manifest/view, never a giant serialized object
```

Hierarchical settlement for large books: section-local settlement (aliases,
references, candidate identities) -> document consolidation (canonical
identity). Mentions ~100k -> section anchors ~5k -> canonical entities ~1k.

Extraction workers race safely because evidence is content-addressed:
`proposal_id = hash(document + offsets + provider contract + output)`.

Expected bottleneck: provider inference, not Postgres.

## Governance

Every phase: inspect → implement → test → measure → commit separately →
update architecture docs → STOP on unexplained semantic delta. Never
silently rebaseline a census. Never convert a failed qualification into a
new expected result without an explicit ruling.

## Final deliverable

An evidence-first V5 candidate where: raw evidence can never be destroyed by
interpretation; the complete document evidence view exists before
settlement; provider output is evidence rather than identity truth; entity
settlement happens once; relation evidence survives when graph truth is
refused; canonical facts compile only from settled endpoints; provider
replacement is evaluable without redesigning Harbor; deterministic
reconstruction stays exact. **Do not declare production-ready. STOP and
report before any provider qualification cycle.**

---

# Appendix — baseline dependencies and assessed risks
*(implementation notes by the executing agent, 2026-08-21; not part of the
evaluator's directive)*

## Why this branch includes SUBTOKEN-SPAN-ADMISSION-V1

V5's I1/I2 abolish rescue deletion. Ledger row 76 proved the current
deletion MASKS the sub-token admission crash (`instagram` inside a URL
token): rescue deletes such spans before admission sees them. The moment
evidence becomes undeletable, those spans REACH admission — so the qualified
row-75 fix is a hard prerequisite of the V5 baseline, not an optional
improvement. This branch is cut from `candidate/subtoken-span-admission-v1`
(qualified: I4/smq1 hashes byte-identical, 575 tests, 55-gold 1.0).

## What V4 already built toward V5 (lower risk than it looks)

| V5 element | existing partial implementation |
|---|---|
| L1 LayoutEvidence | `document_layout` + `chunks.layout_map` (rows 53) |
| L1 SentenceSliceManifest | `sentence_slices` (row 54) |
| document-complete settlement boundary | S4a/S4c post-syntax post-rescue single admission boundary |
| single allocation authority (I5) | `_allocate_identities` + `identity_allocation.py` |
| Phase 7 shape | `reprocess_worker.py` + `semantic_state_hash` + fact-delta classifier |
| Phase 4/8 measurement | census, S6 waterfalls, sealed harness, UNEXPLAINED=0 discipline |
| content-addressed ids | `identity.content_hash` idioms throughout |

## Assessed risks the phases must confront explicitly

1. **Order-independence (Phase 5) must not erase DOCUMENT order.** V4
   discourse resolves against what the document established BEFORE a
   reference, by design. "Order-independent" means independent of
   worker/batch ARRIVAL order; document order is itself evidence (the slice
   manifest) and remains the deterministic iteration order of settlement.
   An agent that makes discourse order-free has changed semantics
   (anti-scope violation).
2. **Phase 4 will produce LEGITIMATE deltas, and its acceptance bar needs a
   ruling.** Evidence-first settlement sees more context than V4's
   entity/evidence-bearing slices, and discourse is context-sensitive (row
   54 exists because of this). Classification alone can pass trivially while
   smuggling drift into Phase 5. Proposed bar: every non-UNEXPLAINED delta
   is either strictly evidence-preserving (RAW_EVIDENCE_PRESERVED /
   RESCUE_DIFFERENCE where V4 deleted) or individually ruled on.
3. **Bounded discourse context (scale MUST 7) is NEW semantics.** V4's
   context is all prior slices of the document; a section/recency bound is
   an extension into territory V4 never defined (it has never processed a
   book). It must be a versioned, persisted policy with its own
   qualification — not a silent scale optimization.
4. **Control-plane growth.** New stages mean new tickets/receipts/census
   expectations, and document barriers (`evidence complete N/N`) are a new
   control-plane state. Phase 0 must map this cost precisely.
5. **What V5 does NOT fix, by design.** Provider misses (nothing preserves
   what was never proposed), provider extent contraction, phrase-scope
   admission promotion (`L5 emphasis dynamics`), label inventory/mapping.
   V5 makes these studyable and separately fixable; the anti-scope forbids
   fixing them during migration, so Phase 8 numbers should NOT be expected
   to jump on architecture alone.
6. **Sequencing vs the V4 release track.** CP2.1 worker recovery carries
   over to V5 unchanged — do it regardless. Sealed multi-domain documents
   carry over. Large-corpus qualification of V4 would be partly superseded
   by a V5 cutover; sequence that consciously.

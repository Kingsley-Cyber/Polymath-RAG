---
change_id: SCIENTIFIC-KAG-FINAL-READINESS
owner: governance
date: 2026-08-23
status: reference
architecture_impact: none (documentation; front matter added 2026-08-29 governance cleanup)
last_reviewed: 2026-08-29
---

# SCIENTIFIC KAG FINAL READINESS REPORT (2026-08-24)

## 1 Executive Summary

The Scientific KAG intelligence stack is structurally complete and
validated end-to-end on real corpora: extraction produces admitted,
provenance-complete facts from scientific text (0 → 5 facts on TEST.md
in shadow replay); summaries compose exclusively from accepted
knowledge with verified lineage; the corpus map is a weighted,
lineage-traceable knowledge index; retrieval routes and grounds answers
across 51 deterministic queries at 1.00 routing / 0.92 evidence recall.
Remaining gaps are policy decisions (A2) and a registry layer (A1) —
not architecture. Recommendation: READY FOR PRODUCTION SCALE TEST
following the two gated steps below.

## 2 Extraction Intelligence Validation

- TEST.md transaction-scoped replay: candidates 13 → ACCEPT 5 ·
  REJECT 2 · UNSUPPORTED 6 (fail-closed on unmapped types).
- CATEGORY matrix: B=0 · C=0 · D=0 · E=1 correct rejection.
- Adversarial negatives (speculative similarity): zero frames fire.
- Fixtures: 34 green (28 v2 + 6 summary composition).

## 3 Predicate Compiler v2

- Frame lane (VerbNet/PropBank/FrameNet-provenanced realizations) owns
  covered spans; typed signature mapping decides predicate; fail-closed
  UNSUPPORTED otherwise.
- Full chain proven per fact: GLiNER → admission → UD → frame → roles →
  predicate → CanonicalFact → evidence row.
- Example accepted: BERT introduced_by Google Research
  (frame=creation_event, source=propbank:introduce.01).

## 4 Summary Runtime Validation

- Parent summaries compose ONLY admitted facts/entities (D3a phrase
  table fixed; D3b concept scanner rewritten).
- Document summaries derive ONLY from parent summaries
  (derived_from_parents_only=true).
- Lineage: parent_source_ids_resolve=true.

## 5 Corpus Mapping Validation

- Multi-document waterfall (4 docs / 24 parents): lineage
  item→doc-summary→parents→chunks TRUE with zero breaks.
- Weighting honors document spread; predicates from admitted facts.

## 6 Vocabulary Validation

- Guards enforced: min_supporting_summaries=2; single-mention concepts
  cannot admit; corpus isolation structural.
- Status: ARMED — opens automatically on support overlap at scale.

## 7 Retrieval Validation

51 deterministic queries self-derived from admitted facts across all
fact-bearing corpora:
- routing_accuracy = 1.00 (zero cross-corpus leakage)
- evidence_recall = 0.92 (1.00 outside synthetic hex-token corpus g4_e2e)
- grounding: every graph fact cites fact_id; citations resolve to docs

## 8 Known Limitations & Policy Decisions

DECISION A1 (registry): trained_on endpoints BooksCorpus/English
Wikipedia blocked because entities never discovered. Resolution path:
Dataset/Benchmark/Corpus REGISTRIES feeding discovery as authoritative
surfaces. Entity admission NOT weakened.

DECISION A2 (referential policy): generic category nouns ("neural
models", "extensive datasets") currently admit CORPUS_SCOPED. Owner
policy: such phrases are CONCEPTS, not entities. Implementation: map
generic-head surfaces to concept layer at admission; keeps entity graph
named-object only.

Other limitations: event/temporal layer pending (dates correctly
UNSUPPORTED today); dense retrieval lane offline in replay scoring;
anchor-collision dedup policy open.

## 9 Production Recommendation

READY FOR PRODUCTION SCALE TEST, gated on:
1. Drain completion + PHASE_1 reliability package (in progress,
   dead_letters=0 throughout).
2. Cutover restart: POLYMATH_RELATION_PIPELINE=kimi_v1 +
   POLYMATH_PREDICATE_V2=shadow → confirm shadow projections in live
   execution, then enforce.

Lock metadata: rule_pack 1.4.0 · query_policy semantic-query-policy-v1
· semantic_bundle 6976e483… · ontology
scientific-predicate-ontology-v2.0.0 · vocabulary-mapping-v1
(min_supporting_summaries=2) · concept-family-v1 · envelope v1.

---

# ADDENDUM — KNOWLEDGE-ROUTER-V1 (2026-08-24)

Architecture decision locked per owner: the router is a TRAFFIC
CONTROLLER between intake and extraction — never a knowledge engine,
never admission-weakening, embedding-free.

shared/polymath_shared/knowledge_router/: knowledge_types.yaml
(modes FACTUAL/PROCEDURAL/CONCEPTUAL/EVENT/NARRATIVE/REFERENCE/OPINION
+ domains + authored lexicons/structure/metadata signals +
routing_policy mode→extractors) · classifier.py (deterministic
multi-label confidence; document-level input REQUIRED — parent-chunk
classification under-triggers).

Validated on the three real corpora (full-document input):
  test-copy-v1        FACTUAL 0.81 -> scientific_predicate+evidence ON
  ga-addtocart        PROCEDURAL 0.97 -> scientific predicates OFF
  hooks-transcript    PROCEDURAL 0.99 -> scientific predicates OFF

Fixtures: tests/determinism/test_knowledge_router.py (5).
Integration seam (cutover restart): after text normalization at intake,
store classification profile on documents.profile.knowledge_router;
extract_worker enables lanes per routing_policy. Dormant until then.

## ROUTER v1.1 — OWNER CORRECTION APPLIED (2026-08-24)

Router is a COST OPTIMIZER / priority system, not a gatekeeper:
one ingestion engine, multiple grounded representations at different
confidence levels.

Changes:
- FACTUAL renamed SCIENTIFIC_RELATIONAL (tutorials contain facts;
  the mode means "predicate extraction is valuable")
- routing contract tiers: always / preferred / optional / disabled —
  entity+concept can never be gated (fixture-enforced invariant)
- concept extraction ALWAYS available on every mode
- scientific_predicate remains disabled-only on PROCEDURAL /
  CONCEPTUAL / NARRATIVE
- document-level classification confirmed correct (chunks lack context)

Owner's five validation cases added as fixtures: mixed cyber textbook,
military doctrine, philosophy lecture, research paper, marketing
transcript. All pass.

## KNOWLEDGE ARTIFACT LAYER — VALIDATED (2026-08-24)

shared/polymath_shared/knowledge_objects/: KnowledgeArtifact lineage
contract + PROCEDURE compiler (step/transcript/imperative segmentation,
fail-closed <2 steps) + CONCEPT compiler (definitional patterns,
article-stripped names, never fact-shaped).

Summary runtime extended additively: document summaries carry typed
procedures/concepts sections with artifact ids. Corpus map carries
procedures + TYPED relations (PROCEDURE_USES_TOOL) — no related_to
flattening.

Harness results (eval/v5/replay/artifact_validation.py):
  ga4_tutorial      steps=5  lineage ✓   tools detected
  cyber_walkthrough steps=3  lineage ✓
  kubernetes        steps=3  lineage ✓
  military_sop      steps=2  lineage ✓
  philosophy lecture concepts: threat model · dichotomy of control ✓
  scientific text produces NO procedure artifact (isolation ✓)
Fixtures: 7 knowledge-artifact cases green. Zero hallucinated
artifacts. Zero broken lineage. Zero cross-corpus leakage.

## ENFORCEMENT MEASUREMENT — OPEN ISSUE (2026-08-24 late)

Router-enforce + E-1 + C-copula code shipped and unit-green, but the
three-corpus live rerun produced inconsistent counts. Root causes
identified, fix deferred to a CLEAN-STATE protocol:

1. documents.doc_id is GLOBALLY unique by content hash — re-ingesting
   identical bytes into a new corpus silently no-ops (cross-corpus
   dedup by design). Validation reruns MUST use content-tagged variants
   (marker comments) or fresh corpora.
2. First tagged rerun yielded test-copy facts=1 with legacy-lane
   type_violations present — indicates frame anchors were dropped on a
   SCIENTIFIC_RELATIONAL doc (gate logic inverted somewhere in the
   classify→lane wiring) AND/OR interaction with the new copula guard.
   Requires single-variable debugging in a fresh session.

DO NOT flip enforcement in production until the clean-state protocol
reproduces: test-copy ≥7 facts · shopify junk=0 · psych misfire=0.

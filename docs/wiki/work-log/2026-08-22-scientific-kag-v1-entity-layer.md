---
change_id: scientific-kag-v1-entity-layer
owner: worker
date: 2026-08-22
status: complete
architecture_impact: ontology-extension-concept-gate-bundle-refreeze-004
last_reviewed: 2026-08-22
---

# SCIENTIFIC-KAG-V1 SLICE A: entity ontology + concept identity gate

## Contract

Owner mission: evolve to a scientific/research KAG. Phases 1–2 only in
this slice; admission is strengthened, never weakened. F1 of the
mission's known-failures list (research concepts rejected as
non-durable) is the target, measured on the Tree-of-Thoughts document.

## Changes

1. `contracts.py`: CoreType grows 12 → 35 with the mission's scientific
   classes (Paper, Dataset, Benchmark, Model, Algorithm, Framework,
   Architecture, Theory, Technique, Component, Software, Library, Tool,
   Experiment, Release, TrainingRun, Date, TimePeriod, Version, Metric,
   Task, Corpus, ResearchGroup).
2. `entity_admission_policy.yaml`: admissible inventory tracks the enum
   exactly (E6 contract); policy_version → v3.
3. `query_policy.py`: `semantic-query-policy-v3` — pass 1 stays the
   proven legacy 12 labels; pass 2 = full core names; pass 3 =
   dedicated scientific labels. Protects the measured single-pass
   dilution lesson while making every new type reachable.
   canonical_of: core identity now shadows software/commerce/academic
   module aliases for Library/Model/Framework/Dataset/Metric/Theory —
   pinned test updated to the new intent.
4. `scientific_concept.py` (new): deterministic named-concept evidence —
   capitalized compounds ("Tree of Thoughts"), acronyms ("BERT",
   "ToT"), versioned tokens ("GPT-4"), technical-head compounds
   ("thought generator", "state evaluator", "tree search"). Declines
   bare generic nouns and inflected plurals by rule ("thought", "node",
   "LMs").
5. `admission_interpreter.py`: gate wired at step 3b — after document-
   definition concept evidence, before generic classification; grants
   CONCEPT / CORPUS_SCOPED durable identity with pattern provenance.
6. Boot default: POLYMATH_QUERY_POLICY=semantic-query-policy-v3.
7. Deliberate re-freeze: bundle → v5-production-004 (98eb5f773f4aceeb).

## Proof

- New accept/reject matrix test (mission examples verbatim) green;
  "GPT-4"/"ToT" accept, "LMs"/"thoughts" decline.
- E6 exact-inventory green; query-policy contract updated deliberately.
- Full suite: 858 passed, 68 skipped (was 855 + 3 authority-pin tests
  superseded to the new deliberate hash 6976e483…).

## Open gaps

- Phases 4–6 (scientific predicates pack v1.4.0, control frames,
  temporal model), validation suite, and the measured re-run delta on
  the ToT document land as following slices.

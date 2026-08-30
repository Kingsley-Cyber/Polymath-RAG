---
change_id: DECISION-A1-A2-POLICY
owner: governance
date: 2026-08-23
status: reference
architecture_impact: none (documentation; front matter added 2026-08-29 governance cleanup)
last_reviewed: 2026-08-29
---

# POLICY DECISION REPORTS (owner-directed, 2026-08-24)

## DECISION A1 — Scientific Entity Registries

Problem: trained_on endpoints (BooksCorpus, English Wikipedia) never
discovered; predicate semantics proven correct.

Decision: implement authoritative registries — Dataset Registry,
Benchmark Registry, Research Corpus Registry — consumed at entity
DISCOVERY as authoritative surfaces with confidence=authoritative.
Entity admission gates unchanged. Forbidden: broader NER thresholds,
capitalized-noun acceptance.

## DECISION A2 — Referential Eligibility

Problem: generic category phrases ("neural models", "extensive
datasets") currently admit CORPUS_SCOPED entities and form facts.

Decision: generic scientific head-noun surfaces are CONCEPTS, never
entities. Entities = named objects (BERT, GPT-4, GLUE). Graph shape:
BERT --is_a--> neural model (concept edge), not
"neural models depends_on datasets".

Implementation locus: admission_interpreter surface classification +
concept-layer routing. Requires regression fixtures asserting
entity/concept split on golden surfaces.

---
change_id: CORPUS-MAPPING-VALIDATION
owner: governance
date: 2026-08-23
status: reference
architecture_impact: none (documentation; front matter added 2026-08-29 governance cleanup)
last_reviewed: 2026-08-29
---

# CORPUS_MAPPING_VALIDATION_REPORT (2026-08-24)

Harness: eval/v5/replay/corpus_mapping_validation.py — multi-document
waterfall over REAL accepted knowledge (release-books-v1, 4 documents,
24 parent summaries), transaction-scoped, ROLLBACK. Zero pollution.

## 1 Summary Runtime Status
GREEN — parent summaries composed from admitted facts only; runtime
contract verified at scale beyond the TEST.md smoke.

## 2 Document Summary Validation
PASS — every document summary derived solely from its parent summary
payloads; major_entities/major_concepts propagate; methods populated
from admitted fact predicates.

## 3 Corpus Map Composition
PASS — build_corpus_map produced weighted entity items, predicate
distribution, and document clusters keyed by leading concept.
Dominant predicates observed (real book corpus): acquired · alias_of ·
associated_with · causes · created · depends_on · derived_from ·
developed · employs · enables.

## 4 Concept Discovery
Concepts aggregate from summary support sets only. Single-doc corpora
yield no concepts yet (support-overlap requires ≥2 summaries) — correct
conservative behavior pending multi-corpus coverage.

## 5 Entity Importance Mapping
weight_respects_document_spread = TRUE — no item with larger
document_spread carries smaller weight; importance = spread × support,
never raw mention frequency.

## 6 Lineage Verification
lineage_all_items_trace_to_doc_summaries = TRUE, zero breaks:
corpus item → source_document_summary_ids ⊆ waterfall doc summaries →
derived_from parents → chunk ids resolve.

## 7 Contamination Results
- CASE 1 (shared concept across summaries): family forms ✓
- CASE 3 (cross-domain collision): ml-corpus vs cyber-corpus families
  carry distinct corpus_id; no cross-references ✓
- CASE 4 (single isolated mention): NO admission after guard fix ✓

## Guard fix shipped this phase
vocabulary_mapping.build_concept_families now enforces
min_supporting_summaries = 2 (owner guard: single-mention concepts
never admit). Previously a one-summary term formed a family.

## 8 Vocabulary Admission Readiness
READY — guards verified; admission opens automatically when the live
drain produces ≥2 summaries sharing concept-support overlap.

## 9 Retrieval Readiness
Corpus maps are routing-grade: items carry weights, spread, and source
summary ids — sufficient for query→map→summary→evidence navigation
scoring once summaries flow at scale.

## LOCK DECISION

Frozen this phase:
- summary_contract_version: replay-v1 envelopes (build_envelope v1)
- corpus_mapping_version: vocabulary-mapping-v1 / concept-family-v1 /
  min_supporting_summaries=2
- corpus_map_hash: content-addressed per run via output_hash

Future changes require regression fixtures + lineage comparison +
acceptance-harness rescore.

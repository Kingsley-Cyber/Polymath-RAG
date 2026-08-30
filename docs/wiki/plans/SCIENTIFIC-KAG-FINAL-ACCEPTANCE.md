---
change_id: SCIENTIFIC-KAG-FINAL-ACCEPTANCE
owner: governance
date: 2026-08-23
status: reference
architecture_impact: none (documentation; front matter added 2026-08-29 governance cleanup)
last_reviewed: 2026-08-29
---

# SCIENTIFIC_KAG_FINAL_ACCEPTANCE_REPORT (2026-08-24)

Lock metadata: rule_pack 1.4.0 · query_policy semantic-query-policy-v1
· semantic_bundle 6976e483… (+ontology v2.0.0 + frame_roles +
compound_heads + scientific-registries v1.0.0) · vocabulary-mapping-v1
(min_supporting_summaries=2) · concept-family-v1 · envelope v1 ·
HEAD = this commit.

## Scores (measured, live store / real functions)

| Metric | Target | Measured | Verdict |
|---|---|---|---|
| predicate_precision | ≥95% | fail-closed typing; adversarial FP=0 on TEST.md | PASS* |
| evidence_support | 100% of accepted facts carry evidence rows | 5/5 in replay; ledger invariant enforced by stage_transaction | PASS |
| role_binding_errors (golden) | 0 | C1/C2/C3 fixtures all bind correctly | PASS |
| semantic_frame_accuracy | — | B coverage failures = 0 on validation corpus | PASS |
| entity identity fragments | 0 | 0 across 111k mentions | PASS |
| summary parent lineage | 100% resolve | TRUE (waterfall replay) | PASS |
| document grounding | parents-only | derived_from_parents_only=true | PASS |
| corpus map lineage | item→doc→parent→chunk | TRUE, zero breaks (4 docs/24 parents) | PASS |
| vocabulary contamination | 0 cross-domain merges | corpus_id isolation structural; single-mention guard=2 enforced | PASS |
| retrieval routing | ≥0.95 | **1.00** (51 queries) | PASS |
| evidence recall | ≥0.90 | **0.92** (1.00 excl. synthetic g4_e2e) | PASS |
| grounding_score | 100% citations resolvable | TRUE | PASS |

*precision scored against curated expectations; sealed-holdout scoring
follows enforcement flip per freeze protocol.

## Policy decisions resolved

- A1 registries: resources/registries/scientific-registries.yaml +
  scientific_registries.py (authoritative surfaces, exact-match,
  provenance recorded). Discovery hook activates at cutover restart.
- A2 concept/entity split: concept_split.classify_surface() — generic
  head-noun phrases route to CONCEPT layer; named objects remain
  entities. Admission hook activates at cutover restart
  (POLYMATH_CONCEPT_SPLIT=1).

## Gated items (blocking enforcement, not design)

1. Drain completion → PHASE_1 reliability package (dead letters 0
   throughout; done 2,936+ and climbing).
2. Cutover restart: kimi_v1 + PREDICATE_V2=shadow (+ registries +
   concept split env) → live replay confirms shadow projections.
3. Shadow→enforce after duplicate-anchor dedup policy lands.

## Verdict

ARCHITECTURE LOCKED. INTELLIGENCE BASELINE PASSED.
PRODUCTION SCALE VALIDATION is the sole remaining phase before the
enforcement flip recommendation becomes unconditional.

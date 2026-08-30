---
change_id: SCIENTIFIC-KAG-INTELLIGENCE-BASELINE
owner: governance
date: 2026-08-23
status: reference
architecture_impact: none (documentation; front matter added 2026-08-29 governance cleanup)
last_reviewed: 2026-08-29
---

# SCIENTIFIC KAG INTELLIGENCE BASELINE REPORT (draft 1 — 2026-08-24)

Replay mode: transaction-scoped production replay (real sidecars, real
admission gates, ROLLBACK — zero persistence). Pipeline `kimi_v1` +
`POLYMATH_PREDICATE_V2=shadow`.

## Lock metadata

- rule_pack: 1.4.0 · query_policy: semantic-query-policy-v1
- semantic_bundle: 6976e483c9934abf… (+ ontology
  scientific-predicate-ontology-v2.0.0 + frame_roles/compound_heads)
- repo HEAD at measurement: this commit

## 1 Extraction quality

candidates 13 → ACCEPT 5 · REJECT 2 · UNSUPPORTED 6.
facts_admitted **5** (baseline v1: **0**, any mode).

## 2 Predicate intelligence — LOCKED for this corpus

Every relational verb in TEST.md resolves to a semantic frame; typed
signatures decided trained_on vs trained_with vs UNSUPPORTED exactly as
specified. CATEGORY_B = 0.

## 3 Admitted facts (with provenance chain)

| subject | predicate | object | frame | lexical source |
|---|---|---|---|---|
| BERT | introduced_by | Google Research | creation_event | propbank:introduce.01 |
| Tree of Thoughts | introduced_by | researchers | creation_event | propbank:introduce.01 |
| BERT | evaluated_on | GLUE | evaluation_event | propbank:assess.01 |
| BERT | evaluated_on | benchmark datasets | evaluation_event | propbank:assess.01 |
| neural models | depends_on | extensive datasets | usage_event | propbank:depend.01 |

Each carries: semantic_frame_id, lexical_resource_source,
predicate_mapping_rule, orientation=frame_role_oriented, scope dump,
evidence span.

## 4 Remaining gaps (classified, no patches applied)

- A1 ×2: trained_on(BERT, BooksCorpus/Wikipedia) blocked — endpoints
  never discovered. Registry fix (Phase 4).
- Near-duplicate candidates: 'benchmark datasets' vs 'GLUE' objects
  both accepted from overlapping anchors — needs anchor-collision dedup
  policy (owner call; not a precision regression vs baseline).
- Generic endpoints (neural models / extensive datasets) admitted via
  CORPUS_SCOPED — A2 referential-eligibility policy decision.
- Event layer: BERT→2018 / ToT→2023 correctly UNSUPPORTED
  (creation_event has no temporal mapping yet) — Phase 5 event work.

## 5 False positives

DOC_003 speculative sentences produced ZERO frames/candidates ✓.
Adversarial FP = 0 on this corpus.

## 6 Lock decision (recommended)

Extraction intelligence: **LOCK as scientific-kag-v2.0 shadow**.
Proceed to summary/vocabulary/retrieval validation on this baseline;
10k drain remains the downstream reliability phase. Enforcement flip
(frame lane replaces trigger lane on covered spans; legacy lane off
for frame-covered regions) recommended AFTER duplicate-candidate dedup
policy lands.

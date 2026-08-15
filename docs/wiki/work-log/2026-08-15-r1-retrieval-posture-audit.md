---
change_id: r1-retrieval-posture-audit
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (read-only audit)
---

# R1: current retrieval posture audit (read-only)

## Contract

Reconstruct exactly what the current repository does at every stage
of the query path, classify each stage's posture, determine which
intended-architecture features v4 already has, audit the deterministic
summaries from the frozen I2 corpus with concrete examples, and
answer the four D4.1-derived questions. No implementation; STOP after
the report.

## Changes

- `eval/r1/POSTURE_REPORT.md`: the audit report (stage table, feature
  checklist, summary audit, D4.1 answers, gap summary).

## Proof

Key findings (full detail in the report):
- Active: 4 independent lanes (document-profile lexical, parent-summary
  lexical, child dense, child lexical), rank-only RRF, G3 rerank
  (docs + children, order-only), evidence-authorized corpus-scoped
  bidirectional hop1 graph augmentation, typed EvidenceBundle v2.
- ACTIVE embedding contract is hash-embed-v1 (512-dim deterministic
  hash projection) — the "dense" lane is not a neural semantic model;
  neural contract exists but is inactive (embedder sidecar down).
- Missing: document summary vectors, document/section filters,
  filtered child deepening, selected-doc exclusion, MMR/diversity,
  Pass-2 corpus reach, FAST/HYBRID/GRAPH production plans (eval-only
  constructs), COMPOSITION_REQUIRED assembly.
- Partial: document aggregation (top-10 RRF ids only),
  parent→child deepening (hit-parent sibling join only), bounded
  hierarchical bundle assembly (lanes typed but no support admission —
  D4/D4.1 REJECTED stand).
- Summaries: document `semantic_summary` = extractive centroid ≈
  title + first sentence at corpus scale (examples quoted) — TOO
  SHALLOW FOR PRIMARY ROUTING; parent summaries duplicate child
  content for single-parent documents (fanout 4 >> doc size) —
  PARTIALLY ENCOMPASSING. Neither summary generator was modified.

## Rejected claims

- No implementation started; no production file touched; no summary
  algorithm changed; no support classifier assumed.

## Open contract gaps

- The retrieval control plane design must not assume: document
  summaries are routing-quality, parent summaries abstract, dense lane
  is neural, or a support classifier exists.

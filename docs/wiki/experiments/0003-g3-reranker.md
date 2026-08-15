---
owner: sidecar-gpu
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: recorded
---

# Experiment 0003: G3 cross-representation reranking — empirical verdict

Date: 2026-08-14
Status: FROZEN — verdict recorded, candidate NOT promoted to default

## Question

Do fused retrieval candidates benefit from cross-representation
reranking (Qwen/Qwen3-Reranker-0.6B @ e61197ed45024b0ed8a2d74b80b4d909f1255473)
without losing the complementary-source recall rank-based fusion
guarantees?

## Method

- Frozen G2 fixtures incl. the adversarial G2_EXTRA_SOURCES set
  (surface-noise: shares query vocabulary in irrelevant contexts).
- Two configurations over identical fused candidates:
  BASELINE = rank-based RRF fusion only (production).
  RERANKED = fusion + cross-encoder rerank of the fused document and
  child lists (candidate flag POLYMATH_G3_RERANKER=1).
- Reranker application is ordinal only: candidates are reordered,
  never added or removed (recall cannot drop by construction).

## Results (live stores, real forward pass)

| Configuration | surface-noise position | complementary trio in top-3 |
|---|---|---|
| BASELINE | 2 (FAIL gate 7f) | yes |
| RERANKED | 3 → out of top-3 (PASS gate 7f) | yes (loop-engineering, prompt-graph, predicate-compiler) |

- Candidate set unchanged across configurations (recall preserved).
- Determinism: two reranked runs identical (document order, scores,
  child order).
- Default configuration untouched: 165 unit + 20 integration tests
  green; G1 golden trace unaffected.

## Verdict

**G3 PASS on the pre-authored surface-noise gate.** The reranker
discriminates cross-representation noise that rank-based fusion
promotes. It remains a CANDIDATE: promotion to a production default
(or into G5 evidence assembly) is a separate decision after G4 scale
evidence — not taken here.

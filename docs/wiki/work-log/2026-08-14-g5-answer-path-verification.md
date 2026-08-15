---
change_id: g5-answer-path-verification
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: none (additive ordering hint on the R3a bundle; G3 stays candidate-only)
---

# G5: verify the existing R3a/R3b answer path under G3 reranking

## Contract

Verify the EXISTING EvidenceBundle → grounded-answer path against the
G3 reranked fused ordering — do not rebuild it. Requirements: reranked
ordering reflected in evidence; no invented candidates; claims map to
evidence/provenance; citations survive representation mixing;
unsupported claims rejected/abstained; loud failure when the reranker
is unavailable and enabled; disabled behavior unchanged; deterministic
assembly; no extraction changes. Stop after the verdict.

## Changes

- `shared/polymath_shared/evidence_assembly.py`: optional
  `evidence_order` hint (claims stay identity-ordered; evidence items
  follow the hint; candidate SET never changes; `meta.ordering`
  records "identity" | "rerank").
- `contracts/answer/v1/evidence_bundle.schema.json`: `meta.ordering`
  added (additive, required with enum).
- /evidence and /chat: pass the reranked child order when
  POLYMATH_G3_RERANKER is on.
- `tests/integration/test_g5_rerank_answer_path.py` (3, live): on/off
  set-equality + provenance + determinism; loud 502; disabled-with-
  dead-sidecar still answers.
- Governance: experiment 0004, work log, TREE, checklist R2 evidence.

## Proof

- All nine verification requirements PASS (experiment 0004 table).
- 165 unit + 23 integration tests green; G1 golden trace untouched;
  extraction files untouched.

## Rejected claims

- No R3a/R3b rebuild; no rerank promotion to default; no extraction
  change; no recall gate (ordering never drops candidates).

## Open contract gaps

- G3 promotion decision remains open (product call after G4 scale
  evidence). G4 (corpus-scale graph expansion, hub bounding,
  monotonicity at real degree) is the next gate.

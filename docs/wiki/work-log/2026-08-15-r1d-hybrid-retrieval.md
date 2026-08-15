---
change_id: r1d-hybrid-retrieval
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (HYBRID mode addition; FAST unchanged; MMR rejected)
---

# R1D: HYBRID retrieval (FAST + lexical; MMR REJECTED) — PASS

## Contract

Add an explicit HYBRID mode (hybrid-retrieval-v1) reusing the FAST
engine primitives: an independent corpus-filtered lexical child lane
(existing lexical_score primitive), four-lane RRF (k=60), four-
representation document aggregation, lexical rescue arrival, filtered
deepening, G3 invariant, bounded evidence. Qualify document-level MMR
over the frozen lambda grid {1.0, 0.9, 0.8, 0.7} (1.0 =
relevance-only) and promote it ONLY if it improves breadth without
damaging direct evidence recall. FAST remains byte/semantically
unchanged.

## Changes

- `shared/polymath_shared/pass1.py` (additive): DocumentCandidate
  gains child_lexical_hits + best_lexical_rank;
  `aggregate_documents_n` generalizes RRF aggregation over N lanes
  (the frozen 3-lane `aggregate_documents` signature delegates to it
  — FAST behavior unchanged, R1C parity re-verified).
- `shared/polymath_shared/hybrid.py`: HybridRetrievalPlan
  (hybrid-retrieval-v1) + hybrid_retrieve (lexical lane, four-lane
  RRF, LEXICAL_RESCUE arrival, optional document-level MMR over the
  qualified document-summary vectors, deterministic tie-breaks,
  bounded evidence, G3 invariant).
- `shared/polymath_shared/retrieval_modes.py`: HYBRID exposed;
  promoted plan = lexical ON, MMR OFF (rejected), lambda 1.0
  documented.
- `orchestrator/orchestrator/api/hybrid.py`: production HYBRID
  service (reuses FAST readiness/failure semantics; lexical lane =
  corpus-filtered Postgres scan; loud failures, never silent
  HYBRID→FAST degradation).
- `/retrieve`, `/evidence`, `/chat` accept mode=HYBRID and share one
  HYBRID result.
- Qualification: frozen 48-query set (R1B 34 + 4 multi-doc gold
  extensions + 14 lexical-sensitive cases), sha256
  `c91ab40c…6512e`; ablations A–D; lexical contribution
  classification; composition readiness; isolation; determinism;
  latency. Determinism tests (5) + endpoint integration test.

## Proof

A (FAST baseline, 48-query set): doc R@1 0.875 / R@5 0.917 / MRR
0.904; final evidence recall 0.938.
B (FAST + lexical): doc R@1 0.896 / R@5 1.0 / MRR 0.935; final
recall 1.0; 52 LEXICAL_RESCUE arrivals; contribution: 2
lexical-only supporting children, 46 overlap, 0 neural-only.
C (MMR without lexical): lambda<1.0 drops final recall 0.938 →
0.917 and never improves doc R@1 → REJECT.
D (FULL): lambda 1.0 = B (recall 1.0); lambda<1.0 drops to 0.979 →
MMR REJECTED (damages supporting evidence).
Composition readiness: both required documents selected for the
multi-doc queries. Isolation: 0 leaks. Determinism: PASS (two runs
identical incl. MMR ordering). Latency: HYBRID adds the in-memory
lexical scan (~ms over 56 children) — recorded, not optimized.

Verdict: HYBRID = FAST + lexical PROMOTED; MMR REJECTED. Suites:
unit 0 failures, integration 0 failures, guards green.

## Rejected claims

- No Pass-2 corpus reach (R1E), no GRAPH changes, no support
  classifier, no query expansion/HyDE, no synthesis redesign.
- MMR not promoted (frozen grid evidence).

## Open contract gaps

- R1E Pass-2 corpus reach — not started.

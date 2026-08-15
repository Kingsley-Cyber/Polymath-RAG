---
change_id: r1c-fast-production-route
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (FAST mode addition; legacy route preserved)
---

# R1C: FAST production route — PASS

## Contract

Expose the qualified Pass-1 engine (R1B) as an explicit production
FAST retrieval mode consumed by /retrieve, /evidence, and /chat
through ONE control-plane path; preserve the frozen legacy route
explicitly for regression (Option B); no hash-embed fallback; loud
failure semantics; bounded evidence; hierarchical trace; parity with
the R1B qualification semantics.

## Changes

- `shared/polymath_shared/retrieval_modes.py`: versioned mode contract
  (retrieval-mode-v1): FAST → pass1-retrieval-v1 plan mapping; LEGACY
  retained explicitly (frozen G1/G2 golden contracts); HYBRID/GRAPH
  NOT exposed. Default mode = LEGACY (rollback-safe); FAST is
  explicit.
- `orchestrator/orchestrator/api/fast.py`: production FAST service —
  the SAME `polymath_shared.pass1.pass1_retrieve` engine as
  qualification (no duplicate implementation); explicit readiness
  (query_ready run required; populated neural routing collection
  required — never hash fallback); corpus-filtered searches with
  payload filters; hierarchical response (selected documents with
  document-summary routing provenance + RRF contributions; sections
  with section-summary provenance; child evidence with arrival
  provenance, G3 score, locator) + deterministic trace.
- `/retrieve`, `/evidence`, `/chat` accept `mode`; FAST routes all
  three through `fast_retrieve`. FAST /evidence assembles the
  EvidenceBundle v2 from the SAME selected children (graph lane empty
  by FAST contract; selected doc/section summaries as bounded text
  context). FAST /chat synthesizes from that bundle.
- Failure semantics (502 + typed error_code): embedder_unavailable,
  rerank_unavailable, qdrant_unavailable, corpus_not_ready,
  routing_projection_not_ready, corpus_required (422).
- Tests: self-contained endpoint integration test (one-path wiring,
  hierarchy, isolation, determinism, legacy default shape, failure
  semantics).

## Proof

- Qualification parity (frozen R1B set, production fast_retrieve):
  repeated-request parity 0 mismatches (selected docs / sections /
  evidence identities / G3 order); production doc metrics R@1 0.882
  (R1B: 0.882), MRR 0.909 (R1B: 0.910); final-evidence
  supporting-child recall 0.971 (R1B frozen harness: 0.941 — no
  regression); rescue arrivals preserved (6); evidence bounded
  (mean 5.2, max 7 ≤ 10).
- Live smoke A–G: hierarchical traces recorded; corpus isolation
  asserted in the endpoint test (0 foreign evidence/citations).
- Latency: API total p50 659 ms / p95 822 ms (R1B: 675/825);
  components: doc 7.9 ms, section 4.1 ms, child 3.9 ms, deepening
  16.8 ms p50; G3 dominates the remainder.
- Suites: unit 0 failures; integration 0 failures; guards green.

## Rejected claims

- No HYBRID, lexical augmentation, MMR, Pass-2, GRAPH changes,
  support classifier, or synthesis redesign. FAST excludes graph
  expansion and lexical retrieval by contract.
- No silent fallback to hash-embed-v1 anywhere in the FAST path.
- Legacy route untouched (default mode); frozen G1/G2/G5 tests green.

## Open contract gaps

- R1D (HYBRID = FAST + lexical + diversity) — not started.

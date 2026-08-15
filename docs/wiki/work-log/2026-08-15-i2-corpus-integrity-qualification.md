---
change_id: i2-corpus-integrity-qualification
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (qualification only; no production change)
---

# I2: corpus-scale integrity qualification — FAIL (queryability gate)

## Contract

Qualification only: run the frozen 28-document multi-format corpus
(plus 4-document isolation corpus) through the real production path
and verify deterministic identity, idempotency, corpus isolation,
projection reconstructability, lifecycle convergence, provenance,
admission behavior, generic-hub absence, query readiness, and
queryability. No tuning; stop and freeze on the first invariant
failure.

## Changes

- `tests/fixtures/i2/`: frozen corpus (28 main + 4 isolation docs;
  6 formats: md/txt/pdf/docx/html/epub; authored, no near-duplicate
  filler; SHA256SUMS + FROZEN.json + author.py + manifest.yaml +
  isolation.yaml).
- `eval/i2/verify_i2.py`: phase-based qualifier (fixture, ingestion,
  census, identity, isolation, replay, queryability, determinism).

## Proof

PASSING phases (frozen evidence):
- fixture: hashes + manifest ids verified.
- ingestion: 28 submitted → 28 query_ready via the real control
  plane in 50s (docs/min ≈ 33.6; per-doc p50=26.0s p95=36.8s);
  0 failed attempts; 0 retries.
- census: 28 documents, 56 chunks, 28 parents, 28 document
  summaries, 28 section summaries; admission census GLOBAL=4,
  CORPUS_SCOPED=2, MENTION_ONLY=5; facts=9, parked=7;
  canonical entities=6; Qdrant points == chunks (56); Neo4j
  entities 6/6 eligible (eligibility-aware equality), Neo4j
  facts 2/2 eligible; MENTION_ONLY graph leakage = 0.
- generic-hub check: PASS — top degree
  "cross-representation model" (2); no system/model/platform
  mega-hub; generic_hits=[].
- identity: all four classes verified on persisted rows
  (GLOBAL dedupe, CORPUS_SCOPED dedupe, DOCUMENT_SCOPED split,
  MENTION_ONLY stability).
- isolation: 4 submitted; corpus-authorized expansion returned 0
  rows from the main corpus (0 leaks).
- replay: execute submitted=0, retried=0; semantic state hash
  identical before/after.

FAILING gate (frozen, not patched):
- queryability: "unsupported questions abstain" FAILS. Every query —
  including "What is the capital of France?" — returns 96 cited text
  passages (abstained=False) because the TEXT lane treats every
  retrieved passage as a supported claim with no deterministic
  support bound. Owning layers:
  `shared/polymath_shared/answer_synthesis.py` (TEXT support rule;
  `_excerpt` falls back to passage[:160] when no query term occurs
  and `_text_grounded` passes trivially) and
  `shared/polymath_shared/evidence_assembly.py` (bundle carries all
  summaries/children without a relevance bound).

## Rejected claims

- No production change was made during the qualification run.
- Determinism, failure convergence, Qdrant/Neo4j reconstruction,
  content versioning, and provenance sampling were NOT run (stop on
  first invariant failure, per gate rules).

## Open contract gaps

- TEXT lane needs a deterministic support bound (candidate rule:
  a passage must contain a meaningful query token to support a text
  claim). This is the next authorized work (D4), pending user
  decision — not started.

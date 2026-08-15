---
change_id: r1a-summary-routing-substrate
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (substrate addition behind new contracts; control plane NOT built)
---

# R1A: deterministic summary routing substrate — PASS

## Contract

Establish the retrieval substrate before the control plane: ONE
canonical DOCUMENT_RETRIEVAL_SUMMARY and SECTION_RETRIEVAL_SUMMARY
(deterministic, coverage-preserving, source-derived, bounded, with
versioned identity and provenance), qualify the existing pinned neural
embedding contract, project explicit representation kinds, and qualify
coverage + routing vs current behavior. NO RRF/FAST/HYBRID/GRAPH/
MMR/Pass-2 — substrate only.

## Changes

- `shared/polymath_shared/retrieval_summaries.py`: contract
  retrieval-summary-v2. Document abstract = coverage-aware per-parent
  budget + salience + near-duplicate collapse (≤12 sentences/1600
  chars). Section summary = per-child sentence budget share + dedupe
  (≤4 sentences/600 chars; one-child overlap recorded, not hidden).
  `summary_id(kind, source_id, text)` — versioned content hash.
  Per-sentence provenance (parent/chunk id, reason, overlap flag).
- Migration 0008 `retrieval_summaries`: authoritative persistence
  (summary_id, kind, contract, corpus/doc/parent, text, provenance).
- `profile_worker` 1.1.0: computes + persists both canonical summaries
  inside the existing stage.
- `project_qdrant_worker` 1.1.0: routing projection under the QUALIFIED
  neural contract in a separate collection (hash vectors never appear
  semantically equivalent): representation_kind in
  {routing_document_summary, routing_section_summary, routing_child},
  payload carries summary_id/chunk_id/doc/parent/source/contract;
  idempotent content-id point ids + per-kind receipts. Batched at the
  contract's 32-text limit.
- Embedder sidecar: manifest weights_sha256 completed with the fresh
  verified snapshot digest (weights LFS-verified against the immutable
  revision 97b0c614…); sidecar serving, /ready verified.
- Qualification: frozen coverage fixture (9 documents, authored
  inventory) + frozen routing set (23 queries, 6 categories) +
  per-document determinism tests (7).

## Proof

Coverage (frozen fixture, v1 vs v2):
- concepts 0.837 → 0.870; section themes 0.657 → 0.778; late content
  0.667 → 0.889; redundancy 0.037 → 0.0; size 400 → 511 chars
  (materially better coverage without unbounded growth; zero
  fabricated sentences).

Routing (frozen 23-query set, I2 corpus):
- document routing: current lexical profile R@1 0.609 / R@3 0.783 /
  MRR 0.714 → candidate summary+neural R@1 0.826 / R@3 0.913 /
  MRR 0.878.
- section routing: current parent lexical R@1 0.652 / MRR 0.736 →
  candidate section summary+neural R@1 0.696 / R@3 0.913 / MRR 0.805.
- global child neural control: R@1 0.870 / R@5 0.957 / MRR 0.905.

Determinism: summary-state hash identical across a full re-profile +
re-projection (4f0ef793…); pure tests green. Suites: unit 0 failures,
integration 0 failures, guards green.

## Rejected claims

- No control plane built: no RRF change, no FAST/HYBRID/GRAPH, no
  MMR, no Pass-2, no support classifier, no synthesis change.
- Routing summaries are explicitly NOT exact-evidence authority
  (recorded for the future control plane).
- PART 8 finding recorded: the repo's snapshot digest file does not
  reproduce from a fresh clean download (environment-dependent cache
  snapshot); the revision pin is immutable and weights were LFS-verified
  against it — pin completed with the verified fresh digest, not
  silently overridden.

## Open contract gaps

- Routing-point receipt reconciliation in verify_worker and the
  census re-drive for routing kinds are deferred to the retrieval
  control plane milestone (projector writes per-kind receipts today;
  verify currently reconciles chunk receipts only).

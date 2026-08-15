---
change_id: q1-qualification
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: census stage reorder (Q1-discovered defect fix)
---

# Q1: heterogeneous production extraction qualification

## Contract

Qualify the production extraction path (lexical lane, frozen compiler
v1.0.1) on a heterogeneous corpus with measured quality gates and a
frozen qualification report. Do NOT enable hybrid evidence mode; do
not begin E1; do not tune extraction. Verdict PASS or FAIL with
exact blocking mechanisms. If PASS: freeze the corpus/results, mark
Q1 COMPLETE, record "production extraction is qualified; further
extraction changes require a demonstrated regression or separately
measured improvement", and proceed to I1.

## Changes

- `eval/gold/qualification_q1.yaml` (new, frozen): 53 items across 11
  heterogeneous classes (business/tech/science/people/geo/time/
  classify/scope/no-relation/passive/OOV), gold authored from sentence
  semantics only. Hash `2ce1d237…`.
- `eval/q1/artifacts/` (new, frozen): Phase H harness run (both arms)
  + manifest/metrics with all hashes.
- `eval/q1/REPORT_Q1.md` (new, frozen): full qualification report.
- `tests/contracts/test_q1_qualification_regression.py` (new): locks
  corpus hash, scorer hash, and baseline metrics.
- **Q1-discovered defect fix**: the census chain reordered —
  `canonicalize` + `project_canonical` now run BEFORE
  `verify_projections` (`control/control/census.py`). Without it,
  every incremental ingestion's verify reconciled canonical state
  that was not yet due → false degraded status (repeatable,
  discovered by the Q1 pipeline run). The temporary verify-side
  gating was reverted (`workers/workers/verify_worker.py` back to
  ungated desired sets).
- Governance: work log, refactor 0006, architecture changelog, TREE
  registration, RAG_E2E_CHECKLIST Q1 → COMPLETE, state docs.

## Proof

- Harness (frozen scorer `94fdc6a9…`): baseline (production) arm —
  P 0.9434, R 0.9434, 0 wrong-predicate, 0 wrong-scope, 1
  wrong-direction, 3 missed, 2 spurious; all residual failures are
  catalogued classes (part_of whole-first direction, spurious
  multi-object pairing, W2 same-side pairing, leadership-trigger
  ambiguity, temporal-location ontology gap). Hybrid Δ worse
  (consistent with Phase H REJECT).
- Pipeline E2E with real GLiNER (9 heterogeneous docs × 8 stages):
  0 failed attempts, 0 degraded runs after the fix, 10/10 facts with
  evidence + full provenance, canonicalization converged, replay
  no-op.
- 134 unit (21 skipped) + 18 integration (2 skipped) tests green;
  three guards green.

## Rejected claims

- No extraction behavior change (compiler, rule pack, ontology,
  thresholds untouched).
- No hybrid default; no E1 work.
- The Q1 corpus is a qualification regression, NOT a held-out
  independent evaluation (exposure count recorded in the report:
  1 authoring-validation run used only to align entity types with
  the frozen ontology signatures, then 1 frozen run).

## Open contract gaps

- I1 (manifest-driven bulk ingestion) and I2 (corpus-scale integrity)
  remain for CORPUS_INGEST_READY.

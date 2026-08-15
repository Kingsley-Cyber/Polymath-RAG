---
change_id: d1-eligibility-receipt-predicate
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: none (defect fix on ADR-0011 boundary)
---

# D1: one shared Neo4j-eligibility predicate (projector/census/verify)

## Contract

Fix smoke-gate defect D1 (work log
2026-08-15-smoke-admission-e2e-fail.md): projection eligibility must
govern receipt expectations. MENTION_ONLY-dependent facts are
intentionally parked in Postgres and are NOT Neo4j projection
failures. One shared deterministic predicate, consumed by projector,
census, and verification; no synthetic receipts for non-projected
artifacts.

## Changes

- `shared/polymath_shared/neo4j_eligibility.py` (new): eligibility
  rule — an entity is eligible iff `admission_class IS DISTINCT FROM
  'MENTION_ONLY'` (NULL = legacy GLOBAL); a fact is eligible iff both
  endpoints are eligible. Exposes SQL fragments + a pure Python
  predicate for tests. Corpus-independent by construction.
- `workers/workers/project_neo4j_worker.py`: entity and fact queries
  now embed the shared fragments (behavior unchanged, single source).
- `control/control/census.py`: `_missing_projection_receipts`
  (project_neo4j branch) joins facts and excludes ineligible facts
  from receipt expectations — parked facts no longer re-arm the
  projector forever.
- `workers/workers/verify_worker.py`: reconciliation is
  eligibility-aware — edges of ineligible facts are removed and their
  receipts (if any) cleared as erroneous; the ineligible set is
  corpus-independent so another corpus's eligible receipts are never
  touched.
- Tests: `tests/determinism/test_neo4j_eligibility.py` (3, pure);
  `tests/integration/test_admission_projection.py` gains
  `test_d1_receipt_expectations_converge` (census sees zero missing
  receipts with parked facts present; verify promotes the run to
  query_ready) and a corpus-scoped store reset (never deletes
  unrelated corpus data).

## Proof

- Integration: admission corpus with 2 parked facts converges —
  `_missing_projection_receipts` = [], verify → `query_ready`.
- Full suites: unit 0 failures; integration 0 failures (29 passed /
  1 skipped) including the frozen reconstruction, chat, evidence
  bundle, and cross-domain suites.

## Rejected claims

- No receipts are synthesized for parked facts: they are excluded
  from expectations, not marked projected.

## Open contract gaps

- None for this defect. (D2 — corpus-scoped graph expansion — is a
  separate change.)

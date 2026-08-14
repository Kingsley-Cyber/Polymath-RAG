---
triggered_by: ADR-0009 (RAG E2E gate C1)
status: done
last_reviewed: 2026-08-14
last_touched: 2026-08-14
---

# Refactor 0004: C1 deterministic Stage-2 canonicalization

ADR-0009 introduced the corpus canonicalization layer. This refactor
materialized it:

- Migration `0005_canonicalization.sql`: `canonical_entities`,
  `canonical_memberships`, `canonicalization_decisions` tables
  (corpus-scoped; memberships carry decision/confidence/basis/version;
  decisions are pairwise with basis, append-only per version).
- `shared/polymath_shared/canonicalizer.py`: pure deterministic policy
  — normalized-exact-name + compatible type + mergeable class → SAME_AS;
  explicit corpus-profile aliases → ALIAS_OF; incompatible types →
  DISTINCT; homonym-risk classes and unknown types → AMBIGUOUS/
  UNRESOLVED abstention. Content-hash canonical ids, order-independent,
  replay-safe, incrementally stable.
- `workers/workers/canonicalize_worker.py`: new census stage
  `canonicalize` (`canonicalize.v1`), after `verify_projections`;
  delete-stale + insert-missing diff inside one stage transaction.
- `control/control/census.py`: stage chain gains `canonicalize`.
- Contract `contracts/canonicalization/v1/
  canonicalization_output.schema.json`; launchd unit; Makefile target.
- Tests: 15 determinism (exact duplicate, alias, homonym, incompatible
  types, ambiguous identity, order independence, replay, incremental,
  removal, basis/version audit, singleton), 4 contract, 1 live E2E
  (worker stage, full lineage, replay no-op, incremental delta,
  source-local rows untouched).
- Harness note: `tests/integration/test_projection_reconstruction.py`
  fixture now marks the `canonicalize` stage complete so the
  projection-receipt re-arm path it targets stays reachable — a
  fixture update for the new chain, not a gate relaxation.

Affected dependents verified: local entity/fact/evidence rows never
mutated (integration asserts row counts before/after); census chain
change verified by the full integration suite; dependency map
unchanged (worker → shared; control unchanged). Reverse dependents:
C2 (canonical KG projection), pending.

Proof: 127 unit + 17 integration tests green; three guards green.
See work log `2026-08-14-c1-canonicalization.md`.

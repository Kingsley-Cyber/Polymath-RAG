---
triggered_by: RAG E2E gate C2 (ADR 0009 consequence)
status: done
last_reviewed: 2026-08-14
last_touched: 2026-08-14
---

# Refactor 0005: C2 canonical KG + provenance projection

C2 projected the C1 canonical registry into Neo4j as a completely
rebuildable graph layer. Changes:

- `workers/workers/project_canonical_worker.py` (new): stage
  `project_canonical` (`project_canonical.v1`), after `canonicalize`.
  Pure `canonical_projection_plan` (unit-tested) feeds MERGE writes:
  `(:CanonicalEntity)` nodes carrying C1 ids + corpus/type/version,
  `[:HAS_MEMBER]` edges carrying decision/confidence/basis/version,
  and `(:Evidence)-[:FROM_CHUNK]->(:Chunk)` source-provenance links.
  Neo4j receives Postgres identities only; never invents or decides.
- Receipts: projection `neo4j`, entity kinds `canonical_entity`,
  `canonical_membership`, `evidence_chunk` (new KIND_* constants in
  shared/projection_contracts.py).
- `workers/workers/verify_worker.py`: `reconcile_canonical` — orphan
  receipts superseded first, then store orphans deleted, then
  missing-in-store receipts cleared; run degrades loudly on gaps.
- `control/control/census.py`: chain gains `project_canonical`;
  re-arm query covers canonical nodes/memberships/evidence links.
- Deployment: launchd unit + Makefile target.
- Tests: 4 plan determinism + 1 live E2E covering the full lineage
  (canonical → member(Doc A/B) → fact → evidence → source), alias
  membership provenance, conflicting facts coexisting, replay no-op,
  incremental delta, removal supersede, destructive reconstruction
  from Postgres, orphan detection, census re-arm.
- Harness: `tests/integration/test_projection_reconstruction.py`
  `_project_all` now RUNS canonicalize + project_canonical for real
  (fixture reflects the production chain).

Affected dependents verified: local entity/fact/evidence rows never
mutated; Postgres remains authority; no new semantic facts; no
policy in Neo4j; dependency map unchanged.

Proof: 131 unit + 18 integration tests green; three guards green.
See work log `2026-08-14-c2-canonical-kg.md`.

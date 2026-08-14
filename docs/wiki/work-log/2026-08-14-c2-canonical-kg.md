---
change_id: c2-canonical-kg-projection
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: new projection stage (canonical graph layer, ADR 0009 consequence)
---

# C2: canonical KG + provenance projection

## Contract

Project the authoritative C1 canonical registry into Neo4j as a
completely rebuildable graph layer with full traversal back to every
source-local entity, fact, evidence record, and source document.
Postgres remains authority; Neo4j remains a disposable projection.

Graph lineage (existing conventions extended, no parallel ontology):

```text
CanonicalEntity -[:HAS_MEMBER]-> Entity -[:REL {fact_id}]-> Entity
Fact -[:SUPPORTED_BY]-> Evidence -[:FROM_CHUNK]-> Chunk
Document -[:HAS_CHUNK]-> Chunk
```

Acceptance (all required):
- every C1 canonical entity exists in Neo4j;
- every canonical membership resolves to the correct local entity;
- membership decision/basis/version remains inspectable;
- canonical → local entity → fact traversal works;
- fact → evidence → document/source traversal remains possible;
- two local entities mapped to one canonical entity retain separate
  original facts and evidence;
- contradictory facts coexist;
- rebuilding Neo4j from an empty database reproduces the canonical
  graph;
- repeated projection is a no-op;
- adding one document produces only the expected graph delta;
- removing/reprocessing a document removes/supersedes only affected
  projection state;
- no orphan canonical memberships survive reconciliation;
- canonical graph IDs are identical to C1 authoritative IDs;
- Postgres/Neo4j census detects missing and extra canonical projection
  state;
- tests cover exact merged entity, alias membership, multiple
  documents, conflicting facts, replay, incremental addition, removal,
  destructive reconstruction, orphan detection, full provenance
  traversal.

## Owner and public contract

- Owner: worker owns the `project_canonical` stage; shared owns the
  receipt identities (extended KIND_* constants).
- No new wire contract (projection stages carry receipts, not wire
  payloads). Reverse dependents: none (verification is verify_worker).

## Design decisions (admitted)

- New census stage `project_canonical` (event `project_canonical.v1`)
  AFTER `canonicalize`, so the registry exists before projection.
- Neo4j receives ONLY Postgres identities (canonical_id,
  local_entity_id, fact_id, evidence_id); it never invents one and
  never decides identity.
- Node/edge shapes: `(:CanonicalEntity {canonical_id, canonical_type,
  normalized_name, corpus_id, canonicalizer_version})` +
  `[:HAS_MEMBER {decision, confidence, basis, canonicalizer_version,
  local_entity_id}]` + `(:Evidence)-[:FROM_CHUNK]->(:Chunk)` (the
  evidence→source link the canonical lineage needs; chunk→document is
  already present as `Document-[:HAS_CHUNK]->Chunk`).
- Receipts: projection `neo4j`, entity kinds `canonical_entity`,
  `canonical_membership` (keyed by local entity id), `evidence_chunk`
  (keyed by evidence id). Same receipt discipline as existing
  projections.
- verify_projections gains canonical reconciliation: missing in store
  → clear receipts (census re-drives); orphans in store → deleted;
  orphan receipts (source row gone) → superseded. Census re-arm query
  extended for project_canonical.
- No new semantic facts are created; conflicting facts stay distinct
  REL edges. No fuzzy matching, no policy in Neo4j.

## Inputs, outputs, persistence, failure modes

- Inputs: Postgres canonical_entities, canonical_memberships,
  evidence rows (corpus-scoped via the run).
- Outputs: Neo4j nodes/edges + projection receipts (attempts +
  active claims).
- Persistence: receipts in Postgres (authority); graph disposable.
- Failure modes: crash between graph write and receipt commit →
  orphan graph state → verify deletes it (existing orphan discipline,
  extended to canonical kinds).

## Dependency edges

- worker → shared (existing edge); census chain gains one stage.
- New files: `workers/workers/project_canonical_worker.py`, launchd
  plist, Makefile target, tests. Modified: census.py, verify_worker.py,
  projection_contracts.py (kind constants), reconstruction test
  fixture (new stage marked ok).
- Reverse dependents: none.

## Verifier and rollback boundary

- Verifier: plan unit tests + live integration tests (all acceptance
  bullets), `make guards`, full suites.
- Rollback boundary: revert the census entry + delete worker/tests;
  canonical graph nodes are disposable (verify reconciliation deletes
  orphaned state).

## Changes

- `workers/workers/project_canonical_worker.py` (new): stage
  `project_canonical`; pure `canonical_projection_plan` + MERGE writes
  (CanonicalEntity nodes, HAS_MEMBER edges with C1
  decision/confidence/basis/version, Evidence→FROM_CHUNK→Chunk
  source links).
- `shared/polymath_shared/projection_contracts.py`: KIND_CANONICAL_ENTITY,
  KIND_CANONICAL_MEMBERSHIP, KIND_EVIDENCE_CHUNK constants.
- `workers/workers/verify_worker.py`: `reconcile_canonical` — orphan
  receipts superseded FIRST, then store orphans deleted, then
  missing-in-store cleared; canonical gaps degrade the run loudly.
- `control/control/census.py`: STAGE_CHAIN + STAGE_EVENTS gain
  `project_canonical`; re-arm query covers the three canonical
  receipt kinds.
- `deployment/launchd/ai.polymath.worker.project-canonical.plist`
  (new); Makefile `dev-worker-project-canonical` target (new).
- Tests: `tests/determinism/test_canonical_projection_plan.py` (4),
  `tests/integration/test_canonical_projection_e2e.py` (1, live).
- Harness: `tests/integration/test_projection_reconstruction.py`
  `_project_all` runs canonicalize + project_canonical for real.
- Governance: refactor 0005, architecture changelog, TREE
  registration, RAG_E2E_CHECKLIST C2 → COMPLETE.

Dependency edges: worker → shared (existing edge); dependency map
unchanged. Local entity/fact/evidence rows never mutated; no new
semantic facts; no canonicalization policy in Neo4j; no fuzzy
matching; contradictions stay distinct REL edges.

## Proof

- Unit/contract: 4 new plan tests green (131 unit total, 21 skipped).
- Integration: 18 passed, 2 skipped — includes live full lineage
  (canonical → member(Doc A) → fact → evidence → source; same for
  Doc B), alias membership provenance, replay no-op, incremental
  delta, removal supersede, DESTRUCTIVE RECONSTRUCTION from Postgres,
  orphan detection, and census re-arm for missing canonical receipts.
- `make guards` green (preflight, repo guard, wiki worm).

## Rejected claims

- No canonicalization policy inside Neo4j; no fuzzy matching; no
  synthetic merged facts; no arbitration of contradictions; no
  mutation of local IDs or evidence; no Q1/I1/reranking/MCP/E1 work.

## Open contract gaps

- Q1/I1/I2 remain for CORPUS_INGEST_READY.

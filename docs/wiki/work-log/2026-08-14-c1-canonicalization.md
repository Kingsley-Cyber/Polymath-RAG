---
change_id: c1-canonicalization
owner: governance
date: 2026-08-14
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: complete
architecture_impact: new stage + new data layer (ADR 0009)
---

# C1: deterministic Stage-2 corpus canonicalization

## Contract

Implement a deterministic corpus-level canonical registry: multiple
document-local entities referring to the same real corpus concept get
a deterministic canonical identity WITHOUT destroying or rewriting
their original source-local identities. Core invariant:
canonicalization ADDS a corpus layer; it NEVER erases source-local
knowledge. Postgres remains authoritative; Neo4j remains a rebuildable
projection (canonical KG projection is C2, out of scope).

Acceptance (all required):
- same obvious entity across two documents gets one canonical identity;
- every canonical member retains its original local entity ID;
- every local fact/evidence/source remains untouched;
- canonical → local → fact → evidence → source traversal works;
- incompatible entity types do not merge;
- ambiguous same-name entities abstain rather than merge;
- aliases resolve without rewriting the original surface;
- unrelated entities remain separate;
- deterministic across repeated runs and ingestion orders;
- replay produces zero duplicate canonical objects/memberships;
- adding a new document only produces the required delta;
- removing/reprocessing a source does not corrupt unrelated canonical
  objects;
- every merge decision records its basis/version;
- no fuzzy/LLM-only merge can become authoritative silently;
- tests cover exact duplicate, alias, homonym, incompatible types,
  ambiguous identity, ingestion-order independence, replay, incremental
  addition.

## Owner and public contract

- Owner: worker owns the canonicalize stage; shared owns the
  deterministic canonicalizer policy.
- Public contract: `contracts/canonicalization/v1/
  canonicalization_output.schema.json` (new wire payload for the
  stage artifact/report). Reverse dependents: C2 (canonical KG
  projection).

## Design decisions (admitted, ADR 0009)

- New Postgres tables (migration 0005): `canonical_entities`,
  `canonical_memberships`, `canonicalization_decisions` (append-only
  pair decision log, per canonicalizer version).
- New census stage `canonicalize` (event `canonicalize.v1`), placed
  after `verify_projections`; worker recomputes the corpus registry in
  one stage transaction (artifact + receipt + status together).
- Canonical id: `cent_<hash(version, corpus, type, surface)>` for
  mergeable groups; `cent_<hash(version, corpus, type, surface,
  local_entity_id)>` for abstained singletons (stable ids, no
  collision between homonyms).
- Conservative policy: SAME_AS only on normalized-exact-name +
  identical core type + mergeable class (Organization, Location,
  Product, Technology, Document); ALIAS_OF only on explicit corpus
  profile alias declarations; DISTINCT on same name + incompatible
  type; AMBIGUOUS/UNRESOLVED abstain for homonym-risk classes,
  unknown types, and empty surfaces.
- No fuzzy matching, no LLM, no string-similarity merges. No fact/
  entity/evidence mutation. No Neo4j canonical projection (C2).

## Inputs, outputs, persistence, failure modes

- Inputs: corpus entities (from facts/evidence of corpus documents)
  + corpus profile alias declarations.
- Outputs: canonical_entities, canonical_memberships (decision,
  confidence, basis, canonicalizer_version),
  canonicalization_decisions (pairwise SAME_AS/ALIAS_OF/DISTINCT/
  AMBIGUOUS/UNRESOLVED with basis), stage artifact with counts.
- Persistence: canonical tables only; delete-stale + insert-missing
  diff inside the stage transaction (replay = no-op, incremental =
  required delta).
- Failure modes: stage failure receipt via stage_transaction
  (unchanged discipline); no silent partial registry.

## Dependency edges

- worker → shared (existing edge); control census chain gains one
  stage (same owner). No dependency map change.
- New files: migration 0005, `shared/polymath_shared/canonicalizer.py`,
  `workers/workers/canonicalize_worker.py`, contract schema, launchd
  plist, Makefile target, tests.
- Reverse dependents: none yet (C2 pending).

## Verifier and rollback boundary

- Verifier: canonicalizer unit tests (all acceptance cases), contract
  schema test, live-store integration tests (worker stage, lineage,
  replay, incremental), `make guards`.
- Rollback boundary: drop migration 0005 tables (not yet applied is
  applied-only; if applied, migration is append-only per repo rules —
  rollback = stop scheduling the stage by reverting the census entry,
  tables remain inert), delete worker + canonicalizer + tests.

## Changes

- `stores/postgres/migrations/0005_canonicalization.sql` (new).
- `shared/polymath_shared/canonicalizer.py` (new): pure deterministic
  policy; content-hash canonical ids; order-independent, replay-safe.
- `workers/workers/canonicalize_worker.py` (new): census stage
  `canonicalize`; delete-stale + insert-missing diff inside the stage
  transaction.
- `control/control/census.py`: STAGE_CHAIN + STAGE_EVENTS gain
  `canonicalize` / `canonicalize.v1` after verify_projections.
- `contracts/canonicalization/v1/canonicalization_output.schema.json`
  (new); `deployment/launchd/ai.polymath.worker.canonicalize.plist`
  (new); Makefile `dev-worker-canonicalize` target (new).
- Tests: `tests/determinism/test_canonicalizer.py` (15),
  `tests/contracts/test_canonicalization_contract.py` (4),
  `tests/integration/test_canonicalization_e2e.py` (1).
- Harness: `tests/integration/test_projection_reconstruction.py`
  `_project_all` marks `canonicalize` ok (new census chain).
- Governance: ADR 0009, refactor 0004, architecture changelog, TREE
  registration, RAG_E2E_CHECKLIST C1 → COMPLETE.

Dependency edges: worker → shared (existing edge); dependency map
unchanged. No local entity/fact/evidence mutation (integration asserts
row counts before/after). No fuzzy/LLM merges. No Neo4j canonical
projection (C2).

## Proof

- Unit/contract: 19 new tests green (127 unit total, 20 skipped).
- Integration: 17 passed, 2 skipped — includes the live canonicalize
  stage with full lineage (canonical → local → fact → evidence →
  source), replay no-op, incremental delta, and untouched
  source-local rows.
- `make guards` green (preflight, repo guard, wiki worm).
- Contract schema validated by jsonschema in tests; migration 0005
  applied to the live stores via `make db-migrate`.

## Rejected claims

- No mutation of local entities/facts/evidence.
- No fuzzy/LLM merges; no REVISES/SUPERSEDES/CONTRADICTS identity
  abuse (those are future fact-layer relations, not identity
  decisions).
- No Neo4j canonical KG (C2).

## Open contract gaps

- Alias declarations beyond corpus profile are future evidence sources.
- C2 consumes this registry.

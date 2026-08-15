---
change_id: e2-admission-production-wiring
owner: governance
date: 2026-08-15
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: complete
architecture_impact: docs/wiki/decisions/0011-entity-admission-boundary.md
---

# E2/C1.1 production wiring: entity admission boundary

## Contract

Wire the qualified entity-admission policy (entity-admission-v1.1,
E2/C1.1: 100% gold + downstream G4 PASS) into the production pipeline
at the identity allocation point, exactly as authorized by commit
41bbaed ("promotion authorized (not wired)"):

- GLOBAL / CORPUS_SCOPED / DOCUMENT_SCOPED / MENTION_ONLY reference
  classes decided per accepted GLiNER span, deterministically, before
  durable entity identity is assigned.
- Identity contract bumps to entity-identity-v2: GLOBAL keeps the
  canonical id (byte-compatible with canonical_entity_id);
  CORPUS_SCOPED = entc_ + hash(corpus, type, surface);
  DOCUMENT_SCOPED = entd_ + hash(corpus, doc, type, surface);
  MENTION_ONLY = stable mention_ id (doc, chunk, offsets, type).
- MENTION_ONLY entities never become Neo4j Entity nodes; facts with a
  MENTION_ONLY endpoint stay parked as unresolved evidence in Postgres.
- Graph expansion becomes canonical bidirectional hop1 (directed UNION,
  dedupe by fact_id, ORDER BY fact_id, LIMIT 20) — the implementation
  measured in eval/g4, promoted because admission removes the generic
  hubs that caused the frozen q09 failure.
- Compiler authority unchanged: span pairing, predicate, direction,
  negation, modality, ontology mapping, and fact identity stay exactly
  as qualified (Q1 frozen report).

## Changes

- `shared/polymath_shared/entity_admission.py` (new): production policy
  entity-admission-v1.1 (decide + allocate_entity_id), deterministic,
  no model, reasons carried. Mirrors eval/admission/entity_admission.py
  v1.1 without experiment markers.
- `stores/postgres/migrations/0007_admission.sql`: entities.admission_class
  (CHECK GLOBAL/CORPUS_SCOPED/DOCUMENT_SCOPED/MENTION_ONLY) + index.
  Legacy NULL rows are treated as GLOBAL by projection filters
  (IS DISTINCT FROM 'MENTION_ONLY').
- `workers/workers/candidates.py`: build_candidates allocates both
  endpoint ids through the admission boundary (sentence-initial context
  derived from slice text); corpus_id parameter (default "eval" keeps
  frozen eval harnesses working).
- `workers/workers/extract_worker.py`: corpus_id lookup; entities rows
  persist admission_class; parse-record entity ids use the SAME
  allocator (compiler's _oriented_pair compares ids); extract contract
  pins admission_policy + identity_contract.
- `workers/workers/project_neo4j_worker.py`: entity and fact queries
  exclude MENTION_ONLY (entities and both fact endpoints).
- `workers/workers/canonicalize_worker.py`: canonicalization input
  excludes MENTION_ONLY and DOCUMENT_SCOPED (doc-local identities do
  not merge across documents).
- `orchestrator/orchestrator/api/retrieve.py`: _neo4j_expand is the
  canonical bidirectional hop1 (two directed clauses inside one CALL ()
  subquery — incoming edges only make the EXISTING fact eligible).
- Tests: `tests/determinism/test_entity_admission.py` (8) —
  allocator class table + id rules + build_candidates boundary;
  `tests/integration/test_admission_projection.py` (2) — real
  production allocation path -> projection gate: mention entities
  never project, parked facts stay Postgres-only, re-projection
  deterministic.

## Proof

- Allocator invariants verified live: GLOBAL id byte-compatible with
  canonical_entity_id; CORPUS_SCOPED merges within a corpus, splits
  across corpora and types; DOCUMENT_SCOPED stable within a doc,
  distinct across docs; MENTION_ONLY stable per span, distinct across
  spans.
- Integration gate passes on the real stores: seeded through
  build_candidates + compile_relation (production boundary), graph
  contains only admitted entities/edges; parked facts present in
  Postgres; identical second projection.
- Suites: unit/determinism 85 passed, integration 25 passed, 0 failed;
  preflight + repo guard + wiki worm all ok.
- Q1 harness untouched (frozen): build_candidates signature backward
  compatible via default corpus_id; harness semantics unchanged.
- Frozen eval hashes re-verified before and after (no eval file
  touched).

## Rejected claims

- No compiler change (authority intact). No canonicalization semantics
  change for GLOBAL/CORPUS_SCOPED. No seed-eligibility change (G4.2
  remains rejected; generic hubs cannot exist in the graph now).
- Verify worker untouched: it reconciles chunk-level receipts; the
  projection filters live in the owning projection workers.
- No numeric fake confidence anywhere.

## Open contract gaps

- G4.2 seed eligibility (generic seeds) still rejected/future work.
- Old global-only entity ids from pre-v2 rows are not interchangeable
  with scoped ids; replay of pre-0007 corpora keeps NULL admission
  class = GLOBAL behavior.

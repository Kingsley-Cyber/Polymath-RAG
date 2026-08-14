---
owner: worker
last_reviewed: 2026-08-14
last_touched: 2026-08-14
status: accepted
---

# ADR 0009: Corpus canonicalization layer (Stage 2)

Status: accepted
Date: 2026-08-14

## Context

Stage-1 extraction is document-local: every fact, entity, and evidence
row is keyed to one source document. The same real-world entity
("AcmeCorp") extracted from two documents exists as two local entities
with no shared corpus identity. R3a/R3b retrieval can cite each fact,
but nothing represents "these are the same concept" across documents.

## Decision

Introduce a Stage-2 canonicalization layer that ADDS a corpus-level
identity without erasing source-local knowledge:

```text
canonical_entity
    ↓ maps to (canonical_memberships)
source-local entity
    ↓ participates in
source-local fact
    ↓ supported by
evidence
    ↓ located in
exact source document/span
```

- Postgres remains workflow authority; new tables
  `canonical_entities`, `canonical_memberships`,
  `canonicalization_decisions` (migration 0005) hold the registry.
- A new census stage `canonicalize` (event `canonicalize.v1`) runs
  after `verify_projections`; the worker recomputes the corpus
  registry deterministically inside one stage transaction.
- Canonical IDs are content hashes of (canonicalizer_version, corpus,
  canonical_type, canonical surface) for mergeable groups, and
  (…, local entity id) for abstained singletons — reproducible,
  order-independent, replay-safe.
- Canonicalization is conservative by policy (v1):
  - SAME_AS: normalized-exact-name match + identical core type +
    mergeable type class (Organization, Location, Product, Technology,
    Document).
  - ALIAS_OF: explicit alias declaration in the corpus profile only.
  - DISTINCT: same normalized name, incompatible core type.
  - AMBIGUOUS / UNRESOLVED: homonym-risk classes (Person, Concept,
    Event, Method, Process, Measurement, TimeReference), unknown
    types, empty surfaces — abstain; each entity stays in its own
    singleton canonical entity.
  - Every pairwise decision is recorded with basis and
    canonicalizer_version; nothing fuzzy or LLM-based can become
    authoritative silently.
- False merges are worse than missed merges; the policy can only be
  relaxed by a new canonicalizer version plus a measured
  before/after qualification on a frozen corpus.

## Consequences

- Canonicalization NEVER mutates local entity/fact/evidence rows;
  lineage back to source spans stays intact.
- C2 will project canonical entities into Neo4j; this ADR deliberately
  stops at the Postgres registry.
- Every run of a corpus re-canonicalizes; identical inputs produce
  identical ids, so replay is a no-op and incremental additions
  produce only the required delta.

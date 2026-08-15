---
owner: governance
last_reviewed: 2026-08-15
last_touched: 2026-08-15
status: accepted
---

# ADR 0011: Entity admission boundary (E2/C1.1 promotion)

## Context

E2/C1.1 qualified a deterministic entity-admission layer (gold 100%,
downstream G4 PASS) but only as an experiment
(`eval/admission/`, work log 2026-08-14-entity-admission.md). The
qualified policy must become production behavior: durable entity
identity must be assigned by reference class, not uniformly from
surface strings. Graph expansion (G4) stays hobbled otherwise —
generic hubs (the system / the model / the platform) act as retrieval
noise attractors.

## Decision

Promote entity admission as a production boundary between accepted
GLiNER spans and durable entity identity, with reference classes:

| Class | Identity | Neo4j Entity? | Canonicalization? |
|---|---|---|---|
| GLOBAL | canonical entity_id(type, surface) | yes | yes |
| CORPUS_SCOPED | entc_ hash(corpus, type, surface) | yes | yes (within corpus) |
| DOCUMENT_SCOPED | entd_ hash(corpus, doc, type, surface) | yes | no (doc-local) |
| MENTION_ONLY | mention_ hash(doc, chunk, offsets, type) | never | no |

- Identity contract version bumps to entity-identity-v2 (persisted via
  entities.admission_class, migration 0007).
- Compiler authority is unchanged: admission decides WHO gets identity;
  the compiler alone decides WHAT is asserted, with which predicate,
  direction, negation, modality, and ontology mapping.
- Facts whose endpoints are MENTION_ONLY remain parked as unresolved
  evidence: persisted in Postgres (authority), never graph-projected.
- Graph expansion promotes to canonical bidirectional hop1 (directed
  UNION inside one CALL () subquery, dedupe by fact_id, ORDER BY
  fact_id, LIMIT 20): incoming edges only make the EXISTING fact
  eligible. The frozen q09 generic-seed criterion failure no longer
  applies because generic surfaces cannot exist in the graph.
- G4.2 (generic-seed eligibility) stays rejected; it is now defense
  in depth, not the only gate.

## Consequences

- Extraction contract gains admission_policy=entity-admission-v1.1 and
  identity_contract=entity-identity-v2; replay of pre-0007 corpora
  keeps NULL admission_class = GLOBAL.
- Parse-record entity ids use the same allocator so the compiler's
  syntactic orientation matching compares identical identities.
- Canonicalization input excludes DOCUMENT_SCOPED and MENTION_ONLY;
  doc-local identities never merge across documents.

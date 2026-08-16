---
change_id: temporal-interpretation-deferred
owner: governance
date: 2026-08-16
status: complete
architecture_impact: records-deferred-required-production-gate
last_reviewed: 2026-08-16
---

# TEMPORAL-INTERPRETATION-V1 — DEFERRED REQUIRED PRODUCTION GATE

## Contract

Amends `2026-08-16-temporal-extraction-architecture.md` (status:
complete-with-one-deferred-durability-gap). The alignment provides
version ATTRIBUTION (receipts/artifacts identify the contract that
produced an attempt) but not yet first-class interpretation
VERSIONING — a durable object for (source_content_version,
extraction_contract_hash) = interpretation owning/referencing
mentions, entities/memberships, facts, evidence, canonicalization
decisions, and projection eligibility. Required invariant: changing
the extraction contract must never require destroying the historical
interpretation produced by the previous contract. Promotion determines
which interpretation is projected/retrieved as current production;
historical interpretations stay attributable and inspectable; Qdrant
and Neo4j project only the promoted interpretation unless historical
access is explicitly requested.

## Changes

- This record; CURRENT_STATE gate table; changelog pointer. No code.

## Proof

- Gate recorded and named so it cannot disappear into the backlog.
- Explicitly NOT built now (user directive): building it before the
  extraction repair risks derailing I4R. It MUST land before the first
  real production model/query-policy upgrade.

## Rejected claims

- No claim that receipts-based attribution equals interpretation
  versioning; the gap is real and named.

## Open contract gaps

- TEMPORAL-INTERPRETATION-V1 implementation awaits its own
  authorization, before the first production provider/policy upgrade.

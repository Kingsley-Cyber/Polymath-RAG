---
triggered_by: ADR-0011 (entity admission boundary)
status: done
last_reviewed: 2026-08-15
last_touched: 2026-08-15
---

# Refactor 0008: E2/C1.1 entity admission production wiring

ADR-0011 promoted the qualified entity-admission boundary into
production. This refactor materialized it:

- `shared/polymath_shared/entity_admission.py`: production policy
  entity-admission-v1.1 — reference classification (GLOBAL /
  CORPUS_SCOPED / DOCUMENT_SCOPED / MENTION_ONLY) + identity
  allocation (identity contract entity-identity-v2). Deterministic,
  model-free, reasons carried; GLOBAL ids byte-compatible with
  canonical_entity_id.
- Migration 0007: `entities.admission_class` (checked column) +
  index; legacy NULL = GLOBAL.
- `workers/workers/candidates.py`: identity allocation at the
  admission boundary (sentence-initial context derived from slice
  text); `corpus_id` parameter with "eval" default keeps the frozen
  Q1/measurement harnesses source-compatible.
- `workers/workers/extract_worker.py`: corpus_id lookup, admission
  class persisted with entity rows, parse-fill entity ids allocated by
  the same admission function (compiler orientation matching compares
  ids), extract contract pins admission_policy + identity_contract.
- `workers/workers/project_neo4j_worker.py`: MENTION_ONLY entities and
  facts with MENTION_ONLY endpoints never project; parked facts remain
  Postgres authority.
- `workers/workers/canonicalize_worker.py`: DOCUMENT_SCOPED and
  MENTION_ONLY entities excluded from canonicalization input.
- `orchestrator/orchestrator/api/retrieve.py`: `_neo4j_expand` is the
  canonical bidirectional hop1 (directed UNION in one CALL () subquery,
  dedupe by fact_id, ORDER BY fact_id, LIMIT 20) — the G4-measured
  variant, promoted because admission removes generic hubs.

Affected dependents verified: compiler/rule pack/ontology/GLiNER
thresholds untouched (Q1 frozen); eval harnesses source-compatible
(default corpus_id); verify worker unaffected (chunk-level receipts);
R3a/R3b resolve entities/facts from Postgres rows that still exist for
parked facts, and graph expansion cannot return mention-endpoint facts
because their nodes never project.

Evidence: work log 2026-08-15-e2-admission-production-wiring.md;
8 determinism tests + 2 integration gate tests; full suites green.

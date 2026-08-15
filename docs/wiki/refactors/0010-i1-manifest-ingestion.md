---
triggered_by: ADR-0013 (manifest-driven bulk ingestion)
status: done
last_reviewed: 2026-08-15
last_touched: 2026-08-15
---

# Refactor 0010: I1 manifest-driven bulk ingestion

ADR-0013 introduced manifest-driven bulk ingestion. This refactor
materialized it:

- `contracts/ingestion/v1/manifest.schema.json`: version-1 closed
  manifest schema (unknown fields fail; source paths unique).
- `shared/polymath_shared/manifest.py`: pure policy — parse/validate,
  canonical form + order-stable manifest id, manifest-relative path
  resolution, I0-only media-type inference, duplicate detection,
  defaults (language/source_tier/enabled).
- `shared/polymath_shared/intake_submission.py`: the ONE intake
  writer (run row + intake.v1 outbox event, content-derived
  idempotency). `orchestrator/orchestrator/api/intake.py` now
  delegates to it — behavior identical, single-document tests green.
- `control/control/manifest_ingest.py`: plan (read-only, Postgres-
  authoritative: content identity, content-derived run id, run
  status, source-locator lineage for changed content), execute
  (submission via the shared writer with configurable batch bound;
  RETRY re-arms failed runs' outbox events and re-enters the census
  candidate set — no history/receipt mutation), status (read-only
  reconciliation + stage distribution).
- `scripts/ingest.py` CLI (plan / run / status) + Makefile targets
  `ingest-plan` / `ingest-run` / `ingest-status`; scripts registry
  entry.
- Frozen fixture `tests/fixtures/i1/` (md, txt, pdf, disabled,
  missing, duplicate, unknown-field, changed-content, secondary
  tier); determinism suite `tests/determinism/test_manifest.py`
  (9 tests) and integration suite
  `tests/integration/test_i1_manifest_ingestion.py` (6 gates).

Affected dependents verified: orchestrator intake behavior unchanged
(shared writer is byte-identical logic); control plane untouched
(census/scheduler/verify not modified); workers untouched. Live CLI
verification: PLAN 1 = 6 new / 1 disabled / 1 missing; EXECUTION 1 =
6 submitted → control plane → 6 query_ready; EXECUTION 2 = 0
submissions; PLAN 3 = 6 NOOP. Full unit + integration suites green.

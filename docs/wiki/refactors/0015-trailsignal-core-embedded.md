---
triggered_by: ADR-0021 (TrailSignal's deterministic research core runs in process)
status: in_progress
last_reviewed: 2026-09-20
last_touched: 2026-09-20
---

# Refactor 0015: embed the TrailSignal research core

> **Active plan:** `docs/migration/EXECUTION_PLAN.md` (Phase 6). Design: `docs/migration/ADR-TRAIL-EMBEDDING.md`. State: `docs/migration/CONTINUATION.md`.

| Step | Change | State |
|---|---|---|
| 1 | Source verification (licence, closure, store port, data files) | done |
| 2 | Byte-identical import + `PROVENANCE.json` + provenance pin | done (branch `migration/ecommerce-consolidation`) |
| 3 | `embedded.py`: service, SQLite store port, in-process transport | done |
| 4 | `POLYMATH_TRAIL_MODE=embedded` switch in the worker's client factory | done |
| 5 | Complete `ecommerce.product_research` run against the embedded core | done (defensible rejection) |
| 6 | Add `packageurl` to `pyproject.toml` + install (merge window) | not started |
| 7 | Port TrailSignal's own operation tests; recorded-envelope equivalence | not started |
| 8 | Trim unrelated contract modules; D1 / M1-01..03 (separate documented changes) | not started |

---
triggered_by: ADR-0020 (DOMAIN_OPERATION — a manifest step binds a domain's own code)
status: in_progress
last_reviewed: 2026-09-20
last_touched: 2026-09-20
---

# Refactor 0014: domain binding seam for the ecommerce consolidation

> **Active plan:** `docs/migration/EXECUTION_PLAN.md` (Phase 3). State: `docs/migration/CONTINUATION.md`.

| Step | Change | State |
|---|---|---|
| 1 | `DOMAIN_OPERATION` in `contracts.STEP_TYPES` + the four `contracts/adapter/v1` enums; manifest validation | done (branch `migration/ecommerce-consolidation`) |
| 2 | `exec_domain` in `workers/workers/adapter_step_worker.py`, registered in `EXECUTORS` | done |
| 3 | `adapters/ecommerce/binding.py` — first operation `hypotheses.validate_bridge` wraps `python/bridge.py` | done |
| 4 | `architecture/dependencies.json` owner `domain_adapter` + forbidden imports | done |
| 5 | Bind the remaining engine capabilities (population, planning, ideation checks, sourcing, parsers, report) | migration Phases 4–8 |
| 6 | Merge + one fleet bounce | not started |

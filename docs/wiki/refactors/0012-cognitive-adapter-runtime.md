---
triggered_by: ADR-0018 (cognitive-adapter boundary)
status: in_progress
last_reviewed: 2026-09-13
last_touched: 2026-09-13
---

# Refactor 0012: the cognitive-adapter runtime (E1 → E7)

> **Active plan:** `docs/wiki/plans/COGNITIVE-ADAPTER-TRAIL-E2E-V1-PLAN.md`; evidence base `…-E0-GAP-MATRIX.md`.

| slice | scope | status | evidence |
|---|---|---|---|
| E0 | reconcile both repos; two-repo gap matrix | DONE | 11.257, 11.258 |
| E1 | ADR-0018; `contracts/adapter/v1` (9 schemas + examples + contract test); pure `shared/polymath_shared/adapter/`; admitted `config/adapters/trail.product_discovery.json` | DONE | 11.259 — 15 contract tests + 12 pure-core tests |
| E2 | migration `0061_adapter_runs.sql`; 7 MCP tools; `adapter_step_worker`; restart-resume integration test; fleet bounce | planned | — |
| E3 | TrailSignal subgraph through its own graph (P6R/P7R/P4W/P8R/P9 → C1 → C2/Q1 → C3) | planned (Trail-side) | — |
| E4 | typed Trail connector (auth, bounded contracts, `ExternalOperationReceiptV1`, poll/resume, cancel, timeouts) against the WORKING tools | planned | — |
| E5 | `trail.product_discovery` end to end with real knowledge + real Trail operations | planned | — |
| E6 | migrate/retire `research_*` after an equivalence proof (baseline harness first) | planned | — |
| E7 | `substack.article_development` on the same runtime | planned | — |

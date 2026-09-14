---
triggered_by: ADR-0019 (harness-executed hypothesis research)
status: in_progress
last_reviewed: 2026-09-13
last_touched: 2026-09-13
---

# Refactor 0013: harness-executed hypothesis research migration (R0 → R5)

> **Active plan + cutover ledger:** `docs/wiki/plans/HARNESS-RESEARCH-MIGRATION-V1-PLAN.md` (§7 is the migration matrix; it is
> updated in the same commit as every slice below — never a stale planning document).

| slice | scope | status | evidence |
|---|---|---|---|
| R0 | authority: ADR-0019, this ledger, plan + cutover ledger, supersession banners, `research/` FROZEN | DONE | 11.265 |
| R1 | contracts: HARNESS_ACTION in the closed vocabulary; `harness_action`, `harness_receipt`, `hypothesis_state`, `hypothesis_transition`, `evidence_admission` schemas + examples; step/submission/result extensions | planned | — |
| R2 | substrate: migration 0062 (hypotheses, transitions, harness actions, admitted evidence); pure hypothesis state machine; HARNESS_ACTION issue/pause/receipt; admitted-only context; `.env.example` names | planned | — |
| R3 | Trail (own governance): ADR-063, A32, HR1 registry snapshot + contracts + replay, HR2 admission/qualification/scoring, HR3 bounded MCP operations, HR4 loop canary | planned (Trail-side) | — |
| R4 | `trail.product_discovery` 2.0.0 on the new loop; Trail-owned acquisition executors removed; neutrality + source-extensibility tests; dead-reference audit | planned | — |
| R5 | live acceptance through the official-client driver with the harness executing the actions; `research/` + `research_*` removed | planned (gated on O1/O4) | — |

---
title: "WORK LOG — HARNESS-RESEARCH-MIGRATION-V1 HR4 PORTFOLIO CONSUMER: Polymath consumes Trail's per-hypothesis (ADR-064) result shape and the acceptance proves the multi-hypothesis loop"
change_id: HARNESS-RESEARCH-MIGRATION-V1-HR4-PORTFOLIO-CONSUMER
date: 2026-09-16
owner: king
last_reviewed: 2026-09-16
status: complete
status_note: "Merged in 7f232e0 (PR 29); the merged-main two-hypothesis proof passed (11.276). Owner-parked LOW item: the terminal envelope has an empty qualifications list. (was: in_progress)"
register: 11.275
architecture_impact: "Trail HR4 (ADR-064) turns opportunity.qualify / opportunity.score into a per-hypothesis portfolio: ResearchResultV1 carries `qualifications`, `trail_scores` and `score_refusals` tuples instead of the singular `qualification` / `trail_score`. Polymath's adapter is the only consumer of that wire. This slice makes the step worker forward every qualification record of every stage to the score request (Trail filters per hypothesis; the caller never selects a winner), joins every per-hypothesis score and refusal record id to the cross-system lineage, and evolves the trail.product_discovery manifest (2.0.0 → 2.1.0, output schema 2.1.0) so the terminal output carries the per-hypothesis records. The scripted acceptance now develops two live hypotheses, tags all field evidence to the non-first one, and asserts the portfolio outcome. Tolerant of the pre-HR4 singular shape, so it can land before or after the Trail merge. No model, harness, or Polymath code reads or ranks a score value (LAW 1). Touches workers/ and shared config → a fleet bounce lands it."
---

## Contract
Owner directive 2026-09-16 (Trail A41/HR4): fix the governor defect with a narrow authorized-ceiling rule, land A41, land HR4 (per-hypothesis portfolio: qualify every live hypothesis independently, score every hypothesis whose qualification passes the scoring hard gates, typed OpportunityScoreRefusalV1 for the rest, no implicit hypotheses[0] winner, no model-selected winner), then run the final merged-main multi-hypothesis product-discovery proof through Polymath and stop hunting hypothetical bugs. This slice is the Polymath half of that proof: the adapter must consume Trail's plural wire without touching a score value, and the acceptance driver must exercise ≥ 2 live hypotheses with the evidence on the non-first one — the exact wrong-selection canary the owner required ("qualify targets hypotheses[0]; do not let it silently disappear").

## Changes
- `workers/workers/adapter_step_worker.py` — `_payload_for("opportunity.score")` forwards every qualification record of every accepted qualify step in acceptance order: the HR4 `qualifications` lists plus any legacy singular `qualification`; Trail filters them per hypothesis. `exec_external` joins `trail_scores[*].record_id` to `trail_score_record_ids` and the external-operation `record_ids`, and records `score_refusals[*].record_id` as `trail_score_refusal_record_ids` (also in `record_ids`), so every per-hypothesis Trail record is in the cross-system lineage. The singular `trail_score` path is kept.
- `config/adapters/trail.product_discovery.json` — `adapter_version` 2.0.0 → 2.1.0, `output_schema_version` 2.0.0 → 2.1.0; the terminal `X_compile.include` adds `qualifications`, `trail_scores`, `score_refusals`; the output schema declares them as arrays (the legacy `qualification` object stays optional).
- `scripts/adapter_mcp_acceptance.py` — θ `C_hypotheses` returns TWO hypotheses; `N_jobs` and `W_interpret` cover every live hypothesis; `load_receipt` tags every scripted observation to the SECOND live hypothesis of the action (`TAGGED_HYPOTHESES`) when two or more are carried; after the run, for `trail.product_discovery`, the driver asserts ≥ 2 hypotheses in the lineage, a Trail score record in the lineage, the tagged hypothesis among `trail_scores`, and — when two or more hypotheses were still live at scoring — an untagged hypothesis among `score_refusals`; the summary is printed as `receipts["portfolio"]`.
- `tests/determinism/test_adapter_product_discovery_loop.py` — the stub Trail speaks the HR4 wire (`qualifications` per hypothesis per stage; `trail_scores` + `score_refusals`), asserts the score request carries every stage's records for every hypothesis in acceptance order, and the loop test asserts the per-hypothesis records reach the terminal output and the refusal id reaches the external-operation lineage but never `trail_score_record_ids`.
- `scripts/scaffold_polymath_v4.py` — declares this work-log.
- `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` — row 11.275.

## Proof
- Pending in this checkpoint: focused suites `tests/determinism/test_adapter_r5_audit.py`, `tests/contracts/test_adapter_contract_v1.py`, `tests/determinism/test_adapter_runtime_pure.py`, `tests/determinism/test_adapter_product_discovery_loop.py` (dev venv rebuilt with all extras), repo guards, and the live merged-main proof: `set -a; . ./.env; set +a; .venv/bin/python scripts/adapter_mcp_acceptance.py --adapter trail.product_discovery --corpus cinema --harness receipts --harness-receipts tests/fixtures/harness_receipts` against the Trail daemon serving merged main (A41 + HR4). Results are recorded here when they exist; nothing below is claimed before it ran.

## Rejected claims
- "Polymath ranks or reads the per-hypothesis scores" — rejected: only record ids join the lineage; the score value is never read (LAW 1).
- "Polymath selects the winning hypothesis before Trail scores" — rejected: the score request forwards every qualification record of every hypothesis; Trail qualifies and scores each independently.
- "The 2.0.0 manifest keeps working unchanged" — rejected: its terminal `include` gathered the singular `qualification`, which the HR4 wire no longer emits; without the manifest evolution the qualification data would silently vanish from the result.

## Open contract gaps
- The live merged-main proof is the completion gate (owner PHASE 5); until it passes this slice is `in_progress` and the migration is not complete.
- `TAGGED_HYPOTHESES` relies on the scripted-receipt harness; a real harness answering through its own MCP connection tags observations itself, so the portfolio assertions apply to `--harness receipts` runs only.

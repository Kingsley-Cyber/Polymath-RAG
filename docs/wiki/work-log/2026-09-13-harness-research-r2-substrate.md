---
title: "WORK LOG — HARNESS-RESEARCH-MIGRATION-V1 R2: durable hypothesis state, the HARNESS_ACTION pause, admitted-only evidence context, θ/φ as runtime operations (migration 0062)"
change_id: HARNESS-RESEARCH-MIGRATION-V1-R2
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.267
architecture_impact: "Migration 0062 (adapter_hypotheses, adapter_hypothesis_transitions, adapter_harness_actions, adapter_admitted_evidence; adapter_runs + awaiting_harness + harness_action_count). Pure hypothesis ledger `shared/polymath_shared/adapter/hypotheses.py`. Runtime: HARNESS_ACTION issue/pause/receipt in transitions + service + store; AGENT_REASON payloads become durable hypotheses/transitions (θ); admission projections + φ verdicts on automatic steps become durable state or a typed gap; the closed φ dedupe rule on VALIDATE; result lineage gains hypothesis/admitted-evidence/harness/snapshot/score ids; adapter_submit gains `kind`. No new process, route or MCP tool; the fleet needs ONE bounce after merge (worker + orchestrator changed)."
---

## Contract
Plan §3.1, §4, §6-Polymath side, §9 tests A, B, E, F(store-level), G, I. The generic engine now owns hypothesis state and evolution:
θ generates/revises/splits through validated AGENT_REASON payloads; φ verdicts arrive from Trail operations (or the closed VALIDATE
dedupe rule) and are applied as transitions with ≥1 cause; a HARNESS_ACTION step pauses the run durably (`awaiting_harness`, not
claimable by a worker) until a HarnessResearchReceiptV1 for THAT action is submitted; only Trail-admitted observations enter an
AGENT_REASON context (`field_evidence`), raw receipts never do; registry priors travel as `trail_prior` coordinates and are refused as
evidence or cause. Missing directive → `HARNESS_DIRECTIVE_MISSING`; invalid φ verdict → `PHI_VERDICT_INVALID`; invalid admission →
`ADMISSION_INVALID` — typed gaps, never silent drops.

## Changes
- `stores/postgres/migrations/0062_adapter_hypotheses.sql` (replay-safe; applied twice to the dev store; rollback in the header).
- `shared/polymath_shared/adapter/hypotheses.py` — pure ledger: `generate`, `apply`, `context_view`, `lineage_intact`; deterministic ids.
- `shared/polymath_shared/adapter/transitions.py` — `harness_action_count`, `max_harness_actions` budget, `awaiting_harness`, HARNESS_ACTION
  issue (compiled action validated against `harness_action`), `validate_receipt`, prior-citation refusal, `kind` consistency; status view `harness_actions`.
- `shared/polymath_shared/adapter/service.py` — `_context_refs(conn, state)` (knowledge + priors + ADMITTED field evidence), `_compile_harness_action`
  (manifest `harness` block + latest `research_directive` output + live hypotheses + registry snapshot), θ ledger on submit (`_apply_theta`),
  receipts bound to the action row, `_apply_phi_outputs` (admission projection + φ verdicts) on automatic steps, lineage ids in the result.
- `shared/polymath_shared/adapter/store.py` — hypotheses/transitions/harness-action/admitted-evidence CRUD; `harness_action_count` persisted.
- `workers/workers/adapter_step_worker.py` — closed φ rule `config.phi: deduplicate` on VALIDATE (identical statements MERGE into the lowest id).
- `orchestrator/orchestrator/api/adapter.py`, `orchestrator/orchestrator/mcp_server.py` — `kind` on submit; tool docstrings describe HARNESS_ACTION.
- `contracts/adapter/v1/adapter_run_status|run_ref.schema.json` — `awaiting_harness`, nine step types, `harness_actions`.
- `.env.example` — the adapter/Trail variable NAMES.
- Tests: `tests/determinism/test_hypothesis_state_machine.py` (4 pure), `tests/determinism/test_adapter_harness_action.py` (4 on Postgres:
  pause + refusals + receipt + admission + φ/θ + dedupe + lineage; second harness identity; missing directive gap; invalid verdict gap);
  neutrality: `hypotheses.py` scanned, `hypotheses` is no longer a domain word (generic engine state).

## Proof
- 72 adapter tests green (`PYTHONPATH=shared:workers:orchestrator:control .venv/bin/python -m pytest -q` over the 10 adapter suites).
- Migration 0062 applied twice to the dev store (replay-safe); the 0061 status CHECK now admits `awaiting_harness`.
- Existing manifests and the two completed production runs are untouched (additive tables; `harness_action_count` defaults to 0).

## Rejected claims
- That the harness receipt should be validated for truth: it is validated as provenance shape only; TrailSignal admission decides (ADR-0019 §5).
- That an `awaiting_harness` run may be re-executed by a worker: `claim_run` selects `status='running'` only; the pause is durable.
- That priors may seed field evidence: a `trail_prior` cited as support or cause is refused by the ledger and by `validate_submission`.

## Open contract gaps
- The live restart test (`tests/integration/test_adapter_runtime_restart.py`) is extended for `awaiting_harness` at R4 once the fleet runs this code.
- The Trail operations producing `registry_snapshot`, `research_directive`, `evidence_admission`, `hypothesis_verdicts` are R3 (ADR-063); until then
  `trail.product_discovery` 1.0.0 is unchanged and no production manifest declares a HARNESS_ACTION.

---
title: "WORK LOG — HARNESS-RESEARCH-MIGRATION-V1 R1: contracts for harness-executed research and durable hypothesis state (closed vocabulary of nine; five new wire contracts; source neutrality enforced)"
change_id: HARNESS-RESEARCH-MIGRATION-V1-R1
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.266
architecture_impact: "Additive within contracts/adapter/v1 (contracts/README.md rule): HARNESS_ACTION joins the closed step vocabulary; new HarnessActionV1, HarnessResearchReceiptV1, HypothesisStateV1, HypothesisTransitionV1, EvidenceAdmissionV1; step/receipt/submission/result/manifest extended (theta_op, cognitive_op, harness block, hypotheses + registry snapshot in context, field_evidence/trail_prior evidence kinds, lineage ids, budgets). Pure core: vocabulary constants + graph-integrity rules. No runtime behaviour, table, route, tool or fleet change (R2)."
---

## Contract
Plan §3.1 + §9 (tests I, partial E, C-neutrality). Wire contracts for the nine-type vocabulary and durable hypothesis state, declared as
JSON Schema + validated examples; the generic engine gains the vocabulary constants and the three ADR-0019 graph rules
(HARNESS_ACTION needs `harness.action_kind` + objective; `theta_op` only on AGENT_REASON; a BRANCH may never target a HARNESS_ACTION
directly — an evidence-gap loop returns through reasoning). Evidence ROLES are domain data (manifest `evidence_roles` + Trail registry
snapshot), never a runtime constant — the neutrality test keeps it that way.

## Changes
- `contracts/adapter/v1/`: `harness_action`, `harness_receipt`, `hypothesis_state`, `hypothesis_transition`, `evidence_admission` (.schema.json + .example.json);
  extended `adapter_manifest` ($defs harness_action_kind/theta_op, step `cognitive_op`/`theta_op`/`harness`, budgets `max_harness_actions`/`max_hypotheses`,
  top-level `evidence_roles`), `adapter_step` (enum, context.hypotheses, context.registry_snapshot, cognitive_op, theta_op, harness_action, evidence kinds
  `field_evidence`/`trail_prior`), `adapter_step_receipt` (enum, harness_receipt_hash, admission_id, hypothesis_transition_ids), `adapter_submission` (`kind`),
  `adapter_result` (lineage: hypothesis_ids, admitted_evidence_ids, harness_action_ids, harness_ids, registry_snapshot_ids, trail_score_record_ids); examples updated.
- `shared/polymath_shared/adapter/contracts.py`: STEP_TYPES (9), AGENT_ANSWERED_STEP_TYPES, RUN_STATUSES + `awaiting_harness`, HARNESS_ACTION_KINDS, THETA_OPS,
  PHI_OPS, HYPOTHESIS_STATUSES, TRANSITION_KINDS, TRANSITION_ACTORS, CITABLE/PRIOR evidence kinds, EVIDENCE_ROLE_PATTERN.
- `shared/polymath_shared/adapter/manifest.py`: the three graph rules above.
- Tests: `tests/contracts/test_adapter_contract_v1.py` (+5: examples of the 14 contracts validate; roles are pattern-shaped everywhere and action kinds closed;
  no score field can enter a receipt/action/observation (LAW 1); a transition needs ≥1 cause ref and knowledge support needs ≥1 id; the action names no
  engine; step/result carry the new kinds/ids), `tests/determinism/test_adapter_runtime_pure.py` (+4: vocabulary/answered-not-executed; the three graph rules),
  `tests/determinism/test_adapter_runtime_neutrality.py` (+1: no source name or harness id in runtime, worker, route or any manifest).

## Proof
- 61 tests green: contracts 20 (`test_adapter_contract_v1.py`), pure 16, neutrality 3, service/store 6, connector 2, trail client 8, worker registration 2, MCP v2 4
  (`PYTHONPATH=shared:workers:orchestrator:control .venv/bin/python -m pytest -q …`).
- Existing manifests (`trail.product_discovery` 1.0.0, `substack.article_development`, `polymath.knowledge_brief`) still load unchanged: additive contract change.

## Rejected claims
- That evidence roles belong in the generic engine: they were first added to `contracts.py` and tripped the neutrality test (`workaround`); they are domain data
  (manifest + Trail snapshot) with a shape rule only.
- That a HARNESS_ACTION step is executable now: the engine refuses it with the existing typed `STEP_TYPE_UNSUPPORTED` gap until R2 lands the mechanics; no
  manifest declares one yet.
- That `contracts/adapter/v2` is required: every change is additive (new schemas, one enum value, optional fields).

## Open contract gaps
- R2: `awaiting_harness` needs migration 0062 (the 0061 status CHECK), the HARNESS_ACTION issue/pause/receipt path, admitted-only context, and budget
  enforcement for `max_harness_actions`/`max_hypotheses` in `transitions._check_budgets`.
- The Trail-side mirrors of HarnessResearchReceiptV1/EvidenceAdmissionV1 (Pydantic) are R3 (ADR-063).

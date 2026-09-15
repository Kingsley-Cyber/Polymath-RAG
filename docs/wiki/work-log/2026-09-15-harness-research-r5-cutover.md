---
title: "WORK LOG — HARNESS-RESEARCH-MIGRATION-V1 R5 cutover: trail.product_discovery reaches TrailSignal (planned → working), scripted acceptance receipts, Trail HR2/A39/A40 landed"
change_id: HARNESS-RESEARCH-MIGRATION-V1-R5-CUTOVER
date: 2026-09-15
owner: king
last_reviewed: 2026-09-15
status: complete
register: 11.272
architecture_impact: "Polymath: the admitted trail.product_discovery manifest no longer plans its eleven Trail operations (availability working); no runtime code change. Trail (under Trail governance, PRs for owner review): HR2, A39, A40 committed; HR3 chain running; HR3 code proven live on a local stack."
---

## Contract
Owner order of 2026-09-15: merge Trail PRs #7 → #8 → #9, resolve D1 with the existing Trail scoring law (Trail alone owns the authoritative
deterministic opportunity score; model/harness confidence never part of it), admit HR2 from the A37 tip, continue HR2 → HR3 → HR4 →
Polymath cutover → full E2E → old-path retirement; no further governance prerequisite unless a demonstrated repository-integrity failure
requires it. This slice is the Polymath cutover: the manifest stops planning the Trail operations and the acceptance driver gets scripted
harness receipts, so a live run can traverse Trail's seven bounded research operations.

## Changes
- `config/adapters/trail.product_discovery.json`: the eleven EXTERNAL_OPERATION steps (D_project, E_filter, H_gaps, J_admit, L_judge, O_territory, Q_admit, R_qualify, T_admit, U_qualify, V_score) carry `availability: working`; `planned_node` removed.
- `tests/determinism/test_adapter_product_discovery_loop.py`: `test_active_config_ends_honestly_at_the_first_planned_trail_operation` → `test_active_config_reaches_trail_at_the_first_operation` (the first Trail call is `registry.project`; θ state stays durable).
- `tests/fixtures/harness_receipts/{AGENT_RESEARCH,PRODUCT_REALITY_CHECK,SUPPLIER_RESEARCH}.json`: scripted HarnessResearchReceiptV1 files for `scripts/adapter_mcp_acceptance.py --harness receipts` (the same source classes and evidence roles the Trail HR3 e2e admits: six community sources with friction/behavior, three retailers with price/competition, three supplier listings with supply/risk).
- `.env.example` already documents the Trail names (P12, 11.267); unchanged.
- Determinism defect found by the CI flake (pre-existing, not the cutover): the harness action's `hypothesis_ids` were ordered by `sorted(hypothesis_id)`, a hash that includes the random run id, so the order (and the receipt target in `tests/determinism/test_adapter_harness_action.py`, `hypothesis_ids[:1]`) changed from run to run. Fix: migration `0064_adapter_hypotheses_seq.sql` (additive `seq BIGSERIAL`), `store.current_hypotheses` returns generation order with the latest revision, `service` issues live hypotheses in that order. The φ deduplicate rule in `workers/workers/adapter_step_worker.py` merged `sorted(ids)[1:]` (hash order) into `ids[0]` (context order), so the survivor flipped between runs; it now merges later duplicates into the earliest-generated hypothesis; `hypotheses.context_view` (the step context) and the test's fake executor likewise use generation order instead of `sorted(id)`. The fleet database needs `0064` applied before the bounce.
- `docs/wiki/plans/HARNESS-RESEARCH-MIGRATION-V1-PLAN.md`: ledger rows T8, R3, R4, R5, D1, O1, O4 updated to the 2026-09-15 state.
- Trail side (Trail governance, not this repo): HR2 `fa7ddc0` (PR #11), A39 `3f5f5c8` (PR #12), A40 `520d942` (PR #13); HR3 real chain running from the A40 tip; local Trail stack (`handoff-drafts/trail_stack_up.sh`) with the HR3 code answered `registry.project` for the polymath principal (five priors, byte-identical replay, audit row in `v2_research_operations`).

## Proof
- `tests/determinism/test_adapter_product_discovery_loop.py` green (the owner loop with two harnesses through StubTrail; the active config reaches Trail at the first operation).
- `scripts/agent_preflight.py`, `scripts/repo_guard.py`, `scripts/wiki_worm.py --check` green.
- Live: Polymath's `trail_client.mint_principal_jwt` + `TrailMCPClient.operate("registry.project")` against the local daemon on 8767 → `operation_kind registry.project`, `status_revision 1`, registry snapshot `trs-da9942986e52f832`, 5 priors, replay identical; `select operation_kind, principal_id from v2_research_operations` → `registry.project | polymath`.
- The live acceptance (`scripts/adapter_mcp_acceptance.py --adapter trail.product_discovery --harness receipts --harness-receipts tests/fixtures/harness_receipts`) runs after this merge lands on the fleet (fast-forward + `.env` Trail secret + bounce); its receipt is recorded in the next work-log.

- Live acceptance attempt 1 (fleet on 8323105, local Trail daemon on the HR3 tip): the run executed four real Trail operations (`registry.project`, `hypotheses.judge`, `gaps.compile`, `evidence.admit`; audit rows in `v2_research_operations`) and ended in `ADMISSION_INVALID`: Trail's `AdmittedObservationV1` carries `anchored_at` and `authority_class` (`ADMITTED_OBSERVATION`) that the v1 `evidence_admission` schema did not declare. Fixed additively (schema + example); the other Trail results are not schema-validated on the Polymath side and the harness receipt contract already matches field for field.

- Live acceptance attempt 2 (after the schema fix): four Trail operations again, then `ADMISSION_INVALID` on `run_id`: Trail echoes the wire `run_ref` (`run:adr-…`, the slug the client sends) while the v1 admission projection requires Polymath's `adr_…` run id. The worker now keys the projection by Polymath's run id (the Trail operation id remains the cross-system link).

- Live acceptance attempt 3 (after the run-id fix): the admission and the first judge passed; the second judge (`L_judge`) ended in `PHI_VERDICT_INVALID` on `REQUIRE_EVIDENCE`. Trail's φ verdict carries its own `VerdictKind` (REJECT/CHALLENGE/DEDUPLICATE/REQUIRE_EVIDENCE/…) plus the `polymath_transition` it maps to (KILL/CONTRADICT/MERGE/…/null); the worker was passing Trail's `kind` straight to Polymath's transition engine. Fixed: the worker translates each verdict to its `polymath_transition` and drops null transitions (`REQUIRE_EVIDENCE` = keep gathering, not a state change).

- Live acceptance attempt 4 (after the verdict-translation fix): the loop ran through the market and product-reality phases and ended at `S_supply` with `HARNESS_DIRECTIVE_MISSING`. Root cause: Trail's `ResearchResultV1` envelope always carries every optional field, and any operation leaves the ones it does not produce null; the worker copied the nulls, so `opportunity.qualify`'s null `research_directive` shadowed the real directive the territory step produced (`_gather` returns the newest occurrence of a key). Fixed: the worker skips null envelope fields when merging a Trail result.

- Live acceptance attempt 5 (after the null-envelope fix): the loop reached the FINAL Trail operation `opportunity.score`, which Trail refused with `HARD_GATE_UNMET` (LAW 1: no score until the qualification hard gates pass). Not a wire bug — the scripted `PRODUCT_REALITY_CHECK` receipt carried one competition observation, but `competitor_review_analysis` needs two independent groups. The three fixtures now mirror the proven Trail HR3 e2e receipts exactly (2 competition, 3 price, 3 supply, 1 risk, 6 friction + 2 behavior), which satisfy every market-delta and supply gate.

## Rejected claims
- "HR3 is WORKING in Trail": not until the HR3 chain records VERIFIED and the owner merges the stacked PRs; the local proof is a smoke on the HR3 tip.
- "The old research path is retired": `research/` and the Hermes symlink (O6) are removed only after the live acceptance passes.

## Open contract gaps
- Root cause of the CI flake was the hash-ordered harness action (fixed above); the `httpx2<2.13` CI pin is therefore precautionary and can be dropped once CI is green twice on the fixed ordering.
- (Superseded below by the ordering fix; kept for the record.) CI drift, not this slice: on a pure `origin/main` (599eef8, green on 2026-09-14) the CI `test` job now fails `tests/determinism/test_adapter_harness_action.py::test_harness_action_pauses_durably_and_a_receipt_resumes_the_same_run_with_lineage` (`revised` instead of `proposed`). Bisected locally in CI-equivalent environments: the only package that moved between the green and failing runs is `httpx2`/`httpcore2` 2.12.0 → 2.13.0, and downgrading exactly those two restores the pass; the fleet lock stays at 2.12.0. `.github/workflows/determinism.yml` pins `httpx2<2.13` / `httpcore2<2.13` until the mechanism (no first-party module imports httpx2) is identified.
- HR4 (Trail live canary with two harness identities and a controlled restart) is not started; it needs the live acceptance first.
- The owner's own Trail stack and production principal secret (O1/O4) remain owner actions; this session used a local stack with local secrets only.

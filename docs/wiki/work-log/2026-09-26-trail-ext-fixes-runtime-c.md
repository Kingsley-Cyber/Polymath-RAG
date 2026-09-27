---
change_id: TRAIL-EXT-FIXES-RUNTIME-C
owner: "@king"
date: 2026-09-26
status: complete
status_note: "TRAIL-EXT-BUGHUNT-V1, group runtime, batch C: B-49, B-66, B-67, B-68, B-69 and the guide's timestamp rule fixed; B-48, B-50 and B-57 fixed in part (the rest needs a migration, a legacy-manifest change or an owner decision); B-51 was already fixed by B-21; B-53 skipped for an owner decision. Every fix has a test that failed on the code before it."
architecture_impact: "shared/polymath_shared/adapter/{service,transitions,hypotheses,manifest,trail_client,harness_guide}.py, workers/workers/adapter_step_worker.py, orchestrator/orchestrator/api/adapter.py (submit route), governance/trail/embedded.py (the Polymath-authored composition module; no pinned file changed), config/adapters/ecommerce.product_research.json (0.7.2 -> 0.7.3), tests/determinism/test_adapter_trail_wire.py + test_autoresearch_harness_contract.py (the manifest pins), tests/contracts/test_trail_ext_runtime_fixes_c.py (new), tests/determinism/test_adapter_trail_ext_runtime_fixes_c.py (new)."
last_reviewed: 2026-09-26
---

# TRAIL-EXT fixes, group `runtime`, batch C

## Contract
- FIX-IT-ALL (plan of record 11.504), the verified findings of TRAIL-EXT-BUGHUNT-V1
  (`docs/wiki/experiments/trail-ext-bughunt-2026-09-26/README.md`), rules in `handoff-drafts/bugfix_rules.md`. Batch C for this group:
  B-48, B-49, B-50, B-51, B-53, B-57, B-66, B-67, B-68, B-69, plus the guide line the acquisition group left (B-03's rule).
- Built on `feat/fix-it-all` @ `d9b5899d` (this branch was rebased onto it; batch A and B are in it as `3eee2f83` .. `d7139ab6`).
- The owner's B-05 decision of the same day (refusal at submit, no trimming) is its own commit and is recorded in the batch A+B
  work-log (`2026-09-26-trail-ext-fixes-runtime.md`).

## Changes
- **B-48** (a rejected submission left no durable trace).
  - The submit route catches `SubmissionRejected` INSIDE its transaction, so the rejection receipt `service.submit` wrote on the step
    row is committed (it was rolled back with the exception), then answers 422 as before.
  - `service._apply_theta` validates both halves (θ GENERATE, then the transitions) before writing anything: a committed refusal carries
    nothing but its receipt. Before, lawful hypotheses were written before an unlawful transition refused the payload (harmless only
    while every refusal rolled back).
  - In part: the step row has one receipt column, so an accepted retry still replaces the rejection receipt. An append-only history
    needs a migration (open gap).
- **B-49** the SPLIT cap counts the hypotheses that are alive (`generate`'s rule), not killed or merged ones.
- **B-50** `config.refs_must_resolve` may now be a map that TYPES a `*_refs` field: `{"trail_score_refs": ["trail_scores",
  "score_refusals"]}` means those refs resolve only against the record ids (a list of ids, or of records carrying `record_id`) found under
  those output keys; every other `*_refs` field keeps the run-wide rule (`true` behaves as before). `ecommerce.product_research`
  0.7.2 -> 0.7.3 types W_interpret's `trail_score_refs` (its own acceptance rule: "a record id returned by V_score"). The refusal names
  the field, the record kinds and the valid ids. Pins: `test_adapter_trail_wire.py` (version) and `test_autoresearch_harness_contract.py`
  (the W_interpret rule, now `true` or this map).
- **B-51** already fixed by B-21 (batch A+B): `S_gaps` has `gaps_from: trail_gate`, so the supply directive is compiled from the market
  qualification's own open gaps only, through Trail's closed gap shape. Its latent `GAP_HYPOTHESIS_UNKNOWN` part cannot occur in the
  graph: `R_qualify` is `S_gaps`'s only predecessor and changes no hypothesis, so its gaps name exactly the hypotheses `S_gaps` sends. No
  new code.
- **B-57** (a redeploy that renames or removes the step a run stands at).
  - `status` no longer raises: the current step's type is None when the loaded manifest lacks it, and the view carries the versions the
    RUN was started under (as `run_ref` already did), not the loaded file's. `next` works through it.
  - `submit` refuses typed (`MANIFEST_VERSION_UNAVAILABLE`, naming both versions and the step); the run stays parked, so rolling the deploy
    back resumes it.
  - `cancel` commits (its trailing status view raised, so the cancel rolled back and a parked run could not be ended).
  - `advance` ends a running run with the terminal gap `MANIFEST_VERSION_UNAVAILABLE` (also for an adapter no longer admitted), never
    an exception out of the unit.
  - Found while fixing, and fixed with it: under batch A's B-06 net, a manifest SET that does not load (a malformed or half-written file:
    every adapter at once) failed each running run the worker claimed. `load_manifest` / `list_manifests` now raise `ManifestInvalid`
    (a `ManifestError`), which `advance` re-raises and the worker treats like a database outage: it backs off and the run waits for the
    fixed deploy. A manifest that is not JSON is `ManifestInvalid` too. The B-06 regression test now provokes its failure with a
    deterministic database refusal (`psycopg.DataError`), since a renamed step is no longer an exception.
  - In part: the run is still interpreted by whatever manifest file is current; pinning a manifest per run is the real fix (open gap).
- **B-66** embedded mode without `POLYMATH_TRAIL_STORE` is the typed gap `TRAIL_STORE_MISSING` at the run's first Trail step, never a
  silent in-memory audit store; `:memory:` works when asked for explicitly. Every embedded test already sets a store.
- **B-67** the worker rebuilds the daemon client (re-mints its JWT) 300 s before the minted token's `exp`
  (`trail_client.token_expires_within`); a pre-minted token and the embedded client keep today's behaviour.
- **B-68** the embedded transport answers a fault of the core itself (anything but a `PermissionError` / `ValueError`: refusals, invalid
  requests and domain refusals stay tool errors) as a JSON-RPC internal error (-32603). The client raises `TrailInternalError` for it,
  and `exec_external` retries it on the same idempotent request like a transport blip (2 / 8 / 30 s). A locked store is no longer
  recorded as `TRAIL_REFUSED`; a lasting fault is a typed step failure. `embedded.py` is the Polymath-authored composition module
  (`test_trail_core_embedding.py` lists it as AUTHORED); no pinned TrailSignal file changed.
- **B-69** a DOMAIN_OPERATION output carrying a key the runtime reads as TrailSignal's (its result fields other than the
  `research_directive` a domain enriches by design, `hypothesis_verdicts`, `operation_kind`, `qualification`) or as its own (`_…`,
  `trail_…`, `hypothesis_transition_ids`) fails the step (STEP_EXECUTOR_ERROR); nothing of it is applied. The ecommerce binding emits
  none of these (every operation's output keys were collected from the scripted runs).
- **Guide** (`harness_guide.py`, section 4): every receipt timestamp is a UTC date-time ending in `Z`; `sample_n` and `query_count` are
  whole numbers. It said "ISO-8601", which the submit check (B-03) refuses when the offset is not UTC.
- **B-53** SKIPPED, owner decision: see Open contract gaps.

## Proof
- New tests: `tests/contracts/test_trail_ext_runtime_fixes_c.py` (21) and `tests/determinism/test_adapter_trail_ext_runtime_fixes_c.py` (7).
  - Run against the code before the fixes: 23 failed, 4 passed (the code-under-test checks and two guards: a pre-minted token keeps
    its client; a domain output of its own keys passes). The later `test_b57_a_manifest_set_that_does_not_load_never_ends_a_run_the_worker_claims`
    failed on the worker before its fix (the run was ended `failed`).
  - After: 28 passed. Where TrailSignal decides, its embedded core is asked (B-66, B-68).
- Per bid: B-48 `test_b48_a_rejected_submission_keeps_its_receipt_through_the_route`, `test_b48_a_rejected_theta_submission_writes_nothing_to_the_ledger`;
  B-49 `test_b49_the_split_cap_counts_live_hypotheses_as_generate_does`; B-50 `test_b50_trail_score_refs_resolve_only_against_the_score_and_refusal_records`;
  B-57 `test_b57_a_parked_run_whose_step_a_redeploy_renamed_stays_readable_refusable_and_cancellable`,
  `test_b57_a_running_run_whose_step_a_redeploy_removed_ends_with_a_typed_gap`, `test_b57_a_manifest_set_that_does_not_load_never_ends_a_run_the_worker_claims`;
  B-66 `test_b66_embedded_mode_without_a_store_is_a_typed_gap_not_a_silent_memory_store`; B-67 `test_b67_a_daemon_client_is_rebuilt_before_its_minted_token_expires`;
  B-68 `test_b68_a_store_fault_reaches_the_client_as_an_internal_error_and_a_refusal_stays_a_refusal`,
  `test_b68_exec_external_retries_an_internal_fault_and_never_records_it_as_trail_refused`;
  B-69 `test_b69_a_domain_output_carrying_a_key_the_runtime_reads_as_trails_or_its_own_is_refused` (11 keys),
  `test_b69_a_domain_verdict_fails_the_step_and_applies_no_transition`; guide `test_the_guide_asks_for_utc_timestamps_ending_in_z_and_whole_counts`.
- With batch C and the B-05 decision: `tests/contracts -k "not test_live_"` 474 passed; every `tests/determinism/test_*adapter*` /
  `test_*trail*` file except the fleet-database ones 292 passed; the other determinism files that import changed code 116 passed. The
  B-05 commit alone on `d9b5899d`: contracts 453, determinism 285, all passed.
  - Left out, as the rules say: `test_adapter_worker_registration.py`, `test_adapter_product_discovery_loop.py`,
    `test_adapter_service_store.py`, `test_adapter_harness_action.py`. Every run used the dead `POLYMATH_PG_DSN`.
- `scripts/agent_preflight.py`, `scripts/repo_guard.py`, `scripts/wiki_worm.py --check`: exit 0. ruff: no new findings in any changed
  file (compared with `git show HEAD:<file>` at the same path); the two new test files are clean.

## Contract dispositions
- ADAPTER_RUNTIME (`contracts/adapter/v1/adapter_step.schema.json`): TESTED_UNCHANGED. No schema under `contracts/adapter/v1` changed.
  New typed codes fit the existing code pattern: gaps `MANIFEST_VERSION_UNAVAILABLE`, `TRAIL_STORE_MISSING`, `RECEIPT_TOO_LARGE`
  (B-05), refusals `MANIFEST_VERSION_UNAVAILABLE`, `RECEIPT_TOO_LARGE`. The status view keeps its schema (a nullable step type it
  already allowed). Manifest `ecommerce.product_research` 0.7.3. Tests: the whole contracts suite (incl. `test_adapter_contract_v1.py`,
  `test_adapter_worker_evidence_surface.py`), `test_adapter_evidence_boundary.py`, `test_adapter_runtime_pure.py`.
  `test_adapter_product_discovery_loop.py` is a fleet-database test, not run (standing rule).
- MCP_SURFACE (transitive; the operating guide both servers publish changed): TESTED_UNCHANGED. `test_mcp_adapter_parity.py`,
  `test_hosted_mcp_acceptance.py`, `test_mcp_principals_registry.py` (contracts run), `test_mcp_principals_gate.py`,
  `test_mcp_server_v2.py` and `test_autoresearch_harness_contract.py` (both servers publish the same guide) pass.

## Rejected claims
- None was rejected outright. B-51 needed no new code: it is B-21's defect, fixed in batch A+B, and its latent part is unreachable in
  the graph (above).

## Open contract gaps
- B-53, OWNER DECISION: the harness action's source-role lists come from the manifest's `harness` block when it has them and replace
  TrailSignal's directive lists. `_compile_harness_action`'s docstring names the manifest block as the role authority, and
  `research_acquire` ENFORCES the action's `disallowed_source_roles` (`SOURCE_DISALLOWED`). Merging (TrailSignal's exclusions ∪ the
  manifest's, the manifest's preference minus that union) would change what the manifest's lists mean and what the hosted reader refuses
  during field research (marketplace, retailer, ad-library and social-trend reads). No harm was shown (TrailSignal's admission applies
  stage suitability anyway), so it stays until the owner decides.
- B-48: an append-only rejection history needs a migration (a table, or a JSONB column on `adapter_steps`) with a replay proof on an
  isolated database; until then the last rejection is durable until an accepted retry replaces it. The dossier journal still says the
  store keeps no rejected submission.
- B-50: the LEGACY `trail.product_discovery` manifest keeps the type-blind `refs_must_resolve: true` (its identity is mirrored by the
  `contracts/adapter/v1` examples, so bumping it is a contract-example change).
- B-57: pin the manifest per run (the manifest JSON or its hash stored at start, versioned files) and load by the run's own version;
  until then a run whose step a redeploy renamed or removed can only be cancelled or end with the typed gap. A removed adapter FILE still
  makes `status` / `cancel` answer 500 (`UnknownAdapter`).
- B-66: a deploy whose worker environment lacks `POLYMATH_TRAIL_STORE` now ends every run at its first Trail step with
  `TRAIL_STORE_MISSING`. The bug hunt found both keys in the live `.env`.
- B-68, upstream: TrailSignal's daemon (FastMCP) still reports an internal fault as a tool error, so daemon mode still records it as
  `TRAIL_REFUSED`; a structured error code needs a TrailSignal change, not the pinned copy.

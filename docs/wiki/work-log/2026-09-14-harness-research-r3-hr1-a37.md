---
title: "WORK LOG — TRAIL R3 execution: A36 verifier bounds, HR1 registry snapshot compiler landed (PR #8), A37 agent-control verification receipts (rolling governance migration)"
change_id: HARNESS-RESEARCH-MIGRATION-V1-R3-HR1-A37
date: 2026-09-14
owner: king
last_reviewed: 2026-09-14
status: complete
register: 11.271
architecture_impact: "Docs only in Polymath. Trail (under Trail governance, PRs for owner review): A36 governance (HR1–HR3 verifiers bounded to `-k research`), HR1 production (planning context: registry snapshot compiler, 8 strict research contracts, directive/judgement/territory; 0033f74, PR #8), A37 governance (agentctl `check`, content-hash-bound verification receipts, opt-in `close --receipt`, measurement git-owned-diff-v2; 7e6532e, PR #9)."
---

## Contract
Owner order of 2026-09-14: finish A35 → admit HR1 from the verified tip → execute HR1 → then the rolling, backward-compatible governance
optimization (fail-closed worktree isolation; instrumentation during HR1; `agentctl check`; immutable receipts after a passing verify;
verification artifacts non-authoritative; receipt-aware close with a compat path; equivalence proof before changing the default). No governance
prerequisite may block HR1 unless it is a demonstrated impossibility.

## Changes
- A36 (44379bc, PR #7 now A32–A36): the demonstrated impossibility — HR1 v1 passed its exact verifier directly (652 s) but the governor executes the
  latest evidenced node's verifier inside `verifier_timeout_seconds` (600) on every pass → `RUN_VERIFIER_EXECUTION: TimeoutExpired`. A36 bounds the
  HR1–HR3 verifiers to `-k research`; ranks A36 129, HR1–HR4 131–134; digests recomputed; one focused test.
- HR1 v2 (admission 986ac71 → 0033f74, PR #8, base = the A35 branch): `src/trail_signal/contexts/planning/` (public contracts + ports; domain
  registry compiler, gap compiler, judgement), `data/source_capabilities.csv` side table, 8 registry entries + generated schemas, 16 research tests,
  replay fixture; gap rows HR-001/HR-002 WORKING with proof tags; hash-bound measurement; bounded exact verifier 9 s + recorded full suite.
- A37 (7e6532e, PR #9, base = the HR1 branch): agentctl `check` (guard + inexpensive task commands, `proof: none`, journaled but never a
  verification gate), `receipt.json` issued only by a passing `verify` (task id, build-run id, authoritative tree without derived task artifacts,
  manifest, governance files, test suite, task contract), `close --receipt` opt-in refusing on any mismatch, measurement `git-owned-diff-v2`
  (derived verification artifacts skipped; v1 runs recompute under v1); rank 132; HR2–HR4 → 133/134/135; equivalence matrix + self-test + focused test.
- Fail-closed worktree isolation: `handoff-drafts/worktree_guard.sh` + `trail_run_tools.assert_worktree` (requested path exists, cwd == toplevel,
  origin == TrailSignal, bound task == expected) before every mutation; guard pipelines fixed to abort for real (`| tee || exit` was fail-open).

## Proof
- Instrumentation baseline (legacy flow, HR1 finish): verify 125 s → remeasure ~60 s → verify 127 s → remeasure ~60 s → close 188 s (~9.5 min);
  identity hashes (manifest, policy, validator, test suite) unchanged throughout; dirty files 33 → 41 → 42 (verify-created logs/record/HANDOFF) =
  the measurement race (`handoff-drafts/logs/hr1_baseline_metrics.json`, `hr1_finish.log`).
- A37 rehearsal (throwaway worktree, deleted): record VERIFIED, governor PASS pre/post; finish = verify 115 s (receipt issued) → measurement digest
  reproduced byte-for-byte after verify (`fresh_equals_recorded_log: true`, no remeasure) → `close --receipt` 52 s (`proof: receipt`) → governor PASS
  plain and vs main → guard PASS → commit. Real A37: committed 7e6532e (verify 116 s issuing the receipt → measurement digest reproduced byte-for-byte after verify, no remeasure → close --receipt 53 s with proof: receipt → governor PASS plain and vs main → guard PASS → commit → pre-push replay PASS), PR #9 base = the HR1 branch.
- Equivalence matrix (tests/architecture/test_agent_control.py): unchanged tree accepted; changed source / manifest / policy / test rejected; wrong
  task rejected; altered verification record rejected; derived log ignored; failed verify leaves no receipt; legacy close still verifies; receipt
  reusable across processes. agentctl self-test 8/8.

- Defects found and fixed by the real run before publication (each with a regression in the matrix): the receipt must be an implicit task-lifecycle path
  for the scope guard (exact `expected_files` tasks); `agentctl check` needs the stacked task's base ref and is journaled, never a closed gate; a directory
  named like a test module under `tests/` must not enter the test-suite hash; the receipt placeholder must exist before the verify-time guard snapshot so the
  pre-push replay accepts a receipt-closed commit (attempt 1 = 430b978, reset, never pushed).

## Rejected claims
- That A37 changes the default close proof: it does not; plain `close` still re-verifies until the recorded equivalence evidence covers a production slice (A38).
- That receipts cache anything by time or task id alone: validity is content-hash equality on every identity input, per task.
- That Trail GitHub CI redness is a diagnostic of these branches: CI fails on `main` itself (environment); the local canonical governor is the truth.

## Open contract gaps
- Owner review of PR #7 (D4 = ADR-063 acceptance record), PR #8 (HR1), and the A37 PR; HR2 (evidence + scoring contexts) from the A37 tip after owner D1;
  HR3 (O1/O4); HR4; then R5 in Polymath.

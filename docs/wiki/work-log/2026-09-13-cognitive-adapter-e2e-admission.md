---
title: "WORK LOG — COGNITIVE-ADAPTER-TRAIL-E2E-V1 E0 (part 1): admit the owner's unified-E2E plan files through governance and reconcile the handoff branch with production"
change_id: COGNITIVE-ADAPTER-TRAIL-E2E-V1-E0-ADMISSION
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.257
architecture_impact: "Docs/governance only. The two owner-directed plan files (PLAN + START-HERE) are declared in scaffold TREE so repo_guard/preflight admit them (PR #3 / issue #4 blocker). The handoff branch is merged with architecture/evidence-first-v5 (11.161-11.256) so the E2E work starts from production truth. No runtime change."
---

> Owner goal (2026-09-13, Stop-hook + issue #4): ONE end-to-end workflow with Polymath as the composition root and
> TrailSignal as a required internal subgraph; first action = admit the two plan files through the normal
> declaration/work-log process, CI green, merge PR #3, then execute START-HERE.

## Contract
`repo_guard.py` and `agent_preflight.py` reject any repository file not declared in `scripts/scaffold_polymath_v4.py::TREE`
("undeclared repository file"). PR #3 (`handoff/unified-adapter-trail-e2e` → `main`) failed `repo-governance` and
`agent-preflight` on exactly the two new plan files. The handoff branch was cut at `1c61a6f` (09-09, register 11.160)
and lacked 143 production commits — including the mandated Parent-MAP forensic audit (11.253), the owner's lifting of
the §19 hold with the completed cinema backfill (11.255), the Cloudflare lanes (11.254/11.255) and the control-tick fix
(11.256) — so "repository state" on that branch contradicted the plan's own reconciliation gate.

## Changes
- **Merge** `architecture/evidence-first-v5` (6b1edd5) into `handoff/unified-adapter-trail-e2e` — automatic, 0 conflicts
  (the branch's only own changes were the two plan files); ledger now runs to 11.256 on the handoff branch.
- **scripts/scaffold_polymath_v4.py::TREE**: declare `docs/wiki/plans/COGNITIVE-ADAPTER-TRAIL-E2E-V1-PLAN.md`,
  `docs/wiki/plans/COGNITIVE-ADAPTER-TRAIL-E2E-V1-START-HERE.md` and this work-log. No ignore rules, no guard change.
- **Register 11.257**, **CONTINUITY checkpoint** (E0 part 1).
- **Plan files**: `last_reviewed: 2026-09-13` added to both frontmatters — `wiki_worm --check` requires it ("missing
  last_reviewed"); content untouched.
- **CI hygiene (determinism workflow RED on the production branch since ≤ 2026-09-12 18:44, never green for these tests)**:
  `test_groq_routing::test_config_map_lanes_are_de_shared_from_the_profile_key` re-pinned to the current doc_parent_map pool
  (the Groq ring + openrouter prefix is asserted exactly; the two Cloudflare map lanes admitted by 11.255 must be dedicated and
  never use a Groq key — the de-sharing intent is unchanged); `test_retirement_proofs_not_vacuous` runs the dry-run scripts with
  `sys.executable` instead of a hard-coded `.venv/bin/python` (absent in worktrees and CI); `test_synthesis_attempt_telemetry`
  uses a stand-in `litellm` module when the SDK is not installed (CI installs none) — the subject is the bound-retry loop, whose
  assertions are unchanged. `test_document_profile_stage` (RED since 11.254 put summary lanes on doc_profile) is green again
  because 11.255 removed them.

## Proof
- Guards on the merged handoff worktree: `agent_preflight.py` ok, `repo_guard.py` ok, `wiki_worm.py --check` ok (recorded in the commit).
- Local: 47 green across `test_synthesis_attempt_telemetry` / `test_groq_routing` / `test_retirement_proofs_not_vacuous` /
  `test_document_profile_stage` on the merged worktree (the 3 CI failures reproduced locally first: the retirement test needs a
  `.venv` the worktree lacks; the pin test fails on the new lanes; the telemetry test only fails where litellm is absent).
- PR #3 checks before this change: `guard` FAIL, `preflight` FAIL (undeclared files), `test` PASS, `validate` PASS. After the push the
  same workflows re-run on the merged branch; merge only when green (issue #4).
- **Plan gate §2 (forensic hold) — reconciled, not bypassed**: the mandated audit was executed and recorded (11.253, `docs/wiki/experiments/pmap-forensic-audit-2026-09-13/`);
  the owner then explicitly lifted the hold ("run the backfill on cinema", 11.255) and the backfill completed (3,810 → 0 unresolved).
  There is no active hold on the merged branch; the plan's "do not resume merely because quota reset" is moot (owner-directed, done).
- **TrailSignal bootstrap (read-only)**: `~/trail-signal-os` @ `c5dd8a6` (main); `agentctl doctor` PASS, `agentctl status` PASS,
  `active_task=ACP1 task_status=complete`. Pre-existing uncommitted local edits in Trail (a P4 build_run's gap_matrix/journal/
  verification + two data CSVs) were found and NOT touched.

## Rejected claims
- **"Declare the files on the stale branch and merge the 75-commit PR as-is"** — REJECTED: the register on that branch ends at
  11.160; any new row collides with production's 11.161+ on the later merge, and the plan's §2 gate would be evaluated against a
  CONTINUITY that still says the hold is active. Reconciling first is what START-HERE step 3 requires.
- **"Bypass repo_guard for docs"** — REJECTED (owner: do not bypass, no ignore rules).

## Open contract gaps
- **PR #3 now carries production** (main is 218 commits behind `evidence-first-v5` + this branch); merging it fast-forwards main to
  production reality. Flagged for the owner; the merge is executed only on green CI as directed.
- **E0 part 2 — the two-repo evidence gap matrix** — next work-log (`…-E0-GAP-MATRIX.md`); no runtime mutation before it.

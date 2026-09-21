---
change_id: CONSOLIDATION-MIGRATION-PHASE9-DETERMINISTIC-SKILL-DEPLOY
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "none — a governance script and an adaptation of the imported engine's parity verifier. No agent host was touched. Branch `migration/ecommerce-consolidation`, not merged."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 9 (mechanism): one source, a deterministic copy, a version receipt, parity verification

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 9: determine why a physical deployed copy exists; if physical deployment remains required, create deterministic deployment with one source, a version
receipt and parity verification; do not manually maintain two sources. `MIGRATION_POLICY.md` "Hermes: verify its technical reason". Decision `AUTO_DECISIONS.md` M-016.

## Changes
- `scripts/deploy_ecommerce_skill.py` — source = `adapters/ecommerce/`; DRY RUN by default; `--execute` copies only new / changed files (sha-verified after each copy) and then runs the engine's own
  verifier, which writes `<target>/MIRROR_RECEIPT.json`; `--check` verifies only (exit 1 on drift); refuses a dirty source unless `--allow-dirty`; refuses the source as its own target; NEVER deletes anything
  in the target. What is copied is exactly what the verifier compares, so runtime state, candidates, exports, compiled registry, patches, SQLite files and the private field-evidence ledger are never deployed.
- `adapters/ecommerce/tests/mirror_check.py` (the engine's existing parity verifier, REUSED) — when the reference is a subdirectory of a larger repository the receipt names THAT repository's commit and the
  subdirectory (`containing_repo_subdir`); `git_dirty` is scoped to the subdirectory; `--no-hermes-link` for staging / test targets. Standalone behaviour is unchanged.
- `scripts/README.md` row; `tests/contracts/test_deploy_ecommerce_skill.py` (3).

## Proof
- WHY a physical copy (evidence class READ): Hermes' gateway is a launchd job (`ai.hermes.gateway`; `launchctl list`), and launchd processes on this machine cannot read `~/Documents` (the standing TCC finding);
  the engine came to live at `~/.hermes/standalone/opportunity-research` by register 11.274. A physical copy outside `~/Documents` therefore remains required. NOT tested by making the gateway read a
  `~/Documents` path.
- Temp targets only: a dry run writes nothing; a deploy of 190 files reaches parity, its receipt names this repository's HEAD + `adapters/ecommerce` + the engine version; forbidden artifacts are absent; a second
  deploy writes 0 files; a hand-edited file makes `--check` exit 1 naming it, and a re-deploy repairs it without deleting an unrelated file; the source is refused as a target.
- Read-only dry run against the REAL Hermes copy (nothing written): 182 of 190 files identical; a deploy would add `binding.py` and update 7 files — exactly this migration's adaptations (`controller.py`,
  `executors.py`, `lived_world.py`, `registry.py`, `report.py`, `tests/mirror_check.py`, `tests/run_all.py`).
- Engine suite 609 / 609 after the verifier change. Guards 0 / 0 / 0 / READY. Evidence class: `INTEGRATION_EXECUTED` on temp targets; the real host: `READ` only.

## Rejected claims
- "Hermes runs the consolidated engine." It does not: its copy is still v2.3.0 as mirrored on 2026-09-20, and deploying to it is a change to the owner's agent host that has not been made.
- "Manual mirroring is gone." The mechanism exists; it replaces manual mirroring only once it is used for the real target, after the merge.

## Open contract gaps
- No architecture contract affected: NOT_AFFECTED. The actual deploy to `~/.hermes` follows the production merge (the source must be the merged `production`, not a branch).

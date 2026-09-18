---
title: "WORK LOG — agent-safety stack (2/2): automation + AGENTS workflow"
change_id: AGENT-SAFETY-AUTOMATION
date: 2026-09-18
owner: governance
last_reviewed: 2026-09-18
status: complete
architecture_impact: "Automates the contract-impact + static-security checks so future agents follow the workflow without being told (session/edit/commit/CI). Adds a tracked pre-commit hook (installed by `make hooks`), Makefile targets (impact / lint-security / hooks), a CI workflow (contract-impact.yml), and AGENTS.md 5.3. Dev/CI only — no runtime dependency, removable."
---

## Contract
Make the impact/security checks automatic and self-documenting so no future agent needs to be
told to run them. Use the smallest maintainable mechanism (the repo has no pre-commit framework):
a tracked hook installed via Make, Makefile targets, a CI gate, and one concise AGENTS.md section.
Acceptance: `make hooks` installs a working pre-commit hook that prints the impact set and blocks
an out-of-scope deferred-contract change; `make lint-security` runs changed-scope ruff `S`; AGENTS
teaches the before/after/complete workflow.

## Changes
- New `scripts/hooks/pre-commit.sh` — runs `contract_impact.py --check --staged` (prints blast
  radius; blocks only a DEFERRED contract touch) + advisory `ruff --select S` on staged Python.
- `Makefile` — `.PHONY` + targets `impact` (staged contract impact), `lint-security`
  (`ruff --select S --ignore S101,S404,S603,S607` over shared/orchestrator/workers/control/scripts),
  `hooks` (install the pre-commit hook into the shared git hooks dir).
- New `.github/workflows/contract-impact.yml` — PR gate: `contract_impact --check` over the PR
  range + changed-scope ruff `S` (advisory).
- `AGENTS.md` §5.3 "Change-impact workflow" — before (inspect callers via graft + contract map),
  after (`contract_impact`), before-complete (one disposition per impacted contract).

## Proof
`make hooks` installs `.git/hooks/pre-commit`; a staged edit runs the hook → prints CHANGED +
TRANSITIVE contracts and exits 0 (no deferred touch); a simulated deferred-contract change exits 1.
`make impact` and `make lint-security` run. `python3 scripts/contract_impact.py --check --staged`
exits 0. repo_guard / wiki_worm green. Application runtime unchanged (dev/CI tooling only).

## Rejected claims
- Adopt a pre-commit framework (rejected — none exists; a tracked hook + `make hooks` is the smaller maintainable equivalent).
- Hard-block commits on ruff `S` findings (rejected — pre-existing debt would block unrelated work; advisory in the hook, reported in CI, classified per the bug pass).
- Run full-repo analysis on every save (rejected — changed-scope only, per the mission).
- Make Polymath runtime depend on the tools (rejected — dev/CI only, removable).

## Open contract gaps
- None for the automation itself. Next: run the tooling against the completed Librarian work (audit) and a bug pass, then continue P5b.

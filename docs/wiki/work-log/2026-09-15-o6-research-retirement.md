---
title: "WORK LOG — HARNESS-RESEARCH-MIGRATION-V1 O6: old-path retirement — research/ package, research_* MCP tools and the research-harness workflow removed; Hermes skill preserved standalone"
change_id: HARNESS-RESEARCH-MIGRATION-V1-O6-RETIREMENT
date: 2026-09-15
owner: king
last_reviewed: 2026-09-15
status: complete
register: 11.274
architecture_impact: "Removes the retired TRAIL OS research/ package (207 tracked files) and its six research_* MCP tools + helpers from orchestrator/orchestrator/mcp_server.py, and deletes .github/workflows/research-harness.yml. The Hermes opportunity-research skill is PRESERVED as a standalone user-level skill outside both repositories (~/.hermes/standalone/opportunity-research), symlinked from ~/.hermes/skills/business/opportunity-research, calling Polymath's public HTTP surface — no coupling to Polymath internals or Trail. A dead-path guard (tests/contracts/test_research_package_removed.py) keeps the old path from returning. Orchestrator is a bundle tree (bundle_integrity.PRODUCTION_DIRS) → a fleet bounce lands the removal in the running MCP surface."
---

## Contract
Owner directive of 2026-09-15, after R5 was proven green and frozen: "Point [the Hermes symlink] to a preserved standalone copy of the Hermes skill, outside both Polymath and Trail. Do not point it into Trail. Do not retire the user-facing skill yet." Authorized sequence: (1) copy the Hermes skill material to a standalone location; (2) repoint `~/.hermes/skills/business/opportunity-research` to it; (3) smoke-test; (4) delete Polymath `research/` and all retired `research_*` machinery; (5) add the dead-path guard `test_research_package_removed`; (6) run repo guards / tests; (7) proceed to HR4; (8) HR4 must include the multi-hypothesis wrong-selection canary. Plan P10 (`HARNESS-RESEARCH-MIGRATION-V1-PLAN.md`) is the removal authority; R5 acceptance is green (register 11.273); the only live dependency on `research/` was that Hermes symlink.

## Changes
- **Preserved (outside both repos):** the whole `research/` tree copied to `~/.hermes/standalone/opportunity-research` (265 files, `__pycache__` excluded); it is self-contained (no internal symlinks; the controller calls Polymath over HTTP via `POLYMATH_URL`, default `127.0.0.1:7200`; only `pyyaml` beyond stdlib). `~/.hermes/skills/business/opportunity-research` repointed from `polymath-v4-main/research` to the standalone copy. Both changes are user-level, outside version control.
- `research/` — the entire package (207 tracked files) removed with `git rm -r`; untracked/gitignored runtime leftovers (`state/`, `candidates/`, `__pycache__`, sqlite) deleted from the worktree.
- `.github/workflows/research-harness.yml` — removed.
- `orchestrator/orchestrator/mcp_server.py` — the `research_*` tool section (comment header, `_RESEARCH_ROOT`/`_RESEARCH_STATE`, `_research_env`/`_research_state_path`/`_research_cli`, and `research_init`/`research_step`/`research_submit`/`research_status`/`research_corpus`/`research_report`) removed; the six names dropped from `_TOOL_NAMES` (25 → 19 tools); the now-unused `import sys` and `import subprocess` dropped; the MCP `instructions` string trimmed of its research_* guidance (keeps the corpus workflow).
- `scripts/scaffold_polymath_v4.py` — 187 TREE entries removed (all `research/` files + the workflow); declares the new guard test.
- `tests/contracts/test_research_package_removed.py` — new dead-path guard (4 assertions): `research/` absent, workflow absent, no `research_*` tools/helpers in the active runtime/config/contract surfaces (history/docs excluded by design), scaffold declares no `research/`.
- `scripts/README.md` — O6 retirement changelog note (companion for the `scripts/` change).

## Proof
- Skill smoke-test (standalone, via the Hermes symlink path): `python/controller.py doctor` → `{"ok": true, "errors": [], graphs: 5, policies/schemas/settings/registry: true}`. The skill's state dir (`candidates/`) resolves into the standalone copy, so runtime writes never touch a repo.
- `orchestrator.mcp_server` imports cleanly: 19 tools, `ask` present, `research_init` absent.
- Guards green: `tests/contracts/test_research_package_removed.py` (4), `tests/contracts/test_retired_paths.py`, `tests/determinism/test_retirement_proofs_not_vacuous.py` — 13 passed. `scripts/repo_guard.py` ok (declared == actual after removing research/ from both the TREE and disk); `--base` companion check satisfied (scripts/ change carries the README companion + this work-log).
- Fence honoured: the one open (orphaned) adapter run was cancelled first → 0 open runs before editing the orchestrator bundle tree; the fleet is bounced after merge/ff so the running MCP surface drops the research_* tools.

## Rejected claims
- "Point the Hermes skill into Trail." Rejected by owner: Trail is a runtime/service authority, not the home for a Hermes prompt/skill; coupling Hermes to Trail internals would recreate the coupling R5 removed. The standalone copy calls Polymath's public surface only.
- "Retire the user-facing skill now." Rejected by owner: R5 is green but HR4 (multi-hypothesis canary) is still ahead; preserving the skill avoids an unnecessary user-facing break.
- "Delete research/ before repointing the symlink." Rejected: the symlink pointed at `polymath-v4-main/research`; the copy + repoint + smoke-test precede the removal so Hermes never loses its skill.
- "ingest_field_evidence.py is retired research machinery." Rejected: it is a general field-evidence ingestion script, not a `research_*` tool; out of the P10 removal scope, left intact.

## Open contract gaps
- Committed vs live: the removal reaches the running orchestrator only after the fleet bounce recorded in Proof; until then the live MCP surface still advertises research_* (now pointing at a deleted `research/` — inert, uncalled, Hermes uses the standalone skill).
- Next: HR4 — two harness identities, restart/resume, deterministic replay, and the REQUIRED multi-hypothesis wrong-selection canary (qualify targets `hypotheses[0]`; do not let it silently disappear).

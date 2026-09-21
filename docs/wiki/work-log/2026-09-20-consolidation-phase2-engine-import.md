---
change_id: CONSOLIDATION-MIGRATION-PHASE2-ENGINE-IMPORT
owner: "@king"
date: 2026-09-20
status: complete
architecture_impact: "additive — a new top-level directory `adapters/ecommerce/` holds the ecommerce engine imported from TRAIL_AGENT_AUTORESEARCH @ a7baa66. No runtime package (`shared/`, `workers/`, `control/`, `orchestrator/`) changes, nothing imports the engine yet, no manifest or contract change, no bounce needed. Branch `migration/ecommerce-consolidation`, not merged."
last_reviewed: 2026-09-20
---

# Consolidation migration — Phase 2: import the ecommerce engine additively

## Contract
`docs/migration/EXECUTION_PLAN.md` Phase 2: import the useful AutoResearch implementation additively, no redesign on import, preserve source
organization, exclude secrets / private ledgers / DBs / `.env` / caches / private historical observations, migrate the behavioural tests.
Gate: imported domain logic passes expected tests in its new location. `MIGRATION_POLICY.md` INV-2 (reuse before rewrite), INV-7 (privacy by
default), INV-8 (additive). Decision record: `docs/migration/AUTO_DECISIONS.md` M-006 (on `production`).

## Changes
- `adapters/ecommerce/` — 193 files from `git archive a7baa66` of `~/Documents/polymath-rebuild/TRAIL_AGENT_AUTORESEARCH` (TRACKED files only, so
  nothing git-ignored there — run state, candidates, exports, compiled registry, review patches, the private field-evidence ledger, SQLite — could
  ride along). Source layout kept: `python/`, `prompts/`, `schemas/`, `graph/`, `registry/`, `tests/`, `docs/`, `SKILL.md`, `manifest.yaml`.
- Excluded after the archive: `MIRROR_RECEIPT.json` (describes the Hermes mirror, not this location), `.github/` (the source repo's CI; this repo has
  its own), `registry/friction_library.upstream.patch` (its diff header carries a machine-local home path; INV-7 "if uncertain, exclude and
  document" — the ten friction-family rows it proposes stay in `registry/` itself, and their upstream-or-drop fate is Phase 7).
- ONE adaptation, in `adapters/ecommerce/tests/run_all.py`: the three cross-repo pins (EvidencePacket schema sha, harness-receipt schema byte copy,
  Polymath's own `transitions.validate_receipt` against a built receipt) looked for a SIBLING `polymath-v4` checkout and fell back to a pass when
  absent. `_PMV4` now resolves to the containing repo when the engine sits at `<repo>/adapters/ecommerce`, else the sibling; `POLYMATH_V4_PYTHON`
  names the interpreter when the checkout is a git worktree without its own `.venv`. The schema byte copies and their sha pins are unchanged.
- `scripts/repo_guard.py` — `IGNORED_PREFIXES` gains the engine's runtime-artifact paths under `adapters/ecommerce/` (state, compiled registry,
  patches, candidates, exports, the private ledger): git-ignored by the engine's own `.gitignore`, never repository files.
- `scripts/scaffold_polymath_v4.py` — 192 `TREE` declarations for the import (`candidates/.gitkeep` sits under an ignored prefix) + the new test.
- `tests/contracts/test_ecommerce_engine_import.py` — 5 pins: layout present · no private / runtime artifact tracked · no real home path in tracked
  text · the TrailSignal evidence ledger is header-only · the engine's own suite + `doctor` pass here under this repo's interpreter against a
  throwaway loop DB with no cross-repo pin skipping.

## Proof
- Engine suite in the new location: **609 / 609** (`tests/run_all.py`), `controller.py doctor` exit 0 — under the Hermes venv interpreter AND
  under this repo's `.venv` interpreter (36.8 s); `OPPORTUNITY_RESEARCH_DB` pointed at a scratch file both times. Before the adaptation: 606 / 606
  with three pins skipping; after: the three pins EXECUTE against this repo and pass.
- `tests/contracts/test_ecommerce_engine_import.py` + `tests/contracts/test_research_package_removed.py`: 9 passed. Negative control: a planted
  file containing a real-shaped home path turned `test_no_machine_local_path_in_tracked_text` red; probe removed.
- Privacy scan over the copy before `git add`: 0 key-like strings, bearer tokens, API keys, e-mail addresses or Reddit user URLs; the one
  machine-path file excluded (above). `registry/trailsignal/research_evidence.csv` is header-only (332 bytes).
- Guards in the worktree: `agent_preflight` 0 · `repo_guard` 0 · `wiki_worm --check` 0 · `bundle_integrity` READY.
- Proof level: `WORKTREE_INTEGRATION_PROVEN` for the import (the executed path is the imported code: the suite runs from `adapters/ecommerce`).
  No fenced package changed, so the editable-install resolution hazard does not apply.

## Rejected claims
- "The ecommerce capability is migrated." It is IMPORTED. Nothing in the adapter runtime calls it; the governed run still cannot use it. That is
  Phase 3 (binding seam) onward.
- "Every historical behaviour is proven here." The suite is fixture-driven; the one complete real run (`calib_books_01`) is a historical artifact
  in the source repo's git-ignored `candidates/` and was deliberately NOT imported (INV-7: raw private observations).
- "Two registries are reconciled." They are not: `adapters/ecommerce/registry/` is now a third physical copy beside Trail's `data/` and the Hermes
  deployed copy. One authority is Phase 7.

## Open contract gaps
- No contract in `architecture/contract-dependencies.yaml` is changed or impacted: NOT_AFFECTED (new directory, no importer).
- `architecture/dependencies.json` has no owner for `adapters/`: DEFERRED to Phase 3, where the binding seam decides who may import the engine
  (an `ARCHITECTURE.md` change needs its ADR + changelog + refactor entry in the same slice).
- The engine keeps byte copies of two Polymath contracts (`schemas/evidence_packet.json` dialect, `schemas/harness_receipt.schema.json`): DEFERRED
  to Phase 4, which replaces the copies with reads of `contracts/` now that both live in one checkout.
- `registry/README.md` and `WORKLOG.md` in the import still mention the excluded patch file: text-only, left as imported history.

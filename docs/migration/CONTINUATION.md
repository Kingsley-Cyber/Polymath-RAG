# Migration Continuation

> Agent-owned restart boundary. Update at every meaningful phase transition. A fresh session continues from this file, the
> controlling documents and the repositories — never from chat history.
>
> **Instruction hierarchy:** 1. user / repository constitutional rules · 2. `MIGRATION_POLICY.md` · 3. `BOOTSTRAP_CONTEXT.md` ·
> 4. `EXECUTION_PLAN.md` · 5. applicable ADRs · 6. `AUTO_DECISIONS.md` · 7. `CONTINUATION.md` · 8. current source + tests + git
> state. Repository facts can invalidate stale factual claims; they do not silently invalidate migration intent. Material
> contradictions are handled under the policy's stop conditions.

## Mission
Polymath ecommerce consolidation migration: one `polymath-v4` checkout carries the complete governed ecommerce reference
implementation — `adapters/ecommerce/` (harvested `TRAIL_AGENT_AUTORESEARCH` intelligence) + `governance/trail/` (the required
deterministic Trail core) on the EXISTING adapter runtime. Harvest behaviour, not architecture. Ecommerce first; no speculative
generic infrastructure.

## Current Phase
**Phases 0–1 — DONE.**
**Phase 2 — import — DONE, gate MET** (`072f1cc`): the engine sits at `adapters/ecommerce/` (193 files of AutoResearch @ `a7baa66`); its own suite passes THERE, 609 / 609 + `doctor`, under this repo's interpreter.
**Phase 3 — domain binding seam — DONE, gate MET** (`076eb6b`, ADR-0020, M-007): new automatic step type `DOMAIN_OPERATION`; a real engine law governed a run through the existing `service.advance` + `EXECUTORS`.
**NEXT: Phase 4 — EvidencePacket integration.** Both phases live on branch `migration/ecommerce-consolidation` (worktree `../pmv4-consolidation`), NOT merged; the live fleet is untouched.

## Repository State
- polymath-v4 `production`: clean, docs only since `758ff8a`; 130+ commits ahead of `origin/main`, nothing pushed.
- **Migration worktree `~/Documents/polymath-rebuild/pmv4-consolidation`, branch `migration/ecommerce-consolidation`** = `production@758ff8a` + `072f1cc` (Phase 2) + `076eb6b` (Phase 3). Clean. It has no `.venv`: run with `/Users/king/Documents/polymath-rebuild/polymath-v4/.venv/bin/python` and `PYTHONPATH=$PWD`.
- Parked worktrees: `pmv4-atom-scope` (Item 2D, UNCOMMITTED, 7 files) · `pmv4-m1-repro` (`review/m1-reproductions` @ `eb63bef`, red on purpose). Merged, removable: `pmv4-governed`, `pmv4-packet-text`.
- AutoResearch: `main` @ `a7baa66` (v2.3.0), clean, 3 commits ahead of GitHub. PUBLIC. Still the engine the Hermes skill runs (the import is a copy; nothing was removed — INV-9).
- Trail: `~/trail-signal-os-worktrees/A41` @ `de64d84`, clean. Untouched.
- Hermes: deployed copy `standalone/opportunity-research` v2.3.0; three skill text files uncommitted (owner's commit).

## Current HEAD / Branch
`production` (docs) · `migration/ecommerce-consolidation` @ `076eb6b` (code).

## Completed
- Owner reframe recorded in the plan of record; harvest map written (registers 11.362; commits `59a4b60`, `9dfd3c3`).
- `docs/migration/` complete: owner-controlling `MIGRATION_POLICY.md`, `BOOTSTRAP_CONTEXT.md`, `EXECUTION_PLAN.md` (+ `README.md`,
  `NEW_SESSION_BOOTSTRAP_PROMPT.md`) installed BYTE-IDENTICAL from `~/Documents/polymath-rebuild/polymath_migration_bootstrap.zip`; the earlier,
  longer owner text kept as `BOOTSTRAP_CONTEXT_EXTENDED.md` (the bundle wins on any difference; it alone states the target tree
  `adapters/ecommerce/` + `governance/trail/` and the report acceptance list). Agent-owned: `CAPABILITY_MAP.md`, `PARITY_MATRIX.md`,
  `AUTO_DECISIONS.md` (M-001…M-005), `ADR-TRAIL-EMBEDDING.md` (DRAFT), `FINAL_MIGRATION_REPORT.md` (skeleton), this file.
- `/polymath-bootstrap` verified: detects `docs/migration/`, reads the documents in order, stops when the policy or plan is
  missing, baseline-first search, Trail / AutoResearch / wrapper names, test isolation, evidence vocabulary (10 of 10).
- Tools discovered: `graphify` and `graft` present; CodeGraph and Ponytail absent.

## Current Architecture
On the migration branch: `adapters/ecommerce/` (the engine, its own layout, its own suite) + `adapters/ecommerce/binding.py` (the ONE door: `OPERATIONS` table, JSON in / JSON out)
+ `DOMAIN_OPERATION` in the existing runtime (`exec_domain` in the existing `EXECUTORS`; out of process; minimal environment; typed gap / `STEP_EXECUTOR_ERROR`). Domain code computes and never
owns state. `service.py`, `transitions.py`, `store.py` and the three shipped manifests are unchanged. Live system: unchanged (four locations; governed adapter → Trail daemon over MCP).

## Capabilities Migrated
IMPORTED (all, fixture-proven in place). BOUND to the runtime: `hypotheses.validate_bridge` (bridge + portfolio admissibility laws). In a product manifest: none yet.

## Authority Map
Polymath: knowledge, EvidencePacket, adapter runtime, ledger, lineage, MCP · ecommerce adapter (to be harvested): niche /
population / planning / hypothesis structure / ideation + variations / sourcing / parsers / lead join / report · Trail:
admission, freshness, independence, judgement, territory, qualification, score / refusal, registry · agent host: execution.
Full table: `CAPABILITY_MAP.md` "Duplicate Authority Map".

## Important Auto Decisions
M-002 docs on `production`, code in the migration worktree · M-003 the bundle controls · M-004 baseline = existing runs · M-005 commerce corpus at Phase 10 after Item 2D ·
**M-006** import via `git archive` (tracked files only), three exclusions, history: the engine lived here as `research/` until 11.274 retired it to the Hermes skill — the O6 dead-path guard stays green ·
**M-007** the seam = one step type + out-of-process binding (rejected: `EXTERNAL_OPERATION` reuse, `VALIDATE` overload, in-process import, host-side only, SDK).

## Tests Passed
In the migration worktree, all database-free, `POLYMATH_PG_DSN` unset: engine suite 609 / 609 + `doctor` · `test_ecommerce_engine_import.py` 5 (INV-7 privacy pins incl. a negative control) ·
`test_adapter_domain_operation.py` 23 · existing `test_adapter_contract_v1` / `_worker_evidence_surface` / `test_mcp_adapter_parity` / `_runtime_neutrality` / `_runtime_pure` / `_r5_audit` /
`test_mcp_server_v2` / `test_research_package_removed` green · guards 0 / 0 / 0 / READY. Reusable asset: `tests/determinism/_adapter_memory_store.py` (runtime tests with NO Postgres).

## Known Failures
- Governed path: D1–D7 and M1-01..M1-12 — none fixed (they are scheduled inside Phases 4–7, where the code they live in is reworked).
- NOT RUN on the branch (deliberately): `test_adapter_evidence_boundary.py`, `test_adapter_product_discovery_loop.py` — they commit `running` runs into the shared Postgres. Run them in the merge window with the fleet drained, or port them onto the memory store.
- Pre-existing red determinism tests on `production` (3 attributed, 5 not baselined). Historical baseline fails canary 2 of 9.

## Current Blocker
None. (The commerce corpus is pre-authorized by the policy and scheduled for Phase 10 — M-005. Item 2D must be merged before it.)

## Next Exact Action
**Phase 4 — EvidencePacket integration** (gate: existing ecommerce understanding logic consumes CURRENT Polymath evidence and produces valid downstream structures). Work in `../pmv4-consolidation`.
1. Read how governed knowledge reaches a step: `B_retrieve` / `F_retrieve` outputs (`_rows`, `_trim_rows`, `_refs_from_rows` in `workers/workers/adapter_step_worker.py`) and the engine's row shape
   (`adapters/ecommerce/python/corpus_polymath.py` `rows_from_response`, `packet_errors`; `schemas/corpus_observation.json`). Write the ONE mapping governed evidence rows → engine `corpus_evidence` rows inside `binding.py`
   (no HTTP from domain code: the runtime already retrieved; `corpus_polymath.py` stays LEGACY_STANDALONE).
2. Bind the first understanding operations that consume that evidence: `understanding.lenses` (`executors.py:52`) and the primitives lineage check (`lived_world.py:471,493` `lineage_ref_errors`, `validate_relevance_map`).
   Watch `structural_lookup`: `registry.load_snapshot` WRITES a compiled file when missing — a domain operation must not write into the repo; give it a temp dir or pre-compile.
3. Replace the engine's two schema BYTE COPIES with reads of `contracts/` when the engine sits inside this repo (keep the pinned copies for standalone use); the three cross-repo pins already point here.
4. Test with `_adapter_memory_store.py` + a fixture manifest whose retrieve executor returns recorded evidence rows (no live retrieval until Phase 11-E).
5. Then Phase 5 in dependency order (population → hypotheses onto `HypothesisStateV1` → field research planning → products → product reality → supply). Draft the ecommerce product manifest
   (`config/adapters/ecommerce.product_research.json`) only when at least the population + hypothesis operations are bound; do NOT edit `trail.product_discovery.json` (INV-9).

## DO NOT REDO
- The comparison, the dependency facts, the registry-drift check, the historical-run inspection (`CAPABILITY_MAP.md`, harvest map).
- The R2a run and the M1 reproductions (never re-run against the shared Postgres).
- The import (Phase 2) and the seam decision (M-007 lists the rejected alternatives with reasons — do not re-litigate).
- Any node-by-node port, second runtime / SDK / ledger, package reshuffle, in-process import of the engine's flat modules, or import of private ledgers.

## Relevant Commits
`production`: `59a4b60` reframe + harvest map · `9dfd3c3` boundary model · `23d517e` bootstrap · `758ff8a` owner bundle installed · `988070a` M-006 + M-007.
`migration/ecommerce-consolidation`: `072f1cc` Phase 2 import (register 11.363) · `076eb6b` Phase 3 seam (register 11.364, ADR-0020). Branch `review/m1-reproductions` `eb63bef`.


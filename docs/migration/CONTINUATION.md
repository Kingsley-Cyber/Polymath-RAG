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
**Phase 0 — DONE** (gate: no unresolved risk of overwriting user work — all four locations clean except Hermes' three uncommitted skill text files, which the migration does not touch).
**Phase 1 — capability forensics — gate MET** (`CAPABILITY_MAP.md`: every major responsibility has a target owner, a source implementation and an action). Two sub-items stay open inside it: the
Trail wire-model file (`workflow/public/operations.py`) and the domain-binding seam decision (Phase 3).
**NEXT: Phase 2 — import the ecommerce implementation additively.** Controlling documents installed from the owner's bundle (M-001 resolved, M-003).

## Repository State
- polymath-v4: `production`, clean, 130+ commits ahead of `origin/main`, nothing pushed. Worktrees parked: `pmv4-atom-scope`
  (Item 2D, UNCOMMITTED, 7 files) · `pmv4-m1-repro` (`review/m1-reproductions` @ `eb63bef`, 12 reproductions red on purpose).
  Merged worktrees safe to remove: `pmv4-governed`, `pmv4-packet-text`.
- AutoResearch: `main` @ `a7baa66` (v2.3.0), clean, 3 commits ahead of GitHub (`a7dbc52`, v2.1.2). PUBLIC repo.
- Trail: `~/trail-signal-os-worktrees/A41` @ `de64d84`, clean, == local `origin/main` ref. Untouched.
- Hermes: `skills/business/opportunity-research` → symlink → `standalone/opportunity-research` (deployed copy v2.3.0). Three
  tracked skill text files edited and uncommitted (owner's commit). Reason for the deployed copy: unknown.

## Current HEAD / Branch
`production` — the document-bootstrap commit (see Relevant Commits).

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
Unchanged. Four locations, no code moved. The governed adapter (28-step `trail.product_discovery`) calls Trail's daemon over
MCP; AutoResearch runs standalone and as the harness (receipt + journal + report bridge, v2.3.0).

## Capabilities Migrated
None.

## Authority Map
Polymath: knowledge, EvidencePacket, adapter runtime, ledger, lineage, MCP · ecommerce adapter (to be harvested): niche /
population / planning / hypothesis structure / ideation + variations / sourcing / parsers / lead join / report · Trail:
admission, freshness, independence, judgement, territory, qualification, score / refusal, registry · agent host: execution.
Full table: `CAPABILITY_MAP.md` "Duplicate Authority Map".

## Important Auto Decisions
M-001 (resolved) · M-002 documents on `production` declared in the scaffold `TREE`; all migration code in a dedicated worktree, new
top-level packages outside the fence set · M-003 the bundle's controlling files control; earlier bootstrap kept as EXTENDED · M-004 today's
existing test runs ARE the Phase 0 baseline (no re-run; Trail baselined at Phase 6) · M-005 commerce corpus = reconstruct the 10-document set
from preserved sources under a NEW corpus id at Phase 10, after Item 2D is merged.

## Tests Passed
None run in Phase 0 (read-only). Last known: AutoResearch 609 checks + doctor green (TG4 close); static guards green today.

## Known Failures
- Governed path: D1–D7 (first real run R2a died at `L_judge`) and M1-01..M1-12 (external review, reproduced) — none fixed.
  A run cannot pass `L_judge` and the product stages without D1, M1-06, M1-07, M1-08; M1-04 is an availability risk.
- Pre-existing red determinism tests on `production` (3 attributed, 5 not yet baselined) — see the M1 verification work-log.
- Historical baseline fails canary 2 of 9.

## Current Blocker
None. (The commerce corpus is pre-authorized by the policy and scheduled for Phase 10 — M-005. Item 2D must be merged before it.)

## Next Exact Action
**Phase 2 — import AutoResearch additively, no redesign on import.**
1. `git worktree add ../pmv4-consolidation -b migration/ecommerce-consolidation production` (M-002).
2. Copy from `~/Documents/polymath-rebuild/TRAIL_AGENT_AUTORESEARCH` @ `a7baa66` into `adapters/ecommerce/`, preserving its layout: `python/`, `prompts/`,
   `schemas/`, `graph/`, `registry/` (WITHOUT `registry/research_evidence.csv`, `registry/compiled/`, `registry/patches/`), `tests/`, `docs/`, `SKILL.md`,
   `manifest.yaml`, `policies` under `graph/`. EXCLUDE: `state/`, `candidates/`, `exports/`, `*.sqlite3*`, `__pycache__/`, `MIRROR_RECEIPT.json`, any `.env`.
   Run a secrets / personal-data scan over the copy before `git add` (INV-7); record what was excluded.
3. Declare every imported file in `scripts/scaffold_polymath_v4.py` `TREE` (generate the lines; `repo_guard` fails otherwise).
4. Gate: `~/.hermes/hermes-agent/venv/bin/python adapters/ecommerce/tests/run_all.py` + `python/controller.py doctor` pass in the NEW location with
   `OPPORTUNITY_RESEARCH_DB` pointed at a temp file (expect ≈ 606: the cross-repo checks look for a sibling `polymath-v4`; repoint them to the repo root as the
   first ADAPT, which also removes the schema byte-copies' sha pins in favour of reading `contracts/` directly).
5. Update `PARITY_MATRIX.md` (Migrated path column), this file, commit on the migration branch. Do NOT merge to `production` yet.
Then Phase 3: decide the binding seam from the verified convention (one global `EXECUTORS: dict[step_type → Executor]` in
`workers/workers/adapter_step_worker.py:509`; `Executor = (step, RunState, Manifest) → ExecOutcome`) — record as M-006 before coding.

## DO NOT REDO
- The AutoResearch-vs-governed comparison, the dependency facts per harvest target, the registry-drift check, the historical-run
  inspection — all recorded (`CAPABILITY_MAP.md`, harvest map).
- The R2a run and the M1 reproductions (preserved; do not re-run against the shared Postgres — `-k memory` only).
- Any node-by-node port, second runtime / SDK / ledger, package reshuffle, or import of private ledgers.

## Relevant Commits
`a125103` R2a record · `faedb20` M1 evidence record · `59a4b60` reframe + harvest map · `9dfd3c3` boundary model ·
`23d517e` bootstrap + first continuation · `c583dc6` CONTINUITY pointer · the document-bootstrap commit (this change) ·
branch `review/m1-reproductions` `eb63bef`.

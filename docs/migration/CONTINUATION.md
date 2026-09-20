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
**Phase 0 — repository truth and capability map: DONE (read-only).**
**BLOCKED before Phase 1:** `MIGRATION_POLICY.md` and `EXECUTION_PLAN.md` were never supplied (decision M-001).

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
- `docs/migration/` created: `BOOTSTRAP_CONTEXT.md` (owner text), `CAPABILITY_MAP.md`, `PARITY_MATRIX.md`, `AUTO_DECISIONS.md`,
  `ADR-TRAIL-EMBEDDING.md` (DRAFT), `FINAL_MIGRATION_REPORT.md` (skeleton), this file.
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
M-001 Phase 0 only, without inventing the two missing controlling files · M-002 documents on `production` declared in the
scaffold `TREE`; all migration code in a dedicated worktree, new top-level packages outside the fence set.

## Tests Passed
None run in Phase 0 (read-only). Last known: AutoResearch 609 checks + doctor green (TG4 close); static guards green today.

## Known Failures
- Governed path: D1–D7 (first real run R2a died at `L_judge`) and M1-01..M1-12 (external review, reproduced) — none fixed.
  A run cannot pass `L_judge` and the product stages without D1, M1-06, M1-07, M1-08; M1-04 is an availability risk.
- Pre-existing red determinism tests on `production` (3 attributed, 5 not yet baselined) — see the M1 verification work-log.
- Historical baseline fails canary 2 of 9.

## Current Blocker
1. `MIGRATION_POLICY.md` and `EXECUTION_PLAN.md` content was not supplied. 2. No commerce corpus exists for the real E2E
(`cinema` only; `ecom-meta-v1` dropped by the owner; a second corpus needs Item 2D merged first).

## Next Exact Action
1. Owner supplies the two controlling files → install them verbatim, declare them in the scaffold `TREE`, commit.
2. Then start the plan's Phase 1. Unknowns 1 and 3 of `CAPABILITY_MAP.md` are partly closed (Trail closure = 16 modules / 6,944 lines,
   third-party `pydantic`, `typing_extensions`, `packageurl`; 57 % of it is unrelated contexts' contract modules pulled by the wire models ·
   executors are one global `dict[step_type → Executor]` in the worker, no per-adapter binding). Remaining reads: `workflow/public/operations.py`
   (can the research wire models stand alone?), the store port, and the Hermes deployed-copy reason.

## DO NOT REDO
- The AutoResearch-vs-governed comparison, the dependency facts per harvest target, the registry-drift check, the historical-run
  inspection — all recorded (`CAPABILITY_MAP.md`, harvest map).
- The R2a run and the M1 reproductions (preserved; do not re-run against the shared Postgres — `-k memory` only).
- Any node-by-node port, second runtime / SDK / ledger, package reshuffle, or import of private ledgers.

## Relevant Commits
`a125103` R2a record · `faedb20` M1 evidence record · `59a4b60` reframe + harvest map · `9dfd3c3` boundary model ·
`23d517e` bootstrap + first continuation · `c583dc6` CONTINUITY pointer · the document-bootstrap commit (this change) ·
branch `review/m1-reproductions` `eb63bef`.

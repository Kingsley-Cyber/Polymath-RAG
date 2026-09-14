---
title: "WORK LOG — HARNESS-RESEARCH-MIGRATION-V1 R0: admit the harness-executed hypothesis research boundary (ADR-0019, plan + cutover ledger, research/ frozen)"
change_id: HARNESS-RESEARCH-MIGRATION-V1-R0
date: 2026-09-13
owner: king
last_reviewed: 2026-09-13
status: complete
register: 11.265
architecture_impact: "Governance only: ADR-0019 supersedes ADR-0018 decisions 2/5/6; refactor 0013; the plan-of-record + §19 cutover ledger; supersession banners on the V1 plan and START-HERE; research/ declared FROZEN (no code removed yet). No runtime, contract, schema, config or fleet change."
---

## Contract
Owner directive (2026-09-13): migrate Polymath + TrailSignal to the harness-executed hypothesis research architecture as one governed
live migration (no parallel replacement; one authoritative implementation per responsibility; migration matrix before major mutation).
R0 admits the authority change through Polymath's normal mechanisms and records repository truth in both repositories.
Acceptance: guards green; ADR/refactor/plan/matrix declared in TREE; every superseded surface named with its old → new row.

## Changes
- `docs/wiki/decisions/0019-harness-executed-hypothesis-research.md` (accepted under the owner directive; supersedes ADR-0018 §2/§5/§6).
- `docs/wiki/refactors/0013-harness-research-migration.md` (R0–R5 ledger).
- `docs/wiki/plans/HARNESS-RESEARCH-MIGRATION-V1-PLAN.md` — plan-of-record + §7 migration matrix (cutover ledger), §10 owner decisions.
- Supersession banners on `COGNITIVE-ADAPTER-TRAIL-E2E-V1-PLAN.md` (§7/§8/E3/E5/E6) and `-START-HERE.md`.
- `research/README.md` banner: FROZEN — migration input only (removed at R5).
- Register 11.265; scaffold TREE declarations.

## Proof
- Repository truth established from disk in both repositories (AGENTS/build contracts/laws/ADR index/ledger; adapter runtime; manifest v1;
  Trail CSVs, scoring implementations, MCP surface; the unpushed Trail OCP branch line ADR-061/062 + OCP1 contracts; Polymath `research/`
  registry copy: 8 CSVs byte-identical to Trail `data/`, 3 drifted AHEAD — friction_library +10 rows, niche_candidates +6, seed +6).
- `agent_preflight.py`, `repo_guard.py`, `wiki_worm.py --check` green on this commit (recorded in the commit message).
- Trail governance baseline on origin/main recorded in the plan §7 (pre-existing failures named by test id).

## Rejected claims
- That ADR-061/062 (unpushed Trail branches, 2026-08-08) are current authority: they are not on `origin/main`; their composition
  (Trail-owned hypothesis IR, Trail pulls knowledge from Polymath) is reversed by the owner's 2026-09-13 directives; their contract
  vocabulary is reused where it matches.
- That `research/` can stay as a "compatibility" path: it is a second product-research authority with a second registry compiler and
  a drifted registry copy; it is frozen now and removed after R5.
- That contracts must move to `contracts/adapter/v2`: `contracts/README.md` permits additive change within v1 (new schemas, one enum value).

## Open contract gaps
- Trail-side authority (ADR-063, A32, HR1–HR4) is admitted through Trail governance in R3; its acceptance authority is the owner.
- Owner decisions listed in plan §10 (score authority, registry delta upstream, OCP branch disposition, principal + stack).

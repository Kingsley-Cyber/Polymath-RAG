# CONTINUATION — live state of the consolidation (update in place; newest facts on top)

## 2026-09-20 — migration NOT started. Waiting for `MIGRATION_POLICY.md` and `EXECUTION_PLAN.md`
`BOOTSTRAP_CONTEXT.md` was received and saved. Its two companion files were not found on disk (both repos, the handoff folder,
Downloads, Desktop). The policy defines the stop conditions, so no execution step has been taken. No code has changed.

### Bootstrap claims — verified against the repositories (2026-09-20)
| Claim | Result |
|---|---|
| Destination `polymath-v4`, local-first | branch `production` @ `9dfd3c3`, clean; nothing pushed; `origin/main` is far behind; recovery is by TAG (see `docs/wiki/plans/CONTINUITY-REPORT.md`) |
| AutoResearch: GitHub main ≈ v2.1.2, later work local-only, ≈ 609 checks | GitHub `main` = `a7dbc52` (v2.1.2); local `main` = `a7baa66` (v2.3.0), 3 commits ahead, clean; `tests/run_all.py` = **609 checks** + `controller.py doctor` green when last run (TG4 close); the deployed copy runs 606 (three cross-repo checks collapse) |
| Trail `A41` clean and equal to `origin/main` | clean; HEAD `de64d84` == local `origin/main` ref (no fetch was made) |
| Hermes holds a deployed copy | `~/.hermes/skills/business/opportunity-research` is a symlink → `~/.hermes/standalone/opportunity-research` (v2.3.0, not a git checkout; parity with the repo = true at the last mirror). WHY it is a copy is NOT established. Unverified lead: launchd-started processes cannot read `~/Documents` on this Mac (TCC) |
| Historical run: 5 concepts × 2 variations, 135 supplier candidates (96 / 39), 8 leads with price + MOQ, 146 Reddit observations | verified in `~/.hermes/standalone/opportunity-research/state/calib_books_01.json` (2026-09-04). Also true: supplier name hard-coded `unresolved` (`sourcing_exa.py:49`); CJ produced 0 leads; 0 / 146 observations carry a harvest date; canary 2 of 9 failed; no rendered HTML exists for that run |
| The in-process Trail seam was demonstrated | yes: `ResearchOperationService.operate` was executed in-process with an in-memory store and the compiled A41 registry (branch `review/m1-reproductions`, `tests/review_m1/trail/`). Size of the needed core: evidence 487 + planning 782 + scoring 347 lines, plus the operation wrapper in `contexts/workflow` and 12 registry CSVs (784 KB), out of 37,132 lines |

### What the bootstrap does not say and a fresh session must know (all in the repo)
- **Read first:** `docs/wiki/reports/2026-09-20/ECOMMERCE-MIGRATION-HARVEST-MAP.md` — capability map, dependency facts per harvest
  target (most are `(state, policies)` functions over dicts; `bridge.py` has zero imports), what stays behind
  (`executors.comments`, the score half of `executors.scoring`), parity fixtures, the nine canaries, duplicates, §10 boundary
  model and the verified constraints (ADR-063 ownership; Trail admits only observations linked to a LIVE hypothesis,
  `admission.py:209-211`; AutoResearch is field-first).
- **Known defects on the governed path** (none fixed): D1–D7 from the first real run and M1-01..M1-12 from the external review —
  `docs/wiki/work-log/2026-09-20-governed-convergence-tg5-r2a.md`, `…-external-review-m1-verification.md`, registers 11.360 / 11.361.
  A run cannot pass `L_judge` and the product stages without D1, M1-06, M1-07, M1-08; M1-04 is an availability risk. M1-01 / 02 /
  03 and D4 are inside Trail's core: once that core is embedded, they become ordinary Polymath changes.
- **Parked work:** worktree `pmv4-atom-scope` holds Item 2D (corpus-scoped `search_atoms`), UNCOMMITTED, 10 new tests green.
  Worktree `pmv4-m1-repro`, branch `review/m1-reproductions` @ `eb63bef`, holds 12 reproductions that are red on purpose.
- **Corpus:** Polymath holds ONE corpus, `cinema`. It is lawful for mechanical runs only. The owner dropped `ecom-meta-v1` from
  the plan. The real ecommerce E2E in the Definition of Done has no corpus yet, and a second corpus requires Item 2D first.
- **Registry drift:** the AutoResearch mirror of Trail's registry carries +6 seeds, +10 friction families
  (`registry/friction_library.upstream.patch`), +6 niche candidates that Trail does not have. Embedding ONE registry must
  decide their fate explicitly.
- **Privacy exclusions already identified:** `registry/research_evidence.csv` (Reddit authors + quotes), `state/`, `candidates/`,
  `*.sqlite3`, any `.env`.
- **Two governance systems now apply in this repo:** the repo's own change-slice discipline (`AGENTS.md`: work-log, register
  row, scaffold `TREE`, guards = 0) and the migration's `docs/migration/` set. `repo_guard` requires every new file to be
  declared in `scripts/scaffold_polymath_v4.py`. The migration policy should state how the two relate.
- **Fence:** edits under `shared/`, `workers/`, `control/` quarantine the live fleet until ONE supervised bounce. New top-level
  packages (`adapters/`, `governance/`) are outside that set.

### Genuine blockers
1. `MIGRATION_POLICY.md` and `EXECUTION_PLAN.md` are missing.
2. The commerce corpus for the real E2E.

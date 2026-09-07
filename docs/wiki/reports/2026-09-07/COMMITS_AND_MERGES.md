---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# COMMITS AND MERGES — ledger of the 2026-09-07 cycle

Branch for every commit: `architecture/evidence-first-v5`. Merge mechanism for every entry: push → four CI checks (agent-preflight, contracts, determinism, repo-governance) → `git -C ../polymath-v4-main merge --ff-only` → push `main`. No merge commits exist; "merged into main" below means fast-forwarded.

| Commit | Purpose | Files / subsystems | Tests | Merged into | Notes |
|---|---|---|---|---|---|
| `a9bbb58` | B1 NEAR-DUPLICATE-GUARD-V1 (register 11.121) | `shared/polymath_shared/dedup.py`, intake worker, upload route, tests, work-log | dedup + replay regression | main | v3.3 port; refuse ≥ 0.95 |
| `cdf1cf4` | BACKLOG B14 queued | OWNER-BACKLOG | — | main | docs |
| `2c2c601` | Implementation to-do + B15 queued | plans | — | main | docs |
| `a336d91`, `71c2126` | BACKLOG B16 queued / refined | OWNER-BACKLOG | — | main | docs |
| `7297fdf` | B16 COMPILER-CORPUS-CONTEXT-V1 (11.122) | `compiler_context.py`, `chat_plan`, `ui.py`, tests, work-log | compiler-context pins | main | IMPLEMENTED (owner hand-test) |
| `93b3edd` | REGION-EXCLUSION-V1 (11.123) | `candidate_engine.py`, `document_region.py`, tests | region pins | main | — |
| `306e499` | DOCUMENT-PROFILE-V1 step 1 (11.125) | `document_profile/compiler.py`, `prompt.py`, plan | 7 pins | main | — |
| `0953a10` | DOCUMENT-PROFILE-V1 steps 2–4 (11.126) | `context.py`, `projection.py`, `doc_profile_worker.py`, `tickets.py`, `fleet_autopilot.py`, `process_supervisor.py`, providers, limiter, tests | 17 | main | dormant until fleet boot |
| `3e0181b` | INTERACTIVE-RELIEF-V1 (11.124) | `ui.py`, embedder caps, work-log | relief pins | main | IMPLEMENTED |
| `f7bb695` | Profile aims 10/10/15/15/10/10/10, lane rotation (11.127) | compiler, prompt, worker, tests | 22 | main | — |
| `8af6790` | Isolated pool = six Groq lanes + fallbacks | `cloud_providers.json`, `limiter.yaml`, `.env.example`, tests | pins | main | keys never in repo |
| `0c78579` | DOCUMENT-PROFILE-V1 step 5: backfill 67/67, compiler v3.1, six slots (11.128) | compiler, prompt, worker, FLEET, autopilot, scripts (`backfill_document_profiles.py`, `document_profile_gate.py`), registry rows, gate JSON, reports folder (first two files), continuity checkpoint | 37 targeted + repo_guard | main (ff 09:18 local) | first live backfill |
| `22f93c3` | Profile lanes paced to 2 compound requests/key/min | `limiter.yaml`, stage test pin, reports, work-log, continuity | 16 | main (ff 09:23 local) | header-measured |
| *(closeout)* | docs(handoff): 2026-09-07 successor bootstrap, hooks, superseded drafts | `docs/wiki/reports/2026-09-07/*` (11 files), `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/README.md`, `docs/wiki/README.md`, continuity, work-log, scaffold | repo_guard, wiki_worm, preflight, 75 targeted tests | main after CI | hash appended below once created |

## Merges
No merge commits. Each fast-forward is verified by `git -C ../polymath-v4-main rev-parse HEAD` == the commit and `git ls-remote origin main` == the commit (VERIFICATION.md).

## Closeout commit

---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# NEXT ACTIONS — ordered continuation (2026-09-07)

## P0 — must happen first (session bootstrap, no code)
1. **Re-read from disk**: `AGENTS.md` → `docs/wiki/plans/CONTINUITY-REPORT.md` (2026-09-07 checkpoint) → this folder's `README.md`, `BE_AWARE.md`, `UNFINISHED_WORK.md`. Why now: the fleet runs from this worktree and several rules are invisible in code. Verification: you can state which paths trigger the fence and why the profile lane uses compound.
2. **Confirm live state** before any edit: `git status --short` (clean), `curl 127.0.0.1:7200/ready`, `scripts/backfill_document_profiles.py --corpus cinema --status` (67 done), `project_qdrant` backlog count. If the owner is testing in the UI, do not touch control/ shared/ workers/.

## P1 — required to complete the current architecture
3. **U1 — DOCUMENT_PROFILE retrieval lane** (`candidate_engine.py`, `chat_retrieval.py`, `compiler_context.py`). Prerequisites: none. Outcome: profile-nominated documents' children enter fusion with provenance; titles ranked by the same source; env flag default OFF until measured. Checkpoint: lane pin tests green; 10-question loops on fixtures B and M hold floors; punch question cites the Laban Workbook with `titles_rank=off`. Risks: gating instead of boosting; using exploration surfaces in normal answers; reusing the wrong vector (must be the PRIMARY's).
4. **Backfill other corpora** with `scripts/backfill_document_profiles.py --corpus <id>` one corpus at a time (six slots, ≈ 6 docs/min; RPD 250/key/day ⇒ ≤ 1 500 documents/day). Checkpoint: `--status` shows tickets done = documents, quality p50 ≥ 0.9, no `dead`.
5. **U2 — phase B flip** (owner go): DAG entry ahead of `verify_projections`, out of `NON_BLOCKING_STAGES`, tolerant readiness. Checkpoint: census shows every previously ready run still ready; new document without a profile is NOT ready; `test_control_plane_v2` order pin updated in the same commit.

## P2 — reliability, measurement, tests
6. **U3 — relief after-measurement** on the owner's next 40 UI turns; restore the rerank deadline to 8 s when the `project_qdrant` backlog is 0 (owner edits `.env`; respawn the orchestrator slot). Flip 11.124 to DONE with the numbers.
7. **U5 — durable shared limiter** (DB row per lane) before any corpus larger than a few hundred documents is backfilled.
8. **U11 — test hygiene**: make the `rerank_deadline_s` pin independent of the shell's `.env`; stabilise census parity under a moving backlog.
9. **U6 — `--requeue-below`** on the backfill script; re-profile the RAPO paper.

## P3 — owner-gated design work (no code until the owner says)
10. **U7 pure-rank composition** — ask for the rule; measure after U1.
11. **U9 ladder L3** — owner go; build as compiler vocabulary only.
12. **U8 lean prompt** — after U3.

## P4 — optional / hygiene
13. U10 deletions, key rotation (owner), Postgres parallel gather back on at the next container recreate, embedder OOM-split monitoring (consider 2 / 4096 if judge timeouts return).

Each step ends with: work-log entry (Contract / Changes / Proof / Rejected claims / Open gaps), register row, declarations in the same commit, `repo_guard` unpiped, push, four CI checks, ff `main` from `../polymath-v4-main`.

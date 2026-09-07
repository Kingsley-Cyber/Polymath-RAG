---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# UNFINISHED WORK, DEPENDENCIES AND HOOKS — state at the 2026-09-07 wrap-up

Companion to `BE-AWARE-REPORT.md` (same folder). The single bootstrap remains `docs/wiki/plans/CONTINUITY-REPORT.md`; this file is the dated snapshot it points to. Register rows for the day: 11.121 (B1 near-duplicate guard), 11.122 (B16 titles), 11.123 (region exclusion), 11.124 (interactive relief), 11.125–11.128 (DOCUMENT-PROFILE-V1).

## A. Finished today (on the branch, CI-gated, fast-forwarded to main unless the last row says otherwise)

| Item | Status | Where |
|---|---|---|
| B1 NEAR-DUPLICATE-GUARD-V1 (v3.3 port, 3 layers, replay exemption) | DONE | 11.121, work-log `2026-09-07-b1-near-duplicate-guard` |
| B16 COMPILER-CORPUS-CONTEXT-V1 (titles, dynamic top-40, dense default) | IMPLEMENTED (owner tests by hand) | 11.122, work-log `2026-09-07-b16-compiler-corpus-context` |
| REGION-EXCLUSION-V1 (TOC / furniture out at union) | DONE | 11.123, work-log `2026-09-07-region-exclusion` |
| INTERACTIVE-RELIEF-V1 (length rule, ceiling, carry on rewrites, rerank deadline 12 s, embedder caps) | IMPLEMENTED — after-measurement pending | 11.124, work-log `2026-09-07-interactive-relief` |
| DOCUMENT-PROFILE-V1 steps 1–5 (compiler, context, stage, projection, pool, backfill 67/67, scale-out) | DONE (steps 1–5) | 11.125–11.128, work-log `2026-09-07-document-profile-stage` |
| Branch hygiene: remote branches pruned to `main` + `architecture/evidence-first-v5` | DONE | manifest `~/Documents/polymath-rebuild/branch_cleanup_manifest_2026-09-07.txt` |

## B. Unfinished — with the dependency that blocks each

| # | Work | Depends on | Owner decision needed? |
|---|---|---|---|
| 1 | **DOCUMENT-PROFILE step 6** — retrieval lane `DOCUMENT_PROFILE`: embed once → prefetch identity / theme / questions / searches / title → RRF → top-k documents → their children enter fusion with `DOCUMENT_PROFILE` provenance (boost, never gate) → receipts; the B16 title ranker reads the same ranking | the profile collection (now populated: 67 points); `candidate_engine` fusion seam; the gate numbers in `experiments/document-profile-gate-gate1.json` | No — it is the owner's plan of record |
| 2 | **Phase B readiness** — `doc_profile` ahead of `verify_projections` in `STAGE_DAG`, out of `NON_BLOCKING_STAGES` (`ingested != query_ready`) | step 6 proven on the gate; new-document path already mints `doc_profile` (phase A) | Owner go on the flip (it changes when a document starts serving) |
| 3 | Relief after-measurement: judge-timeout rate on the next 40 owner UI turns, generation seconds, carry on rewrite turns → record in the relief work-log | owner UI turns (the 15 receipts since the boot are the test suite's own fixtures) | No |
| 4 | Return `POLYMATH_CHAT_RERANK_DEADLINE_S` 12 → 8 | the `project_qdrant` backlog draining (19 tickets open at 15:05Z; the embedder is the shared bottleneck at ~5.8 texts/s) | No |
| 5 | Profile pool limiter is per PROCESS (threading locks) and resets on restart: RPD is advisory; six slots now each start on their own key (`POLYMATH_DOC_PROFILE_LANE_OFFSET`) and hold rpm 12 / conc 1, but a durable shared budget (Postgres row or supervisor-level) does not exist | design choice: DB-backed limiter vs supervisor budget | Design call; propose DB-backed since receipts already live there |
| 6 | ~~Move the profile lanes to a plain instruct model~~ **CLOSED 2026-09-07 — keep `groq/compound` (owner):** the free-plan table gives compound TPM 70K with no daily token cap; gpt-oss-120b / Qwen sit at TPM 8K / TPD 200K (≈ one profile request a minute per key). Measured: one compound profile request = 12 internal calls, 38.5k internal tokens, 40 s; the key's TPM window is charged ~3.7k, RPD 1; the 429s come from the internal models' budgets → rows rpm 2 / conc 1 per key. Remaining question: none | — | No |
| 7 | Pure-rank composition: remove `judged_prefix` doc-fair round robin, aspect seats, diversity slots | owner decision (quotas rejected 2026-09-07, replacement not yet named) | **Yes** |
| 8 | B17 LEAN-PROMPT (instructions 17 k chars/turn vs 6.5 k evidence) | none | Yes (scope) |
| 9 | B14 abstraction ladder L3 as HyDE passages (compiler vocabulary) | none | Yes (go) |
| 10 | Summaries in production (66 active; Manga in Theory and Practice has none); delete "Framed Environment Design.md" (OCR garbage); How to Draw Manga: Illustrating Battles carries a converter watermark in its text | none | **Yes** (data deletions) |
| 11 | Rotate the six Groq keys pasted in chat on 2026-09-07 | owner | **Yes** — owner action |
| 12 | Embedder still logs occasional "mps oom on 4 embed items; splitting to 2 + 2" at caps 4 / 8192 (4 066 splits in 105 k requests since the 14:03Z boot ≈ 3.9 %) | monitoring; consider 2 / 4096 if judge timeouts return | No |
| 13 | Local test hygiene: `.env`-sourced shells fail the `rerank_deadline_s == 8.0` pin; `test_incremental_census` parity flakes while `project_qdrant` moves; `test_fact_endpoint_eligibility` has one live pronoun endpoint (`you`) in facts data | decide: pins read defaults not env; census test snapshots; data cleanup for facts | Design call |
| 14 | One low-quality profile (0.13): the RAPO paper — compound wrote bare `Retrieval:` / `Diffusion:` style lines that parse as unknown tags; a re-run on another lane would likely fix it; a `--requeue-below <q>` flag on the backfill script does not exist yet | small script change | No |
| 15 | B4 / B5 / B6 / B10 from OWNER-BACKLOG | as listed there | per item |

## C. Hooks (where each artefact is reachable from)

- `docs/wiki/plans/CONTINUITY-REPORT.md` → "Latest checkpoint (2026-09-07)" → this folder.
- `docs/wiki/README.md` → layout entry `reports/`.
- `docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` rows 11.121–11.128 → work-logs → this folder.
- `docs/wiki/plans/OWNER-BACKLOG.md` (B1, B13, B14, B15, B16, B17, B18) and `docs/wiki/plans/IMPLEMENTATION-TODO-2026-09-07.md` §1–§10.
- `scripts/README.md` → `backfill_document_profiles.py`, `document_profile_gate.py`; `scripts/scaffold_polymath_v4.py` declares every file named here.
- Memory (assistant): `project_polymath_document_profile`, `project_polymath_compiler_corpus_context`, `project_polymath_retrieval_junk_dedup`.

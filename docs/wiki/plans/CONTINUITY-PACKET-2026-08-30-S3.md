---
change_id: CONTINUITY-PACKET-2026-08-30-S3
owner: governance
date: 2026-08-30
status: living
architecture_impact: none (session hand-off record)
last_reviewed: 2026-08-30
---

# CONTINUITY PACKET — 2026-08-30 session 3 (bootstrap for the next session)

Read this first, then `CLAUDE.md`, then the two work-logs named in §2.
Everything here was measured in-session; anything older than a day must be
re-verified against the DB and the fleet. The previous packet
(`CONTINUITY-PACKET-2026-08-30.md`) is still valid for the fleet layout and
the 2026-08-29/30 history; this one supersedes its "next actions".

## 0. Bootstrap commands (do these before reasoning)

```bash
cd /Users/king/Documents/polymath-rebuild/polymath-v4
git status --short --branch && git log --oneline -8          # expect clean, HEAD >= f2312aa
set -a; . ./.env; set +a
.venv/bin/python scripts/agent_preflight.py && .venv/bin/python scripts/repo_guard.py && .venv/bin/python scripts/wiki_worm.py --check
.venv/bin/python shared/polymath_shared/bundle_integrity.py     # READY, bundle v5-production-001, rule pack 1.5.0
# fleet truth (NOT the packet): every worker type healthy on ONE bundle
.venv/bin/python -c "import os,psycopg; c=psycopg.connect(os.environ['POLYMATH_PG_DSN']).cursor(); c.execute(\"select worker_type,status,count(*),count(distinct left(execution_bundle_hash,12)) from worker_registrations where heartbeat_at>now()-interval '60 seconds' group by 1,2 order by 1\"); print(c.fetchall())"
curl -s 127.0.0.1:7200/ready; curl -s '127.0.0.1:7200/semantic_readiness?corpus_id=cysa-study-v1'
```
Tests: run them BEFORE any fleet restart, never after — the suite rewrites
`shared/polymath_shared/rulepack/scientific-predicate-ontology-v2.yaml`
(`tests/determinism/test_execution_bundle.py`; same bytes, new mtime) and the
mtime fence quarantines every worker (`worker_registrations.status =
quarantined`, `BUNDLE_STALE_CODE_DRIFT`). `pyproject` sets `addopts=-q`;
use `-o addopts=""` to see totals. Known failing on pristine `main` in this
environment: `test_chat_response_contract` ×2, `test_embed_batching`,
`test_fact_endpoint_eligibility::…retirement…`, `test_graph_lifecycle_v2::…qualified…`;
`test_killchain_pass2` and `test_source_recovery_key` need a populated corpus.

## 1. Where things are (measured 13:37 UTC)

| Item | State |
|---|---|
| Branch / main | `architecture/evidence-first-v5` @ `f2312aa`; `main@e416470` via the worktree `../polymath-v4-main` (never `git checkout` in the live tree) |
| Fleet | supervised: intake, profile, extract, canonicalize, project_canonical, project_neo4j, project_qdrant, verify, summaries, control.main — all restarted 13:36 on the current code, one bundle. Hand-started WITH the fleet env: orchestrator `:7200`, a second `workers.extract_worker` (lane parallelism). Older hand starts: reranker `:8743`, batched MLX `:8755`, embedder `:8742`, spaCy `:8744` |
| Fleet env (MANDATORY for anything hand-started; read it with `ps -E -p <supervised pid>`) | `POLYMATH_PROFILE=pipeline POLYMATH_SYNTAX_PROVIDER=spacy POLYMATH_QUERY_POLICY=semantic-query-policy-v3 POLYMATH_RESCUE=on POLYMATH_WORKER_RULE_PACK_VERSION=1.5.0 POLYMATH_CHUNKER=legacy_v1 POLYMATH_RELATION_PIPELINE=kimi_v1 POLYMATH_PREDICATE_V2=enforce POLYMATH_MAX_BATCH_TEXTS=8 POLYMATH_MAX_BATCH_TOKENS=16384 POLYMATH_MPS_CAP_GB=0` — write the assignments inline (zsh does not word-split `$VAR` for `env`). Without them a worker computes a different execution contract and refuses every lease; the orchestrator runs policy v1. |
| Corpus | `cysa-study-v1`, re-created by the owner 13:31: CySA+ Practice Tests 838,705 B (cloud lane) + Learning SQL 114,351 B (local lane); both `extract` leased 13:37 on the two extract workers. The earlier 3-file attempt (with SC-200) was deleted by the owner at 10:06. |
| DB migrations | 0041 applied live (`retrieval_summaries` dual slot) via `docker exec -i polymath-v4-postgres-1 psql -U polymath -d polymath -f - < stores/postgres/migrations/0041_….sql` |
| Stores | Postgres `:5432`; Qdrant host `:6334` (app default; `.env` `QDRANT_URL=6333` is compose-side and NOT read by the app); Neo4j bolt `:7688` (same story); Redis `:6379`. Neo4j still holds 4,212 `Entity` / 102 `Fact` / 1,260 `Chunk` nodes from deleted corpora (purge = owner decision; corpus delete does not remove Chunk/Document nodes) |
| Baseline for the A/B | `eval/quality/2026-08-30-session3/baseline_cysa-study-v1.json` (per-parent mentions / ledger relations / v2 cards / S2 summaries of the pre-fix ingest) + `sample_cysa_pre-fix.md`, `sample_sql_pre-fix.md` (seed 20260830 dumps read by eye) |

## 2. What landed this session (all merged to main, all logged)

| Commit | Change | Work-log |
|---|---|---|
| `077083b` | EXTRACTION-COVERAGE-HARDENING-V1: per-neighborhood dispositions + one single-neighborhood re-issue pass; census promotion barrier on `dropped/unaccounted` (run → `degraded`, reasons in `runs.metadata`); `/semantic_readiness.extraction[]`; `INTERROGATIVE_ATTESTATION` gate + prompt rule 8; `chunks.region_role` (REGION-ROLE-V1, calibrated on 1,024 live chunks); verifier `ontology{}`; 13 supervisor tests fixed | `2026-08-30-extraction-coverage-hardening.md` |
| `b4b5992` | SUMMARY-COMPILER-V1: one deterministic triple-aware compiler for section/document routing cards (`summary_compiler.py`), `retrieval-summary-v3`, dual slot (deterministic always; extractor digest = active `llm_digest` variant when clean), projector/census/verifier read active rows only, verifier `summaries{}` gate (missing cards, starved children), S2 consumes the card | `2026-08-30-summary-compiler.md` |
| `51dd9b2` | llm_live `write_bundle(require_slices=False)` (previous session's LLM-DIRECT fail-close, never run live before); verify `semantic_gaps` count (mine) | coverage-hardening log, correction |
| `6675880` | TICKET-GATE-FAIL-CLOSED-V1, CENSUS-FIRST-GAP-V1 (`chain_verdict`), DELETE-LOCK-TIMEOUT-V1 (409 `runs_in_flight`), PROJECTION-RECEIPT-PURGE-V2 (corpus delete removes every projected id) | same |
| `625c034` | gate expressed on `t.status` only (claim-starvation source pin); gate integration test | same |
| `f2312aa` | `intake.v1` claimable without a ticket (entry stage creates the corpus row; the chain follows) | same |

Register rows: 1.18, 4.3.13–4.3.16, 4.4.8. Owner-delegated decisions
(recorded): gate rule narrow (#6), S2 kept as a thin consumer (#10), old
compiler tests kept via a compatible API, migration 0041 (explicit columns).

## 3. Measured facts to carry forward
- Pre-fix cloud extraction dropped 3 of every 4 neighborhoods per call
  (118/181 CySA+ parents empty, pattern `X...X...`; 67 digests for 46 calls;
  23/46 calls salvaged). The re-issue pass ~4× the cloud calls; the cloud
  provider's real output ceiling is still unknown — read `finish_reason` on
  the running ingest.
- Ontology: ledger 100% on-enum (cloud 245/16 predicates, local 25/11),
  `RELATED_TO` 1.5%. The gate cannot see quiz framing turned into relations
  (`OPPOSES` from "which is NOT…", `ALTERNATIVE_TO` from "is different");
  the interrogative rule catches the first class only.
- Summaries: v2 cards were "longest sentence per child" (no `background`);
  compiler dry run on the pre-fix corpus: 206/206 cards, 61 `llm_digest`
  active, 0 starved, doc cards 1.4–1.6 K chars, replay byte-identical.
- Region roles on the live chunks: CySA+ body 463 / question_bank 219 /
  index 26 / output 9 / legal 3 / code 1; Learning SQL body 88 / noise_ocr 6
  / legal 3. `question_bank` over-fires on non-quiz books (SC-200: 9 false
  positives, stems=2) — harmless, tighten to stems ≥ 3.
- Stage transactions: extract holds its Postgres transaction for the whole
  document (12+ min observed); any UI/API delete waits on it (now 409 after 5 s).
- Two schedulers coexist: the legacy census (gaps → outbox events) and the
  ticket DAG. Ordering now rests on the fail-closed claim gate + first-gap
  census; the legacy pass-through for runs without tickets is gone except
  for `intake.v1`.

## 4. Open decisions (owner) — unchanged from the previous packet plus
1. Neo4j purge of deleted-corpus nodes (4,212 Entity / 102 Fact / 1,260 Chunk).
2. GLiNER retirement (§9.2; caches re-measured 11 GB).
3. `com.polymath.apple-ml` — a Hermes dependency (`~/.hermes/scripts/memory-doctor.sh` checks `:8082`); do not stop without changing Hermes.
4. Soft coverage floor `POLYMATH_CONTROL_EXTRACTION_COVERAGE_FLOOR` — set from the running ingest's `parents_with_extraction/parents_total`.

## 5. Next actions in order
1. **Read the running ingest as it lands** (eyes on, not counters):
   `.venv/bin/python scripts/read_extract_artifact.py "CompTIA%" eval/quality/2026-08-30-session3/baseline_cysa-study-v1.json`
   (same for `"Learning%"`): dispositions, `finish_reason`, re-issues,
   per-parent pattern vs baseline, 4 sampled parents with entities/relations.
   Then `scripts/quality_sample_dump.py "<source_name>" 20260830 <out.md>` and
   read the new cards against the parents next to `sample_*_pre-fix.md`.
   Then the verify artifact (`artifacts` stage `verify_projections`:
   `summaries{}`, `ontology{}`) and `/semantic_readiness` (verdict,
   `extraction[]`, `warnings[]`). Expect `dropped = 0`; if a run is
   `degraded`, `runs.metadata.degraded_reasons` says why.
2. Slice 2 follow-ups: `reprofile.v1` ticket (cards without re-extraction);
   drop the unused parent-tier `parent_summary` Qdrant points (touches the
   chunk-receipt want-set in verifier + census); `question_bank` threshold.
3. Lane assist (§9.4): today = extra hand-started extract workers; make the
   extract slot count a fleet setting (`POLYMATH_EXTRACT_SLOTS`) and give
   the local lane exactly one window.
4. `tests/determinism/test_execution_bundle.py` must stop rewriting the
   ontology yaml (write to a temp copy) — it quarantines the fleet.
5. Corpus delete: also remove Neo4j `Chunk`/`Document` nodes; then the
   owner's Neo4j purge decision.
6. Latent layer phases A–E (plan) only after the base e2e is validated.

## 6. Traps that cost time this session (avoid)
- Editing anything under `shared/polymath_shared`, `workers/workers`,
  `control/control` (`.py/.yaml`) — OR running the test suite — makes every
  worker refuse claims (mtime fence). Restart the fleet after every commit
  that touches those trees; check `worker_registrations.status` after tests.
- Hand-started processes without the fleet env (see §1) — lease refused /
  wrong query policy; `env $VAR` in zsh passes one garbage assignment.
- A UI delete during extraction blocks on the stage transaction; stop the
  extract workers first (or accept the new 409).
- Content-addressed ids (chunks, cards) + surviving `projection_receipts`
  = a re-ingest that skips re-embedding. `delete_corpus` now purges every
  projected id; the orphan sweep is
  `scripts/purge_orphan_projections.py --apply` (owner-gated; the
  auto-mode classifier may block even the dry run — measure by SQL instead).
- The extract ticket shows `ready` from outside while a worker is mid-stage
  (claim + processing + receipt commit in one transaction); look at
  `lease_owner` or `pg_stat_activity` (`idle in transaction` age).
- `macOS` has no `setsid`/`timeout`; use `nohup … &!` (zsh) and `until`
  loops. `find -newermt` needs ISO timestamps (`2026-08-30T10:14:41Z`) — the
  GNU form fails silently with `2>/dev/null`.
- `pytest -q` from `pyproject` + your `-q` = `-qq` (no totals).

## 7. Key files
`shared/polymath_shared/{summary_compiler,retrieval_summaries,region_role,extraction_coverage,semantic_readiness,worker_runtime,raw_evidence}.py`,
`shared/polymath_shared/llm_extraction/{client,gate}.py`,
`workers/workers/{llm_provider,extract_worker,profile_worker,project_qdrant_worker,verify_worker,summary_worker_impl,intake_worker}.py`,
`control/control/{census,scheduler,main}.py`, `orchestrator/orchestrator/api/ui.py` (delete endpoints),
`stores/postgres/migrations/0041_retrieval_summary_variants.sql`,
`scripts/{quality_sample_dump,read_extract_artifact,purge_orphan_projections}.py`,
`tests/determinism/{test_extraction_coverage_gate,test_summary_compiler,test_census_chain_verdict}.py`,
`tests/integration/test_ticket_gate_fail_closed.py`,
`docs/wiki/work-log/2026-08-30-{extraction-coverage-hardening,summary-compiler}.md`,
`docs/wiki/plans/PLAN-AUTHORITY-REGISTER.md` (1.18, 4.3.13–16, 4.4.8), `CLAUDE.md`.

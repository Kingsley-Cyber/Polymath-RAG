---
change_id: CONTINUITY-PACKET-2026-08-30
owner: governance
date: 2026-08-30
status: living
architecture_impact: none (session hand-off record)
last_reviewed: 2026-08-30
---

# CONTINUITY PACKET — 2026-08-30 (hand-off to the next session)

Read this first, then `CLAUDE.md` (operating rules), then
`docs/wiki/plans/LATENT-TRANSFER-LAYER-V1-PLAN.md` (§0, §1.6, §9) and the
tail of `docs/wiki/work-log/2026-08-29-llm-ingestion-migration.md`. Every
claim below was measured in-session; re-verify anything older than a day.

## 1. Where things are

| Item | State |
|---|---|
| Repo | `/Users/king/Documents/polymath-rebuild/polymath-v4` = polymath **v4**, remote `Kingsley-Cyber/Polymath-RAG` |
| Branch | work on `architecture/evidence-first-v5`; `main` is merged from the worktree `/Users/king/Documents/polymath-rebuild/polymath-v4-main` (NEVER `git checkout` in the live tree — it re-stales the fleet) |
| Last merges | `main@d3084ed` LLM-DIRECT-FACTS-V1; before it: locked output cap, short-id contract, breaker wait, MLX caps, stale-projection tolerance, audit fixes + durable controller, plan v1.2 |
| Fleet | supervised by `control.process_supervisor` (workers: intake, profile, extract, canonicalize, project_canonical, project_neo4j, project_qdrant, verify, summaries) — all restarted on the current code 07:2x; `control.main` restarted 07:11 |
| Started BY HAND (no supervisor slot spawned) | orchestrator `:7200` (`cd orchestrator && ../.venv/bin/python -m uvicorn orchestrator.main:app --port 7200`), reranker `:8743`, batched MLX server `:8755` (`.venv/bin/python sidecars/local_extractor/batched_server.py 8755`), embedder `:8742` + spaCy `:8744` (older manual starts). Logs in `/private/tmp/polymath_fleet/*.log` |
| Stopped on purpose | GLiNER sidecar `:8740` (unused in `llm_live`); polymath_v3.3 **relex** launchd agents (plists parked in `~/Library/LaunchAgents.disabled-2026-08-30/`, venv + weights deleted) |
| Corpus | `cysa-study-v1` (purpose `probe`, `query_enabled=false`): 2 docs — CySA+ Practice Tests 838 KB (cloud lane), Learning SQL 114 KB (local lane); both runs `query_ready`, `SEMANTIC_COMPLETE`. Extracted BEFORE the locked-cap fix and BEFORE LLM-DIRECT-FACTS → only 3 facts. **A re-ingest (owner deletes corpus in UI + re-uploads) is required to see the new path.** |
| `.env` | `POLYMATH_WORKER_EXTRACTION_PROVIDER=llm_live`, `POLYMATH_WORKER_CLOUD_MIN_BYTES=450000` (floor 300000) |
| Controller (Postgres `llm_controller_state`) | cloud concurrency 16 (ceiling), local batch budget climbing from 10 K tokens, local concurrency 4 |
| Memory | after fixes: ~2 GB wired, 90% free (was 28.7 GB wired / 16.8 GB swap) |

## 2. Landed today (all merged, all logged in the work-log)
1. Audit of the LLM lane — 32 findings fixed + regression suites (`tests/determinism/test_llm_*.py`, 63+ tests).
2. Durable AIMD controller (`llm_controller_state`, migration 0040), `AdaptiveBudget` for local batch tokens, receipts carry `limiter_effective/batch_tokens_cap/finish_reason`.
3. Stale-projection tolerance (`evidence_assembly.unresolved=`), `delete_document` purges routing cards by `summary_id`, `scripts/purge_orphan_projections.py`.
4. MLX batched server: cache 1 GB / memory 12 GB caps, `clear_cache` per batch, `/ready` reports memory.
5. Breaker: blocking acquire waits out the cooldown (fail-fast had burned ticket retries).
6. GLiNER pin no longer a boot dependency in llm modes.
7. Short neighborhood aliases `n1…nk` (4B model dropped the `:0` hash suffix → 20% quarantined).
8. Output cap = locked `max_tokens=2500` per neighborhood (+700/extra on cloud); batch accounting by expected output 900. Measured: 484-cap → 3 relations; 2500 → 9.
9. LLM-DIRECT-FACTS-V1 (`workers/llm_direct.py`): gated relations → `entities/mentions/facts/evidence` by identity; compiler/harbor bypassed in `llm_live`; GRAPH allowlist has the 17 enum ids. Contract identity includes `materialization`.
10. Plan v1.2 (`LATENT-TRANSFER-LAYER-V1-PLAN.md`): owner Part 3 target frozen (FAST unchanged, HYBRID rescue, GRAPH inherits, lean contract, two vectors/parent), three-layer graph REJECTED, v3.3 `tier_chunker` canonical, model setup §1.6, hardening track §9.

## 3. Measured facts to carry forward
- Extraction unit = one parent (4 children) ≈ **1.2 K tokens**; cloud sends 4 per call (~5.9 K in, ~1 K out); local 1–3 per `/infer_batch` under the AIMD budget. The 60 K-char neighborhood cap never engages.
- Relation schema adherence: ledger predicates 100% on-enum after the gate on both lanes (cloud 245 rows / 16 predicates; local 25 / 11). Raw fallbacks: 1 cloud, 3 local.
- Local yield before the cap fix: 1.2 entities/neighborhood vs cloud 4.25 — re-measure after re-ingest; an A/B on the same document is the gate for "local holds its own weight" (plan §9.4).
- Deterministic summaries ARE built (parent 206 / document 2 / corpus 2, content-addressed) and their routing cards are in the corpus routing collection; the standalone `summary_documents/summary_parents/concept_families` projection (`summary_projection.py`) is **not wired** (tests only).
- GLiNER is not called by any stage in `llm_live`; spaCy is called by `extract` only, for syntax-evidence-v1 — with LLM-DIRECT-FACTS the syntax stage is now unused in `llm_live` and can be removed with GLiNER (§9.2).

## 4. Owner decisions still open (do not assume)
1. Purge the old Neo4j graph (30 k nodes from deleted corpora): `MATCH (n) DETACH DELETE n` — owner said "not yet".
2. Re-ingest the two docs (delete corpus + re-upload) to exercise direct facts + fixed cap.
3. GLiNER full retirement commit (§9.2) — fleet-stale change; needs a quiet fleet; also deletes 9 weight caches (~14 GB).
4. Stop `com.polymath.apple-ml` (PolymathRuntime embedder/reranker duplicates on :808x, ~5 GB) — owner's other runtime.
5. Whether to wire the standalone summary projection (`summary_projection.py`) or retire it.
6. Latent layer build (plan phases A–E) — only after the owner validates the base e2e.

## 5. Next actions in order (proposed)
1. Owner re-ingests → verify `facts` count from `llm_direct` artifact (`artifacts.payload->'llm_direct'`), `finish_reason` distribution, per-lane yield; run `/chat/stream` HYBRID + GRAPH and confirm `retrieval.graph_fact_count > 0`.
2. GLiNER + spaCy retirement (§9.2) in one commit; delete weight caches; `extraction_provider` default `llm_live`.
3. Embed-early DAG split (§9.3); job-level completion + lane assist (§9.4); supervised slots for orchestrator + batched server, park-after-job (§9.5).
4. Neo4j purge (after owner go), then latent layer Phase A.

## 6. Traps that cost time today (avoid)
- **Any edit under `shared/polymath_shared`, `workers/workers`, `control/control` (`.py/.yaml`) makes every worker refuse claims (`BUNDLE_STALE_CODE_DRIFT`) — mtime-based.** Never edit those during an ingest; restart the fleet after every commit: `pgrep -f "workers\.[a-z_]*_worker" | xargs kill -TERM; pgrep -f project_neo4j | xargs kill -TERM` (the neo4j worker needs the second pattern). `control.main` is NOT guarded and caches census verdicts — restart it if runs sit at `reconciling` with zero gaps.
- Merge `main` from the worktree, never by checkout in the live tree.
- The auto-mode classifier blocks some production writes (ticket re-queues, purges); the sanctioned re-queue is `control.tickets._emit_ticket_event` after resetting `attempt`.
- Failed stage tickets at `attempt=3` never retry by themselves.
- MLX server: watch `/ready` memory; if it grows past the cap something is wrong.
- Chrome extension cannot render `127.0.0.1`/`localhost` pages — observe the UI through `/private/tmp/polymath_fleet/orchestrator.log`; `open http://127.0.0.1:7200/ui/` for the owner.
- zsh: quote `--include='*.py'` or grep fails with "no matches found"; `kill $pids` needs `xargs`.
- Tests: run with `--noconftest -p no:cacheprovider` for the pure suites (the repo conftest needs the DB); `tests/integration/test_llm_direct_facts.py` needs the DB and rolls back.

## 7. Key files (this session)
`shared/polymath_shared/llm_extraction/{client,gate,limiter,policy,ontology,state_store}.py`, `workers/workers/{llm_provider,llm_direct,extract_worker}.py`, `sidecars/local_extractor/batched_server.py`, `shared/polymath_shared/evidence_assembly.py`, `orchestrator/orchestrator/api/{ui,chat,evidence,retrieve}.py`, `scripts/purge_orphan_projections.py`, `stores/postgres/migrations/0040_llm_controller_state.sql`, `docs/wiki/plans/{LATENT-TRANSFER-LAYER-V1-PLAN,LATENT-TRANSFER-LAYER-V1-DESIGN-NOTES,PLAN-AUTHORITY-REGISTER}.md`, `docs/wiki/architecture/QUERY-TIME-MAP-2026-08-30.md`.

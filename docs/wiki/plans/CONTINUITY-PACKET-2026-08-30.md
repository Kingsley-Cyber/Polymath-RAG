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
11. **EXTRACTION-COVERAGE-HARDENING-V1** (session 3, owner: "checks are mandatory, grounded in the control plane"): measured that the pre-fix cap had silently dropped 3 of every 4 neighborhoods per cloud call (118/181 CySA+ parents empty, pattern `X...X...`; 16/25 Learning SQL) while the runs promoted to `query_ready`. Now: per-neighborhood dispositions + one single-neighborhood re-issue pass (`workers/llm_provider.py`), census promotion barrier on `dropped/unaccounted` → run `degraded` with reasons (`control/census.py`, `scheduler.apply_degrades`), `/semantic_readiness.extraction`, `INTERROGATIVE_ATTESTATION` gate rule + prompt rule 8, `chunks.region_role` (`region_role.py`, calibrated on the live chunks; noise never reaches the LLM or a routing card), verifier `ontology{}` durable check, 13 supervisor tests fixed. Work-log `2026-08-30-extraction-coverage-hardening.md`; register 4.3.13–4.3.16.
12. **SUMMARY-COMPILER-V1** (session 3, Slice 2, owner spec + "include it in slice 2"): one deterministic compiler (`shared/polymath_shared/summary_compiler.py`) builds every section/document routing card — verbatim sentences with offsets, triple-aware ranking, TF-IDF salience vs the document background, coverage-first (children / ordered regions), Jaccard dedupe, source order, hard bound, relation capsule, keywords, one serialized embed text (`SUMMARY / RELATIONSHIPS / KEY CONCEPTS`). The extractor's per-neighborhood digest is the LLM adapter: when clean it is the ACTIVE `routing_section_summary` vector (`variant=llm_digest`), the deterministic card always persists (`retrieval_summaries` migration 0041: `variant/active/plain_summary/relations/keywords/coverage`, one active row per slot). Projector/census/verifier read active rows only; verifier gates on missing cards and starved children; S2 `parent_summaries` consume the card (uppercase ontology predicates render). Live dry run (rolled back): 206/206 cards, 61 `llm_digest` active, 0 starved, doc cards 1.4–1.6 K chars. Work-log `2026-08-30-summary-compiler.md`; register 1.18 / 4.4.8.

## 3. Measured facts to carry forward
- Extraction unit = one parent (4 children) ≈ **1.2 K tokens**; cloud sends 4 per call (~5.9 K in, ~1 K out); local 1–3 per `/infer_batch` under the AIMD budget. The 60 K-char neighborhood cap never engages.
- Relation schema adherence: ledger predicates 100% on-enum after the gate on both lanes (cloud 245 rows / 16 predicates; local 25 / 11). Raw fallbacks: 1 cloud, 3 local.
- Local yield before the cap fix: 1.2 entities/neighborhood vs cloud 4.25 — re-measure after re-ingest; an A/B on the same document is the gate for "local holds its own weight" (plan §9.4).
- Deterministic summaries ARE built (parent 206 / document 2 / corpus 2, content-addressed) and their routing cards are in the corpus routing collection; the standalone `summary_documents/summary_parents/concept_families` projection (`summary_projection.py`) is **not wired** (tests only).
- GLiNER is not called by any stage in `llm_live`; spaCy is called by `extract` only, for syntax-evidence-v1 — with LLM-DIRECT-FACTS the syntax stage is now unused in `llm_live` and can be removed with GLiNER (§9.2).

## 4. Owner decisions still open (do not assume)
1. Purge the old Neo4j graph — re-measured session 3: **5,352 nodes / 1,065 rels** (Entity 4,212, Chunk 1,024, Fact 105, all `REL` edges rule-pack ids incl. `similar_to` 9); `MATCH (n) DETACH DELETE n` — owner said "not yet".
2. Re-ingest the two docs (delete corpus + re-upload) to exercise direct facts + fixed cap.
3. GLiNER full retirement commit (§9.2) — fleet-stale change; needs a quiet fleet; also deletes the weight caches (re-measured: 7 dirs, **11 GB**).
4. Stop `com.polymath.apple-ml` (PolymathRuntime embedder/reranker on :8081/8082/8085/8090; re-measured 706 MB RSS idle) — owner's other runtime AND a Hermes dependency: `~/.hermes/scripts/memory-doctor.sh` health-checks `:8082` and restarts the agent. Do not stop it without changing Hermes.
5. Whether to wire the standalone summary projection (`summary_projection.py`) or retire it.
6. Latent layer build (plan phases A–E) — only after the owner validates the base e2e.

## 5. Next actions in order (proposed)
1. Owner re-ingests → read `llm_extraction.stats.neighborhoods_*` (expect `dropped=0`, `reissued` small) and `neighborhood_dispositions`, `finish_reason` distribution (cloud output ceiling), `parents_with_extraction/parents_total` per lane → set `POLYMATH_CONTROL_EXTRACTION_COVERAGE_FLOOR`; verify `facts` from `llm_direct`, `INTERROGATIVE_ATTESTATION` count, `region_role` distribution on the new chunks; rerun `sample_dump.py` (seed 20260830; scratchpad of session 3) for the before/after read; run `/chat/stream` HYBRID + GRAPH and confirm `retrieval.graph_fact_count > 0`.
1b. Slice 2 LANDED (item 12). After the rerun, read per card: `retrieval_summaries.coverage` (starved must be 0), `variant` share (`llm_digest` should approach 100% of parents once every neighborhood has a digest), `relations` count per card (facts now flow from LLM-DIRECT), and the verify artifact `summaries{}`; rerun `sample_dump.py` and read the cards against the parents. Still open from the Slice 2 design: `reprofile.v1` ticket (cards without re-extraction), dropping the unused `parent_summary` Qdrant points.
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
- Tests: run with `--noconftest -p no:cacheprovider` for the pure suites (the repo conftest needs the DB); `tests/integration/test_llm_direct_facts.py` needs the DB and rolls back. `pyproject` sets `addopts=-q`; pass `-o addopts=""` or the totals line is suppressed. Five tests (`test_chat_response_contract` ×2, `test_embed_batching`, `test_fact_endpoint_eligibility::…retirement…`, `test_graph_lifecycle_v2::…qualified…`) fail on pristine `main` in this environment — pre-existing, not a regression signal.
- The venv's editable installs resolve to the LIVE tree; to run tests in another worktree set `PYTHONPATH=<wt>/shared:<wt>/workers:<wt>/control:<wt>/orchestrator`.

## 7. Key files (this session)
`shared/polymath_shared/llm_extraction/{client,gate,limiter,policy,ontology,state_store}.py`, `shared/polymath_shared/{region_role,extraction_coverage,semantic_readiness}.py`, `control/control/{census,scheduler,main}.py`, `workers/workers/{llm_provider,llm_direct,extract_worker,intake_worker,profile_worker,verify_worker}.py`, `sidecars/local_extractor/batched_server.py`, `shared/polymath_shared/evidence_assembly.py`, `orchestrator/orchestrator/api/{ui,chat,evidence,retrieve}.py`, `scripts/purge_orphan_projections.py`, `stores/postgres/migrations/0040_llm_controller_state.sql`, `docs/wiki/plans/{LATENT-TRANSFER-LAYER-V1-PLAN,LATENT-TRANSFER-LAYER-V1-DESIGN-NOTES,PLAN-AUTHORITY-REGISTER}.md`, `docs/wiki/architecture/QUERY-TIME-MAP-2026-08-30.md`.

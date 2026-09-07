---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
---

# CONTINUATION REPORT — 2026-09-07

Vocabulary used throughout: **CONFIRMED** = repository evidence (code, tests, receipts, commits) establishes it; **INFERRED** = likely from structure, rationale not recorded; **OWNER PREFERENCE** = desired characteristic, not a technical necessity; **OPERATIONAL REQUIREMENT** = the runtime imposes it; **EXPERIMENTAL** = not promoted to canon.

## 1. What this system is

Polymath v4 is a local-first GraphRAG service for a personal library of books and papers. A document is uploaded, materialised to Markdown-shaped blocks, chunked into parents and 128-token children, extracted (entities, typed relations, facts), canonicalised, projected into Qdrant (vectors), Neo4j (graph) and Postgres (truth + lexical), enriched (summaries, and since today a document retrieval PROFILE), and only then declared `query_ready`. A chat runtime compiles a user question into lane queries against the library, retrieves child chunks through four lanes, judges them with a cross-encoder, composes evidence and asks a synthesizer model to answer with citations. Everything is receipted and idempotent so a stage can be re-run without changing identities. (CONFIRMED: `AGENTS.md`, `control/control/tickets.py` STAGE_DAG, `orchestrator/orchestrator/api/ui.py`, `shared/polymath_shared/candidate_engine.py`.)

## 2. Current system state

| Aspect | State (CONFIRMED unless marked) |
|---|---|
| Runtime processes | One supervisor (`control.process_supervisor`) spawns every slot from its `FLEET` table: `control.main`, orchestrator (uvicorn :7200), MCP server, intake, profile, extract ×3, canonicalize, project_canonical, neo4j, qdrant, verify, compile_objects, summaries ×2, doc_profile ×6, sidecar_embedder (:8742), sidecar_reranker (:8743). Autopilot (`control.fleet_autopilot`) parks/wakes slots by open tickets and query recency. |
| Storage | Postgres (documents, chunks, runs, stage_tickets, receipts, artifacts, outbox_events, query_receipts, parent_enrichments, projection_receipts …; 53 migrations under `stores/postgres/migrations/`), Qdrant 1.13.4 :6334 (child/parent vectors, routing points ≈ 160.7k, and since today `polymath_document_profiles_embed_e794ec4cab197a3f`), Neo4j (entities, relations, facts, canonical memberships). |
| Embedding contract | `embed_e794ec4cab197a3f`: Qwen3-Embedding-0.6B, 1024-d, served by the embedder sidecar; caps `POLYMATH_MAX_BATCH_TEXTS=4`, `POLYMATH_MAX_BATCH_TOKENS=8192` since today (OPERATIONAL). |
| Ingestion contract | materializer 1.1.0 + tier chunker v3.1; children median ≈ 73 words; duplicate guard has three layers (byte hash, normalised hash, containment ≥ 0.95 refuse). |
| Retrieval | `candidate_engine`: lanes A (dense), B (sparse BM25), C (exact terms), D (graph/facts) → RRF → region exclusion → judge (reranker, deadline 12 s today) → composer → presentation-v2. The chat query compiler sees the top-40 library TITLES ranked by content (dense). Document profiles exist in Qdrant but are NOT yet a retrieval lane (step 6 open). |
| Corpora | `cinema` (67 documents; 67/67 profiled today), others listed in `CONTINUITY-REPORT`. |
| Providers | Extraction / enrichment pool in `config/cloud_providers.json` (Gemini, OpenRouter, Ollama primary …); profile pool = six dedicated Groq accounts (`groq/compound`) + Gemini + OpenRouter fallbacks; keys ONLY in `.env`. The chat synthesizer catalog is a separate model set and must never feed the pools (OWNER PREFERENCE, tested). |
| Tests | `tests/determinism` (173 files; pure pins + Postgres-backed stage tests), `tests/contracts` (12), `tests/integration` (43). CI: agent-preflight, contracts, determinism (postgres:16 service + migrations), repo-governance; `research-harness` separate. All four green on `22f93c3`. |
| Git | `main` == `architecture/evidence-first-v5` == `origin/main` == `origin/architecture/evidence-first-v5` at `22f93c3`; worktrees: this checkout (branch) and `../polymath-v4-main` (main). |
| Fleet | Booted 15:04Z today from `22f93c3`'s working tree; orchestrator, embedder, reranker ready at closeout; `project_qdrant` backlog 19 tickets draining; no `doc_profile` tickets open. |

## 3. Work completed in this development cycle (2026-09-06 late → 2026-09-07)

| Implementation | Problem solved | Files / modules | Behaviour change | Tests | Commit | Merged | Limitations |
|---|---|---|---|---|---|---|---|
| **B1 NEAR-DUPLICATE-GUARD-V1** (register 11.121) | An 8-byte-different twin of a book passed the two hash layers | `shared/polymath_shared/dedup.py`, intake worker layer 3, `/upload` | Incoming parents' 5-gram containment vs the corpus's last 250 docs; ≥ 0.95 refused (`NEAR_DUPLICATE_DOCUMENT`), below → lands flagged; `allow_near_duplicate` override; landed docs exempt on intake replay | determinism dedup suite + replay regression | `a9bbb58` | yes | corpus-wide DETECT/CORRECT script not ported from v3.3 |
| **B16 COMPILER-CORPUS-CONTEXT-V1** (11.122) | The query compiler had never seen a title; cross-vocabulary books (Laban) unreachable | `shared/polymath_shared/compiler_context.py`, `chat_plan.user_prompt(titles=)`, `ui._compiler_titles` | Compiler prompt carries top-40 titles ranked by content; dense default; `titles_rank` off/sparse/dense | compiler-context pins | `7297fdf` | yes | status IMPLEMENTED: owner measuring by hand; fixture M dense arm partial |
| **REGION-EXCLUSION-V1** (11.123) | Table-of-contents chunks reached final evidence | `candidate_engine.py` (`structural_noise_reason`, `region:<role>`), `document_region.py` | Noisy roles leave the union before ranking; `demote_noisy_regions=False` bypass | region pins, floors held on fixtures | `93b3edd` | yes | — |
| **INTERACTIVE-RELIEF-V1** (11.124) | Judge timeouts on every turn; over-long answers; rewrite turns losing evidence | `ui.py` (`_PRESENTATION_BLOCK`, `_chat_max_tokens` 6000, CARRY-ARTIFACT `_admit_carry`), `.env` deadline 12 s, embedder caps | Root cause was the embedder OOM-splitting under a 24-book re-projection; length rule; carry cap 16 | relief pins | `3e0181b` | yes | IMPLEMENTED: after-measurement on 40 owner UI turns still owed; deadline to return to 8 s |
| **DOCUMENT-PROFILE-V1 steps 1–4** (11.125, 11.126, 11.127) | Owner architecture: a document-level multi-field retrieval representation | `shared/polymath_shared/document_profile/{compiler,prompt,context,projection}.py`, `workers/workers/doc_profile_worker.py`, `control/control/{tickets,fleet_autopilot,process_supervisor}.py`, `config/cloud_providers.json`, `limiter.yaml` | New stage `doc_profile` (phase A, non-blocking), artifact with receipt chain, own Qdrant collection (dense title/identity/theme + multivectors), isolated pool | 24 → 37 tests | `306e499`, `0953a10`, `f7bb695`, `8af6790` | yes | phase B (gate) not flipped |
| **DOCUMENT-PROFILE-V1 step 5 backfill** (11.128) | Make it live on cinema; compile whatever the model writes | compiler `rag-compiler-v3.1` (ITEM_SPLIT, inline Q split), prompt v3.2, worker (`attempt_lanes`, transient classification, embed slicing, `doc_id` in artifact), FLEET `doc_profile2..6`, autopilot scale-out, `scripts/backfill_document_profiles.py`, `scripts/document_profile_gate.py` | 67/67 profiled, quality p50 1.00, gate top-1 85.8 % / top-3 99.5 % over 400 probes; punch question reaches the Laban Workbook through the profile lane alone | 37 tests, repo_guard | `0c78579` | yes (main ff 09:18 local) | one 0.13 profile (RAPO paper); limiter per process |
| **Profile-lane pacing** | 18 × 429 on the first six-slot run | `limiter.yaml` (rpm 2 / conc 1 per slot), per-slot key offset (`POLYMATH_DOC_PROFILE_LANE_OFFSET`) | One compound request measured = 12 internal model calls, 38.5k internal tokens, ~3.7k charged to the key's TPM window | stage pin | `22f93c3` | yes (main ff 09:23 local) | RPD not durable across restarts |
| Documentation | — | work-logs (4 today), register 11.121–11.128, OWNER-BACKLOG, IMPLEMENTATION-TODO, CONTINUITY checkpoint 2026-09-07, this folder | — | wiki_worm ok | in the commits above + closeout commit | yes | — |

## 4. Current active work — state vocabulary applied

| State | Items |
|---|---|
| **Complete (DONE)** | B1, region exclusion, DOCUMENT-PROFILE steps 1–5, six-slot scale-out, pacing, branch cleanup |
| **Implemented but unverified (IMPLEMENTED)** | B16 titles (owner hand-test; fixture M dense arm partial); INTERACTIVE-RELIEF (after-measurement owed); DP step 3 fallback path (Gemini fallback exercised live on 3 documents — CONFIRMED working) |
| **Partially implemented** | none |
| **Planned, not started** | DP step 6 retrieval lane; DP phase B gate; B14 abstraction ladder (L3 first); B17 lean prompt; durable shared limiter; `--requeue-below` for the backfill script |
| **Intentionally deferred (owner decision pending)** | pure-rank composition (remove round robin / aspect seats / diversity); summaries production; deletion of OCR-garbage documents; Groq key rotation; returning the rerank deadline to 8 s (waits for the `project_qdrant` drain) |
| **Abandoned / demoted experiments** | B15 bridge-hop (demoted after probes: pseudo-relevance feedback cannot reach Laban); "move profile lanes to gpt-oss" (withdrawn: rate-limited out on the free plan) |

## 5. Operational assumptions that must remain true

1. The fleet runs FROM this worktree; a commit that touches control/ shared/ workers/ is followed by a fence round (automatic) or a boot (for `FLEET` changes).
2. `.env` is the only execution contract; hand-started processes without it compute a different contract and are refused leases.
3. The orchestrator is unauthenticated and local; the Caddy layer is the only sanctioned public path.
4. Postgres, Qdrant and Neo4j are local services outside the supervisor; the embedder and reranker share one Metal GPU.
5. The profile collection is keyed by the embedding contract id; changing the embedder invalidates it (as it invalidates every other projection).

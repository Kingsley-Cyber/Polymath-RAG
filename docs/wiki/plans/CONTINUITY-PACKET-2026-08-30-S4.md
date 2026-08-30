---
change_id: CONTINUITY-PACKET-2026-08-30-S4
owner: governance
date: 2026-08-30
status: living
architecture_impact: none (session hand-off record)
last_reviewed: 2026-08-30
---

# CONTINUITY PACKET — 2026-08-30 session 4 (bootstrap for the next session)

Read this first, then `CLAUDE.md`, then
`docs/wiki/work-log/2026-08-30-control-plane-hardening.md`. The S3 packet
stays valid for the fleet layout and history; this one supersedes its
"next actions". §0 of S3 remains the bootstrap command set (HEAD moved to
`b2aedfc`+; the "tests trip the stale-code fence" warning is OBSOLETE —
HASH-FENCE-V2 made the suite fence-safe).

## 1. What this session proved and shipped (all merged, work-logged)

| Item | State |
|---|---|
| STUCK-RUN class | ROOT-CAUSED live (stale incremental verdict cache + attempt-only dirtiness + gap re-arm churn) and KILLED: CENSUS-DIRTY-SIGNAL-V2 (`b2aedfc`), pinned by `test_census_dirty_signal` (3 tests) |
| cysa-study-v1 | `SEMANTIC_COMPLETE`, 2× `query_ready`, 206 parent cards, 1,223 facts; CySA+ coverage 174/181 (baseline 63/181), dropped 0; verify `ontology{}`: 0 off-enum, 0 unknown predicates (CySA+ RELATED_TO 4.4%, SQL 26.2%) |
| Code fence | HASH-FENCE-V2: content-sha256 (stat-cached); byte-identical rewrites (pytest!) can no longer quarantine the fleet |
| Extract transport | 500 joins the retryable set (one transient Ollama 500 had burned a 6-min cloud stage; receipt `7d46676d`) |
| Term gate | TERM-SURFACE-GATE live in the gate: `NON_TERM_SURFACE`/`NON_TERM_ENDPOINT`; measured SQL 10/128, CySA+ 118/2624 caught, 0 false positives; known misses pinned in the test |
| GLiNER→LLM migration | Register §10.1 DONE: `_persist_knowledge_artifacts` wired into llm_live (KNOWLEDGE-ARTIFACT-LLM-V1); §11 (L0/L1/L2 projections + `compile_objects` stage split) is being authored by the other session — build order: stamping → entity cards → BM25 sparse → compile_objects |
| Cloud speed | limiter ceiling 16→32 (AIMD had saturated its cap with ZERO 429s; 429s/headers are the authority) |
| Fleet | Restarted 14:2x UTC on `b2aedfc`: 10 healthy workers, ONE bundle; hand-started with the fleet env: orchestrator `:7200`, second `workers.extract_worker` |
| E2E receipt | **GREEN 14:38 UTC, 8/8 checks** — `e2e-hardening-v2` (Learning SQL bytes + unique footer): upload→`SEMANTIC_COMPLETE` **unassisted in ~7 min** (run `query_ready`, the stuck-run class dead); dropped 0 / unaccounted 0, coverage 17/24; **concepts 13 + procedures 29** on llm_live (was 0/0 — §10.1 live), opportunities 38/248; term gate firing (`NON_TERM_SURFACE` 8, `NON_TERM_ENDPOINT` 16) and flagship clause junk has ZERO mentions in the new doc; `concept_artifacts` rows persisted. Script: session scratchpad `e2e_hardening_proof.py` (port into `scripts/` if it should live on) |

## 2. Traps (new this session)

- **Concurrent sessions share this repo.** `984a0dc` (other session, docs
  register commit) swept this session's uncommitted tree via `add -A`.
  Commit narrowly and early; on "my changes vanished", check
  `git log --stat` before touching the stash.
- **Cross-corpus content collision is fail-loud by design**: identical
  bytes belong to exactly one corpus (`CROSS_CORPUS_CONTENT_COLLISION`).
  An e2e re-ingest needs unique bytes. Debris: `run_5c57865b…`
  (corpus `e2e-hardening-v1`, no corpus row — invisible to the census,
  inert; harmless, deletable only by SQL).
- `runs.updated_at` can look non-monotonic under concurrent touch traffic;
  the decisive instrument for run-row churn is a short-lived
  BEFORE-UPDATE audit trigger, not polling.
- Old registrations from a killed fleet linger `quarantined` in
  `worker_registrations` until the heartbeat window ages them out —
  filter on `status='healthy'` + fresh heartbeat when counting.

## 3. Next actions in order

1. **Read the e2e receipt** (if this packet predates its landing:
   `tasks/…/e2e_hardening_proof` output; expect GREEN on all 8 checks).
2. §11 build order once recorded by the design session: generation
   stamping (register 1.6) → `routing_entity` cards → BM25 sparse named
   vector → `compile_objects` stage split (llm_live keeps the V1 bolt-on
   until the stage exists).
3. Owner decisions carried from S3 §4 (Neo4j purge, GLiNER retirement,
   `com.polymath.apple-ml` Hermes dependency, coverage floor from live
   `parents_with_extraction/parents_total`).
4. Pre-gate junk already in `cysa-study-v1` (SQL RELATED_TO 26%): owner
   call — re-extract Learning SQL under the term gate, or accept until
   the next natural re-ingest.
5. Test debt: summary_runtime_d3/d4 + fact_endpoint hermeticity vs a
   populated DB; 8 pre-existing `orchestrator.orchestrator` collection
   errors under full-suite runs.

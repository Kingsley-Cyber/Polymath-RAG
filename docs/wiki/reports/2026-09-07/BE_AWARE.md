---
owner: @king
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: accepted
supersedes: BE-AWARE-REPORT.md
---

# BE AWARE — repository-specific facts a new model will get wrong (2026-09-07)

Labels: `[OPERATIONAL CONSTRAINT]` `[ARCHITECTURAL REQUIREMENT]` `[OWNER PREFERENCE]` `[PERFORMANCE TRADEOFF]` `[COMPATIBILITY REQUIREMENT]` `[SAFETY / DATA-INTEGRITY INVARIANT]` `[HISTORICAL DECISION]` `[EXPERIMENTAL]` `[TEMPORARY COMPROMISE]` `[DO NOT CHANGE WITHOUT EVIDENCE]`. Changeability scale: *Safe to change locally* → *Safe with tests* → *Requires architectural review* → *Do not change without revisiting system contract*. Owner preferences are labelled as such and are NOT presented as engineering truths; operational constraints are NOT preferences.

---

## A. Fleet and process life

### A1. Every process is a supervised slot; the supervisor is the only spawner
- Classification: `[OPERATIONAL CONSTRAINT]` `[SAFETY / DATA-INTEGRITY INVARIANT]`
- What: `control/control/process_supervisor.py` holds the `FLEET` table and spawns each slot with `.env` and the runtime budget overlaid; readiness probes, restart budget (6 exits → quarantine), fence quarantine.
- Why: hand-started processes computed a different execution contract (leases refused, wrong query policy) and a second orchestrator on :7200 caused a bind loop (CONFIRMED: `CLAUDE.md` operating rules; memory `reference_polymath_medic_and_fence`).
- Prevents: stale-code workers writing receipts the new code cannot read; port fights; silent contract drift.
- Evidence: `process_supervisor.py` `_spawn`, `tests/determinism/test_supervisor_env_overlay.py`, `test_no_legacy_sidecars.py`.
- Changeability: Do not change without revisiting system contract.
- Successor warning: do NOT run `python -m workers.x_worker` or `uvicorn orchestrator.main` by hand "to test quickly". Kill the slot; the supervisor respawns it. A `FLEET` edit only takes effect after a supervisor boot (`scripts/run_fleet_supervised.sh`, `POLYMATH_AUTOPILOT=1`, `.env` sourced).

### A2. The execution-bundle fence: editing control/ shared/ workers/ restarts everything
- Classification: `[OPERATIONAL CONSTRAINT]` `[SAFETY / DATA-INTEGRITY INVARIANT]`
- What: any mtime change under `shared/polymath_shared`, `workers/workers`, `control/control` (`.py/.yaml`) makes workers refuse claims ("claims refused while bundle is stale") and the supervisor restarts every slot within ~2 minutes.
- Why: a worker must execute the bundle its receipts claim (CONFIRMED: log lines in `/private/tmp/polymath_fleet/*.log`, `CLAUDE.md`).
- Prevents: mixed-version receipts inside one run.
- Changeability: Requires architectural review.
- Successor warning: an in-flight ticket rolls back and re-leases; that is expected. Do not edit those paths while the owner is testing in the UI. Do not "fix" the restart by disabling the fence.

### A3. Workers execute tickets serially; throughput = more slots
- Classification: `[ARCHITECTURAL REQUIREMENT]` `[HISTORICAL DECISION]`
- What: `run_worker(batch_size=1)` (LONG-STAGE-LEASE-CORRECTNESS-V1); scale-out = extra `FLEET` entries + an autopilot rule (extract ×3, summaries ×2, doc_profile ×6).
- Why: claiming ahead let the reaper expire queued leases mid-execution (CONFIRMED: docstring in `shared/polymath_shared/worker_runtime.py`).
- Changeability: Requires architectural review.
- Successor warning: do not add a thread pool inside a worker to "parallelise". Add slots (`process_supervisor.FLEET`) and a `desired_slots` rule (`fleet_autopilot.py`), pin both in tests (`test_fleet_autopilot_demand.py`, `test_document_profile_stage.py`).

### A4. Autopilot demand lanes and the memory budget
- Classification: `[OPERATIONAL CONSTRAINT]` `[PERFORMANCE TRADEOFF]`
- What: `fleet_autopilot.LANES` maps stages → slots; a slot exists while its stage has open tickets (+30 s grace; sidecars 300 s; embedder also on query recency 600 s and UI presence).
- Why: 19.6 GB committed when everything ran; the GPU sidecars cannot all be resident (CONFIRMED: module docstring).
- Successor warning: "the doc_profile worker is not running" is normal when no ticket is open. Mint a ticket, do not start the worker.

### A5. One Metal GPU for embedder + reranker; embedder caps
- Classification: `[OPERATIONAL CONSTRAINT]` `[PERFORMANCE TRADEOFF]` `[TEMPORARY COMPROMISE]`
- What: `POLYMATH_MAX_BATCH_TEXTS=4`, `POLYMATH_MAX_BATCH_TOKENS=8192` on the embedder; `POLYMATH_CHAT_RERANK_DEADLINE_S=12` (was 8); never rerank parallel support passes.
- Why: on 2026-09-07 the embedder OOM-split under a 24-book re-projection and starved the judge → `rerank_timeout` on every chat turn (CONFIRMED: work-log `2026-09-07-interactive-relief`, ≈ 3.9 % of requests still split at the new caps).
- Prevents: dead chat during ingestion.
- Changeability: Safe with tests + a live measurement; the 12 s deadline is a compromise to return to 8 s when the `project_qdrant` backlog drains.
- Successor warning: the embedder 422s any request with more than 4 texts — clients must slice (`doc_profile_worker.embed_batch_size`). Embedder throughput does not scale with callers (≈ 5.8 texts/s regardless).

### A6. TransientStageHold vs failed attempt
- Classification: `[ARCHITECTURAL REQUIREMENT]` `[SAFETY / DATA-INTEGRITY INVARIANT]`
- What: a stage raises `TransientStageHold` to hand a ticket back READY without consuming an attempt (dark pool, rate limit, sweep lock); any other exception is a failed attempt with a receipt.
- Why: a summaries worker once waited 4.2 h on a lock (docstring); 429s burned retry budgets (11.78).
- Successor warning: never hold on EVERY error — a document that can never succeed must end as a receipted failure (3-minute stall rule, `[OWNER PREFERENCE]` turned rule). See `doc_profile_worker.transient_pool_error` for the pattern.

## B. Repository governance

### B1. Declarations, registry and the repo guard
- Classification: `[ARCHITECTURAL REQUIREMENT]` `[OWNER PREFERENCE]`
- What: every repo file is declared in `scripts/scaffold_polymath_v4.py`; every script also in `scripts/README.md`; `scripts/repo_guard.py` refuses undeclared files, undeclared scripts, and code changes without a work-log; run it UNPIPED before committing.
- Why: the scaffold is "the only sanctioned shape" (`README.md`); CI `repo-governance` enforces it (CONFIRMED).
- Successor warning: declare a file in the SAME commit as the file — a declaration whose file is not committed turns CI red; never `git add -A`.

### B2. Protected main, one working branch, fast-forward only
- Classification: `[OWNER PREFERENCE]` `[HISTORICAL DECISION]`
- What: push `architecture/evidence-first-v5`, wait for the four checks, `git -C ../polymath-v4-main merge --ff-only`. Remote branches were pruned to these two on 2026-09-07 at the owner's request.
- Why: "I just want the working state and fixes I have to work when I pull it from a different computer" (owner, 2026-09-07). Reason for ff-only over merge commits cannot be verified from repository evidence beyond that statement.
- Successor warning: do not open feature branches unless asked; do not push to `main` directly.

### B3. The single bootstrap file and dated snapshots
- Classification: `[OWNER PREFERENCE]`
- What: `docs/wiki/plans/CONTINUITY-REPORT.md` is updated in place each session; `PLAN-AUTHORITY-REGISTER.md` rows are never deleted (status vocabulary DONE / IMPLEMENTED / CLOSED / QUEUED; a missed gate is IMPLEMENTED, never DONE); dated folders under `docs/wiki/reports/<date>/` are snapshots the continuity report points to.
- Successor warning: `AGENTS.md`/`README.md` used to say "no dated handoff files exist"; as of this closeout dated report folders exist BUT the continuity report remains the entry point. Never fork the continuity report into dated copies.

### B4. Secrets
- Classification: `[SAFETY / DATA-INTEGRITY INVARIANT]` `[OWNER PREFERENCE]`
- What: keys only in `.env` (gitignored); config carries `api_key_env` names; the assistant never reads, prints or writes keys — the owner edits `.env`; never an inline comment on a `.env` value line (pydantic keeps it → orchestrator crash — `[OPERATIONAL CONSTRAINT]`); `research/registry/research_evidence.csv` never committed.
- Successor warning: six Groq keys pasted in chat on 2026-09-07 are to be rotated by the owner; treat them as compromised.

## C. Ingestion and identity invariants

### C1. Frozen identities
- Classification: `[SAFETY / DATA-INTEGRITY INVARIANT]` `[OWNER PREFERENCE]` `[DO NOT CHANGE WITHOUT EVIDENCE]`
- What: chunk vectors, chunk ids, parent/child projection identity and existing graph receipts are never rewritten; new representations are ADDED (new artifact, new collection, new lane).
- Why: owner's verbatim DO NOT list for DOCUMENT-PROFILE-V1; receipts and projections reference these ids (CONFIRMED: `docs/wiki/plans/DOCUMENT-PROFILE-V1.md` §Invariants).
- Changeability: Do not change without revisiting system contract.

### C2. Idempotent stages, receipts, artifacts, outbox
- Classification: `[ARCHITECTURAL REQUIREMENT]`
- What: each stage runs inside `stage_transaction(run_id, stage, contract_hash)`; it writes `artifacts` (merged per run × stage) and a `receipts` row; the control plane mints `stage_tickets` from `STAGE_DAG` and delivers `outbox_events`; re-delivery is normal.
- Successor warning: an intake event CAN be re-delivered after a document has landed (B1 found this) — any fuzzy or paid step must be replay-safe. `contract_hash` changes (prompt/compiler/builder/projection version) create a new execution contract; existing runs keep the old one until re-ingested.

### C3. `ingested != query_ready`
- Classification: `[ARCHITECTURAL REQUIREMENT]` `[OWNER PREFERENCE]`
- What: `verify_projections` gates readiness on Qdrant, routing, Neo4j and canonical projections; `NON_BLOCKING_STAGES` (summaries, compile_objects, `doc_profile` in phase A) do not gate.
- Successor warning: phase B (making `doc_profile` a gate) is planned, not done — moving the DAG entry now would strand nothing but also gate nothing until step 6 proves value (register 11.126 rejected claim).

### C4. Near-duplicate guard tiers
- Classification: `[HISTORICAL DECISION]` `[OWNER PREFERENCE]`
- What: refuse only `certain` (containment ≥ 0.95); `likely` lands flagged; `allow_near_duplicate` override — a port of v3.3's design at the owner's request; the lexical-dedup trap (two editions vs a reformat) is why the threshold is high.
- Changeability: Safe with tests (`POLYMATH_INTAKE_NEAR_DUPLICATE_*` knobs).

## D. Retrieval and chat

### D1. Deterministic everywhere meaning is not produced
- Classification: `[ARCHITECTURAL REQUIREMENT]` `[OWNER PREFERENCE]`
- What: hydration waterfall, dedup, region exclusion, RRF, composition, title ranking are deterministic; LLMs appear only in extraction, enrichment, the profile, the query compiler and the synthesizer; anything under plan §3.23 needs the owner's explicit go.
- Successor warning: do not add an "LLM re-ranker" or "LLM dedup".

### D2. The judge (cross-encoder) is the scoring authority; quotas are rejected
- Classification: `[OWNER PREFERENCE]` `[HISTORICAL DECISION]`
- What: the production redesign retired blocklists and multi-score fusion; the owner rejected doc-fair round robin, aspect seats and diversity slots as "not the design" (2026-09-07) — they still exist in `candidate_engine` (`judged_prefix`, `aspect_prefix_seats`, `compose_diversity_slots`) pending a pure-rank decision.
- Classification note: `[TEMPORARY COMPROMISE]` — code present, design rejected, replacement not yet named by the owner.
- Successor warning: do not extend the quota machinery; do not remove it without the owner's decision either.

### D3. Titles only in the compiler context; dense ranker default
- Classification: `[OWNER PREFERENCE]` (titles, top-40, dynamic) + `[PERFORMANCE TRADEOFF]` measured (dense)
- Evidence: `compiler_context.py`, work-log `2026-09-07-b16-compiler-corpus-context`; dense was the only ranker that put the Laban Workbook in front of a camera question (rank 25 → cited).
- Successor warning: never inject summaries into the compiler prompt ("they get long"); vector reuse between compiler and retrieval is impossible because retrieval embeds the compiler's rewritten text.

### D4. Presentation length rule and the 6 000-token ceiling
- Classification: `[OWNER PREFERENCE]` (complaint-driven) `[TEMPORARY COMPROMISE]`
- Evidence: `ui._PRESENTATION_BLOCK`, `_chat_max_tokens`; register 11.124 IMPLEMENTED — after-measurement owed.

### D5. Chat model catalog ≠ extraction / enrichment / compiler providers
- Classification: `[OWNER PREFERENCE]` `[SAFETY / DATA-INTEGRITY INVARIANT]`
- Evidence: `tests/determinism/test_chat_model_catalog.py` boundary test.

## E. Document profiles (DOCUMENT-PROFILE-V1)

### E1. The profile is additive and separate
- Classification: `[ARCHITECTURAL REQUIREMENT]` `[OWNER PREFERENCE]`
- What: own collection `polymath_document_profiles_<contract>`, one point per document, named dense (title, identity, theme) + MaxSim multivectors (questions, searches, theories, concepts, seealso); artifact `doc_profile` + `doc_profile_qdrant` with the hash chain content → input → raw → compiled → projection; payload carries `doc_id`, `corpus_id`, `title`, topics, terms, quality.
- Successor warning: it does not replace document summaries; SEEALSO is excluded from normal answers by design; the future lane BOOSTS (children enter fusion), never `WHERE doc_id IN top_k`.

### E2. The compiler compiles what the model writes
- Classification: `[OWNER PREFERENCE]` `[ARCHITECTURAL REQUIREMENT]`
- What: `rag-compiler-v3.1` — an unlabeled line under a list tag is a new item unless the previous item is visibly open; `Q: a? B?` splits; text tags merge; prompt v3.2 asks for a label on every line as a backstop.
- Why: "improve the script to compile the output, the model is capable" (owner); the failure shape was non-deterministic (same document, labelled one call and bare the next).
- Successor warning: do not "fix" parse failures with more prompt rules; extend the parser and pin the live shape (`tests/determinism/test_document_profile_compiler.py`).

### E3. `groq/compound` is the lane BECAUSE of the free-plan limits
- Classification: `[OWNER PREFERENCE]` grounded in `[OPERATIONAL CONSTRAINT]`
- What: compound = RPM 30 / RPD 250 / TPM 70K, no daily token cap; gpt-oss-120b and Qwen = TPM 8K / TPD 200K (≈ one profile request a minute per key). One compound request = 12 internal calls (11 llama-4-scout router steps + 1 gpt-oss-120b answer), 38.5k internal tokens, ~40 s; the key's own TPM window is charged ≈ 3.7k, RPD 1. The Groq dashboard attributes usage to the internal models.
- Evidence: work-log `2026-09-07-document-profile-stage` ("Rate limits and the model actually serving"), `config/extraction_models/limiter.yaml` comment.
- Successor warning: do not move the lane to gpt-oss "for speed"; do not read the dashboard's llama-4-scout entries as a mis-pinned model. Pacing = rpm 2 / conc 1 per slot, one slot per key (`POLYMATH_DOC_PROFILE_LANE_OFFSET`).

### E4. The limiter is per process
- Classification: `[OPERATIONAL CONSTRAINT]` `[TEMPORARY COMPROMISE]`
- What: `llm_extraction/limiter.py` uses threading locks; a `limiter.yaml` row is one process's budget; RPD resets on restart.
- Successor warning: six slots × one row ≠ one shared budget. A durable shared limiter is UNFINISHED_WORK U5.

### E5. Text mode on the profile lanes
- Classification: `[COMPATIBILITY REQUIREMENT]`
- What: `structured: "text"`, `json_mode: false` on all nine `profile_*` rows — Groq returns 400 for `response_format: json_object` unless the prompt contains "json"; the profile is labelled lines, never JSON.

### E6. Fallback reachability and lane offsets
- Classification: `[ARCHITECTURAL REQUIREMENT]`
- What: `attempt_lanes` = the first 2 rotated primaries + fallbacks, ≤ 4; without the supervisor offset, rotation is by run hash. With six primaries, the previous `lane_order[:4]` never reached Gemini — the fallback tier was dead code until 2026-09-07.
- Evidence: `test_document_profile_stage.py` (attempt lanes, offset, transient classification); three live documents were answered by Gemini fallbacks after 429s.

## F. Experiments and things not promoted

| Item | Classification | State |
|---|---|---|
| B15 bridge-hop (GRAPH hop-2 in corpus language) | `[EXPERIMENTAL]` demoted | probes showed pseudo-relevance feedback cannot reach Laban; order B14 → B15 |
| B14 abstraction ladder L0–L6 as compiler vocabulary | `[OWNER PREFERENCE]` queued | L3 first, per-rung cited-share gate; not built |
| Sparse title ranker (`POLYMATH_CHAT_COMPILER_TITLES_RANK=sparse`) | `[EXPERIMENTAL]` retained | 80 ms, cannot reach cross-vocabulary books |
| Document vote in routing (11.120) | `[EXPERIMENTAL]` off by default | one env line away |
| `judged_prefix` round robin / aspect seats / diversity slots | `[TEMPORARY COMPROMISE]` | present in code, rejected by the owner, replacement pending |
| Postgres `max_parallel_workers_per_gather = 0` | `[TEMPORARY COMPROMISE]` `[OPERATIONAL CONSTRAINT]` | flip back at the next container recreate (`shm_size: 1gb` is in compose) |

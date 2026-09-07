---
title: "WORK LOG — DOCUMENT-PROFILE-V1 steps 2–4: lean context builder, the doc_profile stage with its isolated pool, and the multi-representation projection"
change_id: DOCUMENT-PROFILE-V1
date: 2026-09-07
owner: governance (owner architecture 2026-09-07; plan of record docs/wiki/plans/DOCUMENT-PROFILE-V1.md)
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: implemented (steps 2–4 of 6; rollout phase A — non-blocking, dormant until the fleet is booted with the new slot)
register: 11.126
package: shared/polymath_shared/document_profile/{context,projection}.py, workers/workers/doc_profile_worker.py, control/control/{tickets,fleet_autopilot,process_supervisor}.py, config/cloud_providers.json (+ stage pin), config/extraction_models/limiter.yaml, tests/determinism/test_document_profile_{context,projection,stage}.py
architecture_impact: "A new durable stage `doc_profile` (event doc_profile.v1) turns what intake already knows about a document — name, heading paths, opening / ending / sampled sections, known terms — into a ~500-token DOCUMENT block, asks the isolated `doc_profile` LLM pool (tier 0 free Gemini lanes, tier 1 a cheap OpenRouter fallback; never the extraction / graph / compiler pools), compiles the reply with rag-profile-v3, writes the profile artifact and projects ONE point per document into its own collection `polymath_document_profiles_<embedding contract>`: named dense vectors title / identity / theme and named multivectors questions[] / searches[] / theories[] / concepts[] / seealso[] (MaxSim), one vector per atomic unit. The two artifacts carry the deterministic receipt chain content hash → input hash → raw response hash → compiled hash → projection hash. Rollout phase A: the stage is the last, non-blocking DAG entry, so nothing about QUERY_READY changes yet; phase B (after the backfill) moves it ahead of verify_projections and out of NON_BLOCKING_STAGES, which is what makes ingested != query_ready. Invariants held: chunk vectors, chunk ids, parent/child projection identity and graph receipts untouched."
---

# WORK LOG — DOCUMENT-PROFILE-V1 steps 2–4

## Contract

Every document can receive one cheap document-level enrichment pass that produces a structured retrieval profile, stored as an artifact with a receipt chain and embedded as several independent document-level representations, without touching the evidence systems (chunks, parents, graph).

## Changes

- **Step 2 — `context.py`** (lean context builder): identity ≈ 40 tokens (frontmatter title / author when present, else the cleaned file name, plus format), structure ≈ 150 (distinct heading paths in document order, furniture and file / page segments removed, an EVEN STRIDE over the whole list so the selection spans the book instead of stopping at chapter 3; whole paths, never clipped), opening 80 / ending 60 (first and last BODY parents — front matter, contents pages and copyright paths excluded), middle 100 (25 / 50 / 75 % samples for unstructured or long documents), terms 20; a smaller budget scales every surface, structure spills into what the excerpts leave unused; `input_hash` = sha256(builder, content hash, rendered blocks, allocation).
- **Step 3 — `doc_profile_worker.py`**: resolves the run's document from its `chunked.v1` payload (or the intake payload), builds the context, calls the pool (`stage_pin("doc_profile")` in pin order, ≤ 3 lanes, transport failures walk to the next lane; a dark pool raises `TransientStageHold` — the ticket is handed back READY, no attempt consumed), compiles, writes `artifact.doc_profile` {schema, prompt, compiler, builder, model, lane, attempts, content_hash, input_hash, raw_response_hash, compiled_hash, quality / format / coverage, ok, valid, missing, issues, context, raw, compiled, representations}; an invalid profile (no semantic core or no query hook) is a stage failure (attempt consumed → ticket retries → dead-letter); then projects and writes `artifact.doc_profile_qdrant` {collection, point_id, projection_key, projection_hash, vectors per surface, valid, missing}. Dependency hooks (`HOOKS`) for the LLM, the embedder and Qdrant.
- **Control plane**: `STAGE_DAG` + `("doc_profile", "doc_profile.v1", ("doc_profile",), ())` as the last entry; `NON_BLOCKING_STAGES` + `doc_profile` (phase A only); autopilot demand lane `("doc_profile", ("doc_profile",), {"doc_profile", "sidecar_embedder", "qdrant"})`; `FLEET` + `("doc_profile", "workers.doc_profile_worker")`.
- **Pool**: providers `profile1` (gemini-3.1-flash-lite, GEMINI_API_KEY_3), `profile2` (GEMINI_API_KEY_4), `profile_fallback` (OpenRouter mistral-small-2603, OPENROUTER_API_KEY) — `structured: null` (plain labelled lines, never JSON mode), `dedicated: true`; `stage_pins.doc_profile = [profile1, profile2, profile_fallback]`; limiter rows profile1 / profile2 (rpm 8, rpd 400, conc 2) and profile_fallback (rpm 20, conc 1). The two Gemini lanes share provider KEYS with compiler3 / compiler4 (their limiter rows are separate); dedicated keys are the owner's to add.
- **Step 4 — `projection.py`**: `collection_name(contract)`, `vectors_config(dim)` (named dense + `MultiVectorConfig(MAX_SIM)`), `ensure_collection`, `texts_to_embed` (fixed batch order), `build_point_vectors` (str → one vector, list → one vector per item), `project_profile` (embed once, upsert one point with payload doc_id / corpus_id / title / topics / terms / quality / hashes / surfaces), `projection_key = hash(source_doc_hash, schema, prompt_version, embedding contract)`, `has_required_vectors` (identity + theme + a Q/SEARCH vector — the projector's half of the readiness contract). `ANSWER_SURFACES = identity, theme, questions, searches, title`; `EXPLORATION_SURFACES = seealso, theories, concepts`.

## Proof

Pure and Postgres-backed tests, 17 green: context (6) — headings vs positions, furniture removal, even stride with whole paths, budget scaling, frontmatter identity, deterministic input hash; projection (4) — one vector per atomic unit, one point per document, collection created once, idempotent projection hash, projection key sensitivity, readiness half; stage (4) — DAG / autopilot / fleet / pool pins, the worker against Postgres with a fake LLM (the v3 sample profile), a stub embedder at the live contract's 1,024 dimensions and a fake Qdrant: `receipts.status = committed`, both artifacts present, `content_hash` = the document's, 64-character input / raw / compiled / projection hashes, `compiled_hash` equal across the two artifacts, quality ≥ 0.7, valid, 3 question vectors, the point's payload carries doc_id and corpus_id, the run status and chunk rows untouched; a dark pool raises the transient hold with no artifact written. Existing pins updated: the control-plane stage order now ends with `doc_profile`; the DAG contract and summary-layer suites unchanged.

Not yet exercised: a LIVE LLM call on the pool and a real point in Qdrant — that is step 5 (the backfill), which also needs the fleet booted with the new `doc_profile` slot (the running supervisor read its FLEET table at boot) and is enrichment spend under the owner's go.

## Rejected claims

- "Put the profile stage ahead of verify now" — no: existing runs never get the new ticket automatically (`ensure_run_tickets` mints chains only for ticketless runs), so a blocking placement would strand no one but would also gate nothing until the backfill exists; phase A keeps the corpus serving and lets the backfill run first.
- "Reuse the extraction pool" — no (owner): enrichment is becoming a control-plane gate; it gets its own lanes so it can neither starve ingestion nor be starved by it.
- "Two excerpts from every major section" — no (owner): too expensive as a default; opening / ending / three samples within a 500-token allocation.
- "TERM as a sparse vector now" — not yet (owner): TERM stays in the payload for lexical / entity use.

## Open contract gaps

- Step 5 backfill: mint `doc_profile` tickets for every existing run (script), boot the fleet with the new slot, run the pool on 67 documents, re-evaluate readiness; measure the self-retrieval gate (each book's own questions retrieve it first).
- Step 6 retrieval lane: prefetch identity / theme / questions / searches / title → RRF → top-k documents → deepen children into fusion with `DOCUMENT_PROFILE` provenance; the title ranker reads the same ranking; receipts.
- Phase B: move the DAG entry ahead of `verify_projections`, drop it from `NON_BLOCKING_STAGES` — the readiness invariant.
- Dedicated provider keys for the profile pool.
- A `TransientStageHold` raised inside the stage transaction still records a failed attempt row before the runtime hands the ticket back (existing behaviour shared with the summary stages); the ticket's own attempt counter is what the retry law reads.

---

# Step 5 — the live backfill (2026-09-07, later the same day)

Owner: "will it replace current doc summaries? if so go ahead and backfill" (answer: no — the profile is ADDITIVE to the summary layer; nothing about summaries changes) and, on the first compile problem, "you should be improving the script to essentially compile the output because the model is capable inference wise" — the compiler absorbs the model's shape; the prompt is not the fix.

## What the first live calls showed

- **Transport** (all nine profile lanes): Groq HTTP 400 — `'messages' must contain the word 'json' … to use response_format json_object`. The registry rows had `structured: null`, the loader fell back to JSON mode and the client sent `response_format: json_object`. Fix: the nine `profile_*` rows are `structured: "text"`, `json_mode: false` (the profile is labelled lines, never JSON). Pinned.
- **Shape** (groq/compound AND openai/gpt-oss-120b, same keys): the model sometimes writes a label once and lists the rest on bare lines — `TOPIC: Screen Combat\nFilm Production\nAction Design…`, all fifteen questions under one `Q:`, ten CONCEPTs joined. The v3 compiler treated every unlabeled line as a wrapped continuation (`LINE_MERGED`) → counts 1 / 1 / 1 / 1 / 1 / 1 / 1, coverage 0.29, and the same document re-asked came back fully labelled with quality 1.00. Non-deterministic output shape, deterministic compile loss.
- **Groq HTTP 413** on one lane for one document (12.9 s), 200 on the next lane for the same prompt (~1.3 k tokens) — compound is agentic; a size error there is transient, not ours.
- **Embedder HTTP 422** on the first real ticket: the projection sends ~63 texts per profile in ONE request; the sidecar rejects more than `POLYMATH_MAX_BATCH_TEXTS` (4 since the OOM relief earlier today). Two tickets burned an attempt each before the fix.

## Changes

- **`compiler.py` → `rag-compiler-v3.1`.** Under a LIST tag an unlabeled line is a NEW item (`ITEM_SPLIT`, info) unless the previous item is visibly open — ends with joining punctuation or a connector word (`and, or, of, the, to, for, with, …`), or, for the sentence-shaped lists Q / THEORY / CONCEPT, the new line starts lowercase after an unterminated item (keyword lists TOPIC / TERM / SEARCH / SEEALSO are usually lowercase, so case says nothing there). Text tags (ONE / SUMMARY / DETAIL) still merge. `Q: a? B? C?` on one line → three questions (`split_inline_questions`). The exact live shape compiles to 4 / 1 / 3 / 2 / 1 / 3 / 2 items with nine `ITEM_SPLIT`s; a genuinely wrapped question (`…when the actor is\nstanding too far away?`) still merges.
- **`prompt.py` → `doc-profile-v3.2`** (secondary): "Start EVERY line with its label … Never write a label once and then list unlabeled lines under it" + "Do not put more than one item on a line".
- **`doc_profile_worker.py`**: (1) `attempt_lanes(pin, run)` = the first 2 rotated primaries + the fallbacks, ≤ 4 — with six primaries the old `lane_order[:4]` never reached Gemini (fallback 1 was dead code); (2) `transient_pool_error` — only 408 / 413 / 425 / 429 / 5xx / transport / `rate_limited` / dark-pool errors hand the ticket back (`TransientStageHold`); a 400 / 401 / 403 / 404 or an empty 200 is a FAILED attempt, so a document that can never be profiled ends as a receipted failure instead of holding forever; (3) `_embed_texts` slices to `embed_batch_size()` (`POLYMATH_MAX_BATCH_TEXTS`, default 4) and asserts one vector per text; (4) the artifact carries `doc_id` / `corpus_id`.
- **`config/cloud_providers.json`**: text mode on the nine profile lanes.
- **`scripts/backfill_document_profiles.py`** (mint / `--dry-run` / `--status`) and **`scripts/document_profile_gate.py`** (self-retrieval gate through the profile collection) — declared in the scaffold and `scripts/README.md`.

## Proof (automated)

Determinism: compiler 10 (three new: the live unlabeled shape, the open-item merge, inline questions), stage 12 (three new: attempt lanes, transient classification, embedding slices), context 6, projection 4, control-plane v2 — 33 green; `repo_guard` ok. Full `tests/determinism` run: the only failure is `test_chat_retrieval_v2 … rerank_deadline_s == 8.0` because this shell had `.env` sourced (`POLYMATH_CHAT_RERANK_DEADLINE_S=12`, the interactive-relief setting); CI does not source `.env`.

## Proof (live)

Canaries after the fix (groq/compound, lean context ≈ 320 prompt tokens + 3.6 k system): Screen Combat Handbook quality 1.00 counts 10 / 10 / 15 / 15 / 10 / 10 / 10; Bayesian reasoning for Laban Movement Analysis 1.00, 4.7 s; Affective Movement Generation 0.94, 8.2 s (after the 413 on the other lane).

Backfill: 67 tickets minted 14:41:41Z; the autopilot spawned the single demand slot at 14:41:44Z; first success after the slicing fix at 14:44Z. Profiles read in full (not counts): Dancyger's editing book → continuity / montage theory, "pacing influences narrative tension"; Keirsey → the four temperaments with MBTI / Jung as SEEALSO; Timing for Animation → "timing controls perceived weight", squash-and-stretch as timing modifiers. Lowest quality so far 0.88 (How to Draw Manga: Illustrating Battles) — its `UNGROUNDED_TERM`s include `Document2PDF Pilot`, `Trial version`, `PDF guide`: the source carries a converter watermark and the profile faithfully reports it (a document-quality finding, like Framed Environment Design's OCR).

## Throughput (owner, mid-backfill: "those are different api accounts, one document at a time is stupid")

Measured on the single slot (15 documents): claim wait + LLM 7–16 s (two outliers 47 / 52 s), embedding 8–9 sidecar calls spanning 9–15 s per document, ≈ 1 document a minute end to end. The runtime executes tickets serially (LONG-STAGE-LEASE-CORRECTNESS-V1) and the fleet scales a stage by SLOTS (EXTRACT-SCALE-OUT-V1: one extract worker per open ticket, capped at 3). **DOC-PROFILE-SCALE-OUT-V1:** `FLEET` gains `doc_profile2..6`; the autopilot wakes one profile worker per open `doc_profile` ticket, capped at six — one document in flight per dedicated key (the run-hash lane rotation spreads them). Pinned in `test_fleet_autopilot_demand` (1 → one slot, 3 → three, 51 → six, never a seventh) and the stage test's FLEET pin. The supervisor reads `FLEET` at boot, so the fleet was booted mid-backfill (in-flight tickets roll back and re-lease). Ceiling that remains: the embedder sidecar (≈ 5.8 texts/s regardless of callers; ~63 texts per profile ≈ 11 s of embedding per document serialized), shared with the 24 `project_qdrant` tickets still draining.

## Rate limits and the model actually serving (owner questions, 15:0xZ)

- **Is the pool inside the provider limits?** Not cleanly on the first six-slot run: 18 × HTTP 429, 2 × 503, 1 × 413 across 88 attempts (all in 14:54–14:59Z, when six slots on run-hash rotation collided on keys; the single-slot phase had one 429). Every event was absorbed by the next lane (`attempt_lanes`) or the Gemini fallback (3 documents); 0 failed receipts, 0 holds after the slicing fix. Peak observed rate 17 Groq requests/min across six keys. Fix shipped: each slot now starts its lane walk on ITS key (`POLYMATH_DOC_PROFILE_LANE_OFFSET` from the supervisor: `doc_profile` → 1 … `doc_profile6` → 6), and because the limiter is per PROCESS (threading locks, no shared state) the profile rows are one slot's budget: rpm 12 / conc 1 / tpm 60 000 / rpd 230 (rpd is advisory — it resets with the process). Pinned in the stage test. A durable shared budget is open work (UNFINISHED-WORK #5).
- **Which model is serving?** The backend sends `model: groq/compound` on every attempt (84 / 84 in the artifacts; registry and pin carry no other Groq model). Groq echoes `"model": "groq/compound"` and reports in `usage_breakdown` that compound routed the request through `meta-llama/llama-4-scout-17b-16e-instruct` (two router steps) and `openai/gpt-oss-120b` (the answer, with reasoning tokens). The Groq dashboard attributes usage to those underlying models — that is compound working as designed, not a mis-pinned model. Consequence: one profile request costs 2–3 model calls on the key, which is the multiplier behind the 429s. Two manual probe calls earlier in the session used other names directly (`openai/gpt-oss-120b` on lane 3: 200 in 3.5 s, same output shape; `qwen/qwen3.8-27b` on lane 2: 429) — canaries, not backend traffic. Keeping compound is the owner's call (UNFINISHED-WORK #6).

**Owner's answer (15:2xZ) and the header measurement.** The owner chose compound FOR the rate limits: free-plan `groq/compound` = RPM 30 / RPD 250 / TPM 70K, no TPD; `openai/gpt-oss-120b` / Qwen = TPM 8K / TPD 200K (one profile request a minute per key). Measured on key 6 with Groq's headers around one real profile request (Timing for Animation, lean context): `x-ratelimit-limit-tokens` 70000 → remaining 69990 before, 66267 after (≈ 3.7k charged to the TPM window), `x-ratelimit-limit-requests` 250 → 230 → 229 (RPD 1); the response's `usage_breakdown` listed 12 internal calls — 11 × llama-4-scout (1.3k → 2.3k prompt each, up to 3k completion) + 1 × gpt-oss-120b (2.5k prompt, 1.5k completion) — 38,541 internal tokens in 40.6 s. So the key's own counters are nowhere near the limit at our cadence; the 429s of the six-slot run were the internal models' budgets under key collisions. Setting: profile rows rpm 2 / conc 1 per slot (one slot per key), AIMD halves on 429 / 503; suggestion to move to gpt-oss WITHDRAWN.

## Result

67/67 cinema documents profiled (0 failed, 0 dead) in 20 min (one slot 14:43–14:54Z ≈ 1 doc/min, six slots 14:54–15:03Z ≈ 6 docs/min); quality p50 1.0 (min 0.13), LLM p50 7.7 s/doc; lanes fallback_gemini1 2, fallback_gemini2 1, groq1 11, groq2 11, groq3 11, groq4 10, groq5 11, groq6 10; 67 points in the profile collection; self-retrieval (own questions + searches → profile lane, RRF) top-1 85.8 %, top-3 99.5 %, median rank 1; punch question top-5: Fight Choreography: The Art of Non-Verbal Dialogue · The Screen Combat Handbook · Stage Combat Arts · How to Draw Manga: Martial Arts and Combat · Grammar of the Shot · … The Laban Workbook for Actors at 6 and Your Move at 15 — the Laban case reached through the profile lane alone.

Quality issues seen across the corpus: UNGROUNDED_TERM 23 (terms not lexically in the source, incl. converter-watermark text), BELOW_TARGET 8, ITEM_SPLIT 7 (the compiler fix exercised live), UNKNOWN_TAG 7 + GARBAGE_LINE 10 (all on the one 0.13 profile, RAPO paper — compound wrote `Retrieval:` / `Diffusion:` style lines), LIST_CAPPED 1. Holds recorded: 5 (all before the slicing fix or transient lane errors that the next lane answered).

## Rejected claims

- "Fix it in the prompt" — no (owner): a prompt rule cannot make a sampled output shape deterministic; the compiler now compiles what the model writes, the rule only raises the odds.
- "Merge unlabeled lines by default because they might be wrapped" — no: plain-text LLM output does not hard-wrap; the observed failure was always a dropped label. Merge only on visible openness.
- "Hold on every pool error" — no: a 400 / 401 / 403 / 404 on every lane is a defect to surface as a failed attempt with receipts, not a ticket parked forever (3-minute stall rule).

## Open contract gaps

- Step 6 retrieval lane `DOCUMENT_PROFILE` (boost, never gate) + the title ranker on the same ranking; then phase B (DAG entry ahead of `verify_projections`, out of `NON_BLOCKING_STAGES`).
- New documents: the DAG mints `doc_profile` for every new run (phase A, non-blocking) — the profile lags ingestion by one pool call; phase B makes it a readiness requirement.
- Converter watermarks and OCR garbage surface as `UNGROUNDED_TERM`s in the profile (How to Draw Manga: Illustrating Battles; Framed Environment Design) — a source-quality decision for the owner, not a compiler one.
- The six Groq keys pasted in chat on 2026-09-07 are to be rotated by the owner.
## Closeout (end of the 2026-09-07 session)

Repository handed off in a continuation-ready state. Git: `main` == `architecture/evidence-first-v5` == `origin/main` at `22f93c3` before the closeout commit; worktree clean; no untracked implementation files; two worktrees (`polymath-v4`, `polymath-v4-main`); no stash. Fleet: orchestrator, embedder, reranker ready; `doc_profile` tickets 67 done / 0 open; `project_qdrant` backlog 19 (deadline stays at 12 s until it drains).

Documentation generated: `docs/wiki/reports/2026-09-07/` — `README.md` (successor bootstrap + operating contract), `CONTINUATION_REPORT.md`, `BE_AWARE.md` (classified rules; supersedes `BE-AWARE-REPORT.md`), `ARCHITECTURE_STATE.md`, `DECISION_REGISTER.md`, `UNFINISHED_WORK.md` (U1–U12; supersedes `UNFINISHED-WORK.md`), `DEPENDENCY_MAP.md`, `NEXT_ACTIONS.md`, `WORKTREE_AND_BRANCH_CLOSEOUT.md`, `COMMITS_AND_MERGES.md`, `VERIFICATION.md`. Hooks: `AGENTS.md` §0, `CLAUDE.md`, `README.md`, `docs/README.md`, `docs/wiki/README.md`, the continuity report's read order.

Verification at closeout: `repo_guard` ok, `wiki_worm --check` ok, `agent_preflight` ok, 75 targeted determinism tests green in a clean shell (the `rerank_deadline_s == 8.0` pin only fails when `.env` is sourced).

Closed today: B1 (11.121), region exclusion (11.123), DOCUMENT-PROFILE steps 1–5 (11.125–11.128) incl. scale-out and pacing. Still IMPLEMENTED: B16 (11.122, owner hand-test), INTERACTIVE-RELIEF (11.124, after-measurement). Next continuation point: `UNFINISHED_WORK.md` U1 — the `DOCUMENT_PROFILE` retrieval lane — then phase B.

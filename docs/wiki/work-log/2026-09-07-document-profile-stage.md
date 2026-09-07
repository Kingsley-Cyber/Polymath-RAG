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

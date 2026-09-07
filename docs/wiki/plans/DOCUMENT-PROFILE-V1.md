---
title: "DOCUMENT-PROFILE-V1 — every admitted document gets a mandatory, compiled, multi-representation retrieval profile before it is query-ready"
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: plan-of-record (owner architecture 2026-09-07)
---

# DOCUMENT-PROFILE-V1 (owner architecture, 2026-09-07)

> Every document admitted into Polymath must receive one cheap document-level semantic enrichment pass. That pass produces a structured Document Retrieval Profile. The profile is compiled, stored, and independently embedded into multiple document-level retrieval representations. A document does not become QUERY_READY until the required profile artifact and vectors exist. Profile generation uses its own isolated API pool. Existing parent, child, and graph retrieval remain evidence systems and are not replaced.
>
> Document profiles provide a mandatory semantic interface to every document and an additional document-discovery lane. They boost and deepen relevant documents, while chunks remain the source of answer evidence.

## Invariants (owner, verbatim)

**DO NOT:** replace current chunk vectors · change chunk IDs · change parent/child projection identity · change existing graph receipts.

**DO:** add document-profile artifacts · add document-profile vectors · add a document-profile retrieval lane · fuse that lane with existing retrieval.

```
DOCUMENT ADMITTED
      │
      ├── existing chunk projection
      ├── existing graph/entity projection
      │
      └── REQUIRED DOCUMENT PROFILE
                │
                ├── lean context builder
                ├── enrichment LLM          (isolated pool: profile.enrich)
                ├── deterministic compiler  (rag-profile-v3)
                ├── profile artifact
                └── profile vector projection
                         │
                         ▼
                   QUERY READY            ingested != query_ready
```

## The profile (labels and counts)

| label | count | meaning |
|---|---|---|
| ONE | 1 | what the document is mainly about |
| SUMMARY | 1 | one or two dense sentences |
| TOPIC | aim 10 (floor 5) | specific major topics |
| TERM | aim 10 (floor 5) | terms, entities, frameworks, acronyms actually supported |
| Q | aim 15 (floor 8) | natural questions the document can answer, spread across its parts |
| SEARCH | aim 15 (floor 8) | short keyword searches (2–6 words, no question mark) |
| THEORY | aim 10 (floor 4) | underlying frameworks, mechanisms, models or explanatory lenses; never invent a named theory |
| CONCEPT | aim 10 (floor 4) | transferable ideas that could appear in another field — mechanisms, relationships, constraints, trade-offs, patterns; never broad nouns |
| SEEALSO | aim 10 (floor 5) | neighbouring, prerequisite, deeper, broader, contrasting or complementary knowledge |

Owner update 2026-09-07: aims raised from the v3 draft (3–5 / 3–7 / 1–5 / 2–5) to 10 / 10 / 15 / 15 / 10 / 10 / 10. Aims are ceilings to reach when the document supports them; floors only raise an informational note; counts are never required.
| END | — | never required |

Correct meaning outranks exact counts. Missing items are omitted, never invented.

## Compiled semantic artifact

```json
{"one": "...", "summary": "...", "topics": [...], "terms": [...], "questions": [...],
 "searches": [...], "theories": [...], "concepts": [...], "seealso": [...]}
```

The compiler emits **atomic units**; the projector decides `str → one vector`, `list[str] → one vector per item`. Never five long strings.

## Readiness (tolerant, minimum semantic contract)

```
profile_valid = has_semantic_core (ONE or SUMMARY)
            and has_identity_vector
            and has_theme_vector
            and has_query_hook (Q or SEARCH)
            and at least one Q/SEARCH vector
TOPIC strongly preferred · TERM preferred · THEORY / CONCEPT / SEEALSO optional
exact counts never required · END never required
```

## Vector projection (separate collection, one point per document)

| representation | kind | answers |
|---|---|---|
| title | dense | does the document call itself something relevant? |
| identity (ONE + "Topics: …") | dense | is this the kind of document I need? |
| theme (SUMMARY) | dense | does its overall content match? |
| questions[] | multivector (MaxSim) | can it answer what I asked? |
| searches[] | multivector | would someone searching this way want it? |
| theories[] / concepts[] | multivector | does it explain by this mechanism / demonstrate this transferable idea? (exploration + ladder rungs) |
| seealso[] | multivector | is it adjacent to where I am exploring? — **excluded from normal answer retrieval** |
| TERM | not a dense vector: lexical / entity linking / filters / graph (sparse later, not required now) |

Collection `polymath_document_profiles_<embedding contract>`; payload doc_id, title, topics, terms, profile_version, quality.

## Receipt chain (deterministic)

```
document content hash → profile input hash → raw LLM response hash → compiled profile hash → embedding projection hash
```
Artifact `document_profile` {schema rag-profile-v3, prompt_version, model, compiler_version, quality, issues, raw, compiled}. `projection_key = hash(source_doc_hash, schema, prompt_version, embedding contract)`. Change chunking → no regeneration; change embedding → re-embed only; change compiler → recompile stored raw; change prompt → regenerate profiles only.

## Lean context builder (~500 tokens, deterministic allocation)

identity ~40 (title, subtitle, meaningful filename, type, author/org, page/meta title) · structure ~150 (TOC / headings; papers: section names; HTML: H1–H3, captions; transcripts: speaker/timestamp/chapter boundaries; no structure: beginning → 25 % → midpoint → 75 % → end) · opening ~60 · ending ~40 · terms ~20 (existing entity/keyword signals). Lean but contextually rich; excerpts and sections may run high in tokens for the API, so the builder trims by allocation, not by dropping surfaces.

## API pool isolation

`profile.enrich` is its own lease class with its own keys / concurrency / rate limits — never the extraction / graph / enhancement pool. Wired 2026-09-07: tier 0 = six DEDICATED Groq accounts (`profile_groq1..6`, groq/compound, RPM 30 / RPD 250 / TPM 70k each, limiter rows at 25 / 230 / 60k), rotated per run, ≤ 2 tried per document → fallback 1 = Gemini flash-lite on its own keys (`profile_fallback_gemini1/2`) → fallback 2 = OpenRouter mistral-small (`profile_fallback_openrouter`) → dead-letter. Keys live only in `.env` (`GROQ_API_KEY_1..6`, `GEMINI_API_KEY_5/6`, `OPENROUTER_API_KEY_2`). Live 2026-09-07: `groq/compound` is agentic (Groq's `usage_breakdown` shows llama-4-scout router steps + gpt-oss-120b answers per request — the dashboard attributes usage there), so one request is 2–3 model calls on the key; six `doc_profile` slots run one document each, every slot starting on its own key (`POLYMATH_DOC_PROFILE_LANE_OFFSET`), limiter rows rpm 12 / conc 1 per process (the limiter is per process). Enrichment is a control-plane gate, so it must not be able to starve ingestion or be starved by it.

## Retrieval

Normal answer retrieval: title ✓ identity ✓ theme ✓ questions ✓ searches ✓ terms ✓ · seealso ✗. Exploration / related knowledge: seealso ✓ topics ✓ terms ✓ theories ✓ concepts ✓ graph ✓. Query: embed once; prefetch identity, theme, questions, searches, title; RRF; the resulting documents **boost and deepen** chunk retrieval (their children enter fusion with `DOCUMENT_PROFILE` provenance and compete through the judge). Never `WHERE doc_id IN top_k` — boost, not gate — until evaluation proves the router.

## Build order

1. Compiler v3 in the repo (THEORY, CONCEPT, counts, atomic representations, tolerant validity) — pure, tested.
2. Lean context builder — pure, tested on md / html / pdf / transcript shapes.
3. Profile pool + stage `document_profile` (ticket after intake; artifact with the receipt chain) — the readiness gate flips to require it.
4. Projection to the profile collection (named dense + multivectors) with the projection key.
5. Backfill every existing document; readiness re-evaluated. — **DONE for cinema 2026-09-07 (11.128):** 67/67 profiled, quality p50 1.0; readiness itself flips in phase B.
6. Retrieval lane + fusion; receipts; the gate below.

## Gate

Per document: its own generated questions retrieve it first (self-retrieval). Per turn: documents reached and cited up on the synthesis loop, factual precision unchanged, frozen fixture floors held; a book with a vocabulary different from the question's (the Laban case) reached through the profile lane without the compiler-title workaround.

**Measured 2026-09-07 (cinema, `document-profile-gate-gate1.json`, before the retrieval lane exists):** self-retrieval top-1 85.8 %, top-3 99.5 %, median rank 1 over 400 probes (3 questions + 3 searches per document); punch question through the profile lane alone → Fight Choreography: The Art of Non-Verbal Dialogue · The Screen Combat Handbook · Stage Combat Arts · How to Draw Manga: Martial Arts and Combat · Grammar of the Shot · … The Laban Workbook for Actors at 6 and Your Move at 15 — the Laban case reached through the profile lane alone.

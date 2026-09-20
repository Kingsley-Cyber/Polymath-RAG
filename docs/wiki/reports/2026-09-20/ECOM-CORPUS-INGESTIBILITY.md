---
title: "Can the old ecom-meta-v1 source material be ingested through the current v4 pipeline? (read-only determination)"
date: 2026-09-20
status: measured
method: "READ-ONLY recon by one sub-agent pass (disk, Postgres SELECTs, Qdrant GETs, v4 materializer run in-process on spool blobs); the central claims re-checked directly afterwards. Nothing was ingested, created or modified. One deviation, disclosed below."
polymath_head: 12c477c
feeds: "docs/wiki/plans/GOVERNED-CONVERGENCE-V1.md (TG5 owner amendment 2026-09-20)"
last_reviewed: 2026-09-20
---

# Verdict: INGESTIBLE WITH PREP — and nothing has to be recovered from an index

Owner question (2026-09-20, with the TG4 word): *"Determine whether the old `ecom-meta-v1` source material can be ingested
through the current V4 ingestion/profile/atom pipeline rather than copying old indexes blindly."*

Yes. The source bytes survive intact in two independent places on this Mac, already in v4's best-supported format
(markdown). Copying old indexes is not an option at all: they no longer exist. **The one real blocker is finish-line
Item 2 sub-item D (corpus-scoped `search_atoms`) — a second corpus must not go live before it.** Nothing here authorizes
an ingest; this report only answers the question.

## 1. Correction to the premise
`ecom-meta-v1` was **not** a v3.3 corpus. It was a **v4 corpus of 10 documents** that lived in this stack from about
2026-09-01 to 2026-09-12 and was deleted. (The "28" in `work-log/2026-09-12-extract-operational-projection.md` counts
extract artifact rows; the same day's readiness log reads `ecom-meta-v1 10/0`.) It was a ~9 % subset of the v3.3
`ecommerce_meta` library.

## 2. Where the source material is (verified on disk)
| Copy | Path | What | Integrity |
|---|---|---|---|
| A — the exact `ecom-meta-v1` bytes | `/Users/king/PolymathRuntime/polymath-v4/spool/` (v4 content-addressed spool, `<aa>/<sha256>`) | 129 blobs / 57 MB total: 67 = `cinema`, 62 orphans; **11 orphans carry `source_file: E:\books\psycho_commerce\…`** = 6.21 MiB | all 11 sha256-verify against their filenames; run through v4's own materializer, two of them normalize to exactly the `doc_57aab6bb…` / `doc_d444fe46…` ids recorded in the skill WORKLOG and `work-log/2026-09-04-final-correctness-pass.md` |
| B — the full v3.3 library it came from | `/Users/king/PolymathRuntime/volumes/ingest-files/9dc27284-5012-44c0-84f9-864bb8193062/` (batch → corpus map in `/Users/king/polymath-v33-archive/manual-ingest-state/*.json`) | **117 `.md` files, 71 MB**, largest 3.4 MB; origin mix 73 epub · 26 pdf · 11 mobi · 6 azw3 · 1 fb2, all pre-converted to markdown with `source_file` / `source_type` / `rag_ready` front matter | 0 unreadable, 0 zero-byte, 100 % valid UTF-8, 0 duplicate titles; 10 of the 11 spool blobs are byte-identical to files in this set |

The 11 titles in copy A: The Innovator's Dilemma · Psychology of Habit · Atomic Habits · Always Alchemy (Hart) · Alchemy
(Sutherland — superseded twin, identical body) · Competing Against Luck · Blue Ocean Strategy · The AI Advantage ·
Building a StoryBrand · The Psychology of Gambling · Netnography. Copy B adds consumer-psychology, pricing, sourcing and
persuasion titles (Positioning, Cashvertising Online, Consumer Behavior, The Strategy and Tactics of Pricing, Contagious,
Misbehaving, SPIN Selling, 42 Rules for Sourcing and Manufacturing in China, …).

Other v3.3 batches also survive under `ingest-files/` (1,107 `.md`, 451 MB in all): `markbuildsbrands_transcripts` 248
files, a 77-file Meta-ads transcript batch, `video_generations_schools` 79, `cybersecurity_study` 26, a 498-file web
scrape. The binary originals (`E:\books\psycho_commerce\`) are on a Windows drive, not on this Mac — irrelevant, the
pre-materialized markdown is what was ingested both times.

## 3. What survives of the old indexes: nothing usable
- v4 Postgres: `corpora` = `cinema` only; `archived_corpora` = 0 rows; `documents` = 67 (`cinema`); `chunks` = 84,152, all
  `cinema`; no `ecom-meta-v1` runs. Qdrant: 4 collections, all on contract `e794ec4cab197a3f`, no ecom collection.
- v3.3: the containers are REMOVED (not stopped); five Docker volumes survive (Mongo 5.2 GB, Qdrant, Neo4j ×2, Redis) and
  are unreadable without booting a removed stack. Same embedding model and dimension (Qwen3-Embedding-0.6B, 1024) as v4,
  but chunk identity, payload schema, collection naming and the document / parent / atom substrate all differ — copied
  vectors would join to nothing. Moot either way.

## 4. What v4 ingestion accepts (verified in code)
- `POST /upload` (`orchestrator/orchestrator/api/ui.py:457-530`): `.md .txt .html .pdf .epub .docx`, cap
  `POLYMATH_UPLOAD_MAX_MB` = 200 MB, byte-identical re-upload in the same corpus → 409. Also `POST /intake`, MCP
  `polymath_upload_file` / `polymath_upload_text`, bulk `scripts/ingest.py` (manifest `plan` / `run` / `status`).
- **`corpus_id` is a free parameter**: the first ingest creates the corpus (`workers/workers/intake_worker.py:297-306`,
  `INSERT … ON CONFLICT DO NOTHING`); no registry step. It inherits the default embedding contract and ontology profile.
- A content-addressed `doc_id` may belong to exactly ONE corpus (`CROSS_CORPUS_CONTENT_COLLISION`,
  `intake_worker.py:226-237`). The 11 blobs were tested against `cinema`'s 67 normalized hashes: **0 collisions**. The
  near-duplicate guard is corpus-scoped, so `cinema`'s books do not interfere.
- DAG (`control/control/tickets.py:24-58`): intake → extract → profile_document → project_qdrant → project_neo4j →
  canonicalize → project_canonical → verify_projections → [non-blocking] compile_objects → parent / document / corpus
  summary → vocabulary → doc_profile. pMAP and parent_enrichment are owner-minted, not in the DAG.
- Paid / external stages: `extract` (the whole provider roster), `doc_profile`, `doc_parent_map`, `parent_enrichment`,
  summaries / vocabulary (pins in `config/cloud_providers.json`). Local: chunking, embedding, reranking, the
  deterministic compilers and projections.
- Measured on `cinema`: upload → query_ready ≈ 5 min for a 500 KB book; **≈ 99 extraction LLM calls per document**
  (6,624 receipts / 67 docs). EXTRAPOLATION, medium confidence: the 11-blob set ≈ 1,000 extraction calls, about an hour;
  the 117-document library ≈ 11,000–12,000 extraction calls plus profile / pMAP / summary calls. Never measured on this
  material.

## 5. The blocker: finish-line Item 2, sub-item D (OPEN, deferred by sequencing, not fixed)
`shared/polymath_shared/document_profile/profile_atom_projection.py:146-159` —
`search_atoms(client, collection, query_vec, kinds, k=12)` filters on `atom_kind` ONLY. All corpora share ONE atom
collection (`polymath_document_profile_atoms_embed_e794ec4cab197a3f`); the payload already carries `corpus_id`
(`:45-46`), and `projected_count` / `purge` in the same file already build `corpus_id` filters — so no backfill is
needed, only the contract change CONTINUITY already prescribes: `search_atoms(…, corpus_ids=[…], …)`, not a post-filter.
Five unscoped callers: `orchestrator/orchestrator/api/ui.py:1723`, `:2022` (inside `_add_corpus_explore_expansion`);
`orchestrator/orchestrator/api/chat_retrieval.py:329`, `:385`, `:848`. Invisible today because `cinema` is alone; the
moment a second corpus exists, Corpus Explore can ground a subquery in the wrong corpus.

## 6. Prep list (in order)
1. **Item 2 / D** — corpus-scope `search_atoms` and its five callers, with a two-corpus isolation test. Needs the
   owner's word (it touches `shared/` + the orchestrator → one bounce).
2. **Owner decision: 10 documents or 117.** The skill's calibration receipts assume the ten-document corpus; the full
   library changes every historical baseline. Pick ONE source copy, never both (10 of 11 are byte-identical across them).
3. Drop the superseded "Alchemy (Sutherland)" twin; keep "Always Alchemy (Hart)" (identical bodies trip the containment
   guard).
4. **Ontology profile**: `cinema` runs `facs_body` (facial-action / movement labels) — wrong for commerce. Choose or
   compose a commerce-appropriate module under `config/ontology/` before the first ingest.
5. Only if the transcript batches come along: strip the per-line `**[m:ss]**` markers first (they fragment chunks). The
   books are clean (no scraped HTML, no foreign scripts).
6. Stage it (owner spend rule): 3–5 books into a probe corpus first, read the `extraction_call_receipts` /
   `llm_provider_attempts` deltas, then decide the rest.

## 7. Unknowns
- The real call / dollar cost on this material (extrapolated from `cinema` only) → the staged probe in 6.6 answers it.
- Whether the binary originals on the Windows drive are still reachable → only matters if v4 should re-parse epub / pdf
  itself instead of trusting the earlier conversion.
- The contents of the v3.3 Mongo / Qdrant volumes → not worth opening; the source bytes make them redundant.

## Disclosure
The pass was read-only with one deviation: to size a Docker volume (macOS hides volume mount points inside the Docker VM)
the sub-agent ran a throwaway `docker run --rm alpine du -sh` with the old Mongo volume mounted `:ro`. It started and
removed a scratch container, touched no Polymath service and wrote nothing. No credential was read or printed.

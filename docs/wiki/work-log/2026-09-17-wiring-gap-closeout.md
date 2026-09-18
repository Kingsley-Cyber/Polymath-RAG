---
title: "WORK LOG — wiring-gap close-out (gold parent, 290 maps, slice G, vNext pin)"
change_id: PMAP-ABSTRACT-QUERY-WIRING-GAP
date: 2026-09-17
owner: orchestrator
last_reviewed: 2026-09-17
status: complete
architecture_impact: "Append-only close of the 2026-09-17 wiring-gap audit. No rewrite of the original dualread:0 receipt. Projects 290 already-compiled cinema parent maps into Qdrant (local embedder, no Groq, no cinema remint). Compiles the missing document summary if the hole is a missing PG row. Turns on new-upload pMAP with POLYMATH_DOC_PARENT_MAP_SINCE (cinema untouched). Pins POLYMATH_DOC_PROFILE_VNEXT=0 so restored v3.2 profiles are not overwritten."
---

## Contract
Stamp the wiring-gap report with measured close-out without deleting the original 0-receipt; prove the Murch gold parent is among dual-read parents; close the named leftovers (290 unprojected maps, 1 missing doc summary, slice G new-ingest maps, vNext overwrite). Acceptance: dual-read receipt names gold parent `chunk_a9a6bf42…`; cinema active PG maps == Qdrant cinema points (or leftover diagnosed); `.env` has `POLYMATH_DOC_PARENT_MAP_ENABLED=1` + `POLYMATH_DOC_PARENT_MAP_SINCE` (ISO now) and `POLYMATH_DOC_PROFILE_VNEXT=0`; no Groq, no cinema pMAP remint.

## Changes
- Report + original work-log: append-only addendum (original §3 `dualread: 0` stays).
- Qdrant parent-map collection: upsert already-compiled maps whose PG rows had no point (parent_id match to current skeleton heading; alias drift ignored).
- Document-summary hole: diagnose 67 vs 66; persist+project only if a cinema doc lacks a `document_retrieval_summary`.
- `.env`: slice G since-guard; vNext off.
- Register 11.279–11.280. TREE: this work-log. Elite plan slice G marked executed.

## Proof
Gold parent (HYBRID Rule of Six, deterministic-template-v3, 2026-09-17 ~13:21Z):
- `lane_sizes.dualread=23`, `latent_rescue=18`, `document_summary=16`
- gold child `chunk_19e875c536…` `arrivals=['SHADOW_DUALREAD']`
- `chunks.parent_id=chunk_a9a6bf42…` (heading The Rule of Six)

290 maps: 7 cinema docs, 290 eligible body rows missing from Qdrant because stored `alias` ≠ current skeleton alias. Upsert by `parent_id` (local embedder, no purge). After: Qdrant cinema **11,993** = PG active **11,993**.

Document summary 67 vs 66: `Manga in Theory and Practice.md` (`doc_594d7f40…`) region_role toc=667 / legal / stub / front_matter / noise_ocr — 546 children all excluded; `_persist_retrieval_summaries` wrote `document: 0`. PG and Qdrant document summaries both 66.

`.env`: `POLYMATH_DOC_PARENT_MAP_ENABLED=1`, `POLYMATH_DOC_PARENT_MAP_SINCE=2026-09-17T13:24:27Z`, `POLYMATH_DOC_PROFILE_VNEXT=0`.

Fleet bounce 2026-09-17T13:27:01Z (`scripts/boot_polymath.sh`, no AUTOPILOT — matching the prior supervisor). Live `control.main` pid 4282 / `profile_worker` 4284 / `doc_parent_map_stage_worker` 4302 carry `ENABLED=1`, `SINCE=2026-09-17T13:24:27Z`, `VNEXT=0`, and `POLYMATH_DOC_PARENT_MAP_CORPUS` unset. Pre-bounce those processes had `VNEXT=1` and no parent-map flags.

Cinema after ≥1 control tick: 48 `doc_parent_map` tickets still `done`, `updated_at` max still `2026-09-13 17:27:05Z` (0 changed/new/gone). PG maps 11,993 (max `created_at` still 2026-09-13). Qdrant cinema 11,993. Murch profile `prompt_version=doc-profile-v3.2`. 0 runs with `created_at` after `SINCE`. 0 stranded `ready`/`failed` pMAP tickets (the stranded rescue has no SINCE filter in SQL; it did not fire).

Guards: `repo_guard` + `wiki_worm --check` after TREE/register.

Post-bounce HYBRID Rule of Six (same query, 13:28Z): `dualread=24`, `latent_rescue=18`; gold child still in payload with `SHADOW_DUALREAD`; `chunks.parent_id` still `chunk_a9a6bf42…`.

## Rejected claims
- Rewriting the original audit so `dualread: 0` disappears.
- Cinema pMAP LLM backfill / Groq spend.
- Purging existing parent-map points (canary purge/rebuild is not this close-out).
- Inventing a document summary for a toc-only book.

## Open contract gaps
- Slice G live mint is proven on the next upload created after `SINCE`, not on cinema (0 such runs exist today).
- Residual (not fired): `auto_map_parents_on_chunks` stranded rescue does not add `r.created_at > SINCE`; only corpus-scope. Today 0 stranded tickets and cinema pMAP is all `done`, so the bounce did not remint. A later `ready`/`failed` cinema ticket with a consumed event would re-arm without a code change.

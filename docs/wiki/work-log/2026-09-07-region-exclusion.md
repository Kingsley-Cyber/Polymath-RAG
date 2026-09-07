---
title: "WORK LOG — REGION-EXCLUSION-V1: noisy regions leave the union; the title ranker gets the passages' own vote; what the section summaries are worth"
change_id: REGION-EXCLUSION-V1
date: 2026-09-07
owner: governance (owner report 2026-09-07: "Timing for Animation › Table of Contents … this looks like junk that made it"; "inspect the section summaries … does it add real value?")
last_reviewed: 2026-09-07
last_touched: 2026-09-07
status: complete
register: 11.123
package: shared/polymath_shared/candidate_engine.py (union exclusion by region role, `toc_links` pattern), shared/polymath_shared/document_region.py (noise_ocr alias), shared/polymath_shared/compiler_context.py + orchestrator/orchestrator/api/ui.py (child lane in the title ranker), tests (candidate engine, document region, compiler context), docs/wiki/experiments/chat-m-replay-region-excl-{B,L}.{json,md}
architecture_impact: "At the union, a candidate whose materializer region role is noisy (front matter, marketing, table of contents, index, bibliography, OCR noise — now including the chunker's `noise_ocr` spelling) is dropped and receipted (`noise_reasons` `region:<role>`), exactly as B8's lexical index-page filter drops its matches; before, noisy roles were only sunk to the end of the fused list, and the document-fair judged prefix then handed a document whose only candidate was its contents page a seat anyway. Document-metadata questions keep the old behaviour (demotion lifted, nothing dropped). The lexical filter also recognises a Markdown table of contents (chapter-file links). The compiler's title ranker (B16) fuses a third lane, the child passages' own vote, so it no longer depends on section summaries existing. No ingestion change; the roles were already on every cinema child."
---

# WORK LOG — REGION-EXCLUSION-V1

## Contract

A table of contents, an index page or front matter never becomes cited evidence for a subject question, whatever the judge's state; a question about the document itself can still reach them. The title ranker ranks the library from what the library says, summaries or not.

## Changes

- `candidate_engine.py`: in the union filter, `structural_noise_reason(text) or "region:<role>"` when `budget.demote_noisy_regions` is on and the candidate's `region_role` is noisy; receipted through the existing `noise_dropped` / `noise_reasons` / `noise_sample`. `_TOC_LINK_RE` + reason `toc_links` (≥ 6 chapter-file links at ≥ 1 per 120 chars). `_sink_noisy` stays (it still orders the lanes' own lists).
- `document_region.py`: `ROLE_NOISE_OCR_ALIAS = "noise_ocr"` in `NOISY_ROLES` — the chunker's `region_role.py` spells OCR noise that way; 121 cinema children carried it and were never demoted.
- `compiler_context.rank_documents(..., child_rows=)` third lane (`routing_child`); `ui._compiler_titles` runs the child search beside the section and document searches (dense or sparse), same limit as sections.
- Tests: the provenance test now pins exclusion + receipt (`region:front_matter`); new `test_document_metadata_questions_keep_noisy_regions_in_the_union`; `toc_links` on the exact shape that reached S1 and a prose-with-one-link negative; `noise_ocr` alias; three-lane title ranking.

## Proof

**The junk, traced (owner's stick-figure CREATE turn, 05:05Z, HYBRID):** S1 was `Timing for Animation › Contents › Table of Contents`, 483 words of `1. [Cover](01_Cover.xhtml) … 11. [Timing for Broadcast Media](11_Chapter01.xhtml#Chapter01) …`, `region_role = toc`, `region_reason = heading:toc` — correctly labelled by the materializer. Why it still landed: (1) noisy roles were demoted, not excluded — sunk to the end of the fused list; (2) the document-fair judged prefix (B11) takes each surfaced document's best fused candidate, and this chunk was Timing for Animation's ONLY candidate, so it took the document's seat regardless of position; (3) the turn's judge missed its 8 s deadline (`rerank_timeout`, enrichment load), so the fusion order stood and the composer's diversity seat put the document's one candidate first; (4) B8's lexical filter did not match — its pattern is page-number links (`[837](…#p837)`), this is a chapter-file link list. `is_document_metadata_query` was False for the request. Corpus-wide: 1,189 `toc` children (Save the Cat 584, Manga in Theory and Practice 538, the rest small), 192 `index`, 361 `bibliography`, 70 `front_matter`, 121 `noise_ocr` (never demoted until now); no frozen-fixture gold chunk carries a noisy role (119 / 119 `body`).

After the change the same text is dropped at the union with reason `toc_links` and, for any role-labelled chunk, `region:toc`; the unit suite pins both and the metadata-question exemption.

**Recall gate (frozen plans, first 10, HYBRID, in-process on the patched engine — `chat-m-replay-region-excl-{B,L}`):**

| fixture / metric | before (B13 recording) | after exclusion | floor |
|---|---|---|---|
| B gold-in-union / in judged | 0.7 / 0.6 | 0.7 / 0.6 | ≥ 0.85 (30-plan recording; equal on this subset) |
| B hit@10 / MRR / survival | 0.6 / 0.417 / 0.857 | 0.6 / 0.417 / 0.857 | ≥ 0.60 / ≥ 0.45 (30-plan) |
| B documents judged / final (p50) | 10.5 / 5.5 | 10 / 5 | — |
| L gold-in-union / in judged | 1.0 / 1.0 | 1.0 / 0.9 | ≥ 0.95 |
| L hit@10 / MRR / survival | 0.9 / 0.775 / 1.0 | 0.9 / **0.825** / 0.9 | ≥ 0.90 / ≥ 0.80 |
| L documents judged / final (p50) | 32 / 15 | 32 / 15 | — |

Reading: B is identical turn for turn. On L two turns changed hands — "HD1" gained its hit@10, "AU62" lost its gold from the judged set (documents judged 29 → 31 on that turn: with the noise gone, two more documents entered the 32 fair seats and displaced it — B11's known survival cost, not the exclusion itself) — so hit@10 is unchanged at 0.9, MRR rose 0.775 → 0.825, survival-given-union 1.0 → 0.9. Every recorded floor holds. Gate MET.

**Section summaries — what they are worth (owner's question):** 11,638 active `section_retrieval_summary` rows for cinema (plus 18,907 inactive superseded variants kept in the table, 1.6 × the live set), median 526 characters ≈ 90 words against sections of 487 words. Quality, measured on 11,616 summaries joined to body parents: 69 % of a summary's content words occur in its section (median; the rest is paraphrase), the summary names 6 of its section's 10 most distinctive words (median), and 0 of 11,616 open with boilerplate — they are structured ("SUMMARY: … RELATIONSHIPS: … KEY CONCEPTS: …") and specific (the FACS and Screen Combat examples are faithful). Their failures are the source's: a mis-parsed PDF ("Framed Environment Design" is OCR of a civil-engineering microcomputer paper) yields a garbage summary of garbage text. Value in chat, measured across the week: B10 — recall identical with the summary-routed lane off; B13 — recall identical with the document-summary vote off; B11 — summary rows in the prompt were cited 0 times in a day; B16 — the section-summary vector index was the title ranker's input, and this item shows the child passages rank the library as well (16 / 20 overlap on the top 20 for the punch and stick questions; children found the Laban Workbook for the punch question when the summary route did not). Conclusion: the summaries are well made and, in chat, unnecessary — every job they had is done as well by the passages. They remain the input of /retrieve's Tier-0 routing and the corpus map, and producing them is enrichment spend (owner's ledger, §3.23).

## Rejected claims

- "Demote harder" — no: any demotion is undone by the document-fair prefix when a document has a single candidate; the fix is exclusion for subject questions, with the metadata exemption that already existed.
- "Fix the chunker's role spelling" — not here: the writer is ingestion (§3.23); the reader accepts both spellings, which covers every existing row.
- "Replace section summaries with parent text in the routing index" — not needed for chat: parents are not embedded, and the child vote already does the routing job as well; whether to keep producing summaries for /retrieve and the corpus map is the owner's decision.

## Open contract gaps

- The exclusion is by role and by the two lexical shapes; a contents page in a format the materializer does not label and the patterns do not match can still surface (the B8 filter's original gap, narrowed).
- `stub` (5,367 children, fragments of 25–50 words) is not noisy and stays; whether tiny fragments should compete is the chunk-size question (EVIDENCE-WINDOW / re-chunk), not this item.
- The 18,907 inactive summary rows are storage; pruning them is a summary-layer decision.
- The live stick-figure turn was not re-run (the owner is testing by hand; no respawn) — the running orchestrator gets this change at the next respawn.

---
title: "WORK LOG — B2: the Sound Design duplicate removed from cinema through the documents API"
change_id: BACKLOG-B2
date: 2026-09-06
owner: governance (owner backlog B2, released 2026-09-06 with the backlog execution order)
last_reviewed: 2026-09-06
last_touched: 2026-09-06
status: complete
register: 11.111
package: data only — corpus `cinema` (documents, chunks, Qdrant points, derived rows); no code
architecture_impact: "None to code. One of two near-identical copies of Sound Design (1,067,157 vs 1,067,149 bytes, 255 sections each, both layers of the duplicate guard blind to an 8-byte difference) was removed with the existing DOCUMENT-DELETE-V1 endpoint (typed confirmation = the file name), which removes the document and everything derived from it in one transaction and receipts every table it touched. The corpus is 67 documents; the surviving copy is untouched; nothing was re-ingested. The systemic fix (near-duplicate containment at intake) remains B1."
---

# WORK LOG — B2

## Contract

Remove the "(1)" copy and nothing else, through the API (never by hand in the stores), with the endpoint's own receipt as proof; the surviving copy keeps every section and chunk.

## Changes

`DELETE /documents/doc_776b4348…?confirm=<file name>` on the orchestrator (40 s). Receipt: chunks 1,975, Qdrant points 2,682, evidence 1,061, orphan facts 987 (facts evidenced only by this copy), mentions 3,753, parent enrichments 255, parent summaries 255, retrieval summaries 707, projection attempts 30,793, extraction call receipts 240, runs 1, documents 1; `projection_receipts` and `document_summaries` reported `skipped` (optional tables the endpoint tolerates).

## Proof

- Before: 68 documents in `cinema`; both copies 255 sections / 1,975 chunks each.
- After: 67 documents (DB and the `/corpora` card, `query_ready: true`); the deleted doc has 0 document rows, 0 chunks; the surviving copy ("… Cinema.md") still has 255 sections and 1,975 chunks.
- No ingest run was created (the delete removes the copy's run so the bytes stay re-ingestable; nothing was re-submitted).

## Rejected claims

- "Delete by hand in Postgres / Qdrant" — rejected: the endpoint is the only path that removes the derived rows, points and orphan facts together and leaves a receipt.
- "Keep both until B1 lands" — rejected by the owner's order; B1 is the guard for the next twin, not a reason to keep this one.

## Open contract gaps

- Facts evidenced only by the removed copy (987) are gone; the surviving copy's own facts stand. If any answer relied on a fact whose sole evidence was the "(1)" copy, the surviving copy's identical text re-derives it on the next enrichment pass.

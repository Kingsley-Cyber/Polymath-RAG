---
change_id: STAGE-K-PILOT-RELEASE-BOOKS
owner: governance
date: 2026-08-25
status: implemented
architecture_impact: none (measurement + report)
last_reviewed: 2026-08-29
---

# STAGE-K PILOT — release-books-v1 (2026-08-25)

## Contract

Qualify the real corpus end-to-end under the G1 neural default:
inventory, summary completion, artifact lanes, /ask grounding, dense
and graph retrieval, latency. Measurement slice; no runtime changes.

## Changes

1. Inventory measured: 25 docs · 15,205 children · 3,811 parents ·
   3,596 section summaries · 22/25 doc summaries · 7,934 facts ·
   0 procedures/concepts.
2. Root-caused gaps: doc-summary holes = pre-summaries-worker runs;
   zero artifacts = corpus predates migration 0033 lanes.
3. **Product finding**: /ask no-corpus fallback returns TEST-corpus
   artifacts (p1-genre-probe) with grounded=True — provenance vs scope
   decision recorded for owner, not patched unilaterally.

## Proof

eval/v5/retrieval/STAGE-K-PILOT-RELEASE-BOOKS.md (tables above);
live /ask transcripts with latencies; fence PASS 13/13 at a1076f4.

## Rejected claims

- NOT claiming pilot "complete" — pipeline qualifies; two product
  decisions and one fresh-ingest validation remain.
- NOT re-extracting the frozen 25-book corpus overnight.

## Open contract gaps

§2.1 redrive of 3 legacy doc summaries · §2.2 artifact-lane validation
on next fresh ingest · §2.3 /ask scoping decision.

---
title: "WORK LOG — ENRICHMENT-ROW-TRUTH-V2: an enrichment row is proof only while its parent chunk exists; orphans are replaced, never reused; sweeps stop writing into deleted documents"
change_id: ENRICHMENT-ROW-TRUTH-V2
date: 2026-09-05
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.83
package: workers/workers/summary_worker_impl.py, shared/polymath_shared/latent/runtime.py
architecture_impact: "Enrichment done-ness and identity reuse now require the row's parent chunk to exist: `_enrichment_row_done` (READY or terminal-INVALID on a LIVE parent; summary_jobs state is never proof), `persist_compiled_parent` deletes an orphan row under the same input_hash instead of answering EXISTING and re-points the row on an INVALID→READY upgrade, and both persistence sites in the sweep skip a parent whose chunk is gone (ENRICH_PERSIST_SKIPPED_DOC_GONE). One-off cleanup removed 922 orphan rows across 64 documents. No schema change."
---

# WORK LOG — ENRICHMENT-ROW-TRUTH-V2

Owner (2026-09-05 15:55Z): "the file however hasn't begun enrichment, idk why, look into that."

## Contract

- **Law 1 — proof needs a live parent.** `_enrichment_row_done(conn, input_hash)` returns done only for a READY row, or an INVALID row of a class in `SEMANTIC_FAILOVER_INELIGIBLE`, whose `parent_id` exists in `chunks`. A `summary_jobs` COMPLETE state with no such row is not done (the job-state fallback is removed).
- **Law 2 — orphans give way.** `persist_compiled_parent` answers EXISTING only when the READY row's parent is alive; any row under the identity whose parent is gone is deleted first, so the new parent's row lands under the same `enrichment_id`. The INVALID→READY upgrade now also sets `parent_id`, `doc_id`, `corpus_id`, `source_child_ids` from the parent that produced it.
- **Law 3 — never write into a deleted document.** Both sweep persistence sites check `_parent_alive` inside their committed transaction and skip with `ENRICH_PERSIST_SKIPPED_DOC_GONE` when the chunk is gone.

## Why (measured)

- handbook.html was deleted and re-uploaded at 15:47–15:49Z while `summaries-3479` still held the previous ingest's parents in memory. At 15:52:34Z it persisted 184 rows (103 READY, 81 terminal) against chunk ids that no longer existed. `/status` and `/documents` reported "enriched 103 / failed 81" for a document whose first real enrichment call came at 15:53:50Z when `summaries-27327` claimed the run's ticket. Corpus-wide there were 922 such orphan rows across 64 documents from earlier deletes and re-ingests.
- Identity reuse made the orphans harmful, not just confusing: a new parent with identical children gets the same `input_hash`, `persist_compiled_parent` answered EXISTING against the orphan, and `_enrichment_done` skipped it — the new parent would never own a row and its gists pointed at dead child ids, unreachable by projection.
- Why the ticket sat READY for four minutes: both summaries workers were mid-ticket on other runs (a parent_summary and a parent_enrichment sweep); the handbook's own ticket was claimed as soon as one freed. Not a defect.

## Changes

- `workers/workers/summary_worker_impl.py`: `_enrichment_row_done`, `_parent_alive`; `_do_enrichment` uses them for done-checks and guards both `_ptx()` persistence sites.
- `shared/polymath_shared/latent/runtime.py`: orphan-aware EXISTING check + orphan delete; ON CONFLICT upgrades re-point the row.
- `tests/determinism/test_enrichment_row_truth.py`: 5 real-Postgres tests (rolled back): READY on live parent done / on dead parent not; job state alone never proof; terminal INVALID only on a live parent; persist replaces an orphan and then answers EXISTING; both persistence sites guard and the job fallback is gone.
- One-off cleanup (2026-09-05 15:58Z, pinned by `enrichment_id` of rows whose parent chunk did not exist): 922 rows deleted, 0 remain. Their Qdrant latent points, if any, are the `purge_orphan_projections.py` job's business.

## Proof

- Tests above green; sweep-serialization, microbatch and identity test files green alongside.
- Live after cleanup: handbook.html 235 READY rows, all on live parents, ticket leased by `summaries-27327`; extraction 202 calls / 7,336 accepted items and climbing.

## Rejected claims

- "Re-point the orphan row to the new parent to save the call." Rejected: gists are keyed by real child chunk ids and the children changed with the chunk contract; a re-pointed row would carry dead gist targets.
- "Make the delete endpoint wait for sweeps." Rejected: a corpus sweep can run for an hour; the delete already supersedes the document's own tickets, and a peer's sweep cannot be told apart from live work without the per-parent guard.

## Open contract gaps

- A FOREIGN KEY `parent_enrichments.parent_id → chunks(chunk_id) ON DELETE CASCADE` would make orphans impossible at the store; deferred because the delete endpoint removes rows by document in a specific order and the migration needs a drift check against CI's fresh schema.
- `summary_jobs` rows for deleted documents are left in place (harmless under Law 1).

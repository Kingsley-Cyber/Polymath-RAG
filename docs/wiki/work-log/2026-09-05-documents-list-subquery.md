---
title: "WORK LOG — DOCUMENTS-LIST-SUBQUERY-V1: GET /documents cross-joined chunks with enrichments (80 s, Files view empty)"
change_id: DOCUMENTS-LIST-SUBQUERY-V1
date: 2026-09-05
owner: governance
last_reviewed: 2026-09-05
last_touched: 2026-09-05
status: shipped
register: 11.77
package: orchestrator/orchestrator/api/ui.py
architecture_impact: "read-path only: the per-corpus document listing computes its per-document counts with correlated subqueries on the (doc_id) indexes instead of a chunks × parent_enrichments join. Same response shape, same numbers. No schema or contract change."
---

# WORK LOG — DOCUMENTS-LIST-SUBQUERY-V1

Owner (2026-09-05, during the 63-document `cinema` ingest): "in the front end I don't see any files."

## Contract

`GET /documents?corpus_id=…` returns the same fields as before (`doc_id, source_name, media_type, bytes, created_at, chunks, parents, enriched, enrich_failed` + recent runs) and must complete in seconds on a corpus of ~80k chunks: every per-document count is a correlated subquery that walks `chunks(doc_id, …)` or `parent_enrichments(doc_id)` for that document only.

## Why

The previous statement `LEFT JOIN chunks c … LEFT JOIN parent_enrichments pe … GROUP BY d.doc_id` with `COUNT(DISTINCT …) FILTER` materialised chunks × enrichments rows per document. Measured 2026-09-05 on `cinema` (67 documents, 79,787 chunks, 1,968 READY enrichments): 79.7 s per request; the Files view fetch never returned, so the corpus looked empty while every document was in fact chunked and extracting. The same endpoint took 48.6 s on `ecom-meta-v1` earlier the same day, which had been mistaken for normal. It passed at small scale because a 1,500-chunk corpus keeps the cross product small.

## Changes

- `orchestrator/orchestrator/api/ui.py::documents` — correlated subqueries; comment records the measurement.
- `tests/determinism/test_documents_list_query.py` — (1) structural: the endpoint source contains no `LEFT JOIN chunks … / LEFT JOIN parent_enrichments …` and uses the subquery form; (2) on the dev store: the subquery form finishes under 5 s on the most-chunked corpus and its numbers equal the old aggregate on a bounded sample (skips without Postgres).
- TREE rows; register 11.77.

## Proof

- Prototype against the dev DB before patching: old form 79.7 s (endpoint), new form 24.7 ms (psql `\timing`), identical row count (67).
- Regression: 2 passed locally in the project venv.
- Live after restarting only the orchestrator under the supervisor: `GET /documents?corpus_id=cinema` 1.9 s locally (67 documents, all with chunks), 1.3 s through `rag.kingsleylab.xyz`, `/ui/` 200.
- Operational note: `kill -TERM` of the uvicorn process left it in a graceful-shutdown limbo (alive, port closed, health 000) that the supervisor did not treat as an exit; `kill -9` produced the respawn in 2 s. Recorded, not changed here.

## Rejected claims

- "The UI has a bug" — rejected: the fetch was correct; the backend never answered within any reasonable client timeout.
- "Add caching" — rejected: the query was pathological, not merely expensive; the correct query needs no cache.

## Open contract gaps

- Bulk ingest of one corpus is embedder-bound (~7 texts/s on the local MLX sidecar, measured optimum at batch 16) and the vector-projection stage projects the CORPUS backlog under whichever run's ticket comes first (chunk and latent selection join `runs.corpus_id`), so the first `query_ready` after a 63-document upload waits for most of the corpus to embed (~3 h for 80k chunks). A second projection worker does not help (the sidecar serialises; measured 89 vs 6 embed calls in 3 min) — an untested `qdrant2` slot was tried and reverted. Throughput needs embedder capacity (the RTX lane), not more pollers.
- Graceful-shutdown limbo of uvicorn under SIGTERM: the supervisor should treat "alive but readiness failing for N probes" as dead sooner (it does, at 5 × 120 s).

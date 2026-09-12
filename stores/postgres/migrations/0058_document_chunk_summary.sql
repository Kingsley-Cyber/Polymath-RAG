-- DOCUMENT-CHUNK-SUMMARY-V1 (execution authority follow-up to §20A, 2026-09-12)
--
-- Root cause, measured with EXPLAIN (ANALYZE, BUFFERS): document_status.py's
-- corpus_document_summaries() computes per-document child/parent/map-eligible
-- counts with `SELECT doc_id, tier, COUNT(*) FROM chunks WHERE doc_id = ANY(%s)
-- GROUP BY 1,2` and a sibling query for map-eligible parents. On `cinema` (the
-- largest corpus) these cost ~100ms + ~47ms per call: `chunks` has 96,391 rows and
-- cinema's 67 documents own 84,152 of them (87% of the whole table), so the planner
-- correctly chooses a sequential scan over the existing `chunks_doc_idx` — this is
-- NOT a TOAST/JSONB issue (already fixed separately by 11.214) and NOT a missing-
-- index bug; it is proportional to raw chunk volume and gets worse as a corpus grows.
--
-- This is an additive, one-row-per-document summary maintained at the SAME write
-- time as the chunks themselves (intake_worker.py already computes `children`/
-- `parents` Python-side immediately after inserting chunks, for the routing_card
-- artifact) — no new query against `chunks` is needed to populate it. `ON DELETE
-- CASCADE` on `doc_id` means every existing chunks/document deletion path already
-- cleans this up for free — the same convention `chunks.doc_id` itself already uses.
CREATE TABLE IF NOT EXISTS document_chunk_summary (
    doc_id              TEXT PRIMARY KEY REFERENCES documents(doc_id) ON DELETE CASCADE,
    corpus_id           TEXT NOT NULL,
    child_count         INT NOT NULL DEFAULT 0,
    parent_count        INT NOT NULL DEFAULT 0,
    map_eligible_count  INT NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS document_chunk_summary_corpus_idx
    ON document_chunk_summary (corpus_id);

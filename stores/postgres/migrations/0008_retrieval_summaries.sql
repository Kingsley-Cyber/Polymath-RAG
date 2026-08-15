-- 0008_retrieval_summaries.sql
-- R1A substrate: canonical deterministic retrieval summaries.
--
-- One authoritative DOCUMENT_RETRIEVAL_SUMMARY per document and one
-- SECTION_RETRIEVAL_SUMMARY per parent/section (contract
-- retrieval-summary-v2). Summaries are ROUTING representations, never
-- exact factual-support authority (child chunks remain the exact
-- evidence). Content-derived identity (no wall-clock metadata) and
-- complete source provenance (selected sentences -> parent/chunk).

BEGIN;

CREATE TABLE IF NOT EXISTS retrieval_summaries (
    summary_id   TEXT PRIMARY KEY,
    kind         TEXT NOT NULL CHECK (kind IN ('document_retrieval_summary', 'section_retrieval_summary')),
    contract     TEXT NOT NULL,
    corpus_id    TEXT NOT NULL,
    doc_id       TEXT NOT NULL,
    parent_id    TEXT,
    summary_text TEXT NOT NULL,
    provenance   JSONB NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS retrieval_summaries_doc_idx ON retrieval_summaries (doc_id);
CREATE INDEX IF NOT EXISTS retrieval_summaries_parent_idx ON retrieval_summaries (parent_id);

COMMIT;

-- 0018: V5 L2 — SPAN HYPOTHESES (rescue as hypothesis, never mutation).
--
-- Every rescue decision becomes an attributable record. The ACTIVE working
-- set keeps V4-effective semantics during migration (R5): a refused
-- boundary widening still removes the source span from argument binding,
-- but that removal is now RECORDED as SUPPRESSED_SOURCE with full evidence,
-- and the raw observation survives in L1 (0017) — destruction becomes
-- disposition. A future qualification gate may change which preserved
-- evidence becomes ACTIVE; this migration must not.

CREATE TABLE IF NOT EXISTS span_hypotheses (
    hypothesis_id      TEXT PRIMARY KEY,     -- content-addressed
    doc_id             TEXT NOT NULL,
    chunk_id           TEXT NOT NULL,
    mechanism          TEXT NOT NULL,        -- boundary_widening | missing_argument | type_reconciliation
    source_char_start  INTEGER,              -- NULL for missing_argument (no source span)
    source_char_end    INTEGER,
    source_surface     TEXT,
    proposed_char_start INTEGER NOT NULL,
    proposed_char_end   INTEGER NOT NULL,
    proposed_surface    TEXT NOT NULL,
    status             TEXT NOT NULL,        -- ACCEPTED | REJECTED
    disposition        TEXT NOT NULL,        -- SUPERSEDED_SOURCE | SUPPRESSED_SOURCE | ADDED | NO_CHANGE
    evidence           JSONB NOT NULL,       -- query identity/labels + outcome detail
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS span_hypotheses_doc_idx ON span_hypotheses(doc_id, chunk_id);
CREATE INDEX IF NOT EXISTS span_hypotheses_source_idx
    ON span_hypotheses(doc_id, chunk_id, source_char_start, source_char_end);

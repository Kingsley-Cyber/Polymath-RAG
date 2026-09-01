-- EXTRACTION-THROUGHPUT-V2: per-batch call receipts. A failed extract
-- stage used to discard EVERY completed cloud call for the document
-- (measured 2026-09-01: 233s of spend re-bought per retry). Receipts
-- are content-addressed by (contract identity, batch content); a
-- retry replays cached raw responses through the same sanitize path
-- and pays only for the calls it never made. Raw model output only —
-- never evidence; the gate re-runs on every replay.
CREATE TABLE IF NOT EXISTS extraction_call_receipts (
    receipt_id   TEXT PRIMARY KEY,          -- ecr_<content hash>
    doc_id       TEXT NOT NULL,
    lane         TEXT NOT NULL,
    model        TEXT NOT NULL,
    raw_text     TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS extraction_call_receipts_doc
    ON extraction_call_receipts (doc_id);

-- 0014: extraction-observability-v1 trace storage.
-- Deterministic event identity (content hash): one trace event can
-- never overwrite another. Disposable/diagnostic — semantic outputs
-- remain in the authoritative tables.

CREATE TABLE IF NOT EXISTS extraction_trace_events (
    trace_event_id TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL,
    doc_id         TEXT,
    chunk_id       TEXT,
    sentence_id    TEXT,
    event_type     TEXT NOT NULL,
    decision       TEXT NOT NULL,
    reason_code    TEXT NOT NULL,
    surface        TEXT,
    char_start     INTEGER,
    char_end       INTEGER,
    envelope       JSONB NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS extraction_trace_run_idx ON extraction_trace_events (run_id, event_type);
CREATE INDEX IF NOT EXISTS extraction_trace_sentence_idx ON extraction_trace_events (sentence_id);
CREATE INDEX IF NOT EXISTS extraction_trace_surface_idx ON extraction_trace_events (surface);

-- 0027: SUMMARY RUNTIME D7-H1/H9 — scheduler identity + indexes.
--
-- Monotonic scheduling identity: ticket_id is a content hash (not
-- monotonic), so advancement needs a BIGINT sequence for keyset
-- paging. Backfilled for existing rows; new rows inherit automatically.
-- Indexes serve the eligible-work-set scan and worker/retry lookups at
-- 1M-ticket scale.

ALTER TABLE stage_tickets ADD COLUMN IF NOT EXISTS seq BIGSERIAL;

CREATE INDEX IF NOT EXISTS idx_ready_stage_queue
    ON stage_tickets(stage, status, corpus_id, seq);
CREATE INDEX IF NOT EXISTS idx_retry_state
    ON stage_tickets(attempt, status);

CREATE TABLE IF NOT EXISTS scheduler_cursors (
    stage      TEXT NOT NULL,
    corpus_id  TEXT NOT NULL DEFAULT '*',
    last_seq   BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (stage, corpus_id)
);

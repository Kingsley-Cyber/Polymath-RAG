-- 0028: SUMMARY RUNTIME D7-5d — creation fairness + hysteresis state.
-- Corpus-level creation gating lives HERE (sticky), not in per-tick
-- threshold races: pause enters at >= watermark, resumes only at
-- <= watermark/2. Fair share = round-robin by last_creation_tick.

CREATE TABLE IF NOT EXISTS corpus_runtime_state (
    corpus_id            TEXT PRIMARY KEY,
    active_tickets       INTEGER NOT NULL DEFAULT 0,
    watermark            INTEGER NOT NULL DEFAULT 64,
    creation_paused      BOOLEAN NOT NULL DEFAULT FALSE,
    last_creation_tick   TIMESTAMPTZ,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

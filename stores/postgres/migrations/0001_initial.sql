-- 0001_initial.sql
-- The first migration creates the load-bearing tables for Polymath v4.
-- See ADR-0002 (Postgres over Mongo) and ADR-0004 (control plane as
-- a separate process that writes to control_heartbeats).

BEGIN;

CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    corpus_id     TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN
                    ('intake','reconciling','query_ready','degraded','failed')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS runs_corpus_status_idx
    ON runs (corpus_id, status);
CREATE INDEX IF NOT EXISTS runs_updated_at_idx
    ON runs (updated_at);

CREATE TABLE IF NOT EXISTS stage_attempts (
    run_id         TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    stage          TEXT NOT NULL,
    contract_hash  TEXT NOT NULL,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at   TIMESTAMPTZ,
    outcome        TEXT CHECK (outcome IN ('ok','failed','skipped')),
    error          TEXT,
    payload        JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (run_id, stage, contract_hash)
);

CREATE TABLE IF NOT EXISTS outbox (
    outbox_id    BIGSERIAL PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    enqueued_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload      JSONB NOT NULL,
    delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS outbox_pending_idx
    ON outbox (enqueued_at) WHERE delivered_at IS NULL;

CREATE TABLE IF NOT EXISTS control_heartbeats (
    control_id        TEXT NOT NULL,
    occurred_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_tick_ok      BOOLEAN NOT NULL,
    last_census_size  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS control_heartbeats_recent_idx
    ON control_heartbeats (control_id, occurred_at DESC);

-- The control plane NOTIFY channel. Postgres LISTEN/NOTIFY is the
-- cheap wakeup mechanism in ADR-0004.
NOTIFY control_tick;

COMMIT;

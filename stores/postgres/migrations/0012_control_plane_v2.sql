-- 0012: CONTROL-PLANE-V2 execution authority (ADR-0014).
-- stage_tickets: explicit handoff + ticket-scoped leases.
-- worker_registrations: identity/compatibility/health.
-- corpus_snapshots: evaluation barrier tokens.
-- runs.execution_contract: the pinned generation identity.

CREATE TABLE IF NOT EXISTS stage_tickets (
    ticket_id        TEXT PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    corpus_id        TEXT NOT NULL,
    stage            TEXT NOT NULL,
    event_type       TEXT NOT NULL,
    generation       INTEGER NOT NULL DEFAULT 1,
    required_artifacts JSONB NOT NULL DEFAULT '[]',
    required_receipts JSONB NOT NULL DEFAULT '[]',
    repair_objects   JSONB NOT NULL DEFAULT '[]',
    attempt          INTEGER NOT NULL DEFAULT 0,
    lease_owner      TEXT,
    lease_expires_at TIMESTAMPTZ,
    status           TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'ready', 'leased', 'done', 'failed', 'repair')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS stage_tickets_stage_status_idx
    ON stage_tickets (stage, status);
CREATE INDEX IF NOT EXISTS stage_tickets_corpus_idx
    ON stage_tickets (corpus_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS stage_tickets_run_stage_gen_idx
    ON stage_tickets (run_id, stage, generation);

CREATE TABLE IF NOT EXISTS worker_registrations (
    worker_id       TEXT PRIMARY KEY,
    worker_type     TEXT NOT NULL,
    pid             INTEGER NOT NULL,
    host            TEXT NOT NULL,
    build_sha       TEXT NOT NULL DEFAULT '',
    contracts       JSONB NOT NULL DEFAULT '{}',
    current_ticket  TEXT,
    processed_count INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    status          TEXT NOT NULL DEFAULT 'healthy'
        CHECK (status IN ('healthy', 'stale', 'quarantined', 'draining')),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    heartbeat_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS worker_registrations_type_idx
    ON worker_registrations (worker_type, status);

CREATE TABLE IF NOT EXISTS corpus_snapshots (
    snapshot_id  TEXT PRIMARY KEY,
    corpus_id    TEXT NOT NULL,
    generation   INTEGER NOT NULL,
    state_hash   TEXT NOT NULL,
    valid        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    invalidated_at TIMESTAMPTZ,
    invalid_reason TEXT
);
CREATE INDEX IF NOT EXISTS corpus_snapshots_corpus_idx
    ON corpus_snapshots (corpus_id, generation, valid);

ALTER TABLE runs ADD COLUMN IF NOT EXISTS execution_contract JSONB
    NOT NULL DEFAULT '{}';

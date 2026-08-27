-- DEAD-LETTER-ARCHIVE-V1
-- Health baselines must evaluate CURRENT system state. Historical,
-- classified-invalid probes are archived with an explicit reason and
-- excluded from dead-letter health -- never silently purged, never
-- counted as live regressions.

CREATE TABLE IF NOT EXISTS dead_letter_archive (
    ticket_id        text PRIMARY KEY,
    run_id           text NOT NULL DEFAULT '',
    stage            text NOT NULL DEFAULT '',
    reason           text NOT NULL,
    excluded_from_health boolean NOT NULL DEFAULT true,
    payload_snapshot jsonb NOT NULL DEFAULT '{}',
    original_updated_at timestamptz,
    archived_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE stage_tickets
    ADD COLUMN IF NOT EXISTS archived_at timestamptz,
    ADD COLUMN IF NOT EXISTS archived_reason text;

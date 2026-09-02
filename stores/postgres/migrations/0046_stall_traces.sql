-- STALL-TRACER-V1 (2026-09-02): one row per stall episode. A unit of work
-- (stage ticket, run, summary job) that has not advanced for the control
-- plane's stall threshold is traced every tick with a diagnosis naming
-- what it waits on; the row is resolved the first tick the unit moves.
-- Detection and evidence only — the tracer never mutates the unit.
CREATE TABLE IF NOT EXISTS stall_traces (
    unit_kind       text        NOT NULL,   -- ticket | run | summary_job
    unit_id         text        NOT NULL,
    stalled_since   timestamptz NOT NULL,   -- the unit's last state change
    run_id          text,
    stage           text,
    corpus_id       text,
    first_traced_at timestamptz NOT NULL DEFAULT now(),
    last_traced_at  timestamptz NOT NULL DEFAULT now(),
    age_s           integer     NOT NULL,
    diagnosis       text        NOT NULL,
    detail          jsonb       NOT NULL DEFAULT '{}'::jsonb,
    resolved_at     timestamptz,
    PRIMARY KEY (unit_kind, unit_id, stalled_since)
);

CREATE INDEX IF NOT EXISTS stall_traces_open_idx
    ON stall_traces (last_traced_at)
    WHERE resolved_at IS NULL;

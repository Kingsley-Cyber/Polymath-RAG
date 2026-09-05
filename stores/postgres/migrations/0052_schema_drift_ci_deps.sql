-- 0052 — SCHEMA-DRIFT (CI-DEPS-V1, 2026-09-05).
-- The first green-capable determinism CI (a fresh postgres:16 built from these
-- migrations) failed 10 stall-tracer tests with `column t.last_error_note does
-- not exist`. Diffing the migration-built schema against the dev database
-- showed three objects that existed only on the dev machine:
--   * stage_tickets.last_error_note — written by control/tickets.py,
--     control/process_supervisor.py and worker_runtime (_fail_ticket, reaper,
--     transient release) with NO migration anywhere: a fresh install broke on
--     the first failed ticket.
--   * runtime_signals and llm_providers — created lazily in code
--     (orchestrator main.py middleware, api/ui.py) with CREATE TABLE IF NOT
--     EXISTS; declared here too so a migrated database is complete before any
--     request arrives. Identical DDL, idempotent.
ALTER TABLE stage_tickets ADD COLUMN IF NOT EXISTS last_error_note TEXT;

CREATE TABLE IF NOT EXISTS runtime_signals (
    key        text PRIMARY KEY,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_providers (
    provider_id text PRIMARY KEY,
    provider    text NOT NULL,
    api_key     text NOT NULL DEFAULT '',
    api_base    text NOT NULL DEFAULT '',
    models      jsonb NOT NULL DEFAULT '[]',
    enabled     boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

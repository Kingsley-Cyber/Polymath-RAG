-- HARNESS-RESEARCH-MIGRATION-V1 R4 — 2026-09-14
-- `adapter_runs.outputs` is JSONB: Postgres does NOT preserve key insertion order, so "the newest step output carrying key X"
-- (the latest research directive, registry snapshot, harness receipt) cannot be derived from the outputs object once a run
-- round-trips through the store. `output_order` records the acceptance order of step ids (a JSONB ARRAY keeps order); a step
-- re-entered through a bounded loop moves to the end. Additive; rollback: ALTER TABLE adapter_runs DROP COLUMN output_order;
ALTER TABLE adapter_runs ADD COLUMN IF NOT EXISTS output_order JSONB NOT NULL DEFAULT '[]'::jsonb;

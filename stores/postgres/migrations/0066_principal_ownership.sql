-- HOSTED-MCP PRINCIPALS — 2026-09-21 (owner decision: docs/migration/OWNER_DECISION_2026-09-21_MERGE_AND_PRINCIPALS.md)
-- Security ownership lives WITH the state it owns — no second run_id -> principal store.
--   adapter_runs.owner_principal_id : the authenticated principal that started the run. NULL = legacy / trusted-local
--       ownership (Hermes on loopback, the UI, tests). NULL never means "open to every principal": a request made on
--       behalf of a principal reaches only rows whose owner equals that principal.
--   query_receipts.principal_id     : the principal a served query belongs to; `client` stays the SOFTWARE identity.
-- Additive, nullable, replay-safe. Rollback: ALTER TABLE adapter_runs DROP COLUMN owner_principal_id;
--                                            ALTER TABLE query_receipts DROP COLUMN principal_id;
ALTER TABLE adapter_runs   ADD COLUMN IF NOT EXISTS owner_principal_id TEXT NULL;
ALTER TABLE query_receipts ADD COLUMN IF NOT EXISTS principal_id       TEXT NULL;
CREATE INDEX IF NOT EXISTS adapter_runs_owner_principal_idx ON adapter_runs (owner_principal_id) WHERE owner_principal_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS query_receipts_principal_idx     ON query_receipts (principal_id, received_at DESC) WHERE principal_id IS NOT NULL;

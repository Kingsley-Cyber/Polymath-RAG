-- 0004_projection_claims.sql
-- Separate the immutable attempt log from the active claim:
--
--   projection_attempts  append-only history: "projection X committed at
--                        time T under contract C" — never deleted;
--   projection_receipts  the active claim: "X is currently believed
--                        present" — superseded (active=false), never
--                        erased.
--
-- VERIFY_PROJECTIONS invalidates claims when a store loses artifacts;
-- the historical commit trail survives. The census reads only ACTIVE
-- claims when computing desired-vs-observed.

BEGIN;

CREATE TABLE IF NOT EXISTS projection_attempts (
    attempt_id     BIGSERIAL PRIMARY KEY,
    projection     TEXT NOT NULL,
    entity_kind    TEXT NOT NULL,
    entity_id      TEXT NOT NULL,
    receipt_hash   TEXT NOT NULL,
    contract       TEXT NOT NULL DEFAULT '',
    written_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS projection_attempts_entity_idx
    ON projection_attempts (projection, entity_kind, entity_id);

ALTER TABLE projection_receipts ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
CREATE INDEX IF NOT EXISTS projection_receipts_active_idx
    ON projection_receipts (projection, entity_kind) WHERE active;

COMMIT;

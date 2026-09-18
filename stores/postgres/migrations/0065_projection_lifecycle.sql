-- 0065_projection_lifecycle.sql
-- PROJECTION-LIFECYCLE-V1 (librarian checklist P1/P2) — extend the projection_receipts
-- manifest with an explicit lifecycle + canonical-linkage columns so the repo answers
-- deterministically: what canonical object should be projected, from which artifact/
-- version/hash, where it should live, what exact projection currently exists, and whether it
-- is PENDING / PROJECTED / STALE / FAILED (and therefore safely rebuildable).
--
-- CAPACITY ONLY. Additive columns only; the SOLE backfill is a FAITHFUL relabel of the
-- existing `active` flag (active=false rows are already the superseded/invalidated ones →
-- STALE; active=true keeps the PROJECTED default). No projection behaviour changes and no row
-- is reinterpreted beyond the meaning `active` already carried. This EXTENDS the existing
-- projection authority (projection_receipts); it never opens a second one.
BEGIN;

ALTER TABLE projection_receipts
    ADD COLUMN IF NOT EXISTS state              TEXT        NOT NULL DEFAULT 'PROJECTED',
    ADD COLUMN IF NOT EXISTS artifact_hash      TEXT,
    ADD COLUMN IF NOT EXISTS projection_version TEXT,
    ADD COLUMN IF NOT EXISTS observed_ref       TEXT,
    ADD COLUMN IF NOT EXISTS error              TEXT,
    ADD COLUMN IF NOT EXISTS updated_at         TIMESTAMPTZ NOT NULL DEFAULT now();

-- idempotent CHECK: state is one of the four lifecycle values.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'projection_receipts_state_chk') THEN
        ALTER TABLE projection_receipts
            ADD CONSTRAINT projection_receipts_state_chk
            CHECK (state IN ('PENDING', 'PROJECTED', 'STALE', 'FAILED'));
    END IF;
END $$;

-- faithful backfill: superseded/invalidated claims (active=false) are STALE.
UPDATE projection_receipts SET state = 'STALE' WHERE NOT active AND state = 'PROJECTED';

CREATE INDEX IF NOT EXISTS projection_receipts_state_idx
    ON projection_receipts (projection, entity_kind, state);

COMMIT;

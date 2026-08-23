-- 0029: CONTRACT-RECONCILIATION-1C — pipeline-version lineage.
--
-- Addendum 5e: contract-pinned claiming is fail-closed but was not
-- self-healing. A run pinned before an upgrade can never be claimed by
-- the upgraded fleet, and nothing regenerated it. This migration adds
-- the lineage substrate so reconciliation can mint a successor run and
-- retire the old one WITHOUT deleting any history:
--
--   runs.supersedes_run_id      forward lineage (successor -> old)
--   runs.superseded_by_run_id   reverse lineage (old -> successor)
--   status 'superseded'         terminal, evidence-preserving close
--                               for both runs and stage tickets
--
-- ONE-ACTIVE-INTENT INVARIANT: a superseded run may have at most one
-- successor, ever. Enforced by a partial unique index on
-- supersedes_run_id; reconciliation is idempotent under this index.

BEGIN;

ALTER TABLE runs ADD COLUMN IF NOT EXISTS supersedes_run_id
    TEXT REFERENCES runs(run_id);
ALTER TABLE runs ADD COLUMN IF NOT EXISTS superseded_by_run_id
    TEXT REFERENCES runs(run_id);

ALTER TABLE runs DROP CONSTRAINT IF EXISTS runs_status_check;
ALTER TABLE runs ADD CONSTRAINT runs_status_check
    CHECK (status IN ('intake','reconciling','query_ready','degraded',
                      'failed','superseded'));

ALTER TABLE stage_tickets DROP CONSTRAINT IF EXISTS
    stage_tickets_status_check;
ALTER TABLE stage_tickets ADD CONSTRAINT stage_tickets_status_check
    CHECK (status IN ('pending','ready','leased','done','failed',
                      'repair','superseded'));

CREATE UNIQUE INDEX IF NOT EXISTS runs_one_successor_idx
    ON runs (supersedes_run_id)
    WHERE supersedes_run_id IS NOT NULL;

COMMIT;

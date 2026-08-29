-- SUMMARY-IDEMPOTENCY-V1 (P23, 2026-08-28)
--
-- Two defects, one symptom.
--
-- CONTROL PLANE. summary_jobs had no uniqueness beyond the surrogate
-- ticket_id, and the ticket id is derived from the RUN
-- (summary_worker_impl._stage_ticket), so every run re-ticketed every
-- parent. The done-check was by ticket_id, which is run-scoped, so it
-- never matched across runs. MEASURED: 21,315 PARENT_SUMMARY tickets
-- for 3,025 distinct input_hash values -- 7.0x, up to 12x for 533
-- hashes. The logical identity of the work is (stage, input_hash), not
-- (run, parent).
--
-- PERSISTENCE. parent_summaries had no notion of authority.
-- summary_id is content-addressed under ON CONFLICT (summary_id) DO
-- NOTHING, so a parent summarised before its entities were ready and
-- again afterwards kept BOTH rows with nothing saying which one counts.
-- MEASURED: 3,025 rows for 1,784 parents; 1,241 parents hold two rows
-- written 4h15m apart with different artifact_hash.
--
-- Why this blocks the rebuild: P14 re-tickets every parent WHILE
-- changing contract generation, so the same mechanism can leave one
-- parent holding a v1 row and a v2 row simultaneously -- exactly the
-- half-old/half-new generation P13 must make impossible.
--
-- The fix is identity and authority, not a SELECT DISTINCT or an
-- ORDER BY created_at LIMIT 1 at the read sites. Those hide the defect.

-- ---------------------------------------------------------------- control
-- One logical job per (stage, input_hash). Retries increment `attempts`
-- on the existing row; they do not manufacture a second job.
--
-- Historical duplicates are collapsed first, keeping the COMPLETE row
-- when one exists (work that actually finished is the survivor) and
-- otherwise the earliest.
DELETE FROM summary_jobs a
      USING summary_jobs b
      WHERE a.stage = b.stage
        AND a.input_hash = b.input_hash
        AND a.ticket_id <> b.ticket_id
        AND (
              (b.state = 'COMPLETE' AND a.state <> 'COMPLETE')
           OR (b.state = a.state AND b.created_at < a.created_at)
           OR (b.state = a.state AND b.created_at = a.created_at
               AND b.ticket_id < a.ticket_id)
        );

CREATE UNIQUE INDEX IF NOT EXISTS summary_jobs_logical_identity_idx
    ON summary_jobs (stage, input_hash);

-- ------------------------------------------------------------ persistence
-- NULL superseded_at means "this is the authoritative summary for this
-- parent". Superseding is explicit and auditable; rows are retained.
ALTER TABLE parent_summaries
    ADD COLUMN IF NOT EXISTS superseded_at timestamptz;

-- Backfill: for every parent with more than one row, the newest row is
-- authoritative and the rest are marked superseded. This encodes the
-- decision that was previously left to whichever SELECT ran first.
UPDATE parent_summaries ps
   SET superseded_at = now()
 WHERE superseded_at IS NULL
   AND EXISTS (
        SELECT 1 FROM parent_summaries newer
         WHERE newer.parent_id = ps.parent_id
           AND newer.superseded_at IS NULL
           AND (newer.created_at, newer.summary_id)
             > (ps.created_at, ps.summary_id)
   );

-- At most ONE authoritative row per parent, enforced by the database
-- rather than by convention at each read site.
CREATE UNIQUE INDEX IF NOT EXISTS parent_summaries_current_idx
    ON parent_summaries (parent_id)
 WHERE superseded_at IS NULL;

CREATE INDEX IF NOT EXISTS parent_summaries_superseded_idx
    ON parent_summaries (parent_id, superseded_at);

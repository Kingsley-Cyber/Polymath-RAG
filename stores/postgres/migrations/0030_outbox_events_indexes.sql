-- 0030: OUTBOX LOOKUP INDEXES — un-wedge the control tick at scale.
--
-- Found live during STEP 1c verification: _emit_ticket_event looks up
--   SELECT payload FROM outbox_events
--    WHERE run_id=%s AND event_type=%s ORDER BY event_id LIMIT 1
-- and worker_runtime.claim_ticket_events joins outbox to tickets on
-- (run_id, event_type) over undelivered rows. outbox_events had ONLY
-- its pkey and idempotency unique index, so every lookup was a
-- sequential scan of a 1.4 GB / 23,908-row payload table -- control
-- ticks observed stuck 5-6+ MINUTES inside this single SELECT,
-- holding row-exclusive locks and starving every worker claim.
--
-- Two indexes, matching the two access shapes:
--   (run_id, event_type)      point lookup + join key
--   (delivered_at) PARTIAL    the undelivered-work scan

BEGIN;

CREATE INDEX IF NOT EXISTS outbox_events_run_type_idx
    ON outbox_events (run_id, event_type);

CREATE INDEX IF NOT EXISTS outbox_events_undelivered_idx
    ON outbox_events (event_id)
    WHERE delivered_at IS NULL;

COMMIT;

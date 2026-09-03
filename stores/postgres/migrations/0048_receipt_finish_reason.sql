-- RECEIPT-COMPLETENESS-V1 (LLM-DIRECT-CANON P3, 2026-09-03): the raw-response
-- ledger must carry the one transport fact the disposition rules read —
-- finish_reason ("length" marks a truncated call whose last item is
-- untrusted and re-issued). Without it a ledger replay cannot follow
-- production's disposition path. Nullable: older receipts fall back to the
-- extract artifact's per-call record (matched by raw_head).
ALTER TABLE extraction_call_receipts ADD COLUMN IF NOT EXISTS finish_reason text;

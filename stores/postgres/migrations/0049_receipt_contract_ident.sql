-- LLM-DIRECT-CANON P6 readiness (2026-09-03): the extraction contract now
-- includes the gate version + attestation policy, so a gate change is a
-- contract change and `scripts/reingest_corpus.py` re-extracts. Receipt
-- keys are derived from the contract identity, so every receipt records
-- the identity it was keyed under; the ledger replay translates a window
-- to the key of the era the document was extracted in. Nullable: older
-- receipts are keyed under the identity that was live when they were
-- written (backfilled from the extract artifact where it round-trips).
ALTER TABLE extraction_call_receipts ADD COLUMN IF NOT EXISTS contract_ident text;
CREATE INDEX IF NOT EXISTS extraction_call_receipts_doc_ident_idx
    ON extraction_call_receipts (doc_id, contract_ident);

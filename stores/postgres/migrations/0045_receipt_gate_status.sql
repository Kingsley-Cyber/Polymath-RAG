-- EXTRACTION-FLEET-V3: PARSED is not ACCEPTED. The receipt records how
-- many proposals the parsed packet carried so replay policy and the
-- provider-equivalence bench can tier lanes by what the compiler
-- actually ACCEPTS, not by HTTP 200s. Quarantined calls (no packet)
-- were never cached and never will be.
ALTER TABLE extraction_call_receipts
    ADD COLUMN IF NOT EXISTS accepted_count INT;

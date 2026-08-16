-- 0010_exact_provenance.sql
-- I3R-R6: exact evidence provenance contract. Evidence rows may carry a
-- provenance contract tag; exact-evidence-v1 rows have chunk-relative
-- span offsets for trigger/subject/object/evidence spans so that
-- chunk_text[start:end] == surface is verifiable.

BEGIN;

ALTER TABLE evidence ADD COLUMN IF NOT EXISTS provenance_contract TEXT NOT NULL DEFAULT 'legacy';

COMMIT;

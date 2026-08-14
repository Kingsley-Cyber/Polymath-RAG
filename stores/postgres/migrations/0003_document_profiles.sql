-- 0003_document_profiles.sql
-- Phase G1: the document retrieval profile — the semantic address for
-- cross-domain routing (distinct from the ingestion profile, which
-- stays a deterministic label-routing artifact).
--
-- The profile is built bottom-up from parent summaries + entities +
-- facts + the ingestion profile, by deterministic aggregation only
-- (no LLM in the ingestion layer). Coverage fields make an incomplete
-- profile explicitly visible to verification (receipt discipline).

BEGIN;

ALTER TABLE documents ADD COLUMN IF NOT EXISTS retrieval_profile JSONB;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS profile_contract TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_parent_count INTEGER;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS summarized_parent_count INTEGER;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS profile_coverage REAL;

COMMIT;

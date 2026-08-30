-- DOCUMENT-REGION-V1: document role as retrieval metadata.
--
-- Role is METADATA, never truth: it never alters child text and never
-- removes a chunk from storage or from the index. It only lets default
-- retrieval prefer answer-bearing regions, while an explicit
-- document-metadata question can still reach the demoted regions.
--
-- NULL is the legacy-safe default: a chunk ingested before this
-- contract keeps competing normally (is_noisy(NULL) is False), so
-- adding this column can never suppress an existing corpus.
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS region_role text;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS region_reason text;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS region_contract text;

-- Retrieval filters on (role) for a bounded candidate set, so a partial
-- index over the demoted rows is enough.
CREATE INDEX IF NOT EXISTS chunks_region_role_idx
    ON chunks (region_role) WHERE region_role IS NOT NULL;

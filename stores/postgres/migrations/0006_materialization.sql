-- 0006_materialization.sql
-- I0 native document materialization provenance (ADR 0010).
--
-- The materialized representation (normalized text + structural source
-- map) is derived, deterministic state. The ORIGINAL bytes remain the
-- document identity: document_id/content_hash are unchanged; these new
-- columns record the original byte hash, the materializer identity,
-- and the char-range -> native-location map used by the citation chain
-- (evidence -> chunk offsets -> source-map segment -> page/chapter).

BEGIN;

ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_hash TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS materialization JSONB;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_map JSONB;

COMMIT;

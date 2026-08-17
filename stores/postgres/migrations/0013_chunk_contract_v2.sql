-- 0013: chunk-contract-v2 (SEMANTIC-CHUNKING-V2) + embedding cache.
-- Chunk rows gain their contract identity and structural metadata;
-- legacy rows keep NULL (they predate the columns and remain
-- reconstructible under legacy_v1). The embedding cache is disposable,
-- content-addressed, rebuildable.

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_contract_version TEXT;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS provider TEXT;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS heading_path JSONB;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS token_count INTEGER;

CREATE TABLE IF NOT EXISTS semantic_embedding_cache (
    cache_key  TEXT PRIMARY KEY,
    vector     JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

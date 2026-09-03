-- GENERATION-SWAP-V1 (2026-09-03, blue/green re-ingest). A blue/green
-- successor's intake writes a SECOND chunk generation for the same document
-- while the serving generation stays live, so (doc_id, chunk_index) is unique
-- per generation, not per document. chunk_id stays the primary key (content
-- addressed, distinct across generations). Legacy rows have a NULL contract;
-- COALESCE keeps them unique among themselves.
ALTER TABLE chunks DROP CONSTRAINT IF EXISTS chunks_doc_id_chunk_index_key;
CREATE UNIQUE INDEX IF NOT EXISTS chunks_doc_generation_index_key
    ON chunks (doc_id, chunk_index, COALESCE(chunk_contract_version, ''));
CREATE INDEX IF NOT EXISTS chunks_doc_generation_idx
    ON chunks (doc_id, chunk_contract_version);
-- readers and the swap look runs up by their blue/green marker
CREATE INDEX IF NOT EXISTS runs_blue_green_idx
    ON runs (corpus_id, status)
    WHERE (metadata->'blue_green') IS NOT NULL;

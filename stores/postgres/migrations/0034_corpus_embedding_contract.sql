-- 0034: EMBEDDING-CONTRACT-REGISTRY-V1 (G1 owner decision, 2026-08-25).
--
-- The embedding contract is CORPUS STATE, not an application setting:
-- vectors only mean something under the contract that produced them,
-- and a query must never be embedded under a different contract than
-- the vectors it searches. Each corpus therefore pins the contract that
-- is AUTHORITATIVE for its retrieval.
--
-- Production default flips to neural (neural-embed-v1). Existing
-- collections are NOT reinterpreted in place; rows whose live Qdrant
-- state proves hash-only projections are corrected by backfill before
-- this migration's default could mislead any reader.

ALTER TABLE corpora
    ADD COLUMN embedding_contract_id text NOT NULL DEFAULT 'neural-embed-v1';

CREATE INDEX corpora_embedding_contract_idx
    ON corpora (embedding_contract_id);

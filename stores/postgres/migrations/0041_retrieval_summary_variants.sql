-- 0041: SUMMARY-COMPILER-V1 — dual-summary slot on retrieval_summaries.
-- The deterministic compiler ALWAYS writes a card (variant 'deterministic');
-- when the extractor's per-neighborhood digest (LLM abstract) is present
-- and clean it becomes the ACTIVE routing representation (variant
-- 'llm_digest') and the deterministic card stays persisted as the
-- fallback. Exactly one active row per (doc, kind, parent) slot; the
-- projector, the census and the verifier read ACTIVE rows only.
-- summary_text = the serialized embed text (SUMMARY / RELATIONSHIPS /
-- KEY CONCEPTS); plain_summary = the extractive summary alone;
-- relations/keywords = the deterministic capsules; coverage = the per-card
-- receipt the verifier gates on.

ALTER TABLE retrieval_summaries
    ADD COLUMN IF NOT EXISTS variant       TEXT    NOT NULL DEFAULT 'deterministic',
    ADD COLUMN IF NOT EXISTS active        BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS plain_summary TEXT    NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS relations     JSONB   NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS keywords      JSONB   NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS coverage      JSONB   NOT NULL DEFAULT '{}';

CREATE UNIQUE INDEX IF NOT EXISTS retrieval_summaries_active_slot
    ON retrieval_summaries (doc_id, kind, COALESCE(parent_id, ''))
    WHERE active;

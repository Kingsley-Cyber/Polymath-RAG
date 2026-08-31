-- LATENT-TRANSFER-LAYER-V1 Phase B (plan §2.1, renumbered 0043).
-- parent_enrichments: the L2 latent artifact per parent — additive,
-- rebuildable, never evidence. status READY|STALE|INVALID; exactly one
-- READY row per parent (partial unique index). summary_jobs gains the
-- PARENT_ENRICHMENT stage.

CREATE TABLE IF NOT EXISTS parent_enrichments (
    enrichment_id     TEXT PRIMARY KEY,
    parent_id         TEXT NOT NULL,
    corpus_id         TEXT NOT NULL,
    doc_id            TEXT NOT NULL,
    source_child_ids  TEXT[] NOT NULL,
    source_hash       TEXT NOT NULL,
    input_hash        TEXT NOT NULL,
    compiler_contract TEXT NOT NULL DEFAULT 'parent-enrichment-v1',
    provider          TEXT NOT NULL,
    model             TEXT NOT NULL,
    prompt_version    TEXT NOT NULL,
    summary           TEXT NOT NULL DEFAULT '',
    children          JSONB NOT NULL DEFAULT '[]'::jsonb,
    abstraction       TEXT NOT NULL DEFAULT '',
    mechanisms        JSONB NOT NULL DEFAULT '[]'::jsonb,
    affordances       JSONB NOT NULL DEFAULT '[]'::jsonb,
    questions         JSONB NOT NULL DEFAULT '[]'::jsonb,
    gist_coverage     DOUBLE PRECISION NOT NULL DEFAULT 0,
    error_class       TEXT,
    status            TEXT NOT NULL CHECK (status IN ('READY','STALE','INVALID')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_at     TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS parent_enrichments_one_ready
    ON parent_enrichments (parent_id) WHERE status = 'READY';
CREATE INDEX IF NOT EXISTS parent_enrichments_doc ON parent_enrichments (doc_id);
CREATE INDEX IF NOT EXISTS parent_enrichments_corpus ON parent_enrichments (corpus_id);
CREATE INDEX IF NOT EXISTS parent_enrichments_input ON parent_enrichments (input_hash);

ALTER TABLE summary_jobs DROP CONSTRAINT IF EXISTS summary_jobs_stage_check;
ALTER TABLE summary_jobs ADD CONSTRAINT summary_jobs_stage_check
    CHECK (stage IN ('PARENT_SUMMARY','DOCUMENT_SUMMARY','CORPUS_MAPPING',
                     'VOCABULARY_MAPPING','PARENT_ENRICHMENT'));

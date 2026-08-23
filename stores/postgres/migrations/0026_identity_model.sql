-- 0026: STEP 1 — DEDUP IDENTITY MODEL storage.
-- Source identity vs processing identity are SEPARATE. Merges are never
-- silent. Contradictions are claim sets, never overwrites.

CREATE UNIQUE INDEX IF NOT EXISTS documents_corpus_source_hash_uq
    ON documents(corpus_id, source_hash);

CREATE TABLE IF NOT EXISTS document_processing_runs (
    run_id           TEXT PRIMARY KEY,
    document_id      TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    artifact_hash    TEXT NOT NULL,
    status           TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dpr_doc_idx ON document_processing_runs(document_id);

CREATE TABLE IF NOT EXISTS entity_merge_receipts (
    merge_id       TEXT PRIMARY KEY,
    corpus_id      TEXT NOT NULL,
    source_entities TEXT[] NOT NULL,
    target_entity  TEXT NOT NULL,
    reason         TEXT NOT NULL,
    support        TEXT[] NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS claim_sets (
    claim_set_id TEXT PRIMARY KEY,
    subject_id   TEXT NOT NULL,
    predicate    TEXT NOT NULL,
    claims       JSONB NOT NULL,   -- [{value, evidence:[...]}]
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (subject_id, predicate)
);

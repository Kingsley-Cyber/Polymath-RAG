-- 0024: SUMMARY INTELLIGENCE RUNTIME (D1) — derived-intelligence storage.
--
-- Six tables per POLYMATH_STAGE_WORKER_IMPLEMENTATION. Every row carries
-- corpus_id, artifact_hash, contract_version, created_by_worker,
-- created_at, source_ids. Idempotency gate lives on artifact_hash
-- (UNIQUE): same input hash returns EXISTING, never duplicates.

CREATE TABLE IF NOT EXISTS summary_jobs (
    ticket_id        TEXT PRIMARY KEY,
    stage            TEXT NOT NULL CHECK (stage IN
        ('PARENT_SUMMARY','DOCUMENT_SUMMARY','CORPUS_MAPPING',
         'VOCABULARY_MAPPING')),
    corpus_id        TEXT NOT NULL,
    document_id      TEXT,
    parent_id        TEXT,
    input_hash       TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    state            TEXT NOT NULL DEFAULT 'READY' CHECK (state IN
        ('READY','CLAIMED','RUNNING','COMPLETE','FAILED','RETRY_WAIT',
         'FAILED_PERMANENT')),
    attempts         INTEGER NOT NULL DEFAULT 0,
    worker_id        TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS summary_jobs_corpus_state_idx
    ON summary_jobs(corpus_id, stage, state);

CREATE TABLE IF NOT EXISTS summary_artifacts (
    artifact_id       TEXT PRIMARY KEY,
    input_hash        TEXT NOT NULL UNIQUE,
    output_hash       TEXT NOT NULL,
    stage             TEXT NOT NULL,
    corpus_id         TEXT NOT NULL,
    contract_version  TEXT NOT NULL,
    created_by_worker TEXT NOT NULL,
    source_ids        TEXT[] NOT NULL DEFAULT '{}',
    payload           JSONB NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS parent_summaries (
    summary_id   TEXT PRIMARY KEY,
    parent_id    TEXT NOT NULL,
    corpus_id    TEXT NOT NULL,
    artifact_hash TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    created_by_worker TEXT NOT NULL,
    source_ids   TEXT[] NOT NULL DEFAULT '{}',
    entities     TEXT[] NOT NULL DEFAULT '{}',
    concepts     TEXT[] NOT NULL DEFAULT '{}',
    summary      TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_summaries (
    summary_id   TEXT PRIMARY KEY,
    document_id  TEXT NOT NULL,
    corpus_id    TEXT NOT NULL,
    artifact_hash TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    created_by_worker TEXT NOT NULL,
    source_ids   TEXT[] NOT NULL DEFAULT '{}',
    major_entities TEXT[] NOT NULL DEFAULT '{}',
    major_concepts TEXT[] NOT NULL DEFAULT '{}',
    methods      TEXT[] NOT NULL DEFAULT '{}',
    domains      TEXT[] NOT NULL DEFAULT '{}',
    questions_answered TEXT[] NOT NULL DEFAULT '{}',
    summary      TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corpus_summaries (
    summary_id   TEXT PRIMARY KEY,
    corpus_id    TEXT NOT NULL,
    artifact_hash TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    created_by_worker TEXT NOT NULL,
    source_ids   TEXT[] NOT NULL DEFAULT '{}',
    dominant_domains   TEXT[] NOT NULL DEFAULT '{}',
    important_entities TEXT[] NOT NULL DEFAULT '{}',
    dominant_concepts  TEXT[] NOT NULL DEFAULT '{}',
    common_predicates  TEXT[] NOT NULL DEFAULT '{}',
    research_topics    TEXT[] NOT NULL DEFAULT '{}',
    document_clusters  JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS concept_vocabulary (
    concept_id  TEXT PRIMARY KEY,
    corpus_id   TEXT NOT NULL,
    canonical   TEXT NOT NULL,
    aliases     TEXT[] NOT NULL DEFAULT '{}',
    related_terms TEXT[] NOT NULL DEFAULT '{}',
    supporting_artifacts TEXT[] NOT NULL DEFAULT '{}',
    confidence  REAL NOT NULL DEFAULT 0.0,
    provenance  JSONB NOT NULL DEFAULT '{}',
    artifact_hash TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    created_by_worker TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (corpus_id, canonical)
);

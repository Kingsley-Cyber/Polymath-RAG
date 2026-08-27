-- KNOWLEDGE-ARTIFACT-PERSISTENCE-V1
-- ProcedureArtifact and ConceptArtifact become first-class durable
-- knowledge objects, equal citizens with facts. They are NOT facts,
-- never enter CanonicalFact tables, and never flatten into the entity
-- graph. Content-addressed ids from knowledge_objects compilers make
-- replay idempotent.

CREATE TABLE IF NOT EXISTS procedure_artifacts (
    procedure_id     text PRIMARY KEY,
    document_id      text NOT NULL,
    corpus_id        text NOT NULL DEFAULT '',
    title            text NOT NULL DEFAULT '',
    goal             text NOT NULL DEFAULT '',
    steps_json       jsonb NOT NULL DEFAULT '[]',
    tools_json       jsonb NOT NULL DEFAULT '[]',
    prerequisites_json jsonb NOT NULL DEFAULT '[]',
    confidence       real NOT NULL DEFAULT 0.0,
    source_chunk_ids text[] NOT NULL DEFAULT '{}',
    generated_by_bundle_hash text NOT NULL DEFAULT '',
    provenance       jsonb NOT NULL DEFAULT '{}',
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS procedure_artifacts_doc_idx
    ON procedure_artifacts (document_id);
CREATE INDEX IF NOT EXISTS procedure_artifacts_corpus_idx
    ON procedure_artifacts (corpus_id);

CREATE TABLE IF NOT EXISTS concept_artifacts (
    concept_id       text PRIMARY KEY,
    document_id      text NOT NULL,
    corpus_id        text NOT NULL DEFAULT '',
    name             text NOT NULL,
    description      text NOT NULL DEFAULT '',
    domain           text NOT NULL DEFAULT 'general',
    related_entities jsonb NOT NULL DEFAULT '[]',
    source_sentence  text NOT NULL DEFAULT '',
    confidence       real NOT NULL DEFAULT 0.0,
    supporting_chunks text[] NOT NULL DEFAULT '{}',
    generated_by_bundle_hash text NOT NULL DEFAULT '',
    provenance       jsonb NOT NULL DEFAULT '{}',
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS concept_artifacts_doc_idx
    ON concept_artifacts (document_id);
CREATE INDEX IF NOT EXISTS concept_artifacts_corpus_idx
    ON concept_artifacts (corpus_id);
CREATE INDEX IF NOT EXISTS concept_artifacts_name_idx
    ON concept_artifacts (name);

-- 0009_mentions.sql
-- I3R-R4: durable mentions. Every GLiNER proposal that survives the
-- admission decision is recorded here with exact provenance, so a
-- proposal can never silently disappear before fact participation.
--
-- mentions        = EVERY accepted GLiNER/admission span (all classes).
-- entities        = durable referential entities (admission classes
--                   GLOBAL / CORPUS_SCOPED / DOCUMENT_SCOPED), whether
--                   or not they ever participate in a fact.
-- MENTION_ONLY    = durable mention ONLY: never an entities row, never
--                   canonicalized, never projected to Neo4j.
--
-- Graph topology stays FACT-DRIVEN: project_neo4j and canonicalization
-- keep their facts-join filters; durable factless entities never reach
-- the graph.

BEGIN;

CREATE TABLE IF NOT EXISTS mentions (
    mention_id          TEXT PRIMARY KEY,
    corpus_id           TEXT NOT NULL,
    doc_id              TEXT NOT NULL,
    chunk_id            TEXT NOT NULL,
    char_start          INT NOT NULL,
    char_end            INT NOT NULL,
    surface             TEXT NOT NULL,
    normalized_surface  TEXT NOT NULL,
    core_type           TEXT NOT NULL,
    gliner_score        REAL NOT NULL,
    extractor_version   TEXT NOT NULL,
    admission_class     TEXT NOT NULL CHECK (admission_class IN
                          ('GLOBAL', 'CORPUS_SCOPED', 'DOCUMENT_SCOPED', 'MENTION_ONLY')),
    entity_id           TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS mentions_doc_idx ON mentions (doc_id);
CREATE INDEX IF NOT EXISTS mentions_corpus_idx ON mentions (corpus_id);

COMMIT;

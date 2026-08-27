-- 0025: SUMMARY RUNTIME D5 — vocabulary mapping storage.
-- Concept families are the semantic bridge between human questions and
-- corpus knowledge. They NEVER redefine identity: no entity ids here,
-- aliases accumulate with provenance, merges leave a support trail.

CREATE TABLE IF NOT EXISTS concept_families (
    concept_id       TEXT PRIMARY KEY,
    corpus_id        TEXT NOT NULL,
    canonical_name   TEXT NOT NULL,
    definition       TEXT,
    artifact_hash    TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    created_by_worker TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (corpus_id, canonical_name)
);

CREATE TABLE IF NOT EXISTS concept_aliases (
    concept_id         TEXT NOT NULL REFERENCES concept_families(concept_id),
    alias              TEXT NOT NULL,
    source_summary_id  TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (concept_id, alias)
);

CREATE TABLE IF NOT EXISTS concept_support (
    concept_id     TEXT NOT NULL REFERENCES concept_families(concept_id),
    artifact_type  TEXT NOT NULL,
    artifact_id    TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (concept_id, artifact_type, artifact_id)
);

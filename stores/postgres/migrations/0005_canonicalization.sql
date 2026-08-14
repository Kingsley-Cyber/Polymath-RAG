-- 0005_canonicalization.sql
-- Stage-2 corpus canonicalization registry (ADR 0009, gate C1).
--
-- Canonicalization ADDS a corpus layer; it never erases source-local
-- knowledge. Local entities, facts, and evidence rows are untouched.
-- The registry is fully recomputable and replay-safe: canonical ids
-- are content hashes, memberships are per (corpus, local entity), and
-- decisions are pairwise with basis + canonicalizer version.
--
-- Postgres remains workflow authority. Neo4j canonical projection is
-- C2 and does not exist yet.

BEGIN;

CREATE TABLE IF NOT EXISTS canonical_entities (
    corpus_id            TEXT NOT NULL REFERENCES corpora(corpus_id) ON DELETE CASCADE,
    canonical_id         TEXT NOT NULL,       -- cent_<content hash>
    canonical_type       TEXT NOT NULL,       -- core type of the canonical group
    normalized_name      TEXT NOT NULL,       -- deterministic canonical surface
    canonicalizer_version TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (corpus_id, canonical_id)
);
CREATE INDEX IF NOT EXISTS canonical_entities_name_idx
    ON canonical_entities (corpus_id, normalized_name);

CREATE TABLE IF NOT EXISTS canonical_memberships (
    corpus_id            TEXT NOT NULL,
    canonical_id         TEXT NOT NULL,
    local_entity_id      TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    decision             TEXT NOT NULL CHECK (decision IN
                            ('SAME_AS','ALIAS_OF','DISTINCT','AMBIGUOUS','UNRESOLVED','SELF')),
    confidence           REAL NOT NULL,
    basis                JSONB NOT NULL DEFAULT '[]'::jsonb,
    canonicalizer_version TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (corpus_id, local_entity_id),
    FOREIGN KEY (corpus_id, canonical_id)
        REFERENCES canonical_entities (corpus_id, canonical_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS canonical_memberships_canon_idx
    ON canonical_memberships (canonical_id);

CREATE TABLE IF NOT EXISTS canonicalization_decisions (
    corpus_id            TEXT NOT NULL,
    decision_id          TEXT PRIMARY KEY,    -- hash(version|a|b), a < b
    local_entity_a       TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    local_entity_b       TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    decision             TEXT NOT NULL CHECK (decision IN
                            ('SAME_AS','ALIAS_OF','DISTINCT','AMBIGUOUS','UNRESOLVED')),
    confidence           REAL NOT NULL,
    basis                JSONB NOT NULL DEFAULT '[]'::jsonb,
    canonical_id         TEXT,                -- merged canonical, null when abstained
    canonicalizer_version TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS canonicalization_decisions_corpus_idx
    ON canonicalization_decisions (corpus_id);

COMMIT;

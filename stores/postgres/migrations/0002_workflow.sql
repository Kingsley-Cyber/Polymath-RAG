-- 0002_workflow.sql
-- Phase B workflow authority: documents, chunks, entities, evidence,
-- facts, receipts, artifacts, outbox delivery, control leases and
-- heartbeats. Postgres is the single system of record; Qdrant and
-- Neo4j are rebuildable projections (Phase F).
--
-- Idempotency: every durable row is keyed by a content hash computed in
-- shared/polymath_shared/identity.py. Replaying identical input is a
-- no-op because the primary keys collide.

BEGIN;

-- ---------------------------------------------------------------------------
-- corpora and documents
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS corpora (
    corpus_id        TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    config_hash      TEXT NOT NULL,          -- frozen-at-intake config digest
    profile          JSONB NOT NULL DEFAULT '{}'::jsonb,  -- OntologyProfile
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id           TEXT PRIMARY KEY,       -- doc_<sha256(normalized bytes)>
    corpus_id        TEXT NOT NULL REFERENCES corpora(corpus_id) ON DELETE CASCADE,
    source_name      TEXT NOT NULL,
    media_type       TEXT NOT NULL,
    byte_length      BIGINT NOT NULL,
    content_hash     TEXT NOT NULL,          -- sha256(normalized bytes)
    profile          JSONB NOT NULL DEFAULT '{}'::jsonb,  -- DocumentProfile
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS documents_corpus_idx ON documents (corpus_id);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id         TEXT PRIMARY KEY,       -- chunk_<sha256(doc_id|idx|text)>
    doc_id           TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    parent_id        TEXT REFERENCES chunks(chunk_id) ON DELETE SET NULL,
    chunk_index      INTEGER NOT NULL,
    tier             TEXT NOT NULL CHECK (tier IN ('parent', 'child')),
    text             TEXT NOT NULL,
    summary          TEXT NOT NULL DEFAULT '',
    char_start       INTEGER NOT NULL,
    char_end         INTEGER NOT NULL,
    embedding_model  TEXT,                   -- release id when embedded
    embedding_hash   TEXT,                   -- digest of embedding payload
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doc_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (doc_id, chunk_index);
CREATE INDEX IF NOT EXISTS chunks_parent_idx ON chunks (parent_id);

-- ---------------------------------------------------------------------------
-- entities, evidence, facts (compiler output)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS entities (
    entity_id        TEXT PRIMARY KEY,       -- ent_<content hash> (identity.py)
    core_type        TEXT NOT NULL,
    normalized_surface TEXT NOT NULL,
    domain_types     JSONB NOT NULL DEFAULT '[]'::jsonb,
    first_seen_doc   TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id      TEXT PRIMARY KEY,       -- ev_<content hash> (identity.py)
    fact_id          TEXT NOT NULL,
    doc_id           TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_id         TEXT NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    span_offsets     JSONB NOT NULL,         -- entity & evidence char offsets
    rule_id          TEXT NOT NULL,
    gliner_scores    JSONB NOT NULL DEFAULT '{}'::jsonb,
    extractor_version TEXT NOT NULL,
    rule_version     TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS evidence_fact_idx ON evidence (fact_id);

CREATE TABLE IF NOT EXISTS facts (
    fact_id          TEXT PRIMARY KEY,       -- fact_<content hash> (identity.py)
    predicate        TEXT NOT NULL,
    subject_id       TEXT NOT NULL REFERENCES entities(entity_id),
    object_id        TEXT NOT NULL REFERENCES entities(entity_id),
    qualifiers       JSONB NOT NULL DEFAULT '{}'::jsonb,  -- temporal/polarity/attribution
    decision         TEXT NOT NULL CHECK (decision IN
                       ('ACCEPT','QUALIFY','REJECT','AMBIGUOUS','UNSUPPORTED','CONFLICT')),
    rule_id          TEXT NOT NULL,
    rule_version     TEXT NOT NULL,
    provenance       JSONB NOT NULL DEFAULT '{}'::jsonb,  -- roleset/vn/fn/semlink + versions
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS facts_subject_idx ON facts (subject_id);
CREATE INDEX IF NOT EXISTS facts_object_idx ON facts (object_id);
CREATE INDEX IF NOT EXISTS facts_predicate_idx ON facts (predicate);

-- ---------------------------------------------------------------------------
-- stage artifacts + receipts (the commit point)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id      TEXT PRIMARY KEY,       -- sha256(run_id|stage|payload digest)
    run_id           TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    stage            TEXT NOT NULL,
    contract_hash    TEXT NOT NULL,
    payload          JSONB NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, stage, contract_hash)
);
CREATE INDEX IF NOT EXISTS artifacts_run_idx ON artifacts (run_id, stage);

CREATE TABLE IF NOT EXISTS receipts (
    receipt_id       TEXT PRIMARY KEY,       -- sha256(run_id|stage|contract_hash)
    run_id           TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    stage            TEXT NOT NULL,
    contract_hash    TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('committed','failed')),
    error            TEXT,
    wall_clock       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, stage, contract_hash)
);
CREATE INDEX IF NOT EXISTS receipts_run_idx ON receipts (run_id);

-- ---------------------------------------------------------------------------
-- outbox: transactional delivery (written in the same tx as the receipt)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS outbox_events (
    event_id         BIGSERIAL PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    event_type       TEXT NOT NULL,
    payload          JSONB NOT NULL,
    idempotency_key  TEXT NOT NULL UNIQUE,   -- content hash; redelivery is a no-op
    enqueued_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS outbox_pending_idx
    ON outbox_events (enqueued_at) WHERE delivered_at IS NULL;

-- ---------------------------------------------------------------------------
-- control plane: leases, heartbeats, census
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS control_owners (
    owner_id         TEXT PRIMARY KEY,       -- sha256(hostname|role|started_at)
    hostname         TEXT NOT NULL,
    role             TEXT NOT NULL,
    started_at       TIMESTAMPTZ NOT NULL,
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS control_leases (
    lease_key        TEXT PRIMARY KEY,       -- e.g. run:<run_id>, stage:<run>:<stage>
    owner_id         TEXT NOT NULL REFERENCES control_owners(owner_id) ON DELETE CASCADE,
    acquired_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at       TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS control_leases_expiry_idx
    ON control_leases (expires_at);

CREATE TABLE IF NOT EXISTS projection_receipts (
    projection       TEXT NOT NULL,          -- 'qdrant' | 'neo4j'
    entity_kind      TEXT NOT NULL,          -- 'chunk' | 'fact' | 'evidence'
    entity_id        TEXT NOT NULL,
    receipt_hash     TEXT NOT NULL,
    written_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (projection, entity_kind, entity_id)
);

-- The census wakeup channel: control ticks via LISTEN/NOTIFY.
NOTIFY control_tick;

COMMIT;

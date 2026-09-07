-- DOCUMENT-SEMANTIC-INDEX-V1 slice S4 — parent-map SQL durability (2026-09-07)
--
-- Postgres is workflow truth for the parent map (Qdrant is a rebuildable
-- projection). Three tables, keyed on the CORRECTED S2/S3 contracts (register
-- 11.133) so persistence inherits durable identity:
--
--   * document_parent_map_batches — the resumable substage ledger. batch_id IS
--     the S3 source-bound batch_hash (planner contract + manifest_hash + per-alias
--     skeleton_hash), so two documents that both alias P0001..P0060 never collide,
--     and re-running the SAME document's mapping yields the SAME batch_id -> the
--     ON CONFLICT DO NOTHING at claim time means restart/retry never duplicates a
--     completed batch's API work.
--   * document_parent_maps — the final authoritative map. map_id IS the S2 map_hash
--     (content identity); parent_id IS the parent chunk_id (never chunk_index); a
--     PARTIAL unique index enforces exactly one ACTIVE map per
--     (doc_id, parent_id, map_contract). Rows are retained; superseding flips
--     active, it does not delete.
--   * document_parent_exclusions — furniture/noise parents ACCOUNTED FOR (§20.3),
--     not mapped, not retrieval-eligible.
--
-- No worker in this slice (S9). Idempotent: safe to re-run.

-- ------------------------------------------------------------------- batches
CREATE TABLE IF NOT EXISTS document_parent_map_batches (
    batch_id          TEXT PRIMARY KEY,          -- S3 batch_hash (source-bound)
    run_id            TEXT NOT NULL,
    doc_id            TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    corpus_id         TEXT,
    map_contract      TEXT NOT NULL,
    ordinal           INTEGER NOT NULL,
    is_combined       BOOLEAN NOT NULL DEFAULT FALSE,
    status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'leased', 'partial', 'done', 'error')),
    expected_count    INTEGER NOT NULL,
    valid_count       INTEGER NOT NULL DEFAULT 0,
    alias_manifest    JSONB NOT NULL,            -- expected alias -> parent_id
    input_hash        TEXT NOT NULL,             -- skeleton/prompt input hash
    raw_response_hash TEXT,                       -- raw model bytes (hashed first, §10)
    provider          TEXT,
    model             TEXT,
    attempt_count     INTEGER NOT NULL DEFAULT 0,
    lease_owner       TEXT,
    lease_expires_at  timestamptz,
    last_error        TEXT,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS document_parent_map_batches_doc_idx
    ON document_parent_map_batches (doc_id, map_contract);
-- Claimable work: pending/partial batches whose lease (if any) has expired.
CREATE INDEX IF NOT EXISTS document_parent_map_batches_claim_idx
    ON document_parent_map_batches (status, lease_expires_at);

-- ---------------------------------------------------------------------- maps
CREATE TABLE IF NOT EXISTS document_parent_maps (
    map_id            TEXT PRIMARY KEY,          -- S2 map_hash (content identity)
    doc_id            TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    parent_id         TEXT NOT NULL,             -- parent chunk_id (Fix C), never chunk_index
    corpus_id         TEXT,
    map_contract      TEXT NOT NULL,
    alias             TEXT NOT NULL,             -- P0001 within the batch (not durable id)
    batch_id          TEXT REFERENCES document_parent_map_batches(batch_id) ON DELETE SET NULL,
    routing_signature TEXT NOT NULL,
    semantic_hooks    JSONB NOT NULL DEFAULT '[]'::jsonb,
    exact_identifiers JSONB NOT NULL DEFAULT '[]'::jsonb,  -- deterministic (§9), not model hooks
    provider          TEXT,
    model             TEXT,
    source_text_hash  TEXT,                       -- parent skeleton text_hash
    map_hash          TEXT NOT NULL,
    quality_flags     JSONB NOT NULL DEFAULT '[]'::jsonb,
    active            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

-- Exactly ONE active map per parent per contract (the authority invariant, §20.2).
CREATE UNIQUE INDEX IF NOT EXISTS document_parent_maps_active_idx
    ON document_parent_maps (doc_id, parent_id, map_contract)
    WHERE active;
CREATE INDEX IF NOT EXISTS document_parent_maps_doc_idx
    ON document_parent_maps (doc_id, map_contract);

-- ---------------------------------------------------------------- exclusions
CREATE TABLE IF NOT EXISTS document_parent_exclusions (
    doc_id       TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    parent_id    TEXT NOT NULL,                  -- parent chunk_id
    map_contract TEXT NOT NULL,
    reason       TEXT NOT NULL,                  -- toc / index / front_matter / ... / empty
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (doc_id, parent_id, map_contract)
);

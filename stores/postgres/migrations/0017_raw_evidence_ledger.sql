-- 0017: V5 L1 — RAW EVIDENCE LEDGER (append-only, immutable).
--
-- The provider's observations, persisted EXACTLY as returned: pre-dedupe,
-- pre-label-mapping, pre-rescue, pre-admission. Nothing downstream may
-- UPDATE or DELETE these rows; interpretation happens in L2+ and records
-- dispositions THERE. This closes the L1 gap named in the Phase 0 map:
-- until now the first durable artifact was the post-rescue, post-admission
-- mention — every earlier transform was unrecoverable.
--
-- proposal ids are content-addressed, so replays and retries land on the
-- same primary keys and inserts are idempotent (ON CONFLICT DO NOTHING).
-- Layout evidence (document_layout, chunks.layout_map) and the sentence
-- slice manifest (sentence_slices) are the other L1 members and already
-- exist; syntax is regenerable from the pinned model and is identified in
-- the evidence bundle rather than duplicated as rows.

CREATE TABLE IF NOT EXISTS raw_entity_proposals (
    proposal_id       TEXT PRIMARY KEY,
    doc_id            TEXT NOT NULL,
    chunk_id          TEXT NOT NULL,
    char_start        INTEGER NOT NULL,
    char_end          INTEGER NOT NULL,
    surface           TEXT NOT NULL,
    provider_label    TEXT NOT NULL,        -- verbatim, never mapped
    provider_score    DOUBLE PRECISION NOT NULL,
    provider_contract JSONB NOT NULL,       -- provider/model/revision/threshold/labels_sha/task
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS raw_entity_proposals_doc_idx
    ON raw_entity_proposals(doc_id, chunk_id);
CREATE INDEX IF NOT EXISTS raw_entity_proposals_surface_idx
    ON raw_entity_proposals(doc_id, lower(surface));

CREATE TABLE IF NOT EXISTS raw_predicate_evidence (
    evidence_id       TEXT PRIMARY KEY,
    doc_id            TEXT NOT NULL,
    chunk_id          TEXT NOT NULL,
    char_start        INTEGER NOT NULL,
    char_end          INTEGER NOT NULL,
    surface           TEXT NOT NULL,
    provider_label    TEXT NOT NULL,        -- the described class label as sent/returned
    provider_score    DOUBLE PRECISION NOT NULL,
    provider_contract JSONB NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS raw_predicate_evidence_doc_idx
    ON raw_predicate_evidence(doc_id, chunk_id);

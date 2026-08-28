-- SEMANTIC-LANE-LIVENESS-V1.
--
-- PROCEDURE and CONCEPT had NO durable record between "document text"
-- and "artifact row". An artifact count alone cannot distinguish
-- "12 of 12 opportunities captured" from "12 of 400 captured", which is
-- exactly the blindness that let other lanes sit dead. This table
-- records the OPPORTUNITY and the DISPOSITION, not just the output.
--
-- One row per (document, lane, run). Low cardinality by construction.
CREATE TABLE IF NOT EXISTS knowledge_lane_attempts (
    doc_id            text NOT NULL,
    corpus_id         text NOT NULL,
    lane              text NOT NULL,          -- 'procedure' | 'concept'
    opportunities     integer NOT NULL,       -- pre-gate candidate signals
    accepted          integer NOT NULL,       -- durable artifacts written
    capped            boolean NOT NULL DEFAULT false,
    disposition       text NOT NULL,          -- ACCEPTED|NO_OPPORTUNITY|GATED
    bundle_hash       text NOT NULL DEFAULT '',
    created_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (doc_id, lane)
);

CREATE INDEX IF NOT EXISTS knowledge_lane_attempts_corpus_idx
    ON knowledge_lane_attempts (corpus_id, lane);

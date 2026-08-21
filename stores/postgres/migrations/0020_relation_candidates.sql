-- 0020: V5 L4 — RELATION CANDIDATE DISPOSITIONS.
--
-- Every compiled relation candidate becomes a durable, attributable record —
-- ACCEPTED, QUALIFIED, PARKED or REFUSED — closing the L4 gap: refused
-- candidates previously existed only in the optional trace. Relation
-- evidence survives even when graph truth is refused (I7); canonical facts
-- remain the ONLY graph-truth artifact (I8) and are unchanged by this table.

CREATE TABLE IF NOT EXISTS relation_candidates (
    candidate_id     TEXT PRIMARY KEY,      -- content-addressed
    doc_id           TEXT NOT NULL,
    chunk_id         TEXT NOT NULL,
    evidence_class   TEXT NOT NULL,
    trigger_surface  TEXT,
    subject_surface  TEXT NOT NULL,
    subject_entity_id TEXT,
    object_surface   TEXT NOT NULL,
    object_entity_id TEXT,
    predicate        TEXT,                  -- rule the compiler selected, if any
    decision         TEXT NOT NULL,         -- ACCEPT | QUALIFY | REJECT | AMBIGUOUS | UNSUPPORTED | ...
    reason           TEXT,
    fact_id          TEXT,                  -- set when a canonical/parked fact was created
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS relation_candidates_doc_idx ON relation_candidates(doc_id, chunk_id);
CREATE INDEX IF NOT EXISTS relation_candidates_decision_idx ON relation_candidates(doc_id, decision);

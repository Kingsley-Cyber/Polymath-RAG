-- 0007_admission.sql
-- Entity admission boundary (E2/C1.1, entity-admission-v1.1).
--
-- Every durable entity row records its reference class. Legacy rows
-- (NULL) are treated as GLOBAL. MENTION_ONLY rows are evidence-only:
-- they never receive Neo4j Entity nodes, and facts touching them are
-- parked as unresolved evidence (persisted, never graph-projected).
-- Identity contract version: entity-identity-v2 — old global-only ids
-- are NOT interchangeable with the new scoped ids.

BEGIN;

ALTER TABLE entities ADD COLUMN IF NOT EXISTS admission_class TEXT
    CHECK (admission_class IN ('GLOBAL', 'CORPUS_SCOPED', 'DOCUMENT_SCOPED', 'MENTION_ONLY'));

CREATE INDEX IF NOT EXISTS entities_admission_idx ON entities (admission_class);

COMMIT;

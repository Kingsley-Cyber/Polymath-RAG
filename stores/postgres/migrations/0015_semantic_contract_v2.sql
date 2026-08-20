-- 0015: semantic-contract-v2 representation (PRODUCTION-WIRING-GATE S2).
--
-- CAPACITY ONLY. This migration makes the database able to REPRESENT the
-- qualified V2 semantics. It changes no behaviour, computes nothing, and
-- deliberately does NOT reinterpret existing rows.
--
--   Existing v1.1 rows remain historical v1.1 evidence until S5 rederives
--   them under V2.
--
-- Every new column is nullable and left NULL for historical rows. There is
-- no backfill: inferring `anchor_kind` from `normalized_surface` would be
-- exactly the normalized-surface classification the contract forbids, and
-- would fabricate provenance for decisions that were never made.
--
-- Three surface representations are kept distinct and must never be
-- substituted for one another:
--   surface / proposal_surface   raw provider evidence (case-bearing)
--   referential_surface          source-faithful discourse envelope
--   normalized_surface           lookup / candidate generation ONLY

-- raw provider evidence. `surface` already holds this for v1.1 rows;
-- proposal_surface makes the role explicit going forward.
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS proposal_surface TEXT;
-- source-faithful syntactic envelope (determiner-bearing), REFERENTIAL-SPAN-V1
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS referential_surface TEXT;

-- ENTITY-HARBOR-V1 decision state
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS anchor_kind TEXT;       -- IDENTITY|CONCEPT|LOCAL_REFERENCE|GENERIC|UNKNOWN
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS decision_status TEXT;   -- RESOLVED|CONTEXT_REQUIRED|ABSTAINED
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS reference_basis TEXT;   -- ANTECEDENT_RESOLVED|DOCUMENT_CONSTITUTED|EXTERNAL_UNRESOLVED|AMBIGUOUS
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS admission_reason TEXT;  -- auditable evidence for the decision

-- CONTRACTION-RESOLUTION-V1 membership. Nullable: a mention that resolves
-- to no canonical entity is normal, not an error.
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS canonical_entity_id TEXT;

-- which semantic contract produced this row. NULL == historical v1.1.
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS semantic_contract TEXT;

-- No `graph_eligible` column is added, by design: eligibility has exactly
-- one authority, derived from Harbor state (wiring invariant 3).

-- Run-level provenance: the semantic bundle a run was interpreted under.
-- Historical runs keep NULL and are NOT rewritten to claim V2.
ALTER TABLE runs ADD COLUMN IF NOT EXISTS semantic_contract TEXT;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS semantic_bundle_sha256 TEXT;

CREATE INDEX IF NOT EXISTS idx_mentions_canonical_entity
    ON mentions (corpus_id, canonical_entity_id);
CREATE INDEX IF NOT EXISTS idx_mentions_semantic_contract
    ON mentions (semantic_contract);

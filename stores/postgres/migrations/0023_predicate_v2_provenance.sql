-- 0023: PREDICATE-COMPILER-V2 SLICE 1 — candidate syntax provenance.
--
-- Makes the V2 hard rules measurable on the L4 ledger:
--   missing_trigger_token      -> trigger_token_id IS NULL
--   chunk_wide/regex intake    -> binding_source IS NULL or not in
--                                 ('UD_DEPENDENCY','NOMINAL_DEPENDENCY')
-- Rows written by legacy_v1/kimi_v1 carry NULLs, which is exactly the
-- signal the slice-7 acceptance gates count. Append-only; idempotent.

ALTER TABLE relation_candidates ADD COLUMN IF NOT EXISTS trigger_token_id INTEGER;
ALTER TABLE relation_candidates ADD COLUMN IF NOT EXISTS subject_token_id INTEGER;
ALTER TABLE relation_candidates ADD COLUMN IF NOT EXISTS object_token_id INTEGER;
ALTER TABLE relation_candidates ADD COLUMN IF NOT EXISTS dependency_path TEXT;
ALTER TABLE relation_candidates ADD COLUMN IF NOT EXISTS binding_source TEXT;
ALTER TABLE relation_candidates ADD COLUMN IF NOT EXISTS sentence_id TEXT;

CREATE INDEX IF NOT EXISTS relation_candidates_binding_source_idx
    ON relation_candidates(doc_id, binding_source);

-- GENERATION-STAMPING-V1 (register 1.6 / §11 L0, 2026-08-30).
-- The extraction generation must be indexable on the rows themselves:
-- LLM-era facts/entities were distinguishable only inside provenance
-- JSON (facts) or not at all (entities), and the open type vocabulary
-- was flattened at storage time (raw types lived only in artifacts).
ALTER TABLE entities ADD COLUMN IF NOT EXISTS extractor_version text;
ALTER TABLE entities ADD COLUMN IF NOT EXISTS generated_by_bundle_hash text;
ALTER TABLE entities ADD COLUMN IF NOT EXISTS raw_types jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE facts    ADD COLUMN IF NOT EXISTS extractor_version text;
CREATE INDEX IF NOT EXISTS facts_extractor_version_idx ON facts (extractor_version);
CREATE INDEX IF NOT EXISTS entities_extractor_version_idx ON entities (extractor_version);

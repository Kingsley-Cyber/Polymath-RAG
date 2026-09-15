-- 0063: deterministic hypothesis order. `adapter_hypotheses` gains an insertion sequence so the live hypotheses of a run are
-- ordered by generation (θ proposal order), never by the run-id-dependent hash in `hypothesis_id`. Additive; existing rows backfill
-- in physical order. (2026-09-15, HARNESS-RESEARCH-MIGRATION-V1 R5)
ALTER TABLE adapter_hypotheses ADD COLUMN IF NOT EXISTS seq BIGSERIAL;
CREATE INDEX IF NOT EXISTS adapter_hypotheses_run_seq_idx ON adapter_hypotheses (run_id, seq);

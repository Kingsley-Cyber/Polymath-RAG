-- HARNESS-RESEARCH-MIGRATION-V1 R2 (ADR-0019 §2/§4) — 2026-09-13
--
-- Durable hypothesis state and the harness-action pause. Additive next to migration 0061:
--   adapter_runs                    + status 'awaiting_harness' (a HARNESS_ACTION step waits for a HarnessResearchReceiptV1),
--                                   + harness_action_count (budget counter, like agent_reason_count)
--   adapter_hypotheses              one row per (hypothesis_id, revision): the immutable HypothesisStateV1 revision
--   adapter_hypothesis_transitions  one row per lifecycle transition; cause_count >= 1 is a CHECK (no transition without lineage)
--   adapter_harness_actions         the issued HarnessActionV1, its receipt (+hash) and Trail admission projection, per step
--   adapter_admitted_evidence       Trail-admitted observations (field_evidence ids) that AGENT_REASON context may cite
--
-- Rollback (owner-run, destructive): DROP TABLE adapter_admitted_evidence, adapter_harness_actions,
--   adapter_hypothesis_transitions, adapter_hypotheses; ALTER TABLE adapter_runs DROP COLUMN harness_action_count;
--   and restore the 0061 status CHECK (without 'awaiting_harness').
-- Replay proof: every statement is idempotent (IF NOT EXISTS / constraint swap guarded by a DO block).
ALTER TABLE adapter_runs ADD COLUMN IF NOT EXISTS harness_action_count INTEGER NOT NULL DEFAULT 0;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'adapter_runs_status_check' AND conrelid = 'adapter_runs'::regclass)
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'adapter_runs_status_check' AND conrelid = 'adapter_runs'::regclass
                       AND pg_get_constraintdef(oid) LIKE '%awaiting_harness%') THEN
        ALTER TABLE adapter_runs DROP CONSTRAINT adapter_runs_status_check;
        ALTER TABLE adapter_runs ADD CONSTRAINT adapter_runs_status_check
            CHECK (status IN ('created','running','awaiting_agent','awaiting_harness','completed','terminal_gap','cancelled','failed'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS adapter_hypotheses (
    hypothesis_id TEXT NOT NULL,
    run_id        TEXT NOT NULL REFERENCES adapter_runs(run_id) ON DELETE CASCADE,
    revision      INTEGER NOT NULL CHECK (revision >= 0),
    status        TEXT NOT NULL CHECK (status IN ('proposed','filtered','retained','revised','split','merged','weakened','strengthened','contradicted','killed','promoted')),
    state         JSONB NOT NULL,          -- HypothesisStateV1 (this revision)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (hypothesis_id, revision)
);
CREATE INDEX IF NOT EXISTS adapter_hypotheses_run_idx ON adapter_hypotheses (run_id, hypothesis_id, revision DESC);

CREATE TABLE IF NOT EXISTS adapter_hypothesis_transitions (
    transition_id TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES adapter_runs(run_id) ON DELETE CASCADE,
    hypothesis_id TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('GENERATE','REVISE','SPLIT','MERGE','WEAKEN','STRENGTHEN','CONTRADICT','KILL','PROMOTE')),
    actor         TEXT NOT NULL CHECK (actor IN ('theta','phi','runtime')),
    step_id       TEXT NOT NULL,
    sequence      INTEGER NOT NULL,
    cause_count   INTEGER NOT NULL CHECK (cause_count >= 1),   -- no transition without lineage
    transition    JSONB NOT NULL,          -- HypothesisTransitionV1
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS adapter_hypothesis_transitions_run_idx ON adapter_hypothesis_transitions (run_id, hypothesis_id, sequence);

CREATE TABLE IF NOT EXISTS adapter_harness_actions (
    action_id    TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES adapter_runs(run_id) ON DELETE CASCADE,
    step_id      TEXT NOT NULL,
    sequence     INTEGER NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('issued','received','admitted','rejected')),
    action       JSONB NOT NULL,           -- HarnessActionV1
    receipt      JSONB,                    -- HarnessResearchReceiptV1
    receipt_hash TEXT,
    admission    JSONB,                    -- EvidenceAdmissionV1 (Trail's verdict projection)
    issued_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    received_at  TIMESTAMPTZ,
    admitted_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS adapter_harness_actions_run_idx ON adapter_harness_actions (run_id, sequence);

CREATE TABLE IF NOT EXISTS adapter_admitted_evidence (
    evidence_id        TEXT PRIMARY KEY,   -- fev_… (Polymath-side id of the admitted observation)
    run_id             TEXT NOT NULL REFERENCES adapter_runs(run_id) ON DELETE CASCADE,
    action_id          TEXT NOT NULL REFERENCES adapter_harness_actions(action_id) ON DELETE CASCADE,
    admission_id       TEXT NOT NULL,
    observation_id     TEXT NOT NULL,
    evidence_role      TEXT NOT NULL,
    polarity           TEXT NOT NULL CHECK (polarity IN ('supporting','contradicting','neutral')),
    independence_group TEXT NOT NULL,
    hypothesis_ids     JSONB NOT NULL DEFAULT '[]'::jsonb,
    record             JSONB NOT NULL,     -- the admitted item of EvidenceAdmissionV1
    admitted_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS adapter_admitted_evidence_run_idx ON adapter_admitted_evidence (run_id, action_id);

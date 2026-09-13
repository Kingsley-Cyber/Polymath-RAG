-- COGNITIVE-ADAPTER-V1 (ADR-0018, plan COGNITIVE-ADAPTER-TRAIL-E2E-V1 E2) — 2026-09-13
--
-- The adapter run is a NEW durable authority next to the ingestion run. E0 (11.258) proved the
-- existing tables cannot host it: `runs.corpus_id` is NOT NULL and its status CHECK is the ingestion
-- lifecycle; `artifacts`, `receipts`, `outbox_events` and `stage_tickets` all REFERENCE runs(run_id);
-- `stage_tickets` has no per-step payload/schema column and UNIQUE(run_id, stage, generation) forbids
-- re-entering a step type (the BRANCH loop). So: three additive tables, no change to any existing one.
--
--   adapter_runs     one row per adapter run: identity + versions (plan §4), the transition state the
--                    pure core needs (shared/polymath_shared/adapter/transitions.py:RunState), the
--                    worker lease, typed failure/gap, idempotency.
--   adapter_steps    one row per ISSUED step (run_id, sequence): the issued AdapterStepV1, the agent's
--                    submission or the automatic output, the AdapterStepReceiptV1, and the
--                    ExternalOperationReceiptV1 reference for EXTERNAL_OPERATION steps (E4).
--   adapter_results  the terminal AdapterResultV1 (one per run) with its content hash.
--
-- Rollback (owner-run, destructive): DROP TABLE adapter_results, adapter_steps, adapter_runs;
-- Replay proof: applied to a freshly migrated empty database (CI shape) and to the dev store — see
-- docs/wiki/work-log/2026-09-13-cognitive-adapter-e2-substrate.md.
CREATE TABLE IF NOT EXISTS adapter_runs (
    run_id                   TEXT PRIMARY KEY,
    adapter_id               TEXT NOT NULL,
    adapter_version          TEXT NOT NULL,
    workflow_version         TEXT NOT NULL,
    retrieval_policy_version TEXT NOT NULL,
    input_schema_version     TEXT NOT NULL,
    output_schema_version    TEXT NOT NULL,
    status                   TEXT NOT NULL CHECK (status IN ('created','running','awaiting_agent','completed','terminal_gap','cancelled','failed')),
    current_step_id          TEXT,
    sequence                 INTEGER NOT NULL DEFAULT 0,
    steps_accepted           INTEGER NOT NULL DEFAULT 0,
    branch_loops             INTEGER NOT NULL DEFAULT 0,
    agent_reason_count       INTEGER NOT NULL DEFAULT 0,
    external_operation_count INTEGER NOT NULL DEFAULT 0,
    input                    JSONB NOT NULL,
    request_options          JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure                  JSONB,
    gap                      JSONB,
    agent_identity           TEXT,
    idempotency_key          TEXT UNIQUE,
    lease_owner              TEXT,
    lease_expires_at         TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    terminal_at              TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS adapter_runs_claimable_idx ON adapter_runs (lease_expires_at) WHERE status = 'running';
CREATE INDEX IF NOT EXISTS adapter_runs_adapter_idx ON adapter_runs (adapter_id, created_at DESC);

CREATE TABLE IF NOT EXISTS adapter_steps (
    run_id             TEXT NOT NULL REFERENCES adapter_runs(run_id) ON DELETE CASCADE,
    sequence           INTEGER NOT NULL,
    step_id            TEXT NOT NULL,
    step_type          TEXT NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('issued','accepted','rejected','executed','failed','skipped')),
    step               JSONB NOT NULL,      -- AdapterStepV1 as issued
    submission         JSONB,               -- AdapterSubmissionV1 (AGENT_REASON)
    output             JSONB,               -- accepted payload / automatic output
    receipt            JSONB,               -- AdapterStepReceiptV1
    external_operation JSONB,               -- ExternalOperationReceiptV1 (EXTERNAL_OPERATION)
    started_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at           TIMESTAMPTZ,
    PRIMARY KEY (run_id, sequence)
);

CREATE TABLE IF NOT EXISTS adapter_results (
    run_id      TEXT PRIMARY KEY REFERENCES adapter_runs(run_id) ON DELETE CASCADE,
    result      JSONB NOT NULL,             -- AdapterResultV1
    result_hash TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

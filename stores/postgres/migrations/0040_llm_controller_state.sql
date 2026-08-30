-- 0040: LOCAL-LLM-EXTRACTION-V1 — durable adaptive-controller state.
-- The AIMD limiters (cloud concurrency, local batch-token budget) lived in
-- worker-process memory: every restart reset them to the yaml seed, so the
-- controller never held the ceiling it had found ("amnesiac AIMD",
-- 2026-08-29). Postgres is the control plane: the effective limit is
-- written on every change and restored when a lane is created.
-- One row per controller key (e.g. 'llm_cloud[default]',
-- 'llm_local:batch_tokens'); state is the controller's own JSON.

CREATE TABLE IF NOT EXISTS llm_controller_state (
    key         TEXT PRIMARY KEY,
    state       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

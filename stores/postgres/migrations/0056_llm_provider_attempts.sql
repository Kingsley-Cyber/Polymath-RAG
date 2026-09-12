-- PROVIDER-ATTEMPT-LEDGER-V1 (conformance audit §5)
--
-- The gap this closes, measured 2026-09-11: a pMAP batch recorded terminal state
-- SUCCESS while the run had issued 181 HTTP 429s. In-run cross-lane failover retries a
-- refused lane on the next lane and only the FINAL outcome reaches
-- document_parent_map_batches, so per-attempt provider pressure was invisible to every
-- durable counter, to the control plane, and to the backfill's own stop conditions.
--
-- One row per PROVIDER ATTEMPT. A function outcome is the reduction of its attempts,
-- never a substitute for them. No credential is ever stored — `account_env` is the
-- environment variable NAME, exactly as the control plane already exposes it.
CREATE TABLE IF NOT EXISTS llm_provider_attempts (
    attempt_id      BIGSERIAL PRIMARY KEY,
    correlation_id  TEXT,                 -- groups the attempts of one logical call
    run_id          TEXT,
    ticket_id       TEXT,
    function        TEXT,                 -- GRAPH_EXTRACTION | DOCUMENT_PROFILE | PMAP | CHAT | ...
    stage           TEXT,
    lane            TEXT NOT NULL,
    provider        TEXT,
    model           TEXT,
    account_env     TEXT,                 -- ENV NAME ONLY, never a secret
    attempt_ordinal INT  NOT NULL DEFAULT 1,

    limiter_admitted BOOLEAN NOT NULL,    -- false => zero HTTP, zero quota
    http_dispatched  BOOLEAN NOT NULL,
    http_status      INT,
    retry_after_s    DOUBLE PRECISION,
    error_class      TEXT,                -- normalized: HTTP_429 / LIMITER_REFUSED / ...
    success          BOOLEAN NOT NULL DEFAULT FALSE,

    latency_ms       INT,
    response_hash    TEXT,
    tokens_in        INT,
    tokens_out       INT,

    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS llm_provider_attempts_time_idx   ON llm_provider_attempts (created_at DESC);
CREATE INDEX IF NOT EXISTS llm_provider_attempts_lane_idx   ON llm_provider_attempts (lane, created_at DESC);
CREATE INDEX IF NOT EXISTS llm_provider_attempts_fn_idx     ON llm_provider_attempts (function, created_at DESC);
CREATE INDEX IF NOT EXISTS llm_provider_attempts_corr_idx   ON llm_provider_attempts (correlation_id);
CREATE INDEX IF NOT EXISTS llm_provider_attempts_status_idx ON llm_provider_attempts (http_status) WHERE http_status IS NOT NULL;

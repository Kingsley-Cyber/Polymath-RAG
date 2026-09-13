-- PROVIDER-ATTEMPT-LEDGER-V4 — the state the ledger could not express (2026-09-12)
--
-- 0056 documented `limiter_admitted = false => zero HTTP, zero quota`. That invariant
-- is true for every seam that goes THROUGH a lane limiter, and it made two real seams
-- unrecordable rather than merely unrecorded:
--
--   * LLMExtractionClient.probe()  — a one-token liveness/auth call that bypasses the
--     limiter by design (a probe must not wait behind a rate hold).
--   * _litellm_generate()          — chat answer synthesis, which dispatches to paid
--     models (anthropic/deepseek-v4-flash-0731 and friends) with no lane limiter at all.
--
-- Recording either as limiter_admitted=false would assert "zero HTTP, zero quota" about
-- a call that really did hit a provider and really did spend; recording it as true would
-- assert an admission that never happened. Both are false, so both seams stayed silent —
-- which is why §15's own LIMITER_BYPASS detection had nothing to detect with.
--
-- Additive and nullable-by-default: existing rows are all limiter-mediated, so FALSE is
-- the correct value for every one of them. No data is rewritten, nothing is dropped.
ALTER TABLE llm_provider_attempts
    ADD COLUMN IF NOT EXISTS limiter_bypassed BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN llm_provider_attempts.limiter_admitted IS
    'Did the LANE LIMITER admit this attempt? false => zero HTTP, zero quota — but ONLY '
    'when limiter_bypassed is false. Read "refused" as (NOT limiter_admitted AND NOT '
    'limiter_bypassed).';
COMMENT ON COLUMN llm_provider_attempts.limiter_bypassed IS
    'This seam does not go through a lane limiter at all (probe, chat synthesis). '
    'limiter_admitted is then not applicable rather than false.';

CREATE INDEX IF NOT EXISTS llm_provider_attempts_bypass_idx
    ON llm_provider_attempts (lane, created_at DESC) WHERE limiter_bypassed;

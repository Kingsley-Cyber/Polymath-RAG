-- REFIRE-EVIDENCE-V1 (§17 / §23 "Re-fire") — 2026-09-12
--
-- The authority requires that production verification "can execute twice using the same
-- commands without source edits". Running it twice satisfies that; PROVING it did is a
-- different thing, and nothing recorded it — the evidence lived in a terminal scrollback
-- and in the agent's own claim that it had re-fired.
--
-- One row per completed run of scripts/verify_final_state.py: which commit it ran at,
-- and the verdict of every gate. A second run at the same commit can then be COMPARED
-- with the first, which makes two failure modes visible that a single run cannot show:
--   * the verification is not reproducible (same commit, different verdicts);
--   * the verification was never actually re-fired at this commit.
--
-- Additive, append-only, and outside the repository tree, so recording a run does not
-- dirty the worktree that the delivery gate inspects.
CREATE TABLE IF NOT EXISTS verification_runs (
    run_id       BIGSERIAL PRIMARY KEY,
    commit_sha   TEXT        NOT NULL,
    worktree_dirty BOOLEAN   NOT NULL DEFAULT FALSE,
    verdicts     JSONB       NOT NULL,   -- {gate_name: status}
    counts       JSONB       NOT NULL,   -- {PASS: n, FAIL: n, ...}
    finished_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS verification_runs_commit_idx
    ON verification_runs (commit_sha, finished_at DESC);

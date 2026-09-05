-- 0053 — MEDIC-V1 (2026-09-05): every autonomous repair the control plane makes is a receipt.
CREATE TABLE IF NOT EXISTS medic_actions (
    action_id  bigserial PRIMARY KEY,
    at         timestamptz NOT NULL DEFAULT now(),
    kind       text NOT NULL,          -- CAPACITY_REARM | CAPACITY_REARM_REFUSED | DEADLOCK_BREAK
    target     text NOT NULL,          -- ticket_id or backend pid
    detail     jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS medic_actions_at_idx ON medic_actions (at DESC);
CREATE INDEX IF NOT EXISTS medic_actions_kind_target_idx ON medic_actions (kind, target, at DESC);

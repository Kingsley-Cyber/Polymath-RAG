-- 0011: semantic-query-policy-v1 provenance on mentions.
-- Temporal durability: raw provider labels are preserved verbatim
-- alongside the canonical mapping; every mention records which query
-- policy version produced it and how the span was discovered
-- (discovery | boundary_rescue | missing_argument_rescue |
-- type_reconciliation). Existing rows keep NULL raw_label (they were
-- produced before the policy existed; their canonical core_type
-- remains authoritative).
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS raw_label TEXT;
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS query_policy_version TEXT;
ALTER TABLE mentions ADD COLUMN IF NOT EXISTS pass_kind TEXT;

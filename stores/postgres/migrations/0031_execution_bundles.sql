-- EXECUTION-BUNDLE-FENCE-V1
-- Every durable execution carries the identity of the exact
-- code+configuration that produced it. worker_registrations gains the
-- boot-time bundle; a dedicated table pins one fleet-active bundle per
-- boot generation so claim-time comparison is O(1) and drift is
-- attributable. Output stamping uses facts.provenance JSONB (no column
-- change) and later artifact tables include generated_by_bundle_hash
-- from day one.

ALTER TABLE worker_registrations
    ADD COLUMN IF NOT EXISTS execution_bundle_hash text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS execution_bundle jsonb NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS execution_bundles (
    bundle_hash      text PRIMARY KEY,
    git_sha          text NOT NULL DEFAULT '',
    tree_dirty       boolean NOT NULL DEFAULT false,
    semantic_authority text NOT NULL DEFAULT '',
    rule_pack_file   text NOT NULL DEFAULT '',
    ontology_file    text NOT NULL DEFAULT '',
    config           jsonb NOT NULL DEFAULT '{}',
    registered_at    timestamptz NOT NULL DEFAULT now(),
    last_seen_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS worker_registrations_bundle_idx
    ON worker_registrations (execution_bundle_hash, status);

-- 0035: QUERY-SCOPE-V1 (owner decision 2026-08-25).
--
-- Scope is EXPLICIT and FAILS CLOSED: no implicit all-corpus search.
-- Corpora carry a durable classification so ordinary production
-- queries never silently include evaluation/fixture/probe mass.
--
--   purpose        production | evaluation | fixture | probe
--   query_enabled  true | false
--
-- Backfill policy (measured, fail-closed):
--   * EVERY existing corpus starts as probe / not query-enabled;
--   * sealed + qualification/fixture families become evaluation /
--     fixture respectively;
--   * an explicit allowlist of REAL user-material corpora is promoted
--     to production + query-enabled.
-- Promoting anything else later is one UPDATE; leaking is a defect.

ALTER TABLE corpora
    ADD COLUMN purpose text NOT NULL DEFAULT 'probe',
    ADD COLUMN query_enabled boolean NOT NULL DEFAULT false;

CREATE INDEX corpora_scope_idx ON corpora (purpose, query_enabled);

-- sealed holdouts are evaluation material, explicitly requestable.
UPDATE corpora SET purpose='evaluation'
 WHERE corpus_id IN ('smq1-sealed-v1','smq3-biomed-v1');

-- frozen fixture/qualification families are evaluation material.
UPDATE corpora SET purpose='fixture'
 WHERE corpus_id LIKE 'i%' AND (corpus_id LIKE 'i_-_%' OR corpus_id LIKE 'i__-%');
UPDATE corpora SET purpose='evaluation'
 WHERE corpus_id IN (
   'e3-qualification-corpus','i2-qualification-corpus',
   'i4-fresh-acceptance-v1','kimi-dev-matrix-v1',
   'polymath-validation-v1','scale-10k-v1','core-3-v1',
   's-validation-parity-v1','s-validation-parity-v2',
   's-validation-v1-shadow','s-val-doc01-cutover-v1',
   's-val-doc01-cutover-v2','s-val-doc01-cutover-v3',
   's-val-doc01-enforce-v1','s-val-doc01-fence-v1');

-- persistent named workspaces for WORKSPACE scope mode.
CREATE TABLE query_workspaces (
    workspace_id text PRIMARY KEY,
    corpus_ids   jsonb NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- production allowlist: REAL user material only.
UPDATE corpora SET purpose='production', query_enabled=true
 WHERE corpus_id IN (
   'release-books-v1',
   'wedding-niche-v1',
   'shopify-mcp-transcript-v1',
   'hooks-transcript-v1',
   'ga-addtocart-transcript-v1',
   'psych-working-memory-v1');

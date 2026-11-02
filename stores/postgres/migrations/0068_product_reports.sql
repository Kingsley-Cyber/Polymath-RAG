-- PRODUCT-DECISION-REPORT-V1 (B4b, plan docs/wiki/plans/PRODUCT-DECISION-REPORT-V1.md §4.6) — 2026-11-02
-- One HTML decision report per product search, stored PRIVATELY per user (the owner's decision of 2026-11-02).
--
--   product_reports         one row per report: the start request, the candidates, the host data (CJ + eBay), the decision
--                           model, the compiled HTML, the agent's verdicts, the upload capabilities and their report-level
--                           expiry (6 h), the current fetch round, when the last compile started. `upload_tokens` holds ONLY
--                           the sha256 of every upload token minted for the report ([{sha256, minted_at, used_at}]: one at
--                           start, then at most one a minute for a status caller without a token — contract C1; at most 30,
--                           the least recently minted-or-used dropped first): a raw token is shown once and never stored; a
--                           token is not one-time — any held token uploads until the report expires. (Plan §4.6 names a single
--                           `upload_token_sha256`: the list is a deviation reported to the owner.) `compile_started_at`: a
--                           `compiling` report older than the service's limit by it was lost and may compile again (C9).
--                           `owner_principal_id` NULL = the owner / a trusted-local caller; NULL never means "open to every
--                           principal" (the rule of adapter_runs.owner_principal_id, 0066): a principal reaches only its own
--                           rows, the owner every row.
--   product_report_uploads  one row per uploaded fetch packet: PRIMARY KEY (report_id, packet_id), so a re-upload of a packet
--                           replaces its row (idempotent); the round, source and kind of the packet, its size and sha256, the
--                           parse status, the parsed records and the refusals.
--
-- Additive: two new tables, no change to any existing one. Replay-safe: every statement is IF NOT EXISTS. This file was edited
-- in place before its first deploy; the closing ALTER brings a database that ran an earlier draft (without `compile_started_at`)
-- to the same shape.
-- Rollback (owner-run, destructive): DROP TABLE IF EXISTS product_report_uploads; DROP TABLE IF EXISTS product_reports;
CREATE TABLE IF NOT EXISTS product_reports (
    report_id           TEXT PRIMARY KEY CHECK (report_id ~ '^rpt_[0-9a-f]{24}$'),
    owner_principal_id  TEXT NULL,
    status              TEXT NOT NULL DEFAULT 'collecting' CHECK (status IN ('collecting','compiling','compiled','failed')),
    request             JSONB NOT NULL,
    candidates          JSONB NOT NULL DEFAULT '{}'::jsonb,
    host                JSONB,
    model               JSONB,
    html                TEXT,
    verdicts            JSONB,
    upload_tokens       JSONB NOT NULL CHECK (jsonb_typeof(upload_tokens) = 'array'
                                              AND jsonb_array_length(upload_tokens) BETWEEN 1 AND 30
                                              AND NOT jsonb_path_exists(upload_tokens,
                                                    '$[*] ? (!(exists (@.sha256)) || !(@.sha256 like_regex "^[0-9a-f]{64}$"))')),
    upload_expires_at   TIMESTAMPTZ NOT NULL,
    round               INTEGER NOT NULL DEFAULT 1 CHECK (round BETWEEN 1 AND 2),
    compile_started_at  TIMESTAMPTZ NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- a principal's own list, newest first; the owner's list of every report, newest first
CREATE INDEX IF NOT EXISTS product_reports_owner_created_idx ON product_reports (owner_principal_id, created_at DESC);
CREATE INDEX IF NOT EXISTS product_reports_created_idx       ON product_reports (created_at DESC);

CREATE TABLE IF NOT EXISTS product_report_uploads (
    report_id   TEXT NOT NULL REFERENCES product_reports(report_id) ON DELETE CASCADE,
    packet_id   TEXT NOT NULL,
    round       INTEGER NOT NULL CHECK (round BETWEEN 1 AND 2),
    source      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    bytes       INTEGER NOT NULL CHECK (bytes BETWEEN 0 AND 2097152),
    sha256      TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    status      TEXT NOT NULL,
    parsed      JSONB,
    refused     JSONB,
    PRIMARY KEY (report_id, packet_id)
);
-- an earlier draft of this migration had no `compile_started_at` (a no-op wherever the CREATE above made it)
ALTER TABLE product_reports ADD COLUMN IF NOT EXISTS compile_started_at TIMESTAMPTZ;

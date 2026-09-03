-- QUERY-RECEIPTS-V1 (2026-09-03): one durable row per served query (/chat,
-- /ask, /retrieve). Before this the only trace of a query was an access-log
-- line and runtime_signals.last_query — no latency, scope, mode, verdict,
-- citations or error survived the request. Written best-effort in its own
-- short transaction AFTER the response is composed; never on the request's
-- critical path.
CREATE TABLE IF NOT EXISTS query_receipts (
    query_id        text        PRIMARY KEY,
    kind            text        NOT NULL,          -- chat | ask | retrieve
    received_at     timestamptz NOT NULL DEFAULT now(),
    client          text,                          -- user-agent head (MCP / UI / curl)
    corpus_ids      text[]      NOT NULL DEFAULT '{}',
    scope           text,                          -- corpus | workspace | all_authorized
    mode            text,                          -- FAST | HYBRID | GRAPH
    latent          boolean,
    question_sha256 text        NOT NULL,
    question_head   text        NOT NULL,          -- first 200 chars
    wall_ms         integer     NOT NULL,
    status          text        NOT NULL,          -- ok | abstained | error
    verdict         text,
    citations       integer,
    claims          integer,
    evidence        integer,
    source_docs     text[]      NOT NULL DEFAULT '{}',
    meta            jsonb       NOT NULL DEFAULT '{}'::jsonb,
    error           text
);
CREATE INDEX IF NOT EXISTS query_receipts_received_idx ON query_receipts (received_at DESC);
CREATE INDEX IF NOT EXISTS query_receipts_kind_idx     ON query_receipts (kind, received_at DESC);

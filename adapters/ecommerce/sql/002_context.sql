-- v2 (docs/10): frozen ContextEnvelopes. Crash-resume must return not only the
-- same pending action but the SAME execution context (reasoning replay
-- stability). One envelope per action; envelopes are write-once.
CREATE TABLE IF NOT EXISTS context_envelopes (
  action_id TEXT PRIMARY KEY REFERENCES actions(action_id),
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  graph_node TEXT NOT NULL,
  context_hash TEXT NOT NULL,
  manifest_json TEXT NOT NULL,
  envelope_json TEXT NOT NULL,
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_envelopes_run ON context_envelopes(run_id);

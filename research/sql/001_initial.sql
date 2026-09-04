-- Opportunity-research loop memory v1 (docs/03). SQLite = workflow state,
-- never knowledge authority. Types/uniqueness/atomicity live here; meaning,
-- policy and transitions live in Python (no SQL business logic, no triggers).
CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'running',
  terminal_reason TEXT,
  verdict TEXT,
  current_graph_node TEXT,
  revision INTEGER NOT NULL DEFAULT 0,
  cycle INTEGER NOT NULL DEFAULT 0,
  objective TEXT,
  control_graph_hash TEXT, loop_spec_hash TEXT, policy_hash TEXT,
  schemas_hash TEXT, prompts_hash TEXT, registry_build TEXT,
  no_progress_cycles INTEGER NOT NULL DEFAULT 0,
  progress_signature TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, terminal_at TEXT);

CREATE TABLE IF NOT EXISTS work_nodes (
  node_id TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES runs(run_id),
  node_type TEXT NOT NULL, status TEXT, authority_class TEXT,
  semantic_hash TEXT, payload_json TEXT NOT NULL,
  created_cycle INTEGER, updated_cycle INTEGER,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY (run_id, node_id));

CREATE TABLE IF NOT EXISTS work_edges (
  edge_id TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES runs(run_id),
  from_node_id TEXT NOT NULL, to_node_id TEXT NOT NULL,
  relationship TEXT NOT NULL, basis_type TEXT, authority_class TEXT,
  evidence_refs_json TEXT, unsupported INTEGER DEFAULT 0, status TEXT,
  created_cycle INTEGER, created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, edge_id));

CREATE TABLE IF NOT EXISTS actions (
  action_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  graph_node TEXT NOT NULL, action_type TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'PENDING',
  request_json TEXT, result_hash TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  revision_at INTEGER,
  created_at TEXT NOT NULL, completed_at TEXT);
-- one logical writer per run: at most one live action
CREATE UNIQUE INDEX IF NOT EXISTS idx_actions_one_pending
  ON actions(run_id) WHERE status IN ('PENDING','RUNNING');

CREATE TABLE IF NOT EXISTS events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  sequence INTEGER NOT NULL,
  event_type TEXT NOT NULL, actor TEXT,
  subject_id TEXT, action_id TEXT,
  payload_json TEXT, payload_hash TEXT,
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, sequence);

CREATE TABLE IF NOT EXISTS checks (
  check_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  subject_type TEXT, subject_id TEXT,
  check_type TEXT NOT NULL, policy_version TEXT,
  verification_level TEXT NOT NULL,
  status TEXT NOT NULL,
  metrics_json TEXT, reason_codes_json TEXT, input_hash TEXT,
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_checks_run ON checks(run_id, check_type);

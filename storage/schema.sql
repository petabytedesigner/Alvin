PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  event_type TEXT NOT NULL,
  module TEXT NOT NULL,
  instrument TEXT,
  correlation_id TEXT,
  ts_utc TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS errors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  module TEXT NOT NULL,
  message TEXT NOT NULL,
  payload_json TEXT
);

CREATE TABLE IF NOT EXISTS config_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  config_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS journal_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT NOT NULL,
  level TEXT NOT NULL,
  message TEXT NOT NULL,
  context_json TEXT
);

CREATE TABLE IF NOT EXISTS order_intents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  intent_id TEXT NOT NULL UNIQUE,
  dedupe_key TEXT NOT NULL,
  instrument TEXT NOT NULL,
  state TEXT NOT NULL,
  side TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_order_intents_state ON order_intents(state);
CREATE INDEX IF NOT EXISTS idx_order_intents_instrument ON order_intents(instrument);

CREATE TABLE IF NOT EXISTS decision_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id TEXT NOT NULL UNIQUE,
  candidate_id TEXT NOT NULL,
  ts_utc TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reconciliation_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL UNIQUE,
  ts_utc TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shadow_evaluations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id TEXT NOT NULL,
  instrument TEXT NOT NULL,
  decision TEXT NOT NULL,
  hypothetical_outcome TEXT NOT NULL,
  notes_json TEXT,
  ts_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  intent_id TEXT NOT NULL,
  status TEXT NOT NULL,
  submitted INTEGER NOT NULL,
  broker_http_status INTEGER NOT NULL,
  broker_order_id TEXT,
  reasons_json TEXT NOT NULL,
  details_json TEXT NOT NULL,
  ts_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_results_intent_id ON execution_results(intent_id);
CREATE INDEX IF NOT EXISTS idx_execution_results_status ON execution_results(status);

CREATE TABLE IF NOT EXISTS intent_state_transitions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  intent_id TEXT NOT NULL,
  previous_state TEXT NOT NULL,
  next_state TEXT NOT NULL,
  allowed INTEGER NOT NULL,
  reasons_json TEXT NOT NULL,
  details_json TEXT NOT NULL,
  ts_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_intent_state_transitions_intent_id ON intent_state_transitions(intent_id);
CREATE INDEX IF NOT EXISTS idx_intent_state_transitions_next_state ON intent_state_transitions(next_state);

CREATE TABLE IF NOT EXISTS execution_audits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  intent_id TEXT NOT NULL,
  correlation_id TEXT NOT NULL,
  instrument TEXT NOT NULL,
  side TEXT NOT NULL,
  previous_state TEXT NOT NULL,
  next_state TEXT NOT NULL,
  execution_category TEXT NOT NULL,
  accepted INTEGER NOT NULL,
  payload_json TEXT NOT NULL,
  ts_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_audits_intent_id ON execution_audits(intent_id);
CREATE INDEX IF NOT EXISTS idx_execution_audits_category ON execution_audits(execution_category);

CREATE TABLE IF NOT EXISTS retry_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  intent_id TEXT NOT NULL,
  should_retry INTEGER NOT NULL,
  retry_after_seconds INTEGER NOT NULL,
  max_attempts INTEGER NOT NULL,
  reason TEXT NOT NULL,
  details_json TEXT NOT NULL,
  ts_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_retry_decisions_intent_id ON retry_decisions(intent_id);

CREATE TABLE IF NOT EXISTS scan_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scan_id TEXT NOT NULL UNIQUE,
  instrument TEXT NOT NULL,
  session TEXT NOT NULL,
  stage TEXT NOT NULL,
  allowed INTEGER NOT NULL,
  stage_group TEXT NOT NULL,
  primary_reason TEXT,
  correlation_id TEXT,
  ts_utc TEXT NOT NULL,
  request_json TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  result_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scan_runs_instrument ON scan_runs(instrument);
CREATE INDEX IF NOT EXISTS idx_scan_runs_stage ON scan_runs(stage);
CREATE INDEX IF NOT EXISTS idx_scan_runs_allowed ON scan_runs(allowed);
CREATE INDEX IF NOT EXISTS idx_scan_runs_ts_utc ON scan_runs(ts_utc);

CREATE TABLE IF NOT EXISTS payload_previews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  preview_id TEXT NOT NULL UNIQUE,
  scan_id TEXT NOT NULL,
  intent_id TEXT,
  instrument TEXT NOT NULL,
  allowed INTEGER NOT NULL,
  units INTEGER,
  order_type TEXT,
  stop_distance REAL,
  risk_amount REAL,
  payload_json TEXT NOT NULL,
  ts_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payload_previews_scan_id ON payload_previews(scan_id);
CREATE INDEX IF NOT EXISTS idx_payload_previews_intent_id ON payload_previews(intent_id);
CREATE INDEX IF NOT EXISTS idx_payload_previews_instrument ON payload_previews(instrument);

CREATE TABLE IF NOT EXISTS scan_decision_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id TEXT NOT NULL UNIQUE,
  scan_id TEXT NOT NULL,
  instrument TEXT NOT NULL,
  stage TEXT NOT NULL,
  candidate_id TEXT,
  intent_id TEXT,
  payload_preview_id TEXT,
  ts_utc TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scan_decision_snapshots_scan_id ON scan_decision_snapshots(scan_id);
CREATE INDEX IF NOT EXISTS idx_scan_decision_snapshots_instrument ON scan_decision_snapshots(instrument);

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

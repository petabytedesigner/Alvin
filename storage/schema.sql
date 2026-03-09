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

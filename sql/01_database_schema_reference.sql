-- Reference design; Codex must implement and migrate a working SQLite schema.
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS run (
  run_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, started_at TEXT NOT NULL,
  finished_at TEXT, status TEXT NOT NULL, config_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ingest_source (
  ingest_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES run(run_id),
  source_name TEXT NOT NULL, source_file TEXT NOT NULL, source_sha256 TEXT NOT NULL,
  source_snapshot TEXT NOT NULL, source_row_count INTEGER NOT NULL,
  imported_at TEXT NOT NULL,
  UNIQUE(run_id, source_name, source_sha256)
);
CREATE TABLE IF NOT EXISTS raw_row (
  raw_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ingest_id TEXT NOT NULL REFERENCES ingest_source(ingest_id),
  source_line_number INTEGER NOT NULL, business_key TEXT,
  raw_json TEXT NOT NULL,
  UNIQUE(ingest_id, source_line_number)
);
CREATE TABLE IF NOT EXISTS finding (
  finding_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES run(run_id),
  ingest_id TEXT, raw_row_id INTEGER, source_name TEXT NOT NULL,
  record_id TEXT NOT NULL, rule_id TEXT NOT NULL, rule_version INTEGER NOT NULL,
  severity TEXT NOT NULL, observed_value TEXT, expected_value TEXT,
  message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN', created_at TEXT NOT NULL,
  UNIQUE(run_id,source_name,record_id,rule_id,rule_version,raw_row_id)
);
CREATE TABLE IF NOT EXISTS review_event (
  event_id TEXT PRIMARY KEY, finding_id TEXT NOT NULL REFERENCES finding(finding_id),
  actor TEXT NOT NULL, old_status TEXT NOT NULL, new_status TEXT NOT NULL,
  reason TEXT NOT NULL, occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_key ON raw_row(business_key);
CREATE INDEX IF NOT EXISTS ix_finding_rule ON finding(rule_id,status);

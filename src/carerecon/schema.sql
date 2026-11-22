CREATE TABLE run (
    run_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    current_date TEXT NOT NULL,
    previous_date TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('INGESTED','COMPLETE','FAILED')),
    policy TEXT NOT NULL,
    config_sha256 TEXT NOT NULL,
    rule_manifest TEXT NOT NULL,
    contract_manifest TEXT NOT NULL
);

CREATE TABLE run_event (
    event_id INTEGER PRIMARY KEY,
    run_id TEXT REFERENCES run,
    batch_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    outcome TEXT NOT NULL,
    detail TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE TABLE run_stage (
    run_id TEXT NOT NULL REFERENCES run,
    stage TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    PRIMARY KEY (run_id, stage)
);

CREATE TABLE ingest_source (
    ingest_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES run,
    source_name TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_snapshot TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    source_row_count INTEGER NOT NULL DEFAULT -1,
    malformed_count INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL,
    contract_version INTEGER NOT NULL,
    headers TEXT NOT NULL,
    unexpected_columns TEXT NOT NULL,
    UNIQUE (run_id, source_name)
);

CREATE TABLE raw_row (
    raw_row_id INTEGER PRIMARY KEY,
    ingest_id TEXT NOT NULL REFERENCES ingest_source,
    source_line_number INTEGER NOT NULL,
    end_line_number INTEGER NOT NULL,
    business_key TEXT,
    raw_json TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    raw_paid_cents INTEGER,
    UNIQUE (ingest_id, source_line_number)
);

CREATE INDEX raw_business_key ON raw_row(ingest_id, business_key);

CREATE TABLE typed_row (
    raw_row_id INTEGER PRIMARY KEY REFERENCES raw_row,
    values_json TEXT NOT NULL,
    payer_claim_id TEXT,
    paid_cents INTEGER,
    transaction_status TEXT,
    contract_valid INTEGER NOT NULL CHECK (contract_valid IN (0,1)),
    issues_json TEXT NOT NULL
);

CREATE INDEX typed_claim ON typed_row(payer_claim_id);

CREATE TABLE finding (
    finding_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES run,
    ingest_id TEXT NOT NULL REFERENCES ingest_source,
    source_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_version INTEGER NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('ERROR','WARN','REVIEW')),
    observed_value TEXT NOT NULL,
    expected_value TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX finding_run_rule ON finding(run_id, rule_id, record_id);

CREATE TABLE finding_evidence (
    finding_id TEXT NOT NULL REFERENCES finding,
    raw_row_id INTEGER NOT NULL REFERENCES raw_row,
    PRIMARY KEY (finding_id, raw_row_id)
);

CREATE TABLE review_event (
    event_id INTEGER PRIMARY KEY,
    finding_id TEXT NOT NULL REFERENCES finding,
    actor TEXT NOT NULL CHECK (length(trim(actor)) > 0),
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL CHECK (new_status IN ('OPEN','ACKNOWLEDGED','RESOLVED','WAIVED')),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    occurred_at TEXT NOT NULL
);

CREATE INDEX review_finding ON review_event(finding_id, event_id DESC);

CREATE VIEW finding_status AS
SELECT f.*,
       COALESCE(e.new_status, 'OPEN') AS status,
       COALESCE(e.reason, '') AS reason,
       COALESCE(e.actor, '') AS actor
FROM finding f LEFT JOIN review_event e ON e.event_id = (
    SELECT event_id FROM review_event WHERE finding_id = f.finding_id ORDER BY event_id DESC LIMIT 1
);

CREATE TABLE reconciliation (
    run_id TEXT NOT NULL REFERENCES run,
    payer_claim_id TEXT NOT NULL,
    expected_cents INTEGER,
    remitted_cents INTEGER,
    difference_cents INTEGER,
    status TEXT NOT NULL,
    remit_count INTEGER NOT NULL,
    posted_count INTEGER NOT NULL,
    evidence_json TEXT NOT NULL,
    PRIMARY KEY (run_id, payer_claim_id)
);

CREATE TABLE control_result (
    run_id TEXT NOT NULL REFERENCES run,
    source_name TEXT NOT NULL,
    source_sha256 TEXT,
    snapshot_date TEXT NOT NULL,
    control_dates TEXT NOT NULL,
    observed_rows INTEGER,
    expected_rows INTEGER,
    declared_minus_observed_rows INTEGER,
    observed_paid_cents INTEGER,
    expected_paid_cents INTEGER,
    declared_minus_observed_cents INTEGER,
    status TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    PRIMARY KEY (run_id, source_name)
);

CREATE TABLE snapshot_change (
    run_id TEXT NOT NULL REFERENCES run,
    payer_claim_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    current_date TEXT NOT NULL,
    previous_date TEXT NOT NULL,
    previous_rows INTEGER NOT NULL,
    current_rows INTEGER NOT NULL,
    previous_values TEXT NOT NULL,
    current_values TEXT NOT NULL,
    difference_cents INTEGER,
    evidence_json TEXT NOT NULL,
    PRIMARY KEY (run_id, payer_claim_id)
);

CREATE TABLE export_artifact (
    run_id TEXT NOT NULL REFERENCES run,
    artifact_path TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    bytes INTEGER NOT NULL,
    exported_at TEXT NOT NULL,
    PRIMARY KEY (run_id, artifact_path, artifact_sha256)
);

CREATE VIEW source_rows AS
SELECT i.run_id, i.source_name, i.source_file, i.source_sha256, i.snapshot_date,
       r.*, t.values_json, t.payer_claim_id, t.paid_cents, t.transaction_status,
       t.contract_valid, t.issues_json
FROM ingest_source i JOIN raw_row r USING (ingest_id) JOIN typed_row t USING (raw_row_id);

CREATE VIEW keyed_rows AS
SELECT *, COUNT(*) OVER (
    PARTITION BY ingest_id, business_key,
    CASE WHEN source_name='source_controls' THEN json_extract(values_json, '$.snapshot_date') END
) AS key_count
FROM source_rows;

CREATE VIEW quarantined_rows AS
SELECT k.* FROM keyed_rows k
WHERE k.contract_valid = 0
   OR (k.key_count > 1 AND k.source_name <> 'member_eligibility')
   OR EXISTS (
       SELECT 1 FROM finding_evidence e JOIN finding f USING (finding_id)
       WHERE e.raw_row_id = k.raw_row_id AND f.ingest_id = k.ingest_id
         AND f.severity = 'ERROR' AND (f.rule_id LIKE 'DQ%' OR f.rule_id LIKE 'RX%')
   );

CREATE VIEW clean_rows AS
SELECT s.* FROM source_rows s
WHERE s.raw_row_id NOT IN (SELECT raw_row_id FROM quarantined_rows);

CREATE TRIGGER source_no_update BEFORE UPDATE ON ingest_source WHEN OLD.source_row_count >= 0 BEGIN
    SELECT RAISE(ABORT, 'Imported source metadata is immutable');
END;
CREATE TRIGGER source_no_delete BEFORE DELETE ON ingest_source BEGIN
    SELECT RAISE(ABORT, 'Imported source metadata is immutable');
END;
CREATE TRIGGER raw_no_update BEFORE UPDATE ON raw_row BEGIN
    SELECT RAISE(ABORT, 'Raw rows are immutable');
END;
CREATE TRIGGER raw_no_delete BEFORE DELETE ON raw_row BEGIN
    SELECT RAISE(ABORT, 'Raw rows are immutable');
END;
CREATE TRIGGER typed_no_update BEFORE UPDATE ON typed_row BEGIN
    SELECT RAISE(ABORT, 'Typed rows are immutable');
END;
CREATE TRIGGER typed_no_delete BEFORE DELETE ON typed_row BEGIN
    SELECT RAISE(ABORT, 'Typed rows are immutable');
END;
CREATE TRIGGER finding_no_update BEFORE UPDATE ON finding BEGIN
    SELECT RAISE(ABORT, 'Original findings are immutable');
END;
CREATE TRIGGER finding_no_delete BEFORE DELETE ON finding BEGIN
    SELECT RAISE(ABORT, 'Original findings are immutable');
END;
CREATE TRIGGER evidence_no_update BEFORE UPDATE ON finding_evidence BEGIN
    SELECT RAISE(ABORT, 'Finding evidence is immutable');
END;
CREATE TRIGGER evidence_no_delete BEFORE DELETE ON finding_evidence BEGIN
    SELECT RAISE(ABORT, 'Finding evidence is immutable');
END;
CREATE TRIGGER review_no_update BEFORE UPDATE ON review_event BEGIN
    SELECT RAISE(ABORT, 'Review events are append-only');
END;
CREATE TRIGGER review_no_delete BEFORE DELETE ON review_event BEGIN
    SELECT RAISE(ABORT, 'Review events are append-only');
END;

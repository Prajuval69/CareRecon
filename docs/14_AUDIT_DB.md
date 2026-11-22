# SQLite evidence and audit

Start with `sql/01_database_schema_reference.sql` and extend schema for typed tables, reconciliation, snapshot changes, source contracts, export artifacts and status history. Enable foreign keys and transactions. Store CSV file SHA-256, per-source ingest ID, source line, run ID, rule version, actor and UTC time. Keep raw imports immutable and choose stable deterministic keys where feasible.

Use parameterized SQL rather than string-concatenated user values. Protect against duplicate ingestion and duplicate finding creation. Supply SQL migration/version metadata and database health check. Output paths must stay in working directory unless explicitly set by user.

# Offline architecture

Input directories -> CSV parser + immutable raw layer -> SQLite raw rows and typed staging -> versioned rule engine -> normalized finding table -> reconciliation + snapshot engine -> review-event audit -> CSV and standalone HTML reports. Use standard-library modules and `sqlite3` with transactions and foreign keys. A CLI is primary UX; dashboard or web app is optional and must not delay core deliverables.

Separate concerns: `cli.py` only parses args; `ingest.py` parses and fingerprints files; `contracts.py` checks columns and basic types; `rules.py` emits findings; `reconcile.py` compares normalized amounts; `snapshots.py` compares stable keys; `review.py` implements append-only status events; `reports.py` exports escaped files; `db.py` owns schema and transactions. Use ISO 8601 UTC timestamps and generated IDs. Write schema migrations or at least explicit schema version in SQLite.

# Source preservation, lineage and idempotency

On every import calculate SHA-256 for input bytes and source controls, record file path and snapshot, row count, import timestamp, run ID, batch ID. SQLite raw rows must retain original string values and 1-based CSV line number (line 1 is header). If same batch/source/hash is imported again, do not create duplicate raw rows or findings; provide a stable idempotent result. A changed file with same filename must be distinguishable by hash.

Use a transaction around each source import. If failure occurs, roll back that source import and write a concise failure event. Do not silence errors or discard rows. Support `--strict` and `--collect-errors` import policies; default preserves raw anomalies for later review.

# Excel-compatible and local HTML reporting

Required exports: `findings.csv` (rule_id, severity, source, record, raw location, observed, expected, status, reason), `reconciliation.csv` (payer claim, expected, remitted, difference, status), `source_controls.csv` (observed/expected rows and paid cents, deltas), `snapshot_changes.csv` (key, event type, previous/current values) and `summary.html` (source provenance, batch, totals, severity counts, important exceptions, operational next steps, interpretation disclaimers).

Outputs must be deterministic apart from timestamps, sorted stably, escaped against HTML injection and CSV spreadsheet formula injection. Required baseline is standards-compliant CSV that opens in Excel. `.xlsx` is a nice-to-have conditional on an optional already-installed library; don't block core on external packages. Include a copyable Word-report narrative in Markdown as a useful supplement.

# Required SQL competency demonstration

Ship documented SQL queries for: record counts, missing member/provider foreign keys, duplicate claims, paid/allowed check, denied-with-payment, remittance aggregation and mismatches, unmatched remittances, pharmacy valid/orphan reversals, raw source totals, prior/current key differences, findings by severity, review history. Include comments explaining joins and grain and a separate `docs/SQL_VALIDATION_NOTES.md` with expected results.

SQL query results for amount totals must agree with independent Python integer-based calculations on seeded examples. Expose `--sql-report` or a `sql` folder of executable queries against created typed tables. Do not confuse record counts with number of source import events.

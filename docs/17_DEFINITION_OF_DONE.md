# Definition of Done — strict

A finished project has a complete import/validate/reconcile/snapshot/review/export CLI, persistent SQLite data, machine-readable evidence, documented rule definitions, rerun idempotency, and reports. All 13 expected seeded anomalies must be detected with specified rule+record pairs exactly once per run. RX010 valid matched reversal must not trigger orphan-reversal or invalid-negative alerts. Source control mismatch +1 row and +1234 cents must be independently measured. P012 difference +275 cents; P099 disappearance must be review-only.

Tests must include negative and boundary cases, SQL/Python agreement, source lineage, schema issues, review audit, CSV/HTML security, CLI and reruns. Codex must run actual tests and record observed counts. A README with reproducible commands and explicit synthetic-data limitations is mandatory. Do NOT write resume bullets claiming finished functionality before passing these gates.

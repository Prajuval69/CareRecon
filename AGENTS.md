# AGENTS.md — CareRecon mandatory Codex engineering contract

This repository is a *starter kit*. The `starter/` files generate and verify demonstrative fixtures only. Implement a real, fully operational system under `src/carerecon/`; don't stop when the starter checks pass.

## Required sequence
1. Read `README_FIRST.md`, `prompts/MASTER_CODEX_PROMPT.md`, `docs/00_INDEX.md`, and all numbered docs.
2. Inspect provided raw CSVs, expected scenarios, configuration, SQL and tests. Keep the exact fixture anomaly IDs stable.
3. Implement the full CLI, typed source loaders, quality engine, reconciler, review state, SQLite evidence store, exports and tests.
4. Execute seeded fixtures, import, validate, reconcile, compare-snapshot, export, and automated tests.
5. Verify findings against `data/expected/seeded_scenarios.json`, including *negative test* that valid RX010 reversal is not incorrectly flagged.
6. Record observed execution in `deliverables/IMPLEMENTATION_STATUS.md`, exact test counts, limitations, and reproducible commands.

## Hard constraints
- Python 3.11+, core standard library `csv`, `sqlite3`, `decimal`, `argparse`, `datetime`, `hashlib`, `pathlib`, `logging`, `unittest`.
- No internet requirement after Python; no Docker, AWS, paid APIs, accounts, external DB, external patient data, or PHI.
- Synthetic data exclusively. Never claim HIPAA compliance, real-world insurance adjudication, or access to patient records.
- SQLite INTEGER cents or Python Decimal for money. Never binary floating point for exact amount comparison.
- Preserve raw input line number, source filename/hash, batch ID, run ID and record primary/business key.
- Invalid records must remain inspectable, not silently dropped; isolate quarantine from analytic clean views.
- Idempotent, atomic imports; no duplicate findings on rerun of the same run/source/rule/version.
- Distinguish hard rule violations from anomalies requiring review. Flag snapshot disappearances for review; they are not automatically deleted claims or fraud.
- Handle reversals/adjustments as legitimate when referencing a valid original; do not automatically reject negative amounts.
- Use exact joins at documented grain; do not duplicate claim paid totals when joining to provider remittances.
- Keep review history append-only with reason and actor; never overwrite prior decisions.
- Make no claims of production deployment, enterprise customer work, revenue recovery or real healthcare data.

## Quality gates (all required)
- 13 planted scenarios detected as described, with valid matched reversal RX010 not flagged as orphan or invalid negative amount.
- Reconciliation row-level report for both matching and mismatched remittance examples.
- Raw source control totals are compared and mismatches detected; do not hide mismatches by changing seed controls.
- Snapshot P099 disappearance flagged for review, not automatically deleted.
- Data dictionary, schema version, rule manifest, import lineage and human review audit present.
- Zero division-by-zero and robust handling of invalid dates, malformed CSVs, missing columns and empty batches.
- Cross-platform paths, safe local file writes, no hard-coded credentials.
- Python/SQL reconciliation calculations agree, and golden acceptance tests pass.
- Final README with commands and proof from observed runs.

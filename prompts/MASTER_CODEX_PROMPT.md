# MASTER CODEX PROMPT — BUILD CARE RECON END-TO-END

You are a senior Python data engineer, US payer-provider-pharmacy data quality analyst, SQL developer, QA engineer and technical writer. This project is an offline, synthetic, auditable data-quality and reconciliation platform for an entry-level **Milliman Healthcare Data Analyst Intern** portfolio. **Do the implementation**, not just a plan.

## Read-first contract
- Read `AGENTS.md`, `README_FIRST.md`, `docs/00_INDEX.md`, every `docs/*.md` numbered file, `config/*.json`, `sql/*.sql`, `data/expected/*.json`, and the generated fixture CSVs.
- Start by describing the planned module layout and mapping every acceptance criterion to tests. Then implement everything in `src/carerecon/`.
- Do not ask for credentials, AWS, Docker, APIs, an external database or healthcare datasets. Use ONLY synthetic examples provided here and Python 3.11+ standard library.

## Build the application
1. CLI package `python -m carerecon` (standard `PYTHONPATH=src` or optionally install with local packaging).
2. Commands: `init-db`, `ingest`, `validate`, `reconcile`, `compare-snapshot`, `list-findings`, `review`, `export`, `demo`, `verify`.
3. Ingest current and previous CSV sources preserving source file digest, row number, column values, batch IDs, rejected-row evidence, schema version, UTC timestamps. Reject missing required headers gracefully.
4. Define record grains and business keys explicitly for payer claims, provider remittances, pharmacy claims, eligibility, provider/pharmacy directory and source controls.
5. Rule engine driven by `config/rules.json`: active/inactive, version, severity, description, scope. Implement the 13 seeded scenarios with correct deterministic evidence. Implement coverage for valid exceptions such as matched prescription reversal RX010.
6. Reconcile payer_claims to provider_remittances at payer_claim_id grain; support unmatched, orphan and amount mismatch findings. Explain that a claim need not necessarily have a remit (pending state). Do not blindly require all claims to have matched remits.
7. Compare raw source row counts and paid cents to `source_controls.csv`, independent of curation. A mismatch is an exception, never silently corrected.
8. Compare current and prior snapshot by stable business key; missing P099 is a 'needs review' snapshot event, not proof of deletion or fraud. Duplicate current IDs must remain detected and not arbitrarily collapsed.
9. Track finding statuses `OPEN`, `ACKNOWLEDGED`, `RESOLVED`, `WAIVED`, with append-only review history, actor and rationale. Waiver never removes original finding. No arbitrary auto-waiver.
10. Persist all runs, imports, rows, findings, reconciliations, report artifacts and review events in SQLite. Use database transactions, uniqueness keys and foreign keys.
11. Export `findings.csv`, `reconciliation.csv`, `source_controls.csv`, `snapshot_changes.csv`, and `summary.html`; HTML must escape values and work offline. Include user-friendly metric definitions, row-count verification, limitation banners and batch metadata.
12. Provide reusable SQL queries for profiling, duplicates, orphan references, source totals, matching/mismatching remittances and finding status distribution. Validate SQL vs independent Python totals.
13. Fully automated `unittest` suite: one test per seeded scenario at minimum, clean-case negative tests, idempotent reruns, malformed files, dates, nulls, duplicate IDs, wrong signs, empty folders, prior snapshot, status review audit, graceful CLI errors, and output integrity.
14. Update `README.md` with setup, exact commands for Windows and Unix, sample output, architecture, demo workflow, screenshots or text artifacts, security disclaimers and actual test results.
15. Generate real demo artifacts in `deliverables/` and record commands and observed test output in `deliverables/IMPLEMENTATION_STATUS.md`.

## Input fixtures and golden contract
- Run `python starter/generate_fixtures.py --seed 2026`, `python starter/verify_fixtures.py`, `python -m unittest discover -s tests -p 'test_*.py' -v`.
- Review `data/expected/seeded_scenarios.json` and `docs/08_GOLDEN_FIXTURES.md` before implementing checks.
- Preserve IDs and expected findings. Do not edit fixtures just to make checks pass. Correct implementation must detect seeded data issues and avoid false positives on RX010.
- Use a local temporary test database so no tests depend on preexisting state. Idempotency tested by reimporting identical sources.

## Correctness principles
- Money is cents as integers or Decimal; compute raw controls *before* rejecting questionable records.
- Must distinguish medical claim (one row per claim) from provider remit (potentially multiple events); aggregate remits to claim once with explicit void/reversal semantics before comparing.
- Include row provenance and source hashes in every finding. Never leak confidential data (none should exist).
- Document all assumptions; do not mistake provider reimbursement mismatch for confirmed fraud.
- No claims of HIPAA certification, real insurance adjudication or professional deployment.
- Avoid unrelated complex ML; this project targets SQL/Python/data-validation/reporting in Milliman's JD.

## Acceptance conditions
- Run CLI demo end-to-end, produce reports, verify planted scenarios, inspect SQLite and files, execute full tests and report actual passing test count.
- Clearly state what was implemented, tested, simulated and unfinished. If blocked, leave accurate status and propose concrete fixes; no false completion claims.

## Suggested project structure
- `src/carerecon/__main__.py`, `cli.py`, `config.py`, `models.py`, `db.py`, `ingest.py`, `rules.py`, `reconcile.py`, `snapshots.py`, `review.py`, `reports.py`, `audit.py`, `utils.py`.
- `tests/test_ingest.py`, `test_rules.py`, `test_reconcile.py`, `test_controls.py`, `test_snapshots.py`, `test_reviews.py`, `test_reports.py`, `test_cli.py`.
- `sql/`, `data/`, `config/`, `docs/`, `deliverables/`.

**Implement working code now. The starter's generators and sample SQL are NOT the completed product.**

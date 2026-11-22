# CareRecon — Healthcare Data Quality & Reconciliation Engine (Codex starter)

**Purpose:** Build a job-relevant, offline, reproducible healthcare data engineering/analytics portfolio project for a Milliman Healthcare Data Analyst Intern application. This is **Project 2**, deliberately different from the **ClaimLens** claims analytics project: CareRecon is about multi-source reconciliation, data contracts, audit trails, exception workflows, and report-level accuracy—not building another claims KPI dashboard.

## Read this first
1. Open the folder in Codex, not just the ZIP preview.
2. Read `AGENTS.md`, then `prompts/MASTER_CODEX_PROMPT.md`, and `docs/00_INDEX.md`.
3. Paste `prompts/CODEX_START_MESSAGE.md` into Codex.
4. Codex must implement a real working application under `src/carerecon/` and produce validated test outputs; starter files are scaffolding, **not a completed solution**.

## Zero-cloud requirements
- Python 3.11 or newer; SQLite and Python standard library for the core pipeline.
- **No AWS, Docker, API keys, cloud services, paid services, external database, or real health records.**
- Runs on Windows with Command Prompt/PowerShell and on Linux/macOS after Python installation.
- Spreadsheet exports: Excel-compatible CSV required; `.xlsx` optional only when the library is installed, never a blocking dependency.

## Working starter verification (NOT finished implementation)
```bash
python starter/generate_fixtures.py --seed 2026
python starter/verify_fixtures.py
python -m unittest discover -s tests -p "test_*.py" -v
```

## What a finished build must deliver
- Source-preserving import, record-level traceability, strict schemas and versioned rules.
- Deterministic quality checks with severity and evidence; controlled exception review.
- Payer-versus-provider remittance reconciliation, control-total checks, pharmacy reversals, and prior-snapshot comparisons.
- Full run tracking, immutable audit events, rerun idempotency, snapshot comparisons, SQL and Python cross-checks.
- CSV exceptions, CSV reconciliation summaries, and a local human-readable HTML report.
- All seeded exceptions detected plus clean exceptions *not* falsely flagged.
- Passing tests and reproducible demo commands in the final README.

See `docs/17_DEFINITION_OF_DONE.md` before treating this as resume-ready.

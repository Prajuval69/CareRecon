# CareRecon

CareRecon is a local Python and SQLite application that checks synthetic healthcare extracts, compares payer payments with provider remittances, and gives an analyst evidence to review. Each finding links back to the file digest and CSV line that produced it.

## Run the demo

Use Python 3.11 or newer from the repository root. The project has no third-party runtime dependencies and runs offline. Choose the setup line for your shell.

| Shell | Setup |
| --- | --- |
| Windows PowerShell | `$env:PYTHONPATH = 'src'` |
| Windows Command Prompt | `set "PYTHONPATH=src"` |
| Linux or macOS | `export PYTHONPATH=src` |

On systems where the executable is called `python3`, use it in place of `python`.

```text
python starter/generate_fixtures.py --seed 2026
python starter/verify_fixtures.py
python -m carerecon demo --reset
python -m unittest discover -s tests -p "test_*.py" -v
```

The demo prints the run ID and absolute report paths. It writes `output/generated/carerecon.sqlite` and reports under `output/generated/reports`. Run `demo` without `--reset` to keep existing reviews. With `--reset`, the demo builds a fresh evidence database and replaces the specified database after success. Keep the demo database separate from working runs.

## Observed seed 2026 results

| Check | Result |
| --- | --- |
| Lineage | 78 raw records from 8 sources |
| Seeded scenarios | 13 of 13 detected exactly once |
| Matching remittances | P001, P002, P004, and P005 |
| P012 amount | 8,900 payer cents vs. 9,175 posted cents, a +275-cent difference |
| P003 and RM_ORPHAN | P003 remains ambiguous. RM_ORPHAN points to an absent payer claim. |
| Source controls | Payer declaration exceeds the raw count by 1 row. Pharmacy declaration exceeds raw paid cents by 1,234. |
| Prior-only key | P099 is flagged for review of extract scope. |
| RX010 | Matched RX002 at −1,400 cents and produced zero findings. |
| Automated tests | 75 passed, including 65 application tests and 10 starter fixture tests. |

The checked-in report bundle includes an acknowledged snapshot finding and a waived denial example with review history. [HTML summary](deliverables/reports/summary.html) · [Implementation status and logs](deliverables/IMPLEMENTATION_STATUS.md)

## Run each stage

The commands below use the default SQLite file. Add `--db PATH` to choose a separate database. Copy the value after `run_id=` into each occurrence of `RUN_ID`.

```text
python -m carerecon init-db
python -m carerecon ingest --batch manual-2026 --source-dir data/raw/current --snapshot-date 2026-05-31 --previous-date 2026-04-30
python -m carerecon validate --run RUN_ID
python -m carerecon reconcile --run RUN_ID
python -m carerecon compare-snapshot --run RUN_ID --current data/raw/current --previous data/raw/previous
python -m carerecon verify --run RUN_ID
python -m carerecon list-findings --run RUN_ID --status OPEN
python -m carerecon review --finding FINDING_ID --status ACKNOWLEDGED --actor demo-analyst --reason "Confirm the extract window."
python -m carerecon export --run RUN_ID --output output/generated/manual-reports
python -m carerecon sql-report --run RUN_ID
```

Copy a `finding_id` from the listing to run the review command. Acknowledged findings may be resolved, waived, or reopened. Resolved or waived findings can be reopened. Every transition requires an actor and reason. Repeating the latest decision with the same actor and reason is idempotent.

Use `verify --integrity-only` for a different synthetic batch. `verify` without that option checks seed 2026 against the expected scenarios. Run `python -m carerecon --help` or append `--help` to any command to see options.

## How it works

```text
Current CSVs ──> frozen file digests ──> raw records + typed staging
                                                 │
                              ┌──────────────────┴──────────────────┐
                              │                                     │
                contracts / quality / controls     payer-to-remittance comparison
                              │                                     │
Prior payer CSV ──> immutable snapshot comparison                    │
                              │                                     │
                              └───────────> SQLite evidence <───────┘
                                                    │
                                  review events + CSV / HTML reports
```

- Ingest fingerprints the exact source bytes. It commits the complete current batch or rolls it back. Collect-errors mode retains invalid records and line spans. `--strict` rolls back on malformed or ill-typed CSV rows. Missing headers, missing files, and invalid UTF-8 are import failures in either mode.
- The run pins the contract and rule manifests. Reimporting identical bytes under the same batch, dates, policy, and manifests reuses the run. Changed content or manifests create a new run. The prior file, once attached, stays pinned to that run. Use a new batch for a different prior file with otherwise identical inputs.
- Payer/remit comparison groups signed `POSTED` events by claim ID and excludes `VOID` events. Duplicate payer keys and incomplete payment evidence prevent a definitive comparison. Claims without usable posted activity can be pending or outside the remit extract.
- Source controls use raw records before quarantine. Snapshot comparison uses payer claim ID and reports added, changed, ambiguous, unchanged, incomplete, and disappeared keys.
- SQLite schema version 1 stores run events, typed values, evidence links, reviews, and export hashes. Each report is atomically replaced. Export again after review to refresh the displayed status.

| Reference | Contents |
| --- | --- |
| [Data dictionary](docs/04_DATA_DICTIONARY.md) | Source grains, lineage, and output fields |
| [Rule manifest](config/rules.json) | IDs, versions, severities, descriptions, and enabled flags |
| [Source contracts](config/source_contracts.json) | Required columns, types, keys, and nullable fields |
| [SQL validation notes](docs/SQL_VALIDATION_NOTES.md) | Runnable queries, independent calculations, and expected rows |
| [Analyst writeup](deliverables/ANALYST_FINDINGS.md) | Observed findings and review decisions |

## Troubleshooting and limits

- An unknown run usually means the command points at a different `--db` file. Each stage uses the same run ID and database.
- An incomplete amount control means the raw paid column could not be fully parsed or the CSV record boundaries were uncertain. Inspect the quarantine and source lineage exports before rerunning with a corrected synthetic extract.
- A busy database has a five-second lock timeout. Close competing writers and retry. Run `demo --reset` on a dedicated demo database while it is closed elsewhere.
- RX010 is a matched full reversal under the fixture convention. The comparison uses the explicit original transaction ID, matching pharmacy, chronology, and opposite cents. The fixture assigns different fabricated member and NDC values to RX010 and RX002. Member and NDC equality would require a revised fixture contract.
- All records, reviewers, and organizations are synthetic. The rules illustrate analyst workflows and have no authority for benefits, clinical decisions, fraud determinations, or regulatory compliance. The pipeline uses SQLite signed 64-bit integer cents and fails clearly on out-of-range calculations.

To exercise a larger synthetic batch, run `python scripts/load_test.py --size 10000` with the same shell setup. The script builds temporary CSVs and an evidence database without changing the seeded fixtures.

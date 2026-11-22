# CareRecon implementation status

The complete offline CLI and SQLite pipeline ran on Windows 11 with Python 3.12.4 and SQLite 3.45.3. The application code is under [`src/carerecon/`](../src/carerecon/). The verified evidence run used batch `evidence-2026` and run ID `1aaf06271841b46ba313d665b120c9418894f37cfd2729bcfc7e225a026e80cc`.

## Observed execution

| Gate | Evidence |
| --- | --- |
| Fixture integrity | Regenerated seed 2026, ran the starter verifier, and checked all eight CSVs plus the expected-scenarios JSON against their original SHA-256 hashes. |
| Complete workflow | Ran `demo --reset`, then exercised each manual stage. The evidence run reached `COMPLETE` with 8 imports, 78 raw and 78 typed rows, and 13 findings. |
| Reconciliation | 19 rows total. Four matched, one mismatched, one was ambiguous, one was orphaned, and 12 were pending or outside the observed remit activity. P012 was 9,175 minus 8,900 = +275 cents. |
| Source controls | Six comparisons. Payer count was 20 declared vs. 19 observed. Pharmacy payment control was 14,234 cents declared vs. 13,000 observed. The other four controls matched. |
| Snapshot | 19 keys in the union. Six added, 11 unchanged, one ambiguous, and one disappeared. P099 produced a REVIEW finding and was acknowledged for extract-window follow-up. |
| Review audit | Three appended events. P099 was acknowledged, and P010 was acknowledged and waived in the synthetic exercise. The audit retained both original findings. |
| SQL parity and database health | Independent SQL agreed with Python for every reconciliation row and all six raw controls. Ten named analyst queries executed. SQLite integrity was `ok`, with zero foreign-key violations. |
| Rerun integrity | The identical import reused its run ID. The rerun retained 8 imports, 78 raw rows, 13 findings, 3 review events, and 10 artifact versions. All 10 report hashes matched before and after rerun and matched the database. |
| Automated tests | **75 passed, zero failures or errors** in 5.771 seconds. This includes 65 application tests and 10 starter fixture tests. |
| Synthetic load | 10,000 additional claim/remit pairs, 20,078 raw rows total, and 10,000 additional zero-difference matches. All 10 exports and both SQL parity checks completed in 2.172 seconds on this execution. |

[CLI and evidence inspection log](DEMO_RUN_LOG.txt) · [Full test output](TEST_RUN_LOG.txt) · [Offline HTML result](reports/summary.html)

## Golden finding coverage

Each listed rule, source, and record combination appeared exactly once in the evidence run.

| Rule | Record | Observed evidence |
| --- | --- | --- |
| DQ001 | P003 | Two raw payer records had the same key. |
| DQ002 | P006 | Member ID was blank. |
| DQ003 | P007 | Provider PR999 was absent from the directory. |
| DQ004 | P008 | Service date was beyond M013's coverage. |
| DQ005 | P009 | Paid cents exceeded allowed cents by 550. |
| DQ006 | P010 | The denied record had 300 paid cents. |
| RC001 | P012 | Posted payment exceeded payer paid cents by 275. |
| RC002 | RM_ORPHAN | P_NO_SUCH_CLAIM was absent. |
| RX001 | RX003 | Dispense days supply was zero. |
| RX002 | RX004 | The reversal referenced RX_UNKNOWN. |
| CT001 | payer_claims | Declared count exceeded observed count by 1. |
| CT002 | pharmacy_claims | Declared amount exceeded observed amount by 1,234 cents. |
| SS001 | P099 | Prior-only key classified as REVIEW. |

RX010 matched the original RX002 with exactly opposite paid cents at the same pharmacy. It had zero findings, including zero invalid-day, orphan-reversal, and negative-payment findings. P001, P002, P004, and P005 had zero-difference remittances. P003 remained ambiguous throughout processing. [Finding CSV](reports/findings.csv) · [Reconciliation CSV](reports/reconciliation.csv) · [Review audit CSV](reports/review_history.csv)

## Reproduce

Run from the repository root. PowerShell setup is shown below. Command Prompt uses `set "PYTHONPATH=src"`; Linux and macOS use `export PYTHONPATH=src`.

```powershell
$env:PYTHONPATH = 'src'
python starter/generate_fixtures.py --seed 2026
python starter/verify_fixtures.py
python -m carerecon demo --reset
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/load_test.py --size 10000
```

The README lists individual CLI commands and argument substitutions. The evidence log preserves the exact commands used to create the reviewed report bundle. [README](../README.md)

## Scope and limitations

- Windows was verified on this host. Python 3.11 compatibility and POSIX shell commands are documented for supported environments. This run used Python 3.12 and did not exercise a Linux or macOS host.
- The pharmacy test covers a full inverse payment. Partial or prorated reversals require a different rule, and the fixture's fabricated member and NDC fields differ between RX010 and RX002. The implemented match is based on the referenced transaction ID, pharmacy, chronology, and cents.
- The remittance feed has no original event field. In this model, VOID events do not contribute to posted totals and signed POSTED events adjust the amounts for a claim. Period dates describe extracts and are supplied by the caller.
- When malformed quoting obscures record boundaries, the parser retains the entire consumed physical-line span and marks affected controls incomplete. SQLite limits exact stored amounts and SQL sums to signed 64-bit cents. Imports stream from fingerprinted temporary files. Cross-source checks and exports use in-memory collections, and report replacement is atomic per file.
- Authentication and .xlsx export are outside the delivered scope. The actors, sources, and data are synthetic, and the rules serve as local analytical examples.

# CLI contract

Design a discoverable `python -m carerecon` interface with `--help`. Required subcommands: `init-db --db PATH`, `ingest --batch NAME --source-dir DIR --db PATH`, `validate --run RUN_ID`, `reconcile --run RUN_ID`, `compare-snapshot --current DIR --previous DIR --run RUN_ID`, `list-findings --run RUN_ID [--status OPEN]`, `review --finding ID --status STATUS --actor NAME --reason TEXT`, `export --run RUN_ID --output DIR`, `demo --reset`, `verify --run RUN_ID`.

The `demo` command should execute full deterministic pipeline using default fixtures, print concise statistics and absolute report paths, and return non-zero for true execution errors (not simply detected data quality exceptions). Windows PowerShell, Command Prompt, Linux and macOS instructions required. Use pathlib, argparse, consistent exit codes, and stderr for failures.

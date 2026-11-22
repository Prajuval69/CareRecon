# Performance, portability and determinism

Use streaming CSV parsers when practical; avoid loading all data for large files. For SQLite, use indexed business keys and batch transactions. Support a synthetic `--size` generator or a reproducible load test with >=10k rows after core is complete; its data must remain synthetic. Record observed timing only, never invent throughput numbers.

Tests and CLI run with Python 3.11+ on a standard Windows laptop; path handling portable. No requirements for Docker, cloud account, Linux VM or subscription. Optional extra packages must be documented and entirely optional.

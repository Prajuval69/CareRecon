# Test plan and coverage matrix

Fixture tests in `tests/test_starter_fixtures.py` only prove data exist; they do not test the product. Create full `tests/test_import.py`, `test_contracts.py`, `test_rules.py`, `test_reconciliation.py`, `test_controls.py`, `test_snapshots.py`, `test_review.py`, `test_reporting.py`, `test_cli.py`, `test_idempotency.py` with temp database/files per test.

Specific assertions: expected 13 positive IDs, two clean RX010 negative checks, duplicate key P003, prorated/reversal assumptions, P012 275 cents, pharmacy controls 1234 cents, current payer control +1 row, missing P099, valid remit matches, malformed date, empty source, missing header, repeated source hash, no duplicate audit entry, output formula sanitization, HTML escaping, SQL injection defense, integer-cents accuracy and no division-by-zero. Include integration demo test.

"""Compare independent declarations against raw input evidence."""

import json

from .models import group
from .util import encode


def compare_controls(db, run, findings, declarations):
    by_source = group(declarations, lambda row: row.key)
    contracts = json.loads(run["contract_manifest"])["contracts"]
    sources = set(by_source) | (set(contracts) - {"source_controls"})
    unknown_control_rows = any(row.key is None for row in declarations)
    for name in sorted(sources):
        source = findings.sources.get(name)
        candidates = by_source.get(name, ())
        current = [row for row in candidates if row["snapshot_date"] == run["current_date"]]
        undated = any(row["snapshot_date"] is None for row in candidates)
        declaration = current[0] if len(current) == 1 and current[0].valid and not undated else None
        if name == "source_controls" or name not in contracts:
            source = None
        money_col = contracts.get(name, {}).get("money_col")
        observed_rows = source["source_row_count"] if source else None
        observed_cents = raw_total(db, source, money_col) if source else None
        expected_rows = declaration["expected_rows"] if declaration else None
        expected_cents = declaration["expected_paid_cents"] if declaration else None
        complete_rows = source and not source["malformed_count"]
        row_delta = expected_rows - observed_rows if expected_rows is not None and complete_rows else None
        cent_delta = expected_cents - observed_cents if None not in (expected_cents, observed_cents) else None

        if source is None:
            status = "UNKNOWN_SOURCE"
        elif len(current) > 1:
            status = "AMBIGUOUS_CONTROL"
        elif undated or unknown_control_rows:
            status = "INCOMPLETE"
        elif not candidates:
            status = "CONTROL_MISSING"
        elif not current:
            status = "WRONG_SNAPSHOT"
        elif row_delta is None or cent_delta is None:
            status = "INCOMPLETE"
        elif row_delta or cent_delta:
            status = "MISMATCH"
        else:
            status = "MATCH"
        if row_delta and not unknown_control_rows:
            findings.add("CT001", "source_controls", name, observed_rows, expected_rows, [declaration])
        if cent_delta and not unknown_control_rows:
            findings.add("CT002", "source_controls", name, observed_cents, expected_cents, [declaration])
        db.execute(
            "INSERT INTO control_result VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run["run_id"], name, source["source_sha256"] if source else None, run["current_date"],
             encode(sorted({row["snapshot_date"] for row in candidates if row["snapshot_date"]})),
             observed_rows, expected_rows, row_delta, observed_cents, expected_cents, cent_delta, status,
             encode([row.raw_id for row in candidates])),
        )


def raw_total(db, source, money_col):
    if source["malformed_count"]:
        return None
    if not money_col:
        return 0
    total = 0
    for (amount,) in db.execute(
        "SELECT raw_paid_cents FROM raw_row WHERE ingest_id=?", (source["ingest_id"],)
    ):
        if amount is None:
            return None
        total += amount
    return total

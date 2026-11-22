"""Integrity, SQL parity and fixture acceptance checks."""

from collections import Counter
import json

from .config import PRIOR
from .db import get_run, imports, stage_done, transaction
from .findings import Findings
from .models import group, records
from .reconcile import check_reconciliation_parity
from .rules import reversal_matches
from .util import CareReconError

RAW_TOTALS_SQL = """
SELECT i.source_name, COUNT(r.raw_row_id) AS raw_rows,
       CASE WHEN i.malformed_count > 0 THEN NULL
            WHEN i.source_name NOT IN ('payer_claims','provider_remittances','pharmacy_claims') THEN 0
            WHEN COUNT(r.raw_row_id)=COUNT(r.raw_paid_cents) THEN COALESCE(SUM(r.raw_paid_cents),0)
       END AS raw_paid_cents
FROM ingest_source i LEFT JOIN raw_row r USING(ingest_id)
WHERE i.run_id=? AND i.source_snapshot='current' AND i.source_name<>'source_controls'
GROUP BY i.ingest_id ORDER BY i.source_name
"""


def require(condition, message):
    if not condition:
        raise CareReconError(f"Verification failed: {message}")


def verify(db, run_id, expected_path=None):
    with transaction(db, write=False):
        run = get_run(db, run_id)
        require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity")
        require(not db.execute("PRAGMA foreign_key_check").fetchone(), "foreign keys")
        for stage in ("validate", "reconcile", "compare-snapshot"):
            require(stage_done(db, run_id, stage), f"missing stage {stage}")
        check_reconciliation_parity(db, run_id)
        sql_controls = [tuple(row) for row in db.execute(RAW_TOTALS_SQL, (run_id,))]
        python_controls = [tuple(row) for row in db.execute(
            """SELECT source_name,observed_rows,observed_paid_cents FROM control_result
               WHERE run_id=? AND source_sha256 IS NOT NULL ORDER BY source_name""", (run_id,),
        )]
        require(sql_controls == python_controls, "SQL/Python raw control totals")
        if expected_path is None:
            return "PASS: SQLite integrity, SQL/Python reconciliation and raw control parity"

        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        detected = Counter(tuple(row) for row in db.execute(
            "SELECT rule_id,source_name,record_id FROM finding WHERE run_id=?", (run_id,),
        ))
        for item in expected["expected_findings"]:
            pair = item["rule_id"], item["source"], item["record_id"]
            require(detected[pair] == 1, f"{pair} expected once, found {detected[pair]}")
        for item in expected["must_not_flag"]:
            require(not any(rule == item["rule_id"] and key == item["record_id"]
                            for rule, _, key in detected), f"unexpected finding for {item['record_id']}")
        source_map = imports(db, run_id)
        require({name: row["source_row_count"] for name, row in source_map.items()}
                == expected["expected_raw_rows"], "raw row counts")
        require(PRIOR in source_map, "prior payer snapshot")
        require(not any(key == "RX010" and source == "pharmacy_claims" for _, source, key in detected),
                "valid RX010 emitted a finding")
        pharmacy = group(records(db, Findings(db, run).sources["pharmacy_claims"]), lambda row: row.key)
        require(len(pharmacy["RX010"]) == 1 and
                reversal_matches(pharmacy["RX010"][0], pharmacy["RX002"]), "RX010 valid inverse of RX002")
        verify_amounts(db, run_id)
        count = len(expected["expected_findings"])
        return (f"PASS: {count}/{count} planted findings, RX010 clean, expected raw counts, "
                "SQLite integrity and SQL/Python parity")


def verify_amounts(db, run_id):
    checks = (
        ("reconciliation", "payer_claim_id", "P012", "difference_cents", 275),
        ("reconciliation", "payer_claim_id", "P003", "status", "AMBIGUOUS"),
        ("reconciliation", "payer_claim_id", "P_NO_SUCH_CLAIM", "status", "ORPHAN"),
        ("control_result", "source_name", "payer_claims", "declared_minus_observed_rows", 1),
        ("control_result", "source_name", "pharmacy_claims", "declared_minus_observed_cents", 1234),
        ("snapshot_change", "payer_claim_id", "P099", "event_type", "DISAPPEARED"),
        ("finding", "record_id", "P099", "severity", "REVIEW"),
    )
    for table, key, record, column, expected in checks:
        row = db.execute(f"SELECT {column} FROM {table} WHERE run_id=? AND {key}=?", (run_id, record)).fetchone()
        require(row is not None and row[0] == expected, f"{table} {record} {column}={expected}")
    matches = {row[0] for row in db.execute(
        "SELECT payer_claim_id FROM reconciliation WHERE run_id=? AND status='MATCH'", (run_id,),
    )}
    require({"P001", "P002", "P004", "P005"} <= matches, "expected matched remittances")

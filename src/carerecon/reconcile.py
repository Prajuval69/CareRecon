"""Reconcile signed POSTED remits at claim grain and check independent SQL results."""

from collections import Counter
from importlib.resources import files

from .db import get_run, stage
from .findings import Findings
from .models import group, records
from .util import CareReconError, encode

CLAIMS = "payer_claims"
REMITS = "provider_remittances"


def reconcile(db, run_id):
    with stage(db, run_id, "reconcile") as pending:
        if not pending:
            return
        findings = Findings(db, get_run(db, run_id))
        claim_rows = list(records(db, findings.sources[CLAIMS]))
        remit_rows = list(records(db, findings.sources[REMITS]))
        claims = group(claim_rows, lambda row: row.key)
        remits = group(remit_rows, lambda row: row["payer_claim_id"])
        event_counts = Counter(row.key for row in remit_rows)
        claim_unknown = any(row.key is None for row in claim_rows)
        remit_unknown = any(row["payer_claim_id"] is None for row in remit_rows)

        for key in sorted(claims.keys() | remits.keys()):
            payers, events = claims.get(key, ()), remits.get(key, ())
            usable = [row for row in events if row.valid and event_counts[row.key] == 1]
            posted = [row for row in usable if row["remit_status"] == "POSTED"]
            incomplete_remits = len(usable) != len(events) or remit_unknown
            received = sum(row["paid_cents"] for row in posted) if posted and not incomplete_remits else None
            paid = payers[0]["paid_cents"] if len(payers) == 1 and payers[0].valid else None
            delta = None
            if len(payers) > 1:
                status = "AMBIGUOUS"
            elif not payers and not claim_unknown and len(usable) == len(events):
                status = "ORPHAN"
                for row in usable:
                    findings.add("RC002", REMITS, row.label, key, "payer claim present in extract", [row])
            elif paid is None or incomplete_remits:
                status = "INCOMPLETE"
            elif received is None:
                status = "NOT_AVAILABLE"
            else:
                delta = received - paid
                status = "MATCH" if delta == 0 else "MISMATCH"
                if delta:
                    findings.add("RC001", REMITS, key, received, paid, posted, payers)

            db.execute(
                "INSERT INTO reconciliation VALUES(?,?,?,?,?,?,?,?,?)",
                (run_id, key, paid, received, delta, status, len(events), len(posted),
                 encode([row.raw_id for row in (*payers, *events)])),
            )
        check_reconciliation_parity(db, run_id)


def check_reconciliation_parity(db, run_id):
    sql = files("carerecon").joinpath("reconciliation.sql").read_text(encoding="utf-8")
    sql_rows = [tuple(row) for row in db.execute(sql, {"run": run_id})]
    python_rows = [tuple(row) for row in db.execute(
        """SELECT payer_claim_id,expected_cents,remitted_cents,difference_cents,status,remit_count,posted_count
           FROM reconciliation WHERE run_id=? ORDER BY payer_claim_id""", (run_id,),
    )]
    if sql_rows != python_rows or any(
        isinstance(amount, float) for row in sql_rows for amount in row[1:4]
    ):
        raise CareReconError("SQL/Python reconciliation parity failed.")

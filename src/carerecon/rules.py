"""Illustrative reasonability checks from the pinned rule manifest."""

from collections import Counter

from .controls import compare_controls
from .db import get_run, stage
from .findings import Findings, contract_findings
from .models import group, records


def validate(db, run_id):
    with stage(db, run_id, "validate") as pending:
        if not pending:
            return
        run = get_run(db, run_id)
        findings = Findings(db, run)
        inputs = {
            name: list(records(db, source)) for name, source in findings.sources.items()
            if source["source_snapshot"] == "current"
        }
        for name, rows in inputs.items():
            contract_findings(findings, name, rows)
        check_payer(findings, inputs)
        check_pharmacy(findings, inputs["pharmacy_claims"])
        compare_controls(db, run, findings, inputs["source_controls"])


def check_payer(findings, inputs):
    source = "payer_claims"
    claims = inputs[source]
    providers = group(inputs["provider_directory"], lambda row: row.key)
    members = group(inputs["member_eligibility"], lambda row: row.key)
    for key, rows in group(claims, lambda row: row.key).items():
        if len(rows) > 1:
            findings.add("DQ001", source, key, len(rows), 1, rows)

    for row in claims:
        if row.malformed:
            continue
        member, provider, service = row["member_id"], row["provider_id"], row["service_date"]
        if member is None and row.key:
            findings.add("DQ002", source, row.label, member, "nonblank member_id", [row])
        if provider and provider not in providers and not findings.sources["provider_directory"]["malformed_count"]:
            findings.add("DQ003", source, row.label, provider, "provider_id in directory", [row])
        intervals = members.get(member, ())
        if member and service and not any(
            item["effective_date"] <= service <= item["end_date"] for item in intervals if item.valid
        ) and all(item.valid for item in intervals) and not findings.sources["member_eligibility"]["malformed_count"]:
            coverage = [{"effective_date": item["effective_date"], "end_date": item["end_date"]}
                        for item in intervals]
            findings.add("DQ004", source, row.label, {"member_id": member, "service_date": service},
                         {"coverage_intervals": coverage}, [row], intervals)
        paid, allowed = row["paid_cents"], row["allowed_cents"]
        if row["status"] == "PAID" and paid is not None and allowed is not None and paid > allowed:
            findings.add("DQ005", source, row.label, paid, allowed, [row])
        if row["status"] == "DENIED" and paid is not None and paid != 0:
            findings.add("DQ006", source, row.label, paid, 0, [row])


def check_pharmacy(findings, transactions):
    source = "pharmacy_claims"
    by_key = group(transactions, lambda row: row.key)
    reversals = group(
        (row for row in transactions if row["transaction_type"] == "REVERSAL"),
        lambda row: row["original_rx_claim_id"],
    )
    counts = Counter({
        key: sum(reversal_matches(row, by_key.get(key, ())) for row in rows)
        for key, rows in reversals.items()
    })
    for row in transactions:
        if row.malformed:
            continue
        if row["transaction_type"] == "DISPENSE" and row["days_supply"] is not None and row["days_supply"] < 1:
            findings.add("RX001", source, row.label, row["days_supply"], "at least 1", [row])
        if row["transaction_type"] != "REVERSAL" or not row.valid:
            continue
        original_id = row["original_rx_claim_id"]
        originals = by_key.get(original_id, ())
        if not reversal_matches(row, originals) or counts[original_id] != 1:
            findings.add(
                "RX002", source, row.label,
                {"original_rx_claim_id": original_id, "paid_cents": row["paid_cents"],
                 "pharmacy_id": row["pharmacy_id"], "matching_reversals": counts[original_id]},
                "unique referenced dispense at same pharmacy, on or before reversal, with opposite payment",
                [row], originals,
            )


def reversal_matches(row, originals):
    if not row.valid or len(originals) != 1:
        return False
    original = originals[0]
    return (
        original.valid and original["transaction_type"] == "DISPENSE"
        and original["days_supply"] > 0
        and original["pharmacy_id"] == row["pharmacy_id"]
        and original["fill_date"] <= row["fill_date"]
        and original["paid_cents"] > 0
        and row["paid_cents"] == -original["paid_cents"]
    )

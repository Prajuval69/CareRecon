"""Write stable findings and link every contributing raw row."""

import json

from .db import imports
from .models import group
from .util import CareReconError, encode, identity, utc_now

BUILT_IN = {
    "CN001": "Record does not satisfy its source contract.",
    "CN002": "Business key repeats in a source that requires unique keys.",
}


class Findings:
    def __init__(self, db, run):
        self.db = db
        self.run_id = run["run_id"]
        self.sources = imports(db, self.run_id)
        self.manifest = {r["rule_id"]: r for r in json.loads(run["rule_manifest"])["rules"]}

    def add(self, rule_id, source, record, observed, expected, primary=(), related=()):
        if rule_id in BUILT_IN:
            version, severity, description = 1, "ERROR", BUILT_IN[rule_id]
        else:
            rule = self.manifest[rule_id]
            if rule["dataset"] != source:
                raise CareReconError(f"{rule_id}: config dataset must be {source}")
            if not rule["enabled"]:
                return
            version, severity, description = rule["version"], rule["severity"], rule["description"]
        ingest_id = self.sources[source]["ingest_id"]
        evidence_ids = sorted({row.raw_id for row in (*primary, *related)})
        finding_id = identity(self.run_id, ingest_id, record, rule_id, version,
                              sorted(row.line for row in primary))
        self.db.execute(
            """INSERT INTO finding VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(finding_id) DO NOTHING""",
            (finding_id, self.run_id, ingest_id, source, record, rule_id, version, severity,
             encode(observed), encode(expected), description, utc_now()),
        )
        self.db.executemany(
            "INSERT OR IGNORE INTO finding_evidence VALUES(?,?)",
            ((finding_id, raw_id) for raw_id in evidence_ids),
        )


def contract_findings(findings, source_name, source_records):
    for row in source_records:
        if row.issues:
            findings.add("CN001", source_name, row.label, row.issues, "valid source record", [row])
    if source_name not in {"payer_claims", "payer_claims_previous", "member_eligibility", "source_controls"}:
        for key, rows in group(source_records, lambda row: row.key).items():
            if len(rows) > 1:
                findings.add("CN002", source_name, key, len(rows), 1, rows)

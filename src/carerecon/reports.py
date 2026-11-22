"""Deterministic analyst reports and persisted export fingerprints."""

import csv
from html import escape
import io
import json
from pathlib import Path
import tempfile

from .db import get_run, imports, stage, stage_done
from .findings import BUILT_IN
from .util import CareReconError, digest, encode, utc_now

FINDINGS_QUERY = """
SELECT f.finding_id,f.run_id,r.batch_id,f.source_name AS source,f.record_id,
       f.rule_id,f.rule_version,f.severity,i.source_file,i.source_sha256,i.snapshot_date,
       f.observed_value,f.expected_value,f.message,f.status,f.reason,f.actor,f.created_at
FROM finding_status f JOIN ingest_source i USING(ingest_id) JOIN run r ON r.run_id=f.run_id
WHERE f.run_id=:run
ORDER BY f.rule_id,f.record_id,f.rule_version,f.finding_id
"""

TABLES = {
    "reconciliation.csv": "SELECT * FROM reconciliation WHERE run_id=:run ORDER BY payer_claim_id",
    "source_controls.csv": "SELECT * FROM control_result WHERE run_id=:run ORDER BY source_name",
    "snapshot_changes.csv": "SELECT * FROM snapshot_change WHERE run_id=:run ORDER BY payer_claim_id",
    "review_history.csv": """
        SELECT e.* FROM review_event e JOIN finding f USING(finding_id)
        WHERE f.run_id=:run ORDER BY e.event_id
    """,
    "quarantine.csv": """
        SELECT q.source_name,q.business_key,q.source_file,q.source_sha256,q.source_line_number,
               q.end_line_number,q.key_count,q.issues_json,q.raw_json
        FROM quarantined_rows q WHERE q.run_id=:run ORDER BY q.source_name,q.source_line_number
    """,
    "source_lineage.csv": """
        SELECT i.*,r.batch_id FROM ingest_source i JOIN run r USING(run_id)
        WHERE i.run_id=:run ORDER BY source_name
    """,
    "quality_totals.csv": """
        WITH clean AS (
            SELECT ingest_id,COUNT(*) AS rows,SUM(paid_cents) AS cents
            FROM clean_rows WHERE run_id=:run GROUP BY ingest_id
        )
        SELECT i.source_name,i.source_row_count AS raw_rows,COALESCE(c.rows,0) AS clean_rows,
               i.source_row_count-COALESCE(c.rows,0) AS quarantined_rows,
               CASE WHEN i.source_name IN ('payer_claims','payer_claims_previous','provider_remittances',
                                           'pharmacy_claims') THEN COALESCE(c.cents,0) END AS clean_paid_cents
        FROM ingest_source i LEFT JOIN clean c USING(ingest_id)
        WHERE i.run_id=:run ORDER BY i.source_name
    """,
}


REPORT_NAMES = {*TABLES, "findings.csv", "summary.html", "run_manifest.json"}


def sheet_cell(value):
    if isinstance(value, str) and (
        value.startswith(("\r", "\n", "\t")) or value.lstrip().startswith(("=", "+", "-", "@"))
    ):
        return "'" + value
    return value


def csv_bytes(headers, rows):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows([sheet_cell(value) for value in row] for row in rows)
    return buffer.getvalue().encode("utf-8-sig")


def listing(db, run_id, status=None):
    for row in db.execute(FINDINGS_QUERY, {"run": run_id}):
        if status is None or row["status"] == status:
            yield dict(row)


def lineage_rows(db, run_id):
    linked = {}
    for row in db.execute(
        """SELECT e.finding_id,s.source_name,s.source_file,s.source_sha256,
                  s.source_line_number,s.end_line_number,s.raw_row_id
           FROM finding_evidence e JOIN source_rows s USING(raw_row_id)
           WHERE s.run_id=? ORDER BY s.source_name,s.source_line_number""", (run_id,),
    ):
        item = dict(row)
        linked.setdefault(item.pop("finding_id"), []).append(item)
    return linked


def html_table(headers, rows):
    def cells(tag, row):
        return "".join(f"<{tag}>{escape(str(v) if v is not None else '')}</{tag}>" for v in row)

    body = "".join(f"<tr>{cells('td', row)}</tr>" for row in rows)
    return f"<table><thead><tr>{cells('th', headers)}</tr></thead><tbody>{body}</tbody></table>"


def summary(db, run, tables, findings):
    def serialize(query):
        return [tuple(row) for row in db.execute(query, (run["run_id"],))]

    sources = serialize("""SELECT source_name,source_file,source_sha256,snapshot_date,source_row_count,
                                  contract_version FROM ingest_source WHERE run_id=? ORDER BY source_name""")
    summary_rows = serialize("""SELECT severity,status,COUNT(*) FROM finding_status
                                WHERE run_id=? GROUP BY severity,status ORDER BY severity,status""")
    recon_counts = serialize("""SELECT status,COUNT(*) FROM reconciliation
                                 WHERE run_id=? GROUP BY status ORDER BY status""")
    movements = serialize("""SELECT event_type,COUNT(*) FROM snapshot_change WHERE run_id=?
                             GROUP BY event_type ORDER BY event_type""")
    snapshot_counts = serialize("""SELECT COALESCE(SUM(previous_rows>0),0),COALESCE(SUM(current_rows>0),0),
                                     COALESCE(SUM(previous_rows>0 AND event_type<>'AMBIGUOUS'),0),
                                     COALESCE(SUM(current_rows>0 AND event_type<>'AMBIGUOUS'),0)
                                     FROM snapshot_change WHERE run_id=?""")
    outcomes = [
        (row["rule_id"], row["record_id"], row["severity"], row["status"], row["message"],
         row["observed_value"], row["expected_value"], row["actor"], row["reason"])
        for row in findings
    ]
    quality_headers, quality = tables["quality_totals.csv"]
    control_headers, controls = tables["source_controls.csv"]
    displayed_controls = ("source_name", "expected_rows", "observed_rows", "declared_minus_observed_rows",
                          "expected_paid_cents", "observed_paid_cents", "declared_minus_observed_cents", "status")
    controls = [tuple(dict(zip(control_headers, row))[header] for header in displayed_controls)
                for row in controls]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CareRecon reconciliation summary</title>
<style>
body {{font: 1rem/1.55 system-ui,sans-serif; color:#17263b; background:#f4f6f8; margin:0}}
main {{max-width:76rem; margin:auto; padding:2rem clamp(1rem,4vw,3rem) 4rem}}
h1,h2 {{line-height:1.15}} h2 {{margin-top:2rem}}
section {{overflow:auto}} table {{border-collapse:collapse;width:100%;background:#fff;font-size:.9rem}}
td,th {{border-bottom:1px solid #d9e1e9; padding:.55rem; text-align:left; vertical-align:top; overflow-wrap:anywhere}}
th {{background:#e3e9ef}} .notice {{padding:.75rem 1rem;background:#fff3d9}}
code {{overflow-wrap:anywhere}}
</style></head><body><main>
<h1>CareRecon reconciliation summary</h1>
<p class="notice">Synthetic examples only. Illustrative reconciliation for analyst review.</p>
<p>Batch <strong>{escape(run['batch_id'])}</strong><br>Run <code>{escape(run['run_id'])}</code><br>
Current snapshot {escape(run['current_date'])} · Prior snapshot {escape(run['previous_date'])} · Imported {escape(run['started_at'])}</p>
<section><h2>Findings by severity and review status</h2>
{html_table(("Severity", "Review status", "Findings"), summary_rows)}
<p>ERROR identifies a synthetic contract or reconciliation failure. WARN and REVIEW call for analyst judgment.
Check the source rows for each open finding and record the reason for any waiver or resolution.</p>
{html_table(("Rule", "Record", "Severity", "Review status", "Description", "Observed", "Expected", "Actor", "Reason"), outcomes)}
</section>
<section><h2>Payment reconciliation</h2>
<p>One row per payer claim key. Difference is total signed POSTED remittances minus the payer amount, in cents.
NOT_AVAILABLE can reflect pending activity or extract scope. AMBIGUOUS and INCOMPLETE need usable source data.</p>
{html_table(("Status", "Claim keys"), recon_counts)}</section>
<section><h2>Raw source controls</h2>
<p>Control deltas are declared minus observed. Blanks indicate comparisons unavailable from the source evidence.
Confirm extract completeness and period with the source owner when declarations disagree.</p>
{html_table(displayed_controls, controls)}
<h2>Quality-adjusted source totals</h2>
<p>Clean totals exclude contract rejects, duplicate keys where uniqueness is required, and hard claim or pharmacy rule failures.</p>
{html_table(quality_headers, quality)}</section>
<section><h2>Snapshot movements</h2>
<p>Confirm extraction scope for disappeared keys. Snapshot evidence alone cannot establish a deletion or adjudication outcome.</p>
{html_table(("Movement", "Keys"), movements)}
{html_table(("Prior keys", "Current keys", "Prior without ambiguity", "Current without ambiguity"), snapshot_counts)}
</section>
<section><h2>Source lineage</h2>
{html_table(("Source", "File", "SHA-256", "Snapshot", "Raw records", "Contract version"), sources)}
</section></main></body></html>
""".encode("utf-8")


def atomic_write(target, content):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".carerecon-", delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export(db, run_id, directory):
    directory = Path(directory).resolve()
    with stage(db, run_id, "export", repeat=True):
        if not all(stage_done(db, run_id, name) for name in ("validate", "reconcile", "compare-snapshot")):
            raise CareReconError("Run validate, reconcile and compare-snapshot before export.")
        run = get_run(db, run_id)
        tables = {}
        for name, query in TABLES.items():
            cursor = db.execute(query, {"run": run_id})
            tables[name] = tuple(col[0] for col in cursor.description), cursor.fetchall()
        findings = list(listing(db, run_id))
        headers = tuple(col[0] for col in db.execute(FINDINGS_QUERY, {"run": run_id}).description)
        evidence = lineage_rows(db, run_id)
        rows = [(*row.values(), encode(evidence.get(row["finding_id"], []))) for row in findings]
        tables["findings.csv"] = headers + ("raw_locations",), rows
        content = {name: csv_bytes(*table) for name, table in tables.items()}
        content["summary.html"] = summary(db, run, tables, findings)
        content["run_manifest.json"] = (json.dumps({
            "classification": "synthetic-only", "run_id": run_id, "batch_id": run["batch_id"],
            "schema_version": db.execute("PRAGMA user_version").fetchone()[0],
            "config_sha256": run["config_sha256"], "import_policy": run["policy"],
            "rule_manifest": json.loads(run["rule_manifest"]),
            "built_in_contract_rules": BUILT_IN,
            "contract_manifest": json.loads(run["contract_manifest"]),
        }, indent=2, sort_keys=True) + "\n").encode("utf-8")
        protected = {Path(row["source_path"]).resolve() for row in imports(db, run_id).values()}
        protected.update(Path(row[2]).resolve() for row in db.execute("PRAGMA database_list") if row[2])
        for name in content:
            target = directory / name
            if target.resolve() in protected or target.is_symlink() or (target.exists() and not target.is_file()):
                raise CareReconError(f"Unsafe report destination {target}.")
        directory.mkdir(parents=True, exist_ok=True)
        for name, data in sorted(content.items()):
            target = directory / name
            atomic_write(target, data)
            db.execute("INSERT OR IGNORE INTO export_artifact VALUES(?,?,?,?,?)",
                       (run_id, str(target), digest(data), len(data), utc_now()))
    return sorted(directory / name for name in content)

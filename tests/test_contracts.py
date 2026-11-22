import json

from support import CareReconTest
from carerecon.util import CareReconError, integer


class ContractTests(CareReconTest):
    def test_duplicate_header_rejected(self):
        path = self.current / "member_eligibility.csv"
        path.write_text(path.read_text().replace("plan_id", "member_id"), encoding="utf-8")
        with self.assertRaisesRegex(CareReconError, "duplicate"):
            self.ingest()

    def test_bad_integer_and_enum_retain_raw_values(self):
        self.edit("provider_remittances", lambda rows: [
            dict(rows[0], paid_cents="1e3", remit_status="PENDING"), *rows[1:]
        ])
        self.run_pipeline()
        issues = self.db.execute("SELECT issues_json FROM quarantined_rows WHERE business_key='RM001'").fetchone()[0]
        self.assertEqual(len(json.loads(issues)), 2)
        status = self.db.execute("SELECT status FROM reconciliation WHERE payer_claim_id='P001'").fetchone()[0]
        self.assertEqual(status, "INCOMPLETE")

    def test_surplus_columns_and_multiline_lineage(self):
        path = self.current / "pharmacy_directory.csv"
        lines = path.read_text(encoding="utf-8").splitlines()
        rows = [lines[0] + ",notes", lines[1] + ',"café\nreview"', *(row + "," for row in lines[2:])]
        path.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="")
        self.ingest()
        row = self.db.execute("""
            SELECT s.raw_json,s.source_line_number,s.end_line_number,i.unexpected_columns
            FROM source_rows s JOIN ingest_source i USING(ingest_id) WHERE s.business_key='PH001'
        """).fetchone()
        self.assertEqual((row[1], row[2]), (2, 3))
        self.assertEqual(json.loads(row[0])["columns"]["notes"], "café\nreview")
        self.assertEqual(json.loads(row[3]), ["notes"])

    def test_malformed_quoted_record_recovers_next_record(self):
        path = self.current / "payer_claims.csv"
        lines = path.read_text(encoding="utf-8").splitlines()
        lines.insert(2, '"unexpected"characters,1')
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.run_pipeline()
        defect = self.db.execute("""
            SELECT issues_json,raw_text FROM quarantined_rows
            WHERE source_name='payer_claims' AND source_line_number=3
        """).fetchone()
        self.assertIn("CSV parse", defect[0])
        self.assertIn("unexpected", defect[1])
        self.assertEqual(self.db.execute("""
            SELECT source_line_number FROM source_rows WHERE business_key='P002' AND source_name='payer_claims'
        """).fetchone()[0], 4)
        self.assertEqual(self.db.execute("SELECT status FROM control_result WHERE source_name='payer_claims'")
                         .fetchone()[0], "INCOMPLETE")

    def test_csv_width_and_blank_fields_are_quarantined(self):
        path = self.current / "pharmacy_directory.csv"
        path.write_text(path.read_text() + "PH999,,2026-01-01\n", encoding="utf-8")
        self.run_pipeline()
        issues = self.db.execute("SELECT issues_json FROM quarantined_rows WHERE business_key='PH999'").fetchone()[0]
        self.assertIn("CSV width", issues)
        self.assertIn("name:", issues)

    def test_integer_bounds_and_format(self):
        self.assertEqual(integer("-9223372036854775808"), -(2**63))
        self.assertEqual(integer("+9223372036854775807"), 2**63 - 1)
        self.assertEqual(integer("0000123"), 123)
        for invalid in ("1.2", "0x42", "", "9223372036854775808", "-9223372036854775809"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                integer(invalid)

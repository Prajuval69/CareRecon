from support import CareReconTest
from carerecon.verify import verify


class ControlTests(CareReconTest):
    def controls(self):
        return {row["source_name"]: row for row in self.db.execute("SELECT * FROM control_result")}

    def test_raw_and_curated_totals_are_distinct(self):
        run_id = self.run_pipeline()
        rows = self.controls()
        self.assertEqual(rows["payer_claims"]["declared_minus_observed_rows"], 1)
        self.assertEqual(rows["payer_claims"]["observed_rows"], 19)
        self.assertEqual(rows["pharmacy_claims"]["declared_minus_observed_cents"], 1234)
        self.assertEqual(rows["pharmacy_claims"]["observed_paid_cents"], 13000)
        self.assertEqual({name for name, row in rows.items() if row["status"] == "MISMATCH"},
                         {"payer_claims", "pharmacy_claims"})
        raw = self.db.execute("SELECT COUNT(*) FROM clean_rows WHERE source_name='payer_claims'").fetchone()[0]
        self.assertLess(raw, rows["payer_claims"]["observed_rows"])
        self.assertIn("raw control parity", verify(self.db, run_id))

    def test_unparsable_paid_total_is_incomplete(self):
        self.edit("pharmacy_claims", lambda rows: [dict(rows[0], paid_cents="unknown"), *rows[1:]])
        run_id = self.run_pipeline()
        row = self.controls()["pharmacy_claims"]
        self.assertEqual(row["status"], "INCOMPLETE")
        self.assertIsNone(row["observed_paid_cents"])
        self.assertIsNone(row["declared_minus_observed_cents"])
        self.assertEqual(row["declared_minus_observed_rows"], 0)
        self.assertIsNone(self.db.execute("SELECT 1 FROM finding WHERE rule_id='CT002'").fetchone())
        self.assertIn("raw control parity", verify(self.db, run_id))

    def test_missing_wrong_period_and_duplicate_declarations(self):
        self.edit("source_controls", lambda rows: [
            dict(rows[0], snapshot_date="2026-04-30"), *rows[2:],
            dict(rows[2], expected_rows="417"),
        ])
        self.run_pipeline()
        rows = self.controls()
        self.assertEqual(rows["member_eligibility"]["status"], "WRONG_SNAPSHOT")
        self.assertEqual(rows["provider_directory"]["status"], "CONTROL_MISSING")
        self.assertEqual(rows["pharmacy_directory"]["status"], "AMBIGUOUS_CONTROL")

    def test_period_is_matched_explicitly(self):
        self.edit("source_controls", lambda rows: [
            *rows, dict(rows[0], snapshot_date="2026-04-30", expected_rows="0"),
        ])
        self.run_pipeline()
        row = self.controls()["member_eligibility"]
        self.assertEqual(row["status"], "MATCH")
        self.assertEqual(row["expected_rows"], 13)

from support import CareReconTest
from carerecon.snapshots import compare
from carerecon.util import CareReconError


class SnapshotTests(CareReconTest):
    def test_prior_key_disappearance_has_review_severity(self):
        run_id = self.run_pipeline()
        result = self.db.execute("SELECT * FROM snapshot_change WHERE payer_claim_id='P099'").fetchone()
        self.assertEqual((result["event_type"], result["previous_rows"], result["current_rows"]),
                         ("DISAPPEARED", 1, 0))
        self.assertEqual(result["previous_date"], "2026-04-30")
        self.assertEqual(result["current_date"], "2026-05-31")
        finding = self.db.execute("""
            SELECT severity,status FROM finding_status WHERE run_id=? AND record_id='P099'
        """, (run_id,)).fetchone()
        self.assertEqual(tuple(finding), ("REVIEW", "OPEN"))

    def test_added_changed_unchanged_and_ambiguous_keys(self):
        self.edit("payer_claims_previous", lambda rows: [dict(rows[0], paid_cents="5700"), *reversed(rows[1:])],
                  previous=True)
        self.run_pipeline()
        changes = {row[0]: tuple(row[1:]) for row in self.db.execute("""
            SELECT payer_claim_id,event_type,difference_cents FROM snapshot_change
        """)}
        self.assertEqual(changes["P001"], ("CHANGED", 50))
        self.assertEqual(changes["P002"], ("UNCHANGED", 0))
        self.assertEqual(changes["P003"], ("AMBIGUOUS", None))
        self.assertEqual(changes["P013"], ("ADDED", None))

    def test_unknown_current_key_blocks_disappearance_alert(self):
        self.edit("payer_claims", lambda rows: [dict(rows[0], payer_claim_id=""), *rows[1:]])
        self.run_pipeline()
        self.assertEqual(self.db.execute(
            "SELECT event_type FROM snapshot_change WHERE payer_claim_id='P099'"
        ).fetchone()[0], "INCOMPLETE")
        self.assertIsNone(self.db.execute("SELECT 1 FROM finding WHERE rule_id='SS001'").fetchone())

    def test_reject_changed_current_and_recover(self):
        run_id, _ = self.ingest()
        path = self.current / "payer_claims.csv"
        before = path.read_bytes()
        path.write_bytes(before + b"\n")
        with self.assertRaisesRegex(CareReconError, "Current payer file differs"):
            compare(self.db, run_id, self.current, self.previous)
        self.assertEqual(self.db.execute("SELECT status FROM run").fetchone()[0], "FAILED")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM ingest_source").fetchone()[0], 7)
        path.write_bytes(before)
        compare(self.db, run_id, self.current, self.previous)
        self.assertEqual(self.db.execute("SELECT status FROM run").fetchone()[0], "INGESTED")

    def test_previous_immutable_and_duplicate_previous_key_ambiguous(self):
        self.edit("payer_claims_previous", lambda rows: [*rows, rows[0]], previous=True)
        run_id = self.run_pipeline()
        self.assertEqual(self.db.execute("""
            SELECT event_type FROM snapshot_change WHERE payer_claim_id='P001'
        """).fetchone()[0], "AMBIGUOUS")
        self.edit("payer_claims_previous", lambda rows: rows[:-1], previous=True)
        with self.assertRaisesRegex(CareReconError, "Prior payer file differs"):
            compare(self.db, run_id, self.current, self.previous)
        self.assertEqual(self.db.execute("""
            SELECT previous_rows FROM snapshot_change WHERE payer_claim_id='P001'
        """).fetchone()[0], 2)

from support import CareReconTest
from carerecon.reconcile import check_reconciliation_parity, reconcile


class ReconciliationTests(CareReconTest):
    def results(self):
        return {row["payer_claim_id"]: row for row in self.db.execute("SELECT * FROM reconciliation")}

    def test_matches_mismatch_pending_and_orphan(self):
        run_id = self.run_pipeline()
        rows = self.results()
        self.assertEqual([key for key, row in sorted(rows.items()) if row["status"] == "MATCH"],
                         ["P001", "P002", "P004", "P005"])
        self.assertEqual(tuple(rows["P012"])[2:6], (8900, 9175, 275, "MISMATCH"))
        self.assertEqual(tuple(rows["P003"])[2:6], (None, 6650, None, "AMBIGUOUS"))
        self.assertEqual(rows["P_NO_SUCH_CLAIM"]["status"], "ORPHAN")
        self.assertEqual(rows["P011"]["status"], "NOT_AVAILABLE")
        self.assertIsNone(rows["P011"]["remitted_cents"])
        check_reconciliation_parity(self.db, run_id)

    def test_multiple_postings_signed_adjustment_and_void(self):
        self.edit("provider_remittances", lambda rows: [
            dict(rows[0], paid_cents="6000"), *rows[1:],
            dict(rows[0], remit_id="RM_ADJUST", paid_cents="-250"),
            dict(rows[0], remit_id="RM_VOID", paid_cents="50000", remit_status="VOID"),
        ])
        run_id = self.run_pipeline()
        row = self.results()["P001"]
        self.assertEqual(tuple(row)[2:8], (5750, 5750, 0, "MATCH", 3, 2))
        check_reconciliation_parity(self.db, run_id)

    def test_void_only_is_not_a_payment(self):
        self.edit("provider_remittances", lambda rows: [dict(rows[0], remit_status="VOID"), *rows[1:]])
        self.run_pipeline()
        self.assertEqual(tuple(self.results()["P001"])[2:8], (5750, None, None, "NOT_AVAILABLE", 1, 0))

    def test_duplicate_remit_id_across_claims_blocks_both_comparisons(self):
        self.edit("provider_remittances", lambda rows: [
            *rows, dict(rows[0], payer_claim_id=rows[1]["payer_claim_id"]),
        ])
        self.run_pipeline()
        rows = self.results()
        for key in ("P001", "P002"):
            self.assertEqual(rows[key]["status"], "INCOMPLETE")
            self.assertIsNone(rows[key]["difference_cents"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM finding WHERE rule_id='CN002'").fetchone()[0], 1)

    def test_malformed_claim_key_prevents_orphan_assertion(self):
        self.edit("payer_claims", lambda rows: [dict(rows[0], payer_claim_id=""), *rows[1:]])
        self.run_pipeline()
        self.assertEqual(self.results()["P_NO_SUCH_CLAIM"]["status"], "INCOMPLETE")
        self.assertIsNone(self.db.execute("SELECT 1 FROM finding WHERE rule_id='RC002'").fetchone())

    def test_signed_cents_preserve_precision_beyond_float_range(self):
        self.edit("payer_claims", lambda rows: [
            dict(rows[0], paid_cents="9007199254740993", allowed_cents="9007199254740993"), *rows[1:],
        ])
        self.edit("provider_remittances", lambda rows: [dict(rows[0], paid_cents="9007199254740994"), *rows[1:]])
        run_id = self.run_pipeline()
        self.assertEqual(self.results()["P001"]["difference_cents"], 1)
        check_reconciliation_parity(self.db, run_id)

    def test_reconciliation_overflow_rolls_back_results(self):
        self.edit("provider_remittances", lambda rows: [
            dict(rows[0], paid_cents="9223372036854775807"), *rows[1:],
            dict(rows[0], remit_id="RM_LARGE", paid_cents="1"),
        ])
        run_id, _ = self.ingest()
        with self.assertRaises(OverflowError):
            reconcile(self.db, run_id)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM reconciliation").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT status FROM run WHERE run_id=?", (run_id,)).fetchone()[0], "FAILED")

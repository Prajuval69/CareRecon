import sqlite3

from support import CareReconTest
from carerecon.review import review
from carerecon.util import CareReconError


class ReviewTests(CareReconTest):
    def setUp(self):
        super().setUp()
        self.run_pipeline()
        self.finding = self.db.execute("SELECT finding_id FROM finding WHERE rule_id='SS001'").fetchone()[0]

    def test_history_acknowledge_waive_reopen_and_resolve(self):
        for status, reason in (
            ("ACKNOWLEDGED", "Checked scope"),
            ("WAIVED", "Validated extract window"),
            ("OPEN", "Received revised scope"),
            ("ACKNOWLEDGED", "Review restarted"),
            ("RESOLVED", "Confirmed final scope"),
        ):
            self.assertTrue(review(self.db, self.finding, status, "demo-analyst", reason))
        self.assertEqual(self.db.execute(
            "SELECT status FROM finding_status WHERE finding_id=?", (self.finding,)
        ).fetchone()[0], "RESOLVED")
        history = self.db.execute("""
            SELECT old_status,new_status,actor,reason,occurred_at FROM review_event ORDER BY event_id
        """).fetchall()
        self.assertEqual([tuple(row[:2]) for row in history],
                         [("OPEN","ACKNOWLEDGED"), ("ACKNOWLEDGED","WAIVED"), ("WAIVED","OPEN"),
                          ("OPEN","ACKNOWLEDGED"), ("ACKNOWLEDGED","RESOLVED")])
        self.assertEqual([row[4] for row in history], sorted(row[4] for row in history))
        with self.assertRaisesRegex(sqlite3.IntegrityError, "append-only"):
            self.db.execute("DELETE FROM review_event")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
            self.db.execute("UPDATE finding SET record_id='replacement'")

    def test_invalid_transition_blank_reason_and_actor(self):
        for status, actor, reason in (
            ("WAIVED", "demo", "No approval"), ("ACKNOWLEDGED", "demo", " "),
            ("ACKNOWLEDGED", "", "First review"),
        ):
            with self.subTest(status=status, actor=actor), self.assertRaises(CareReconError):
                review(self.db, self.finding, status, actor, reason)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM review_event").fetchone()[0], 0)

    def test_repeat_identical_event_is_side_effect_free(self):
        self.assertTrue(review(self.db, self.finding, "ACKNOWLEDGED", "Demo O'Neil", "Same review"))
        self.assertFalse(review(self.db, self.finding, "ACKNOWLEDGED", "Demo O'Neil", "Same review"))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM review_event").fetchone()[0], 1)

    def test_quoted_unknown_finding_id_is_a_literal(self):
        with self.assertRaisesRegex(CareReconError, "Unknown finding"):
            review(self.db, "O'Neil", "ACKNOWLEDGED", "demo", "Check exact ID")

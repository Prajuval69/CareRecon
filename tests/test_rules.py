import json

from support import CareReconTest, ROOT
from carerecon.rules import reversal_matches
from carerecon.models import group, records
from carerecon.db import imports

GOLDEN = ROOT / "data/expected/seeded_scenarios.json"


def scenario_test(item):
    def test(self):
        run_id = self.run_pipeline()
        rows = self.db.execute("""
            SELECT f.*,i.source_sha256 FROM finding f JOIN ingest_source i USING(ingest_id)
            WHERE f.run_id=? AND f.rule_id=? AND f.record_id=? AND f.source_name=?
        """, (run_id, item["rule_id"], item["record_id"], item["source"])).fetchall()
        self.assertEqual(len(rows), 1, item["reason"])
        finding = rows[0]
        self.assertEqual(finding["rule_version"], 1)
        self.assertEqual(len(finding["source_sha256"]), 64)
        line = self.db.execute("""
            SELECT MIN(r.source_line_number) FROM finding_evidence JOIN raw_row r USING(raw_row_id)
            WHERE finding_id=?
        """, (finding["finding_id"],)).fetchone()[0]
        self.assertGreaterEqual(line, 2)
    return test


class RuleTests(CareReconTest):
    def test_matched_reversal_not_orphan(self):
        run_id = self.run_pipeline()
        self.assertIsNone(self.db.execute("""
            SELECT finding_id FROM finding WHERE rule_id='RX002' AND record_id='RX010'
        """).fetchone())
        source = imports(self.db, run_id)["pharmacy_claims"]
        rx = group(records(self.db, source), lambda row: row.key)
        self.assertTrue(reversal_matches(rx["RX010"][0], rx["RX002"]))

    def test_matched_reversal_has_no_days_or_negative_payment_finding(self):
        self.edit("pharmacy_claims", lambda rows: [*rows[:-1], dict(rows[-1], days_supply="0")])
        self.run_pipeline()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM finding WHERE record_id='RX010'").fetchone()[0], 0)
        row = self.db.execute("SELECT paid_cents FROM clean_rows WHERE business_key='RX010'").fetchone()
        self.assertEqual(row[0], -1400)

    def test_wrong_reversal_sign_amount_pharmacy_and_date(self):
        self.edit("pharmacy_claims", lambda rows: [
            *rows[:-1], dict(rows[-1], paid_cents="1400"),
            dict(rows[-1], rx_claim_id="RX011", paid_cents="-1401"),
            dict(rows[-1], rx_claim_id="RX012", pharmacy_id="PH004"),
            dict(rows[-1], rx_claim_id="RX013", fill_date="2026-05-14"),
        ])
        self.run_pipeline()
        findings = {row[0] for row in self.db.execute("SELECT record_id FROM finding WHERE rule_id='RX002'")}
        self.assertEqual(findings, {"RX004", "RX010", "RX011", "RX012", "RX013"})

    def test_negative_dispense_is_quarantined(self):
        self.edit("pharmacy_claims", lambda rows: [dict(rows[0], paid_cents="-123"), *rows[1:]])
        self.run_pipeline()
        self.assertEqual(self.db.execute("SELECT rule_id FROM finding WHERE record_id='RX001'").fetchone()[0], "CN001")

    def test_duplicate_valid_reversals_are_ambiguous(self):
        self.edit("pharmacy_claims", lambda rows: [*rows, dict(rows[-1], rx_claim_id="RX011")])
        self.run_pipeline()
        findings = {row[0] for row in self.db.execute("SELECT record_id FROM finding WHERE rule_id='RX002'")}
        self.assertEqual(findings, {"RX004", "RX010", "RX011"})

    def test_multiple_eligibility_intervals_and_inclusive_boundary(self):
        self.edit("member_eligibility", lambda rows: [*rows, dict(rows[-1], effective_date="2026-11-15",
                                                                end_date="2026-12-15")])
        self.run_pipeline()
        self.assertIsNone(self.db.execute("SELECT 1 FROM finding WHERE record_id='P008'").fetchone())


for scenario in json.loads(GOLDEN.read_text(encoding="utf-8"))["expected_findings"]:
    setattr(RuleTests, f"test_seeded_{scenario['rule_id']}", scenario_test(scenario))

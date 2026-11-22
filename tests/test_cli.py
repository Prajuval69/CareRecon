import json
import subprocess
import sys

from support import CareReconTest, ROOT
from carerecon.sql_report import sql_reports
from carerecon.verify import verify


class CliTests(CareReconTest):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "carerecon", *map(str, args)], cwd=ROOT, env=self.env(),
                              text=True, encoding="utf-8", capture_output=True, timeout=30)

    def test_demo_cli_end_to_end_and_reset(self):
        db = self.base / "demo.sqlite"
        out = self.base / "reports"
        args = ("demo", "--reset", "--db", db, "--output", out)
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS: 13/13 planted findings, RX010 clean", result.stdout)
        run_id = result.stdout.splitlines()[0].split("=")[1]
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        listing = self.cli("--db", db, "list-findings", "--run", run_id, "--status", "OPEN")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertEqual(len([json.loads(line) for line in listing.stdout.splitlines()]), 13)
        self.assertTrue((out / "summary.html").is_file())

    def test_help_invalid_usage_and_actionable_error(self):
        self.assertIn("compare-snapshot", self.cli("--help").stdout)
        self.assertEqual(self.cli("reconcile").returncode, 2)
        result = self.cli("validate", "--db", self.db_path, "--run", "unknown")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown run", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_reset_does_not_replace_non_demo_database(self):
        self.ingest()
        result = self.cli("demo", "--reset", "--db", self.db_path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("only demo runs", result.stderr)
        self.assertEqual(self.db.execute("SELECT batch_id FROM run").fetchone()[0], "test-2026")

    def test_golden_verifier_and_named_sql_queries(self):
        run_id = self.run_pipeline()
        report = dict(sql_reports(self.db, run_id))
        self.assertEqual(len(report), 10)
        self.assertEqual(report["Duplicated raw payer keys"], [{"payer_claim_id": "P003", "occurrences": 2}])
        rx = {row["reversal"]: row["status"] for row in report["Valid and orphan or incompatible pharmacy reversals"]}
        self.assertEqual(rx, {"RX004": "ORPHAN_OR_INCOMPATIBLE", "RX010": "MATCH"})
        self.assertIn("PASS: 13/13", verify(self.db, run_id, ROOT / "data/expected/seeded_scenarios.json"))

import csv
import hashlib
import json

from support import CareReconTest
from carerecon.reports import export, sheet_cell
from carerecon.review import review
from carerecon.util import CareReconError


class ReportingTests(CareReconTest):
    def test_reports_and_digests_are_deterministic(self):
        run_id = self.run_pipeline()
        directory = self.base / "reports"
        paths = export(self.db, run_id, directory)
        first = {path.name: path.read_bytes() for path in paths}
        self.assertEqual(len(paths), 10)
        self.assertEqual(first, {path.name: path.read_bytes() for path in export(self.db, run_id, directory)})
        artifacts = self.db.execute("SELECT artifact_path,artifact_sha256,bytes FROM export_artifact").fetchall()
        self.assertEqual(len(artifacts), 10)
        for path, sha256, length in artifacts:
            from pathlib import Path
            contents = first[Path(path).name]
            self.assertEqual((hashlib.sha256(contents).hexdigest(), len(contents)), (sha256, length))
        manifest = json.loads(first["run_manifest.json"])
        self.assertEqual((manifest["run_id"], manifest["schema_version"]), (run_id, 1))
        self.assertEqual(len(manifest["rule_manifest"]["rules"]), 13)

    def test_csv_formula_prefixes_escape_without_changing_signed_money(self):
        for value in ("=123", "+123", "-123", "@review", "   =123", "\tword", "\rword"):
            with self.subTest(value=value):
                self.assertEqual(sheet_cell(value), "'" + value)
        self.assertEqual(sheet_cell(-1400), -1400)
        run_id = self.run_pipeline()
        finding = self.db.execute("SELECT finding_id FROM finding WHERE rule_id='RC001'").fetchone()[0]
        review(self.db, finding, "ACKNOWLEDGED", "+reviewer", "=123")
        out = self.base / "reports"
        export(self.db, run_id, out)
        with (out / "findings.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        row = next(row for row in rows if row["rule_id"] == "RC001")
        self.assertEqual((row["reason"], row["actor"]), ("'=123", "'+reviewer"))
        self.assertEqual({item["source_name"] for item in json.loads(row["raw_locations"])},
                         {"payer_claims", "provider_remittances"})

    def test_html_escapes_user_content_and_keeps_review_visible(self):
        run_id = self.run_pipeline(batch="<batch>")
        finding = self.db.execute("SELECT finding_id FROM finding WHERE rule_id='SS001'").fetchone()[0]
        review(self.db, finding, "ACKNOWLEDGED", "örlí", "<b>review this</b>")
        out = self.base / "reports"
        export(self.db, run_id, out)
        html = (out / "summary.html").read_text(encoding="utf-8")
        self.assertIn("&lt;batch&gt;", html)
        self.assertIn("&lt;b&gt;review this&lt;/b&gt;", html)
        self.assertIn("örlí", html)
        self.assertNotIn("<b>review this</b>", html)
        self.assertIn("Synthetic examples only", html)

    def test_export_refuses_to_overwrite_control_input(self):
        run_id = self.run_pipeline()
        original = (self.current / "source_controls.csv").read_bytes()
        with self.assertRaisesRegex(CareReconError, "Unsafe report destination"):
            export(self.db, run_id, self.current)
        self.assertEqual((self.current / "source_controls.csv").read_bytes(), original)
        self.assertFalse((self.current / "findings.csv").exists())
        export(self.db, run_id, self.base / "reports")
        self.assertEqual(self.db.execute("SELECT status FROM run").fetchone()[0], "COMPLETE")

    def test_empty_exports_keep_headers(self):
        for name in self.settings.contracts["contracts"]:
            self.edit(name, lambda rows: [])
        self.edit("payer_claims_previous", lambda rows: [], previous=True)
        run_id = self.run_pipeline()
        out = self.base / "reports"
        export(self.db, run_id, out)
        self.assertIn("payer_claim_id,expected_cents", (out / "reconciliation.csv").read_text(encoding="utf-8-sig"))
        self.assertEqual(len((out / "findings.csv").read_text(encoding="utf-8-sig").splitlines()), 1)

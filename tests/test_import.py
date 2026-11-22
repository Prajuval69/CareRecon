import hashlib
import json
import sqlite3

from support import CareReconTest
from carerecon.util import CareReconError


class ImportTests(CareReconTest):
    def test_full_lineage_and_immutable_raw(self):
        run_id, created = self.ingest()
        self.assertTrue(created)
        row = self.db.execute("""
            SELECT s.*,i.contract_version,r.batch_id,r.config_sha256 FROM source_rows s
            JOIN ingest_source i USING(ingest_id) JOIN run r ON r.run_id=s.run_id
            WHERE s.source_name='payer_claims' AND s.business_key='P001'
        """).fetchone()
        self.assertEqual((row["run_id"], row["batch_id"], row["contract_version"]), (run_id, "test-2026", 1))
        expected_hash = hashlib.sha256((self.current / "payer_claims.csv").read_bytes()).hexdigest()
        self.assertEqual(row["source_sha256"], expected_hash)
        self.assertEqual(row["source_line_number"], 2)
        self.assertEqual(row["source_file"], "payer_claims.csv")
        self.assertEqual(json.loads(row["raw_json"])["columns"]["paid_cents"], "5750")
        self.assertEqual(row["paid_cents"], 5750)
        self.assertEqual(len(row["config_sha256"]), 64)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
            self.db.execute("UPDATE raw_row SET raw_text = ''")
        self.assertEqual(self.db.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_collect_bad_date_and_strict_atomic_rollback(self):
        self.edit("pharmacy_claims", lambda rows: [dict(rows[0], fill_date="2026-02-30"), *rows[1:]])
        with self.assertRaisesRegex(CareReconError, "pharmacy_claims.csv line 2"):
            self.ingest(strict=True)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM raw_row").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT outcome FROM run_event").fetchone()[0], "FAILED")
        run_id = self.run_pipeline()
        row = self.db.execute("SELECT * FROM quarantined_rows WHERE run_id=? AND business_key='RX001'",
                              (run_id,)).fetchone()
        self.assertIn("fill_date", row["issues_json"])
        self.assertIn("2026-02-30", row["raw_text"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM clean_rows WHERE business_key='RX001'").fetchone()[0], 0)
        finding = self.db.execute("SELECT rule_id FROM finding WHERE record_id='RX001'").fetchone()
        self.assertEqual(finding[0], "CN001")

    def test_missing_header_does_not_replace_committed_batch(self):
        prior, _ = self.ingest()
        path = self.current / "provider_remittances.csv"
        path.write_text("remit_id\nRM001\n", encoding="utf-8")
        with self.assertRaisesRegex(CareReconError, "missing required columns"):
            self.ingest()
        self.assertEqual(self.db.execute("SELECT run_id FROM run").fetchone()[0], prior)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM ingest_source").fetchone()[0], 7)

    def test_missing_source_from_empty_folder(self):
        empty = self.base / "empty"
        empty.mkdir()
        with self.assertRaisesRegex(CareReconError, "Missing required local source member_eligibility.csv"):
            self.ingest(directory=empty)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM run").fetchone()[0], 0)

    def test_malformed_utf8_fails_atomically(self):
        path = self.current / "pharmacy_directory.csv"
        path.write_bytes(path.read_bytes() + bytes([255]))
        with self.assertRaisesRegex(CareReconError, "malformed UTF-8"):
            self.ingest()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM ingest_source").fetchone()[0], 0)

    def test_empty_file_has_useful_header_error(self):
        (self.current / "member_eligibility.csv").write_bytes(b"")
        with self.assertRaisesRegex(CareReconError, "missing or invalid CSV header"):
            self.ingest()

    def test_header_only_batch_completes(self):
        for name in self.settings.contracts["contracts"]:
            self.edit(name, lambda rows: [])
        self.edit("payer_claims_previous", lambda rows: [], previous=True)
        run_id = self.run_pipeline()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM raw_row").fetchone()[0], 0)
        self.assertEqual(set(row[0] for row in self.db.execute("SELECT status FROM control_result")),
                         {"CONTROL_MISSING"})
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM reconciliation WHERE run_id=?",
                                         (run_id,)).fetchone()[0], 0)

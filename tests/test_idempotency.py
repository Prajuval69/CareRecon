from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from threading import Barrier

from support import CareReconTest
from carerecon.db import database
from carerecon.ingest import ingest
from carerecon.reports import export


class IdempotencyTests(CareReconTest):
    def counts(self):
        tables = ("run", "run_event", "run_stage", "ingest_source", "raw_row", "finding", "finding_evidence",
                  "reconciliation", "control_result", "snapshot_change", "export_artifact")
        return {table: self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}

    def test_workflow_retry_does_not_duplicate_rows_events_or_exports(self):
        run_id = self.run_pipeline()
        out = self.base / "reports"
        export(self.db, run_id, out)
        counts = self.counts()
        self.assertEqual(self.ingest(), (run_id, False))
        self.assertEqual(self.run_pipeline(), run_id)
        export(self.db, run_id, out)
        self.assertEqual(self.counts(), counts)

    def test_changed_source_creates_new_run_and_preserves_old(self):
        first, _ = self.ingest()
        self.edit("payer_claims", lambda rows: [dict(rows[0], paid_cents="5700"), *rows[1:]])
        second, created = self.ingest()
        self.assertTrue(created)
        self.assertNotEqual(first, second)
        rows = self.db.execute("""
            SELECT run_id,paid_cents,source_sha256 FROM source_rows
            WHERE source_name='payer_claims' AND business_key='P001'
        """).fetchall()
        self.assertEqual({row[0]: row[1] for row in rows}, {first: 5750, second: 5700})
        self.assertEqual(len({row[2] for row in rows}), 2)

    def test_changed_rule_manifest_versions_and_disabled_rules(self):
        first = self.run_pipeline()
        rules = deepcopy(self.settings.rules)
        for rule in rules["rules"]:
            if rule["rule_id"] == "DQ001":
                rule["version"] = 2
                rule["severity"] = "WARN"
            if rule["rule_id"] == "DQ006":
                rule["enabled"] = False
        second = self.run_pipeline(settings=replace(self.settings, rules=rules))
        self.assertNotEqual(first, second)
        results = self.db.execute("""
            SELECT run_id,rule_version,severity FROM finding WHERE rule_id='DQ001'
        """).fetchall()
        self.assertEqual({row[0]: tuple(row[1:]) for row in results}, {first: (1,"ERROR"), second: (2,"WARN")})
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM finding WHERE rule_id='DQ006' AND run_id=?", (second,),
        ).fetchone()[0], 0)
        self.assertEqual(self.db.execute(
            "SELECT status FROM reconciliation WHERE payer_claim_id='P003' AND run_id=?", (second,),
        ).fetchone()[0], "AMBIGUOUS")

    def test_concurrent_import_serializes_and_reuses_identity(self):
        start = Barrier(2)

        def worker():
            with database(self.db_path) as connection:
                start.wait(timeout=5)
                return ingest(connection, self.settings, self.current, "parallel", "2026-05-31", "2026-04-30")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(len({run_id for run_id, _ in results}), 1)
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(self.counts()["raw_row"], 65)

"""Per-test fixture directories and temporary evidence stores."""

import csv
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from carerecon.config import Settings
from carerecon.db import database
from carerecon.ingest import ingest
from carerecon.reconcile import reconcile
from carerecon.rules import validate
from carerecon.snapshots import compare


class CareReconTest(unittest.TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.current = self.base / "current"
        self.previous = self.base / "previous"
        shutil.copytree(ROOT / "data/raw/current", self.current)
        shutil.copytree(ROOT / "data/raw/previous", self.previous)
        self.db_path = self.base / "evidence.sqlite"
        self.db = self.enterContext(database(self.db_path))
        self.settings = Settings.load(ROOT / "config")

    def ingest(self, **options):
        params = dict(settings=self.settings, directory=self.current, batch="test-2026",
                      current_date="2026-05-31", previous_date="2026-04-30")
        return ingest(self.db, **(params | options))

    def run_pipeline(self, **options):
        run_id, _ = self.ingest(**options)
        validate(self.db, run_id)
        reconcile(self.db, run_id)
        compare(self.db, run_id, self.current, self.previous)
        return run_id

    def edit(self, source, transform, previous=False):
        path = (self.previous if previous else self.current) / f"{source}.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            headers, rows = reader.fieldnames, list(reader)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, headers, lineterminator="\n")
            writer.writeheader()
            writer.writerows(transform(rows))

    @staticmethod
    def env():
        return os.environ | {"PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"}

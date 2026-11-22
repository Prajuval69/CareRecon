"""Exercise the full pipeline on a reproducible, temporary synthetic batch."""

import argparse
import csv
from pathlib import Path
import shutil
import tempfile
from time import perf_counter

from carerecon.config import ROOT, Settings
from carerecon.db import database
from carerecon.ingest import ingest
from carerecon.reconcile import reconcile
from carerecon.reports import export
from carerecon.rules import validate
from carerecon.snapshots import compare
from carerecon.verify import verify


def append_rows(path, rows):
    with path.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)


def extend_batch(current, size):
    append_rows(current / "payer_claims.csv", (
        (f"LOAD-{n:06d}", "M001", "PR001", "2026-05-15", "PAID", 7000, 5000, 4321)
        for n in range(size)
    ))
    append_rows(current / "provider_remittances.csv", (
        (f"LOAD-REMIT-{n:06d}", f"LOAD-{n:06d}", "PR001", "2026-05-16", 4321, "POSTED")
        for n in range(size)
    ))
    controls = current / "source_controls.csv"
    with controls.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row["source_name"] in {"payer_claims", "provider_remittances"}:
            row["expected_rows"] = int(row["expected_rows"]) + size
            row["expected_paid_cents"] = int(row["expected_paid_cents"]) + size * 4321
    with controls.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=10_000, help="number of synthetic claim/remit pairs")
    args = parser.parse_args()
    if args.size < 1:
        parser.error("--size must be positive")
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        current, previous = base / "current", ROOT / "data/raw/previous"
        shutil.copytree(ROOT / "data/raw/current", current)
        extend_batch(current, args.size)
        settings = Settings.load(ROOT / "config")
        start = perf_counter()
        with database(base / "load.sqlite") as db:
            run_id, _ = ingest(db, settings, current, "synthetic-load", "2026-05-31", "2026-04-30")
            validate(db, run_id)
            reconcile(db, run_id)
            compare(db, run_id, current, previous)
            paths = export(db, run_id, base / "reports")
            result = verify(db, run_id)
            count = db.execute("SELECT COUNT(*) FROM raw_row").fetchone()[0]
            matches, delta = db.execute(
                """SELECT COUNT(*), SUM(difference_cents) FROM reconciliation
                   WHERE payer_claim_id LIKE 'LOAD-%' AND status='MATCH'"""
            ).fetchone()
            if (matches, delta) != (args.size, 0):
                raise RuntimeError(f"Expected {args.size} zero-delta load matches, got {matches} with delta {delta}")
        elapsed = perf_counter() - start
        print(f"Synthetic load: {args.size:,} added claim/remit pairs, {count:,} raw rows, "
              f"{matches:,} added matches, {len(paths)} exports.")
        print(result)
        print(f"Observed elapsed pipeline time: {elapsed:.3f} s")


if __name__ == "__main__":
    main()

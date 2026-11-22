"""Command-line entry points for the local CareRecon pipeline."""

import argparse
from contextlib import closing, contextmanager
import json
import logging
from pathlib import Path
import sqlite3
import tempfile

from .config import ROOT, Settings
from .db import APPLICATION_ID, database, get_run, imports
from .ingest import ingest
from .reconcile import reconcile
from .reports import REPORT_NAMES, export, listing
from .review import TRANSITIONS, review
from .rules import validate
from .snapshots import compare
from .sql_report import sql_reports
from .util import CareReconError
from .verify import verify

LOG = logging.getLogger("carerecon")
DEFAULT_DB = Path("output/generated/carerecon.sqlite")


def parser():
    cli = argparse.ArgumentParser(description="CareRecon · offline reconciliation of synthetic data")
    cli.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite evidence file")
    commands = cli.add_subparsers(dest="command", required=True)

    def add(name, help_text, *, run=False, config=False):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--db", type=Path, default=argparse.SUPPRESS, help="SQLite evidence file")
        if run:
            command.add_argument("--run", required=True, metavar="RUN_ID")
        if config:
            command.add_argument("--config", type=Path, default=ROOT / "config", help="configuration directory")
        return command

    add("init-db", "Create or check the evidence schema")
    load = add("ingest", "Import and fingerprint a current batch", config=True)
    load.add_argument("--batch", required=True)
    load.add_argument("--source-dir", required=True, type=Path)
    load.add_argument("--snapshot-date", help="current extract window as YYYY-MM-DD")
    load.add_argument("--previous-date", help="prior extract window as YYYY-MM-DD")
    mode = load.add_mutually_exclusive_group()
    mode.add_argument("--strict", action="store_true", help="roll back an import with malformed or ill-typed rows")
    mode.add_argument("--collect-errors", action="store_true", help="retain invalid rows in quarantine (default)")
    add("validate", "Evaluate current source contracts, rules and controls", run=True)
    add("reconcile", "Compare posted remittances and claim payments", run=True)
    snapshot = add("compare-snapshot", "Import and compare the prior payer snapshot", run=True)
    snapshot.add_argument("--current", type=Path, help="optionally verify against the current payer CSV")
    snapshot.add_argument("--previous", type=Path, default=ROOT / "data/raw/previous")
    findings = add("list-findings", "List findings as newline-delimited JSON", run=True)
    findings.add_argument("--status", choices=TRANSITIONS)
    decision = add("review", "Append a review status change")
    decision.add_argument("--finding", required=True)
    decision.add_argument("--status", required=True, choices=TRANSITIONS)
    decision.add_argument("--actor", required=True)
    decision.add_argument("--reason", required=True)
    reports = add("export", "Write Excel-compatible CSVs and offline HTML", run=True)
    reports.add_argument("--output", required=True, type=Path)
    audit = add("verify", "Check SQLite, SQL parity and seeded expectations", run=True)
    verification_mode = audit.add_mutually_exclusive_group()
    verification_mode.add_argument("--expected", type=Path, default=ROOT / "data/expected/seeded_scenarios.json")
    verification_mode.add_argument("--integrity-only", action="store_true", help="skip assertions specific to seed 2026")
    add("sql-report", "Execute the independent analyst SQL queries", run=True)
    demo = add("demo", "Run and verify the seeded workflow end to end", config=True)
    demo.add_argument("--reset", action="store_true", help="replace an existing demo-only database after success")
    demo.add_argument("--output", type=Path)
    return cli


@contextmanager
def demo_database(path, reset):
    if not reset:
        with database(path) as db:
            yield db
        return
    path = path.absolute()
    if path.is_symlink():
        raise CareReconError("Choose a regular database path for demo reset.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as reader:
            if (reader.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                    or reader.execute("SELECT 1 FROM run WHERE batch_id<>'demo-2026' LIMIT 1").fetchone()):
                raise CareReconError("Demo reset requires a CareRecon database containing only demo runs.")
    with tempfile.TemporaryDirectory(prefix=".carerecon-demo-", dir=path.parent) as temporary:
        replacement = Path(temporary) / path.name
        with database(replacement) as db:
            yield db
        replacement.replace(path)


def run_demo(args):
    settings = Settings.load(args.config)
    settings_demo = settings.demo
    current = ROOT / settings_demo["raw_current_dir"]
    previous = ROOT / settings_demo["raw_previous_dir"]
    output = args.output or Path(settings_demo["export_dir"])
    if args.db.resolve() in {output.resolve() / name for name in REPORT_NAMES}:
        raise CareReconError("Database path collides with a report destination.")
    with demo_database(args.db, args.reset) as db:
        run_id, _ = ingest(db, settings, current, "demo-2026",
                           settings_demo["current_snapshot_date"], settings_demo["previous_snapshot_date"],
                           settings_demo["reject_bad_rows"])
        validate(db, run_id)
        reconcile(db, run_id)
        compare(db, run_id, current, previous)
        result = verify(db, run_id, ROOT / "data/expected/seeded_scenarios.json")
        paths = export(db, run_id, output)
        raw = sum(source["source_row_count"] for source in imports(db, run_id).values())
        total = db.execute("SELECT COUNT(*) FROM finding WHERE run_id=?", (run_id,)).fetchone()[0]
    print(f"run_id={run_id}")
    print(f"Synthetic demo imported {raw} records across 8 sources and produced {total} findings.")
    print(result)
    for path in paths:
        print(path)


def dispatch(args, db):
    match args.command:
        case "init-db":
            print(f"Initialized {args.db.resolve()}")
        case "ingest":
            settings = Settings.load(args.config)
            run_id, created = ingest(
                db, settings, args.source_dir, args.batch,
                args.snapshot_date or settings.demo["current_snapshot_date"],
                args.previous_date or settings.demo["previous_snapshot_date"],
                args.strict or (settings.demo["reject_bad_rows"] and not args.collect_errors),
            )
            print(f"run_id={run_id}")
            print("Imported current sources." if created else "Reused identical current sources.")
        case "validate" | "reconcile":
            action = validate if args.command == "validate" else reconcile
            action(db, args.run)
            print(f"{args.command} complete for {args.run}")
        case "compare-snapshot":
            compare(db, args.run, args.current, args.previous)
            print(f"compare-snapshot complete for {args.run}")
        case "list-findings":
            get_run(db, args.run)
            for row in listing(db, args.run, args.status):
                print(json.dumps(row, sort_keys=True))
        case "review":
            added = review(db, args.finding, args.status, args.actor, args.reason)
            print("Review event recorded." if added else "Identical review event already recorded.")
        case "export":
            for path in export(db, args.run, args.output):
                print(path)
        case "sql-report":
            for title, rows in sql_reports(db, args.run):
                print(json.dumps({"report": title, "rows": rows}, sort_keys=True))
        case "verify":
            print(verify(db, args.run, None if args.integrity_only else args.expected))


def main(argv=None):
    args = parser().parse_args(argv)
    logging.basicConfig(format="CareRecon: %(message)s", level=logging.ERROR)
    try:
        if args.command == "demo":
            run_demo(args)
        else:
            if args.command not in {"ingest", "init-db"} and not args.db.is_file():
                raise CareReconError(f"Database {args.db} does not exist. Run ingest or init-db.")
            with database(args.db) as db:
                dispatch(args, db)
        return 0
    except (CareReconError, OSError, ValueError, KeyError, OverflowError, sqlite3.Error) as exc:
        message = str(exc)
        if isinstance(exc, sqlite3.OperationalError) and ("locked" in message or "busy" in message):
            message = "Database is busy. Close other writers and retry."
        elif isinstance(exc, OverflowError) or "integer overflow" in message:
            message = "An exact amount exceeds SQLite's signed 64-bit cents range."
        LOG.error("%s", message)
        return 1

"""SQLite lifecycle, transactions and persisted run metadata."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

from .util import CareReconError, utc_now

SCHEMA_VERSION = 1
APPLICATION_ID = 0x4352434E


@contextmanager
def database(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys = ON")
        initialize(db)
        yield db
    finally:
        db.close()


def initialize(db):
    with transaction(db):
        version = db.execute("PRAGMA user_version").fetchone()[0]
        app_id = db.execute("PRAGMA application_id").fetchone()[0]
        if version == SCHEMA_VERSION and app_id == APPLICATION_ID:
            return
        if version or app_id or db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone():
            raise CareReconError("Database is not a supported CareRecon schema. Choose a new database.")
        chunk = ""
        for line in Path(__file__).with_name("schema.sql").read_text(encoding="utf-8").splitlines():
            chunk += line + "\n"
            if sqlite3.complete_statement(chunk):
                db.execute(chunk)
                chunk = ""
        db.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


@contextmanager
def transaction(db, write=True):
    db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


def get_run(db, run_id):
    row = db.execute("SELECT * FROM run WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise CareReconError(f"Unknown run {run_id!r}. Ingest sources first.")
    return row


def imports(db, run_id):
    return {row["source_name"]: row for row in db.execute(
        "SELECT * FROM ingest_source WHERE run_id = ? ORDER BY source_name", (run_id,)
    )}


def event(db, run_id, batch, stage, outcome, detail):
    db.execute(
        "INSERT INTO run_event(run_id,batch_id,stage,outcome,detail,occurred_at) VALUES(?,?,?,?,?,?)",
        (run_id, batch, stage, outcome, detail, utc_now()),
    )


def stage_done(db, run_id, stage):
    return db.execute("SELECT 1 FROM run_stage WHERE run_id=? AND stage=?", (run_id, stage)).fetchone()


@contextmanager
def stage(db, run_id, name, repeat=False):
    run = get_run(db, run_id)
    try:
        with transaction(db):
            done = stage_done(db, run_id, name)
            if done and not repeat:
                yield False
                return
            yield not done
            now = utc_now()
            db.execute("INSERT OR IGNORE INTO run_stage VALUES(?,?,?)", (run_id, name, now))
            complete = all(stage_done(db, run_id, item) for item in (
                "validate", "reconcile", "compare-snapshot", "export"
            ))
            if not done or db.execute(
                "SELECT outcome FROM run_event WHERE run_id=? AND stage=? ORDER BY event_id DESC LIMIT 1",
                (run_id, name),
            ).fetchone()[0] == "FAILED":
                event(db, run_id, run["batch_id"], name, "OK", "")
            failed = db.execute(
                """SELECT 1 FROM run_event WHERE outcome='FAILED' AND event_id IN (
                       SELECT MAX(event_id) FROM run_event WHERE run_id=? GROUP BY stage
                   ) LIMIT 1""", (run_id,),
            ).fetchone()
            status = "FAILED" if failed else "COMPLETE" if complete else "INGESTED"
            if not done or run["status"] != status:
                db.execute("UPDATE run SET status=?, finished_at=? WHERE run_id=?", (
                    status, now if complete or failed else None, run_id,
                ))
    except Exception as exc:
        with transaction(db):
            db.execute("UPDATE run SET status='FAILED', finished_at=? WHERE run_id=?", (utc_now(), run_id))
            event(db, run_id, run["batch_id"], name, "FAILED", str(exc))
        raise

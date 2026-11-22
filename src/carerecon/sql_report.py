"""Execute the repository's named, read-only SQL analysis queries."""

import sqlite3

from .config import ROOT
from .db import get_run, transaction


def sql_reports(db, run_id):
    with transaction(db, write=False):
        get_run(db, run_id)
        title, statement = "", ""
        for line in (ROOT / "sql/04_analysis.sql").read_text(encoding="utf-8").splitlines():
            if line.startswith("-- Report: "):
                title = line.removeprefix("-- Report: ")
            statement += line + "\n"
            if sqlite3.complete_statement(statement):
                yield title, [dict(row) for row in db.execute(statement, {"run": run_id})]
                statement = ""

"""Fingerprint and stage an immutable copy of the imported CSV records."""

from contextlib import ExitStack, contextmanager
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile

from .config import PRIOR
from .contracts import business_key, parse_fields
from .db import event, get_run, imports, transaction
from .util import CareReconError, encode, identity, integer, iso_date, utc_now


@contextmanager
def open_source(directory, name):
    filename = f"{name}.csv"
    base = Path(directory).resolve()
    path = base / filename
    if path.resolve().parent != base or not path.is_file():
        raise CareReconError(f"Missing required local source {filename} in {base}")
    with path.open("rb") as source, tempfile.TemporaryFile(mode="w+b") as captured:
        sha256 = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            sha256.update(chunk)
            captured.write(chunk)
        captured.seek(0)
        with io.TextIOWrapper(captured, encoding="utf-8-sig", newline="") as stream:
            yield path, sha256.hexdigest(), stream


class PhysicalLines:
    """Track physical line spans consumed by the CSV parser."""

    def __init__(self, stream):
        self.stream = stream
        self.number = 0
        self.consumed = []

    def __iter__(self):
        return self

    def __next__(self):
        line = next(self.stream)
        self.number += 1
        self.consumed.append(line)
        return line


def load_source(db, run_id, name, source, manifest, strict):
    path, sha256, stream = source
    source_contract = "payer_claims" if name == PRIOR else name
    contract = manifest["contracts"][source_contract]
    lines = PhysicalLines(stream)
    reader = csv.reader(lines, strict=True)
    try:
        headers = next(reader)
    except (StopIteration, csv.Error) as exc:
        raise CareReconError(f"{path.name}: missing or invalid CSV header") from exc
    if len(headers) != len(set(headers)) or any(not header.strip() for header in headers):
        raise CareReconError(f"{path.name}: duplicate or empty CSV column names")
    missing = set(contract["required"]) - set(headers)
    if missing:
        raise CareReconError(f"{path.name}: missing required columns {', '.join(sorted(missing))}")
    extra = sorted(set(headers) - set(contract["required"]))
    run = get_run(db, run_id)
    snapshot = "previous" if name == PRIOR else "current"
    ingest_id = identity(run_id, name, sha256)
    db.execute(
        """INSERT INTO ingest_source
           (ingest_id,run_id,source_name,source_file,source_path,source_sha256,source_snapshot,
            snapshot_date,imported_at,contract_version,headers,unexpected_columns)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ingest_id, run_id, name, path.name, str(path), sha256, snapshot,
         run[f"{snapshot}_date"], utc_now(), manifest["schema_version"], encode(headers), encode(extra)),
    )
    count = malformed = 0
    while True:
        start = lines.number + 1
        lines.consumed.clear()
        csv_issues = []
        try:
            cells = next(reader)
            if len(cells) != len(headers):
                csv_issues.append(f"CSV width: expected {len(headers)} fields, got {len(cells)}")
        except StopIteration:
            break
        except csv.Error as exc:
            cells = []
            csv_issues.append(f"CSV parse: {exc}")
        count += 1
        malformed += bool(csv_issues)
        values = dict(zip(headers, cells))
        typed, issues = parse_fields(values, contract)
        issues = csv_issues + issues
        if issues and strict:
            raise CareReconError(f"{path.name} line {start}: {'; '.join(issues)}")
        paid = None
        if contract.get("money_col"):
            try:
                paid = integer((values.get(contract["money_col"]) or "").strip())
            except ValueError:
                pass
        raw_id = db.execute(
            """INSERT INTO raw_row(ingest_id,source_line_number,end_line_number,business_key,
                                   raw_json,raw_text,raw_paid_cents) VALUES(?,?,?,?,?,?,?)""",
            (ingest_id, start, lines.number, business_key(values, contract),
             encode({"columns": values, "extra_cells": cells[len(headers):]}),
             "".join(lines.consumed), paid),
        ).lastrowid
        db.execute(
            "INSERT INTO typed_row VALUES(?,?,?,?,?,?,?)",
            (raw_id, encode(typed), typed.get("payer_claim_id"), typed.get("paid_cents"),
             typed.get("remit_status") or typed.get("status") or typed.get("transaction_type"),
             not issues, encode(issues)),
        )
    db.execute(
        "UPDATE ingest_source SET source_row_count=?, malformed_count=? WHERE ingest_id=?",
        (count, malformed, ingest_id),
    )


def stage_source(db, run_id, name, source, manifest, strict):
    try:
        load_source(db, run_id, name, source, manifest, strict)
    except UnicodeDecodeError as exc:
        raise CareReconError(f"{source[0].name}: malformed UTF-8") from exc


def ingest(db, settings, directory, batch, current_date, previous_date, strict=False):
    batch = batch.strip()
    if not batch:
        raise CareReconError("Batch name cannot be blank.")
    try:
        current_date, previous_date = iso_date(current_date), iso_date(previous_date)
        if previous_date >= current_date:
            raise CareReconError("Previous snapshot date must precede the current snapshot date.")
        policy = "strict" if strict else "collect-errors"
        with ExitStack() as files:
            sources = {name: files.enter_context(open_source(directory, name))
                       for name in sorted(settings.contracts["contracts"])}
            checksums = {name: source[1] for name, source in sources.items()}
            run_id = identity(batch, current_date, previous_date, policy, settings.fingerprint, checksums)
            with transaction(db):
                existing = db.execute("SELECT 1 FROM run WHERE run_id=?", (run_id,)).fetchone()
                if existing:
                    return run_id, False
                db.execute(
                    """INSERT INTO run(run_id,batch_id,current_date,previous_date,started_at,status,
                                       policy,config_sha256,rule_manifest,contract_manifest)
                       VALUES(?,?,?,?,?,'INGESTED',?,?,?,?)""",
                    (run_id, batch, current_date, previous_date, utc_now(), policy, settings.fingerprint,
                     encode(settings.rules), encode(settings.contracts)),
                )
                for name, source in sources.items():
                    stage_source(db, run_id, name, source, settings.contracts, strict)
                event(db, run_id, batch, "ingest", "OK", f"{len(sources)} current sources")
                return run_id, True
    except Exception as exc:
        with transaction(db):
            event(db, None, batch, "ingest", "FAILED", str(exc))
        raise


def attach_previous(db, run, current, previous):
    """Called inside the snapshot stage transaction."""
    run_id = run["run_id"]
    sources = imports(db, run_id)
    if current is not None:
        with open_source(current, "payer_claims") as source:
            if source[1] != sources["payer_claims"]["source_sha256"]:
                raise CareReconError("Current payer file differs from this run. Ingest a new run.")
    with open_source(previous, PRIOR) as source:
        if PRIOR in sources:
            if source[1] != sources[PRIOR]["source_sha256"]:
                raise CareReconError("Prior payer file differs from this run. Use a new batch for this pair.")
            return
        manifest = json.loads(run["contract_manifest"])
        stage_source(db, run_id, PRIOR, source, manifest, run["policy"] == "strict")

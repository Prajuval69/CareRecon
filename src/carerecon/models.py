"""Typed staging access shared by the independent Python checks."""

from collections import defaultdict
from dataclasses import dataclass
import json


@dataclass(frozen=True)
class Record:
    raw_id: int
    line: int
    key: str | None
    values: dict
    valid: bool
    issues: tuple[str, ...]

    @property
    def label(self):
        return self.key or f"line:{self.line}"

    @property
    def malformed(self):
        return any(issue.startswith("CSV ") for issue in self.issues)

    def __getitem__(self, field):
        return self.values[field]


def records(db, source):
    for row in db.execute(
        """SELECT r.raw_row_id, r.source_line_number, r.business_key,
                  t.values_json, t.contract_valid, t.issues_json
           FROM raw_row r JOIN typed_row t USING(raw_row_id)
           WHERE r.ingest_id=? ORDER BY r.source_line_number""", (source["ingest_id"],)
    ):
        yield Record(row[0], row[1], row[2], json.loads(row[3]), bool(row[4]), tuple(json.loads(row[5])))


def group(records, key):
    grouped = defaultdict(list)
    for row in records:
        value = key(row)
        if value is not None:
            grouped[value].append(row)
    return grouped

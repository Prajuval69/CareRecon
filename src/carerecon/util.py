"""Shared exact value and serialization helpers."""

from datetime import UTC, date, datetime
import hashlib
import json
import re


class CareReconError(Exception):
    """An actionable pipeline or input error."""


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(value).hexdigest()


def identity(*values):
    return digest(encode(values).encode("utf-8"))


def utc_now():
    return datetime.now(UTC).isoformat(timespec="microseconds")


def iso_date(value):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("expected YYYY-MM-DD")
    return date.fromisoformat(value).isoformat()


def integer(value):
    if value is None or not re.fullmatch(r"[+-]?[0-9]{1,19}", value):
        raise ValueError("expected an integer")
    result = int(value)
    if not -(2**63) <= result < 2**63:
        raise ValueError("outside SQLite integer range")
    return result

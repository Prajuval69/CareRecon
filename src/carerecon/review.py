"""Append-only human review of rule findings."""

from .db import transaction
from .util import CareReconError, utc_now

TRANSITIONS = {
    "OPEN": {"ACKNOWLEDGED"},
    "ACKNOWLEDGED": {"RESOLVED", "WAIVED", "OPEN"},
    "RESOLVED": {"OPEN"},
    "WAIVED": {"OPEN"},
}


def review(db, finding_id, status, actor, reason):
    actor, reason = actor.strip(), reason.strip()
    if not actor or not reason:
        raise CareReconError("Review requires a nonblank actor and reason.")
    with transaction(db):
        finding = db.execute(
            "SELECT status,actor,reason FROM finding_status WHERE finding_id=?", (finding_id,),
        ).fetchone()
        if finding is None:
            raise CareReconError(f"Unknown finding {finding_id!r}.")
        current = finding["status"]
        if (current, finding["actor"], finding["reason"]) == (status, actor, reason):
            return False
        if status not in TRANSITIONS[current]:
            raise CareReconError(f"Invalid review transition {current} to {status}.")
        db.execute(
            """INSERT INTO review_event(finding_id,actor,old_status,new_status,reason,occurred_at)
               VALUES(?,?,?,?,?,?)""",
            (finding_id, actor, current, status, reason, utc_now()),
        )
        return True

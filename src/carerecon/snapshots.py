"""Compare immutable payer files by raw key and typed attributes."""

from .config import PRIOR
from .db import get_run, stage
from .findings import Findings, contract_findings
from .ingest import attach_previous
from .models import group, records
from .util import encode


def compare(db, run_id, current, previous):
    with stage(db, run_id, "compare-snapshot", repeat=True) as pending:
        run = get_run(db, run_id)
        attach_previous(db, run, current, previous)
        if not pending:
            return
        findings = Findings(db, run)
        now = list(records(db, findings.sources["payer_claims"]))
        before = list(records(db, findings.sources[PRIOR]))
        contract_findings(findings, PRIOR, before)
        current_keys = group(now, lambda row: row.key)
        previous_keys = group(before, lambda row: row.key)
        current_unknown = any(row.key is None for row in now)
        previous_unknown = any(row.key is None for row in before)

        for key in sorted(current_keys.keys() | previous_keys.keys()):
            old, new = previous_keys.get(key, ()), current_keys.get(key, ())
            delta = None
            if len(old) > 1 or len(new) > 1:
                kind = "AMBIGUOUS"
            elif not new and not current_unknown:
                kind = "DISAPPEARED"
                findings.add("SS001", PRIOR, key, "absent from current extract", "review expected extract scope", old)
            elif not old and not previous_unknown:
                kind = "ADDED"
            elif not old or not new or not old[0].valid or not new[0].valid:
                kind = "INCOMPLETE"
            else:
                kind = "UNCHANGED" if old[0].values == new[0].values else "CHANGED"
                delta = new[0]["paid_cents"] - old[0]["paid_cents"]
            db.execute(
                "INSERT INTO snapshot_change VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, key, kind, run["current_date"], run["previous_date"], len(old), len(new),
                 encode([row.values for row in old]), encode([row.values for row in new]), delta,
                 encode([row.raw_id for row in (*old, *new)])),
            )

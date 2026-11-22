# Failure modes and resilience

Missing source file: explain required filename and exit safely. Wrong column headers: provide missing-column list; preserve previous committed runs. Malformed CSV or date: row-level reject/evidence without crashing entire workflow when policy allows. Duplicate business key: preserve both raw rows, flag ambiguity. Missing external control: a distinguishable `control missing` state, not a fabricated match. Unparsable amount: cannot compute exact control; mark incomplete rather than zero.

Report exports should write temp file then atomically replace destination. SQLite concurrency should handle database busy with a bounded retry or actionable message. Unexpected exceptions must set a failed run status. No silent swallowing of discrepancies.

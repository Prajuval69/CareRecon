# Previous/current snapshot comparison

Compare `data/raw/previous/payer_claims_previous.csv` to current `payer_claims.csv` by stable payer claim ID and explicitly declared snapshot windows. Find disappeared P099; classify as REVIEW, not definitive deletion or fraud. Also report newly added IDs, changed attributes and duplicates/ambiguous keys. For changed amounts calculate delta in cents.

Do not use row order for matching. If duplicate keys exist in either snapshot, emit a non-silent ambiguity status and do not choose a random row. Keep snapshots immutable and report counts both including and excluding ambiguous keys.

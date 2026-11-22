-- Reference queries after implementation of the normalized audit schema.
SELECT rule_id, severity, status, COUNT(*) AS findings
FROM finding GROUP BY rule_id, severity, status ORDER BY findings DESC, rule_id;

-- Count actual imported records, not the number of ingest events.
SELECT i.source_name, COUNT(r.raw_row_id) AS raw_records
FROM ingest_source i LEFT JOIN raw_row r ON i.ingest_id=r.ingest_id
GROUP BY i.source_name ORDER BY i.source_name;

SELECT event_id, finding_id, actor, old_status, new_status, reason, occurred_at
FROM review_event ORDER BY occurred_at, event_id;

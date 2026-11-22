-- Independent claim-grain reconciliation using staged types and raw key counts.
WITH claim_rows AS (
    SELECT business_key, contract_valid, paid_cents FROM source_rows
    WHERE run_id = :run AND source_name = 'payer_claims'
),
claim_keys AS (
    SELECT business_key AS claim_id, COUNT(*) AS claim_count,
           CASE WHEN COUNT(*) = 1 AND MIN(contract_valid) = 1 THEN MAX(paid_cents) END AS expected
    FROM claim_rows WHERE business_key IS NOT NULL GROUP BY business_key
),
events AS (
    SELECT payer_claim_id, paid_cents, transaction_status,
           contract_valid = 1 AND key_count = 1 AS usable
    FROM keyed_rows WHERE run_id = :run AND source_name = 'provider_remittances'
),
event_totals AS (
    SELECT payer_claim_id AS claim_id, COUNT(*) AS event_count, SUM(usable) AS usable_count,
           COUNT(CASE WHEN usable AND transaction_status = 'POSTED' THEN 1 END) AS posted_count,
           SUM(CASE WHEN usable AND transaction_status = 'POSTED' THEN paid_cents END) AS remitted
    FROM events WHERE payer_claim_id IS NOT NULL GROUP BY payer_claim_id
),
keys AS (
    SELECT claim_id FROM claim_keys UNION SELECT claim_id FROM event_totals
),
comparison AS (
    SELECT keys.claim_id, c.expected, COALESCE(c.claim_count, 0) AS claims,
           COALESCE(e.event_count, 0) AS events, COALESCE(e.posted_count, 0) AS posted,
           COALESCE(e.event_count <> e.usable_count, 0)
               OR EXISTS (SELECT 1 FROM events WHERE payer_claim_id IS NULL) AS incomplete_remits,
           EXISTS (SELECT 1 FROM claim_rows WHERE business_key IS NULL) AS unknown_claim,
           COALESCE(e.event_count = e.usable_count, 1) AS all_events_usable, e.remitted AS total
    FROM keys LEFT JOIN claim_keys c USING(claim_id) LEFT JOIN event_totals e USING(claim_id)
)
SELECT claim_id, expected, CASE WHEN NOT incomplete_remits THEN total END AS remitted,
       CASE WHEN expected IS NOT NULL AND NOT incomplete_remits THEN total - expected END AS difference,
       CASE
           WHEN claims > 1 THEN 'AMBIGUOUS'
           WHEN claims = 0 AND NOT unknown_claim AND all_events_usable THEN 'ORPHAN'
           WHEN expected IS NULL OR incomplete_remits THEN 'INCOMPLETE'
           WHEN total IS NULL THEN 'NOT_AVAILABLE'
           WHEN total = expected THEN 'MATCH'
           ELSE 'MISMATCH'
       END AS status,
       events, posted
FROM comparison
ORDER BY claim_id;

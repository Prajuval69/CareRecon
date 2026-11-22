-- Run with :run set to a CareRecon run ID. The CLI sql-report command binds it.
-- Report: Source row counts and independent raw amounts
SELECT i.source_name, i.source_snapshot, COUNT(r.raw_row_id) AS raw_records,
       CASE WHEN i.malformed_count = 0
                 AND i.source_name IN ('payer_claims','provider_remittances','pharmacy_claims','payer_claims_previous')
                 AND COUNT(r.raw_row_id) = COUNT(r.raw_paid_cents)
            THEN COALESCE(SUM(r.raw_paid_cents), 0) END AS raw_paid_cents
FROM ingest_source i LEFT JOIN raw_row r USING (ingest_id)
WHERE i.run_id = :run GROUP BY i.ingest_id ORDER BY i.source_name;

-- Report: Duplicated raw payer keys
SELECT business_key AS payer_claim_id, COUNT(*) AS occurrences
FROM source_rows
WHERE run_id = :run AND source_name = 'payer_claims' AND business_key IS NOT NULL
GROUP BY business_key HAVING COUNT(*) > 1 ORDER BY business_key;

-- Report: Missing member or provider references
-- EXISTS keeps multiple member coverage intervals from multiplying claims.
SELECT c.business_key AS payer_claim_id, json_extract(c.values_json,'$.member_id') AS member_id,
       json_extract(c.values_json,'$.provider_id') AS provider_id,
       NOT EXISTS (
           SELECT 1 FROM source_rows m
           WHERE m.run_id = c.run_id AND m.source_name = 'member_eligibility'
                 AND m.business_key = json_extract(c.values_json,'$.member_id')
       ) AS missing_member_reference,
       NOT EXISTS (
           SELECT 1 FROM source_rows p
           WHERE p.run_id = c.run_id AND p.source_name = 'provider_directory'
                 AND p.business_key = json_extract(c.values_json,'$.provider_id')
       ) AS missing_provider_reference
FROM source_rows c
WHERE c.run_id = :run AND c.source_name = 'payer_claims'
      AND (missing_member_reference OR missing_provider_reference)
ORDER BY c.business_key, c.source_line_number;

-- Report: Paid exceeds allowed or denial has payment
SELECT business_key AS payer_claim_id, transaction_status, paid_cents,
       json_extract(values_json,'$.allowed_cents') AS allowed_cents
FROM source_rows
WHERE run_id = :run AND source_name = 'payer_claims'
      AND ((transaction_status = 'PAID' AND paid_cents > json_extract(values_json,'$.allowed_cents'))
           OR (transaction_status = 'DENIED' AND paid_cents <> 0))
ORDER BY business_key, source_line_number;

-- Report: Valid and orphan or incompatible pharmacy reversals
WITH rx AS (
    SELECT business_key, paid_cents, transaction_status, contract_valid, key_count,
           json_extract(values_json,'$.pharmacy_id') AS pharmacy,
           json_extract(values_json,'$.fill_date') AS fill_date,
           json_extract(values_json,'$.days_supply') AS days_supply,
           json_extract(values_json,'$.original_rx_claim_id') AS original
    FROM keyed_rows WHERE run_id = :run AND source_name = 'pharmacy_claims'
),
matching AS (
    SELECT r.business_key AS reversal, o.business_key AS original
    FROM rx r JOIN rx o ON o.business_key = r.original
    WHERE r.transaction_status = 'REVERSAL' AND o.transaction_status = 'DISPENSE'
          AND r.contract_valid AND o.contract_valid AND o.key_count = 1
          AND r.pharmacy = o.pharmacy AND o.fill_date <= r.fill_date
          AND o.days_supply > 0 AND o.paid_cents > 0 AND r.paid_cents = -o.paid_cents
),
matching_counts AS (
    SELECT original, COUNT(*) AS reversals FROM matching GROUP BY original
)
SELECT rx.business_key AS reversal, rx.original,
       CASE WHEN NOT rx.contract_valid THEN 'INCOMPLETE'
            WHEN EXISTS (
                SELECT 1 FROM matching m JOIN matching_counts c USING(original)
                WHERE m.reversal = rx.business_key AND m.original = rx.original AND c.reversals = 1
            ) THEN 'MATCH' ELSE 'ORPHAN_OR_INCOMPATIBLE' END AS status
FROM rx WHERE transaction_status = 'REVERSAL' ORDER BY reversal;

-- Report: Reconciliation outcomes and posted-only totals
-- The independent aggregation is in src/carerecon/reconciliation.sql.
SELECT payer_claim_id, expected_cents, remitted_cents, difference_cents, status
FROM reconciliation WHERE run_id = :run
ORDER BY payer_claim_id;

-- Report: Remittances referencing absent claims
SELECT r.business_key AS remit_id, r.payer_claim_id, r.paid_cents
FROM source_rows r JOIN reconciliation c
ON r.run_id = c.run_id AND r.payer_claim_id = c.payer_claim_id
WHERE r.run_id = :run AND r.source_name = 'provider_remittances' AND c.status = 'ORPHAN'
ORDER BY remit_id;

-- Report: Prior and current payer key differences
WITH previous AS (
    SELECT business_key FROM source_rows
    WHERE run_id = :run AND source_name = 'payer_claims_previous' AND business_key IS NOT NULL
),
current AS (
    SELECT business_key FROM source_rows
    WHERE run_id = :run AND source_name = 'payer_claims' AND business_key IS NOT NULL
),
prior_only AS (SELECT business_key FROM previous EXCEPT SELECT business_key FROM current),
current_only AS (SELECT business_key FROM current EXCEPT SELECT business_key FROM previous)
SELECT business_key, 'PRIOR_ONLY' AS side FROM prior_only
UNION ALL SELECT business_key, 'CURRENT_ONLY' FROM current_only
ORDER BY side, business_key;

-- Report: Findings by severity and review status
SELECT severity, status, COUNT(*) AS findings
FROM finding_status WHERE run_id = :run GROUP BY severity, status ORDER BY severity, status;

-- Report: Append-only review history
SELECT e.event_id, e.finding_id, e.actor, e.old_status, e.new_status, e.reason, e.occurred_at
FROM review_event e JOIN finding f USING(finding_id)
WHERE f.run_id = :run ORDER BY e.event_id;

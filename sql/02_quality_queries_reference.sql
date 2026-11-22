-- Conceptual SQL checks. Adapt to curated/typed tables defined by Codex.
-- Duplicate payer claim IDs at raw grain
SELECT payer_claim_id, COUNT(*) AS row_count
FROM payer_claims_typed
GROUP BY payer_claim_id HAVING COUNT(*) > 1;

-- Missing provider references
SELECT c.payer_claim_id, c.provider_id
FROM payer_claims_typed AS c
LEFT JOIN provider_directory_typed AS p ON c.provider_id = p.provider_id
WHERE p.provider_id IS NULL;

-- Claim vs remit: aggregate POSTED remittance per claim to avoid row multiplication.
WITH remit_sum AS (
  SELECT payer_claim_id, SUM(paid_cents) AS remitted_cents
  FROM provider_remittances_typed
  WHERE remit_status='POSTED'
  GROUP BY payer_claim_id
)
SELECT c.payer_claim_id, c.paid_cents, r.remitted_cents,
       r.remitted_cents - c.paid_cents AS variance_cents
FROM payer_claims_typed c
JOIN remit_sum r ON r.payer_claim_id=c.payer_claim_id
WHERE r.remitted_cents <> c.paid_cents;

-- Important: duplicate payer claims like P003 must be quarantined or aggregated
-- according to a documented policy BEFORE reconciling against remits.

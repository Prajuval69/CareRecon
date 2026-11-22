# Payer vs provider remittance reconciliation

Provider remittance `remit_id` is event grain; `payer_claim_id` is claim grain. Resolve posted-versus-void events, aggregate posting amounts per payer claim, and compare to a unique usable payer claim. P012 must yield RC001 with delta +275 cents. RM_ORPHAN must yield RC002. Matching P001, P002, P004 and P005 are expected to match. P003 is duplicated in payer raw file: mark as ambiguous or quarantine before comparison; never double-count claim paid amount.

Don't flag every payer claim without a remittance as incorrect: a claim may be pending/out of extraction scope. Report matched, mismatched, orphaned, ambiguous and not-available statuses with documented interpretation. Show reconciliation amounts in integer cents and display formatted currency only for human-facing outputs. Include independent SQL and Python consistency checks.

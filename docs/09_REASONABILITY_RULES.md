# Reasonability checks

Implement duplicates on raw payer claim business keys before any de-duplication; missing member IDs; provider foreign keys; service date within member eligibility (as defined here); claim payment compared to allowed amount for standard paid claims; denied claim with nonzero payment warning. Pharmacies need days-supply checks for DISPENSE, and a reversal referencing a valid dispense with compatible amount/identity.

Document rule exceptions and assumptions. For actual health insurance datasets, dates, reversals, denials, adjustments, and allowed/paid relationships can be more nuanced. Do NOT equate an outlier or exception with confirmed fraudulent activity, clinical error or recoverable payment. Return review-ready findings, not automated medical or payment decisions.

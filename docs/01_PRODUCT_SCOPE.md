# Product scope and differentiation

CareRecon is a **source-to-source healthcare data quality and reconciliation engine**, not a second claims BI dashboard. Simulate periodic receipt of synthetic payer claims, provider remittances, pharmacy transactions, eligibility/directory references and source control totals. Validate basic data contracts, reconcile at correct grain, compare current and prior snapshots, preserve audit evidence, and output practical reports for an analyst to review.

In scope: deterministic ingest, schema validation, row-level provenance, reasonability rules, rule versioning, payer/remit comparison, control checks, pharmacy reversal references, snapshot changes, review workflow, SQL reports, CLI and tests. Out of scope: real patient data, production HIPAA systems, claim adjudication, actuarial pricing, fraud accusation, treatment decisions, cloud infrastructure, external APIs and paid software. All domain rules are illustrative and must be labeled as such.

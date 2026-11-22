# Data dictionary

`payer_claims`: payer_claim_id TEXT, member_id TEXT, provider_id TEXT, service_date ISO date, status PAID/DENIED, billed_cents INT, allowed_cents INT, paid_cents INT. `provider_remittances`: remit_id TEXT, payer_claim_id TEXT, provider_id TEXT, remit_date ISO date, paid_cents INT, remit_status POSTED/VOID. `pharmacy_claims`: rx_claim_id TEXT, member_id TEXT, pharmacy_id TEXT, ndc TEXT, fill_date ISO date, days_supply INT, quantity INT, paid_cents INT, transaction_type DISPENSE/REVERSAL, original_rx_claim_id optional.

`member_eligibility`: member_id TEXT, effective_date ISO date, end_date ISO date, plan_id TEXT. `provider_directory`: provider_id TEXT, specialty TEXT, active_from, active_to. `pharmacy_directory`: pharmacy_id, name, active_from, active_to. `source_controls`: source_name, expected_rows INT, expected_paid_cents INT, snapshot_date ISO date. The `ndc` values here are fabricated identifiers; do not present as real valid NDC codes. The examples are synthetic and not medical advice.

## Keys and versioned contracts

| Feed | Expected grain | Business key |
| --- | --- | --- |
| Payer claims and prior payer claims | One logical claim per snapshot | `payer_claim_id` |
| Provider remittances | One posting or void event | `remit_id` |
| Pharmacy claims | One dispense or reversal | `rx_claim_id` |
| Member eligibility | One coverage interval for a member and plan | Lookup uses `member_id` and all available intervals |
| Provider and pharmacy directories | One row per reference entity | `provider_id` or `pharmacy_id` |
| Source controls | One declaration per feed and snapshot date | `source_name`, qualified by `snapshot_date` |

The [source contract manifest](../config/source_contracts.json) lists required headers and field types. A column may be required even when its value is allowed to be blank. Blank payer member IDs are checked by DQ002. Dates use YYYY-MM-DD, evidence timestamps use UTC, and amounts use signed integer cents. Synthetic provider and drug identifiers are text, including any leading zeroes.

## SQLite evidence schema

| Relation | Grain and useful fields |
| --- | --- |
| `run`, `run_stage`, `run_event` | Batch and run ID, pinning of both manifests, snapshot dates, import policy, and stage outcomes |
| `ingest_source` | Run and source, filename and resolved path, SHA-256, snapshot, header list, unexpected columns, record count, contract version, and import time |
| `raw_row` | One parsed record or malformed span, immutable raw text, column tokens, business key, 1-based physical start/end lines, and independently parsed raw paid cents |
| `typed_row` | One row per raw record, typed values, indexed claim key and status columns when applicable, contract validity, and issue text |
| `source_rows`, `clean_rows`, `quarantined_rows` | Evidence, usable analytic rows, and rows excluded by contract, duplicate keys, or hard claim/pharmacy rules |
| `finding`, `finding_evidence` | Immutable finding details and the supporting raw record IDs. RC001 links the payer row and all contributing posted remittances. |
| `finding_status`, `review_event` | Current review status and an append-only event stream with previous status, new status, actor, rationale, and UTC time |
| `reconciliation` | One row per claim key. Expected cents come from the unique usable payer row, and remitted cents are the signed sum of posted events. Difference is remitted minus expected. |
| `control_result` | One row per controlled source for the current extract window. Deltas are declared minus observed. NULL means unavailable. |
| `snapshot_change` | One row per payer key in either snapshot, with status, period dates, typed attributes, multiplicity, and current-minus-prior amount when comparable |
| `export_artifact` | Run, absolute output path, SHA-256, byte length, and export time for each distinct exported version |

The primary evidence keys in `finding_evidence` and the JSON record references in reconciliation, control, and snapshot results refer to `raw_row.raw_row_id`. Batch and run lineage are recovered through `ingest_source`. The schema version is stored as SQLite `PRAGMA user_version` and exported with the run manifest.

# SQL validation notes

Run the seeded pipeline first. With `PYTHONPATH=src`, run `python -m carerecon sql-report --db PATH --run RUN_ID`. The command executes the ten labeled queries in [`sql/04_analysis.sql`](../sql/04_analysis.sql) using the run ID as a bound parameter. It emits one JSON object per query. To execute the SQL directly against the database, bind `:run` to the same run ID in your SQLite client.

## Independent checks

- [`src/carerecon/reconciliation.sql`](../src/carerecon/reconciliation.sql) independently groups raw payer business keys and unique typed remittance events. It computes all claim-grain statuses, signed posted totals, differences, and event counts. The CLI compares each SQL row with the persisted output from the Python reconciler.
- `verify` independently aggregates `raw_row` by source import and compares the row counts and exact raw amounts to the Python control results. NULL identifies an incomplete sum. For the six controlled sources, the seed has 19 payer rows and 146,350 raw payer cents, plus 10 pharmacy rows and 13,000 raw pharmacy cents.
- SQL paid amounts stay as integers. Claim expected amounts appear once for each unique usable payer key. Signed `POSTED` remittance events contribute to the sum. `VOID` rows contribute to source controls when present and are excluded from posted payments.
- The missing-reference query uses `EXISTS` to avoid multiplying claims when a member has several coverage intervals. The pharmacy example checks the original ID, compatible pharmacy and date, exact inverse payment, and uniqueness. The snapshot key query reports set differences as inputs to review. The application additionally classifies ambiguity and incomplete evidence.

## Expected demonstration rows

| Query | Observed result |
| --- | --- |
| Duplicate payer keys | P003 appears twice |
| Missing references | P006 has no member ID and P007 has unknown provider PR999 |
| Paid/allowed and denial | P009 exceeds allowed by 550 cents and P010 is denied with 300 cents paid |
| Reconciliation | P001, P002, P004, and P005 match. P012 is +275 cents. P003 is ambiguous. |
| Orphan remittances | RM_ORPHAN references P_NO_SUCH_CLAIM |
| Pharmacy reversals | RX004 has an absent original. RX010 matches RX002. |
| Snapshot key differences | P099 is prior-only. P013 through P018 are current-only. |
| Review history | One P099 acknowledgement and an acknowledgement plus waiver for P010 in the reviewed bundle |

The files named `*_reference.sql` preserve the starter examples. The live schema is defined in [`src/carerecon/schema.sql`](../src/carerecon/schema.sql).

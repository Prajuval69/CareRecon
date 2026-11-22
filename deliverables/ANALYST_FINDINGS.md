# CareRecon analyst findings

**Batch evidence-2026 · Synthetic extracts only**  
Current snapshot May 31, 2026 · Prior snapshot April 30, 2026

The run evaluated 78 raw records across eight source files and detected all 13 planted findings. The 19 reconciliation rows represent 18 current payer keys and one orphan key. Four payments matched, one differed, one payer key had duplicate source rows, and 12 current payer keys had no posted payment available for comparison.

| Evidence | Observed | Analyst action |
| --- | --- | --- |
| P012 remittance | 9,175 posted cents against 8,900 payer cents. Difference +275 cents. | Inspect the payer row and RM006 for timing or adjustment context. |
| P003 duplicate | Two raw rows share one claim ID. The posting is visible and the payer amount remains blank in reconciliation. | Ask the extract owner to clarify the duplicate before comparing amounts. |
| RM_ORPHAN | The remittance references P_NO_SUCH_CLAIM. | Confirm payer extract coverage for the referenced key. |
| Payer row count | 20 declared and 19 observed. | Check the raw extract against the source manifest. |
| Pharmacy paid total | 14,234 declared cents and 13,000 observed. | Confirm the original control calculation, including signed reversals. |
| RX010 | The same pharmacy posted a −1,400-cent reversal for RX002. | No exception under the synthetic full-reversal rule. |
| P099 prior-only key | The key appears in the prior extract and is absent from the current extract. | Confirm the extract window. The review remains acknowledged. |

The fictional analyst also acknowledged P010 and waived it as a review-workflow exercise. The original finding and both transitions remain in the evidence. The seeded scenarios exercise contract and reconciliation rules. They carry no conclusion about fraud, clinical validity, claim adjudication, or recoverable amounts.

[HTML summary](reports/summary.html) · [Finding evidence](reports/findings.csv) · [Review history](reports/review_history.csv)

# Independent source control totals

`source_controls.csv` declares expected raw row counts and expected paid cents per source. Compare controls against **raw** source rows, not curated/cleaned records, otherwise known errors may be masked. For payer_claims the declared count is one greater than actual; for pharmacy_claims the declared paid total is 1234 cents higher than actual. All other source controls are accurate.

Preserve independent totals with source name, file hash and snapshot date. If data type parsing fails in a paid column, report an incomplete-control status rather than silently treating the amount as zero. Avoid comparing controls across different snapshot periods. Include separate reports for raw controls and quality-adjusted totals.

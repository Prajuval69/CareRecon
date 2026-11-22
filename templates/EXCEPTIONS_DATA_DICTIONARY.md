# Report fields and meanings

`finding_id`: stable exception identifier; `run_id`: pipeline run; `rule_id`: check identifier; `rule_version`: version applied; `source_name`: inbound file origin; `source_sha256`: bytes fingerprint; `source_row`: original CSV row; `record_id`: business key; `severity`: ERROR/WARN/REVIEW; `observed_value`: value seen; `expected_value`: defined comparison; `message`: analyst explanation; `status`: OPEN/ACKNOWLEDGED/RESOLVED/WAIVED; `review_events`: human decision audit; `generated_at`: UTC reporting time.

Data synthetic and intentionally includes invalid examples. None of the findings establish fraud, treatment error or recoverable payment.

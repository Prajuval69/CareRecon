# Versioned source data contracts

Use `config/source_contracts.json` to define required headers, business keys and expected column types. A missing required header is a batch-level failure with useful error message and no partial import. Data type problems should produce row-level evidence; preserve raw text and source row. Reject CSV formula injection in exports by escaping cells beginning with =, +, -, or @ when source text is untrusted. Numeric negative cents must remain numeric to support valid reversals; escape only human-facing text outputs.

Detect unexpected columns without throwing away data. Record schema version with import. Validate filenames and base paths without path traversal, inspect duplicate headers and preserve non-ASCII text. Schema validation and business-rule evaluation are distinct stages. Include tests for malformed UTF-8, missing file, empty source, duplicate header and bad integer text.

# Privacy and security

All members, providers, pharmacies and claims are synthetic. Do not use PII/PHI, external health records, scraping, real provider identifiers or real pharmacy identifiers. Do not claim HIPAA compliance. Keep processing local and offline; refuse to connect to production systems. Treat file contents as untrusted input: validate CSV headers, file names, numeric types and dates; use parameterized SQL and escaped HTML; neutralize spreadsheet formula injection for text fields; avoid overwriting arbitrary filesystem paths.

Use no credentials, tokens, paid services or cloud resources. If an error is data-dependent, include safe sample record IDs and rule names, not private records. Every dataset and report should display a clear synthetic-data disclaimer.

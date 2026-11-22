# Deterministic versioned rule engine

Use `config/rules.json` as the authoritative manifest of 13 seeded rules. Each finding must include rule_id, rule_version, severity, dataset, record ID, source hash, original line number when possible, observed/expected values, description, run ID, timestamp, and review status. Deduplicate by stable finding identity. Implement active rule controls and version history; different rule version is a distinct evaluation.

Errors represent clear rule failures under documented synthetic contract. WARN/REVIEW means analytical investigation is necessary. Store all triggered findings even when other rules flag same record. A rule should not crash when one field fails parsing; instead produce a useful parse/contract failure and avoid a misleading downstream numerical comparison. Maintain repeatable sort order in outputs.

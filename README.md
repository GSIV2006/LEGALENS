# LEGALENS Rules/Data Bundle

## What is included
- `rules/legal_metrology_ruleset.json`: operative baseline of declaration checks.
- `rules/sources.json`: official government source documents, with the 2025 medical-device notice explicitly marked draft/non-operative.
- `rules/decision_statuses.json`: stable compliance-status vocabulary.
- `rules/legalens_rules.db`: standalone SQLite rules database.
- `rules/seed_rules.sql`: seed/migration starter.

## Integration
Keep your existing operational inspection/OCR database separate from the rules database.
Use `ruleset_version` on each inspection so a result remains reproducible when rules change.

## Important modeling rule
Do not treat OCR as proof of physical quantity. OCR checks the declared quantity; physical quantity requires measurement.

## Demo wording
"LEGALENS uses AI-powered OCR and semantic field verification to determine a package's compliance status against the configured Legal Metrology ruleset."

-- LEGALENS Legal Metrology rules seed
-- Baseline: PCR 2011 consolidated through 2023 amendments.
-- Draft 2025 medical-device amendment is recorded separately as non-operative source metadata.

PRAGMA foreign_keys = ON;

INSERT OR REPLACE INTO rule_sets
(code, version, jurisdiction, title, effective_from, status, source_url)
VALUES
('LM_PCR_2011_CONSOLIDATED_2023',
 '2023-consolidated',
 'India',
 'Legal Metrology (Packaged Commodities) Rules, 2011 — consolidated through 2023 amendments',
 '2024-01-01',
 'operative_baseline',
 'https://consumeraffairs.nic.in/sites/default/files/file-uploads/latestnews/LM_PCR_All_Amendements.pdf');

-- Apply the JSON in legal_metrology_ruleset.json to declaration_rules.
-- Apply sources.json to rule_sources.
-- Apply decision_statuses.json to decision_statuses.

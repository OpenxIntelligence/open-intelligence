-- G2 additive clinician-note provenance; no new patient, author or source master.
-- Apply after the published 001, 002 and 003 scripts in a controlled migration.
-- Preserve old rows as NULL/unknown, never fabricate facility or specialty.
BEGIN;
ALTER TABLE ehr.clinical_note_versions ADD COLUMN IF NOT EXISTS facility_id text;
ALTER TABLE ehr.clinical_note_versions ADD COLUMN IF NOT EXISTS department_id text;
ALTER TABLE ehr.clinical_note_versions ADD COLUMN IF NOT EXISTS note_kind text;
-- Existing source-note version immutability and patient-scope policies remain.
-- IDs supplied by the fictional test host are descriptors, NOT identity proof.
COMMIT;

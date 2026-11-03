-- B-01c additive EHR persistence port. Apply after 001 and 002, in an
-- independently controlled migration transaction, never from request handlers.
-- Same EHR tables, identity owner and append-only journal; no new patient master.
BEGIN;
ALTER TABLE ehr.clinical_encounter_commands ADD COLUMN IF NOT EXISTS operation text;
ALTER TABLE ehr.clinical_encounter_commands ADD COLUMN IF NOT EXISTS result_json text;
ALTER TABLE ehr.clinical_encounter_commands ADD COLUMN IF NOT EXISTS occurred_at timestamptz;
-- Historical B-01 reserve_command rows are intentionally not backfilled with
-- invented results. The EHR service will reject such an incomplete receipt.
-- Existing reject_command_mutation trigger still forbids changing a receipt.
COMMIT;

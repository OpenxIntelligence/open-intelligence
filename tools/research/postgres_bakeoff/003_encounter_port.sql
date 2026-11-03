-- B-01c: additive fields on the ORIGINAL B-01 EHR tables.
-- Research migration fixture only. It does NOT create another patient master,
-- note ledger or event stream. Patient/EHR source remains first party.
ALTER TABLE ehr.clinical_encounter_commands
    ADD COLUMN IF NOT EXISTS operation text;
ALTER TABLE ehr.clinical_encounter_commands
    ADD COLUMN IF NOT EXISTS result_json text;
ALTER TABLE ehr.clinical_encounter_commands
    ADD COLUMN IF NOT EXISTS occurred_at timestamptz;

-- B-01 experiment's reserve_command uses hash-only reservation rows. A real
-- clinical command must store all three fields or none; never accept a
-- partially filled receipt. Existing B-01 reservations remain distinguishable.
DO $constraint$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'oi_clinical_command_receipt_whole') THEN
        ALTER TABLE ehr.clinical_encounter_commands
            ADD CONSTRAINT oi_clinical_command_receipt_whole
            CHECK ((operation IS NULL AND result_json IS NULL AND occurred_at IS NULL)
               OR (operation IS NOT NULL AND result_json IS NOT NULL AND occurred_at IS NOT NULL));
    END IF;
END;
$constraint$;

CREATE INDEX IF NOT EXISTS oi_ehr_encounter_patient_key
    ON ehr.clinical_encounters(patient_id,external_key);

-- A historical note header's latest_version must never move backwards;
-- source versions themselves already have append-only protection in B-01.
CREATE OR REPLACE FUNCTION ehr.guard_latest_note_version()
RETURNS trigger LANGUAGE plpgsql AS $guard$
BEGIN
    IF NEW.encounter_id IS DISTINCT FROM OLD.encounter_id
       OR NEW.note_key IS DISTINCT FROM OLD.note_key
       OR NEW.latest_version <> OLD.latest_version + 1 THEN
        RAISE EXCEPTION 'OI-NOTE-HEADER: immutable identity and monotonic version';
    END IF;
    RETURN NEW;
END;
$guard$;
DROP TRIGGER IF EXISTS oi_note_header_version ON ehr.clinical_note_headers;
CREATE TRIGGER oi_note_header_version
    BEFORE UPDATE ON ehr.clinical_note_headers
    FOR EACH ROW EXECUTE FUNCTION ehr.guard_latest_note_version();
